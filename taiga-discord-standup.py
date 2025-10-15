import os
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io

# Configuration from environment variables
TAIGA_URL = os.environ.get('TAIGA_URL', 'https://api.taiga.io/api/v1')
TAIGA_USERNAME = os.environ['TAIGA_USERNAME']
TAIGA_PASSWORD = os.environ['TAIGA_PASSWORD']
PROJECT_SLUG = os.environ['PROJECT_SLUG']
DISCORD_WEBHOOK = os.environ['DISCORD_WEBHOOK']

# Sprint task status columns
SPRINT_COLUMNS = [
    ('Not Started', '⏸️'),
    ('In Progress', '🔄'),
    ('Done', '✅'),
]

def get_taiga_auth_token():
    """Authenticate with Taiga and get auth token"""
    response = requests.post(
        f'{TAIGA_URL}/auth',
        json={
            'type': 'normal',
            'username': TAIGA_USERNAME,
            'password': TAIGA_PASSWORD
        }
    )
    response.raise_for_status()
    return response.json()['auth_token']

def get_project_data(auth_token):
    """Get project details"""
    headers = {'Authorization': f'Bearer {auth_token}'}
    response = requests.get(
        f'{TAIGA_URL}/projects/by_slug?slug={PROJECT_SLUG}',
        headers=headers
    )
    response.raise_for_status()
    return response.json()

def get_sprints(auth_token, project_id):
    """Get all sprints (milestones) for the project"""
    headers = {'Authorization': f'Bearer {auth_token}'}
    response = requests.get(
        f'{TAIGA_URL}/milestones?project={project_id}',
        headers=headers
    )
    response.raise_for_status()
    return response.json()

def get_current_sprint(sprints):
    """Get the current active sprint based on date range"""
    now = datetime.now().date()
    for sprint in sprints:
        if sprint.get('estimated_start') and sprint.get('estimated_finish'):
            start = datetime.fromisoformat(sprint['estimated_start'].replace('Z', '+00:00')).date()
            end = datetime.fromisoformat(sprint['estimated_finish'].replace('Z', '+00:00')).date()
            if start <= now <= end:
                return sprint
    
    # If no active sprint, return the most recent one
    if sprints:
        sorted_sprints = sorted(sprints, key=lambda x: x.get('estimated_start', ''), reverse=True)
        return sorted_sprints[0] if sorted_sprints else None
    return None

def get_sprint_tasks(auth_token, project_id, milestone_id):
    """Get tasks for a specific sprint"""
    headers = {'Authorization': f'Bearer {auth_token}'}
    params = {'project': project_id, 'milestone': milestone_id}
    
    response = requests.get(
        f'{TAIGA_URL}/tasks',
        headers=headers,
        params=params
    )
    response.raise_for_status()
    return response.json()

def organize_tasks_by_status(tasks):
    """Organize tasks by their status"""
    tasks_by_status = {}
    
    for task in tasks:
        if task is None:
            continue
            
        status_info = task.get('status_extra_info')
        if status_info and isinstance(status_info, dict):
            status = status_info.get('name', 'Unknown')
        else:
            status = 'Unknown'
            
        if status not in tasks_by_status:
            tasks_by_status[status] = []
        tasks_by_status[status].append(task)
    
    return tasks_by_status

def create_sprint_standup_embed(project, sprint, sprint_tasks, sprint_tasks_by_status):
    """Create the daily standup embed with sprint tasks"""
    
    project_url = project.get('url', f"https://tree.taiga.io/project/{PROJECT_SLUG}")
    
    # Calculate sprint metrics
    sprint_total = len([t for t in sprint_tasks if t is not None])
    sprint_done = len(sprint_tasks_by_status.get('Done', []))
    sprint_name = sprint['name'] if sprint else 'No Active Sprint'
    
    # Build description (without @everyone - we'll send that separately)
    description = f"**{datetime.now().strftime('%A, %B %d, %Y')}** • [Open Project]({project_url})\n\n"
    description += (
        "Hey team, this is your daily reminder to head to the most recent "
        "[Sprints page](https://discord.com/channels/1401686577629106246/1407869050050314311) "
        "and check in with the team. Please comment on the sprint post what you will get done today, "
        "or if you are too busy, just let the team know you are not available today. Thank you!"
    )
    
    fields = []
    
    # Sprint board header
    if sprint and sprint_total > 0:
        sprint_completion = (sprint_done / sprint_total * 100) if sprint_total > 0 else 0
        
        fields.append({
            "name": f"🏃 {sprint_name} - {sprint_done}/{sprint_total} tasks complete ({sprint_completion:.0f}%)",
            "value": f"Active sprint with **{sprint_total}** tasks",
            "inline": False
        })
        
        # Create task columns
        for status_name, emoji in SPRINT_COLUMNS:
            tasks = sprint_tasks_by_status.get(status_name, [])
            count = len(tasks)
            
            column_lines = []
            
            # Show top 3 tasks per column
            for task in tasks[:3]:
                if task is None:
                    continue
                
                ref = task.get('ref', '')
                subject = task.get('subject', 'No title')[:25]
                
                # Get assignee
                assigned_info = task.get('assigned_to_extra_info')
                if assigned_info and isinstance(assigned_info, dict):
                    assigned = assigned_info.get('username', '?')
                else:
                    assigned = '?'
                
                # Get user story reference if available
                us_ref = ""
                if task.get('user_story_extra_info'):
                    us_ref = f" (US#{task['user_story_extra_info'].get('ref', '')})"
                
                column_lines.append(f"**#{ref}** @{assigned}{us_ref}\n{subject}...")
            
            if len(tasks) > 3:
                column_lines.append(f"\n*+{len(tasks) - 3} more*")
            
            if not column_lines:
                column_lines.append("*—*")
            
            column_value = "\n\n".join(column_lines)
            
            fields.append({
                "name": f"{emoji} {status_name} ({count})",
                "value": column_value,
                "inline": True
            })
    
    return {
        "title": f"🌅 Daily Standup • {project['name']}",
        "description": description,
        "color": 0x5865F2,
        "fields": fields,
        "thumbnail": {
            "url": "https://tree.taiga.io/images/logo-color.png"
        },
        "footer": {
            "text": "🏃 Sprint Tasks Board",
            "icon_url": "https://tree.taiga.io/images/logo-color.png"
        },
        "timestamp": datetime.now().isoformat()
    }

def create_sprint_board_image(sprint_name, sprint_tasks_by_status, sprint_done, sprint_total):
    """Create a beautiful visual sprint board image"""
    
    # Image dimensions
    width = 1200
    height = 800
    
    # Colors (modern, clean palette)
    bg_color = (30, 33, 36)  # Dark background
    card_bg = (47, 51, 56)   # Card background
    not_started_color = (114, 137, 218)  # Blue
    in_progress_color = (250, 166, 26)   # Orange
    done_color = (67, 181, 129)          # Green
    text_color = (255, 255, 255)         # White
    text_secondary = (185, 187, 190)     # Gray
    
    # Create image
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to use a nice font, fallback to default
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
        header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        task_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        task_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # Draw title
    title_text = f"🏃 {sprint_name}"
    draw.text((40, 40), title_text, fill=text_color, font=title_font)
    
    # Draw progress
    completion = (sprint_done / sprint_total * 100) if sprint_total > 0 else 0
    progress_text = f"{sprint_done}/{sprint_total} tasks complete ({completion:.0f}%)"
    draw.text((40, 95), progress_text, fill=text_secondary, font=small_font)
    
    # Progress bar
    bar_x = 40
    bar_y = 125
    bar_width = 1120
    bar_height = 20
    
    # Background bar
    draw.rounded_rectangle(
        [bar_x, bar_y, bar_x + bar_width, bar_y + bar_height],
        radius=10,
        fill=(60, 63, 68)
    )
    
    # Progress bar fill
    if sprint_total > 0:
        fill_width = int((sprint_done / sprint_total) * bar_width)
        if fill_width > 0:
            draw.rounded_rectangle(
                [bar_x, bar_y, bar_x + fill_width, bar_y + bar_height],
                radius=10,
                fill=done_color
            )
    
    # Column setup
    columns = [
        ('Not Started', '⏸️', not_started_color),
        ('In Progress', '🔄', in_progress_color),
        ('Done', '✅', done_color)
    ]
    
    column_width = 360
    column_spacing = 20
    start_y = 180
    
    # Draw columns
    for idx, (status_name, emoji, color) in enumerate(columns):
        x = 40 + (idx * (column_width + column_spacing))
        
        # Column header
        draw.rounded_rectangle(
            [x, start_y, x + column_width, start_y + 60],
            radius=12,
            fill=color
        )
        
        tasks = sprint_tasks_by_status.get(status_name, [])
        count = len(tasks)
        
        header_text = f"{emoji} {status_name}"
        draw.text((x + 20, start_y + 12), header_text, fill=(255, 255, 255), font=header_font)
        
        count_text = f"{count} tasks"
        draw.text((x + 20, start_y + 45), count_text, fill=(255, 255, 255), font=small_font)
        
        # Draw task cards
        card_y = start_y + 80
        for task_idx, task in enumerate(tasks[:5]):  # Max 5 tasks per column
            if task is None:
                continue
            
            # Task card background
            card_height = 90
            draw.rounded_rectangle(
                [x, card_y, x + column_width, card_y + card_height],
                radius=8,
                fill=card_bg
            )
            
            # Task reference
            ref = task.get('ref', '?')
            ref_text = f"#{ref}"
            draw.text((x + 15, card_y + 12), ref_text, fill=color, font=task_font)
            
            # Task title (truncated)
            subject = task.get('subject', 'No title')[:30]
            draw.text((x + 15, card_y + 38), subject, fill=text_color, font=small_font)
            
            # Assignee
            assigned_info = task.get('assigned_to_extra_info')
            if assigned_info and isinstance(assigned_info, dict):
                assigned = assigned_info.get('username', 'Unassigned')
            else:
                assigned = 'Unassigned'
            
            assignee_text = f"@{assigned}"
            draw.text((x + 15, card_y + 62), assignee_text, fill=text_secondary, font=small_font)
            
            card_y += card_height + 12
        
        # Show "X more" if needed
        if len(tasks) > 5:
            more_text = f"+{len(tasks) - 5} more tasks"
            draw.text((x + 15, card_y), more_text, fill=text_secondary, font=small_font)
    
    return img

def send_to_discord(embeds):
    """Send embeds to Discord via webhook with @everyone ping"""
    response = requests.post(
        DISCORD_WEBHOOK,
        json={
            'content': '@everyone',  # This goes outside the embed and will ping
            'embeds': embeds
        }
    )
    response.raise_for_status()

def main():
    try:
        print("🔐 Authenticating with Taiga...")
        auth_token = get_taiga_auth_token()
        
        print("📊 Fetching project data...")
        project = get_project_data(auth_token)
        
        print("🏃 Fetching sprints...")
        sprints = get_sprints(auth_token, project['id'])
        current_sprint = get_current_sprint(sprints)
        
        if not current_sprint:
            print("⚠️ No active sprint found!")
            return
        
        print(f"📋 Current sprint: {current_sprint['name']}")
        
        print("📋 Fetching sprint tasks...")
        sprint_tasks = get_sprint_tasks(auth_token, project['id'], current_sprint['id'])
        
        print("🎨 Building standup embed...")
        sprint_tasks_by_status = organize_tasks_by_status(sprint_tasks)
        
        sprint_done = len(sprint_tasks_by_status.get('Done', []))
        sprint_total = len([t for t in sprint_tasks if t is not None])
        
        sprint_embed = create_sprint_standup_embed(
            project,
            current_sprint,
            sprint_tasks,
            sprint_tasks_by_status
        )
        
        print("📨 Sending to Discord...")
        send_to_discord_with_image(
            [sprint_embed],
            current_sprint['name'],
            sprint_tasks_by_status,
            sprint_done,
            sprint_total
        )
        
        print("✅ Standup sent successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        try:
            error_embed = {
                "title": "⚠️ Standup Automation Failed",
                "description": f"```{str(e)}```",
                "color": 0xE74C3C
            }
            # Use simple send for errors
            send_to_discord([error_embed])
        except:
            pass
        raise

if __name__ == "__main__":
    main()
