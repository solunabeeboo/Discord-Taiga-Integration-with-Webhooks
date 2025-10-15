import os
import requests
import json
import io
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# Configuration
TAIGA_URL = os.environ.get('TAIGA_URL', 'https://api.taiga.io/api/v1')
TAIGA_USERNAME = os.environ['TAIGA_USERNAME']
TAIGA_PASSWORD = os.environ['TAIGA_PASSWORD']
PROJECT_SLUG = os.environ['PROJECT_SLUG']
DISCORD_WEBHOOK = os.environ['DISCORD_WEBHOOK']

SPRINT_COLUMNS = [
    ('Not Started', '⏸️'),
    ('In Progress', '🔄'),
    ('Done', '✅'),
]

# =============================================================================
# TAIGA API FUNCTIONS
# =============================================================================

def get_taiga_auth_token():
    """Authenticate with Taiga"""
    response = requests.post(f'{TAIGA_URL}/auth', json={
        'type': 'normal',
        'username': TAIGA_USERNAME,
        'password': TAIGA_PASSWORD
    })
    response.raise_for_status()
    return response.json()['auth_token']

def get_project_data(auth_token):
    """Get project details"""
    headers = {'Authorization': f'Bearer {auth_token}'}
    response = requests.get(f'{TAIGA_URL}/projects/by_slug?slug={PROJECT_SLUG}', headers=headers)
    response.raise_for_status()
    return response.json()

def get_sprints(auth_token, project_id):
    """Get all sprints"""
    headers = {'Authorization': f'Bearer {auth_token}'}
    response = requests.get(f'{TAIGA_URL}/milestones?project={project_id}', headers=headers)
    response.raise_for_status()
    return response.json()

def get_current_sprint(sprints):
    """Get active sprint based on date"""
    now = datetime.now().date()
    for sprint in sprints:
        if sprint.get('estimated_start') and sprint.get('estimated_finish'):
            start = datetime.fromisoformat(sprint['estimated_start'].replace('Z', '+00:00')).date()
            end = datetime.fromisoformat(sprint['estimated_finish'].replace('Z', '+00:00')).date()
            if start <= now <= end:
                return sprint
    
    if sprints:
        sorted_sprints = sorted(sprints, key=lambda x: x.get('estimated_start', ''), reverse=True)
        return sorted_sprints[0] if sorted_sprints else None
    return None

def get_sprint_tasks(auth_token, project_id, milestone_id):
    """Get tasks for sprint"""
    headers = {'Authorization': f'Bearer {auth_token}'}
    params = {'project': project_id, 'milestone': milestone_id}
    response = requests.get(f'{TAIGA_URL}/tasks', headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def organize_tasks_by_status(tasks):
    """Group tasks by status"""
    tasks_by_status = {}
    for task in tasks:
        if task is None:
            continue
        status_info = task.get('status_extra_info')
        status = status_info.get('name', 'Unknown') if status_info and isinstance(status_info, dict) else 'Unknown'
        if status not in tasks_by_status:
            tasks_by_status[status] = []
        tasks_by_status[status].append(task)
    return tasks_by_status

# =============================================================================
# IMAGE GENERATION
# =============================================================================

def create_sprint_board_image(sprint_name, sprint_tasks_by_status, sprint_done, sprint_total):
    """Generate visual sprint board"""
    
    width, height = 1200, 800
    
    # Colors
    bg_color = (30, 33, 36)
    card_bg = (47, 51, 56)
    not_started_color = (114, 137, 218)
    in_progress_color = (250, 166, 26)
    done_color = (67, 181, 129)
    text_color = (255, 255, 255)
    text_secondary = (185, 187, 190)
    
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Load fonts
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
        header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        task_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        title_font = header_font = task_font = small_font = ImageFont.load_default()
    
    # Title
    draw.text((40, 40), f"🏃 {sprint_name}", fill=text_color, font=title_font)
    
    # Progress
    completion = (sprint_done / sprint_total * 100) if sprint_total > 0 else 0
    draw.text((40, 95), f"{sprint_done}/{sprint_total} tasks complete ({completion:.0f}%)", fill=text_secondary, font=small_font)
    
    # Progress bar
    bar_x, bar_y, bar_width, bar_height = 40, 125, 1120, 20
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], radius=10, fill=(60, 63, 68))
    if sprint_total > 0:
        fill_width = int((sprint_done / sprint_total) * bar_width)
        if fill_width > 0:
            draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_width, bar_y + bar_height], radius=10, fill=done_color)
    
    # Columns
    columns = [
        ('Not Started', '⏸️', not_started_color),
        ('In Progress', '🔄', in_progress_color),
        ('Done', '✅', done_color)
    ]
    
    column_width, column_spacing, start_y = 360, 20, 180
    
    for idx, (status_name, emoji, color) in enumerate(columns):
        x = 40 + (idx * (column_width + column_spacing))
        tasks = sprint_tasks_by_status.get(status_name, [])
        count = len(tasks)
        
        # Column header
        draw.rounded_rectangle([x, start_y, x + column_width, start_y + 60], radius=12, fill=color)
        draw.text((x + 20, start_y + 12), f"{emoji} {status_name}", fill=(255, 255, 255), font=header_font)
        draw.text((x + 20, start_y + 45), f"{count} tasks", fill=(255, 255, 255), font=small_font)
        
        # Task cards
        card_y = start_y + 80
        for task in tasks[:5]:
            if task is None:
                continue
            
            card_height = 90
            draw.rounded_rectangle([x, card_y, x + column_width, card_y + card_height], radius=8, fill=card_bg)
            
            ref = task.get('ref', '?')
            draw.text((x + 15, card_y + 12), f"#{ref}", fill=color, font=task_font)
            
            subject = task.get('subject', 'No title')[:30]
            draw.text((x + 15, card_y + 38), subject, fill=text_color, font=small_font)
            
            assigned_info = task.get('assigned_to_extra_info')
            assigned = assigned_info.get('username', 'Unassigned') if assigned_info and isinstance(assigned_info, dict) else 'Unassigned'
            draw.text((x + 15, card_y + 62), f"@{assigned}", fill=text_secondary, font=small_font)
            
            card_y += card_height + 12
        
        if len(tasks) > 5:
            draw.text((x + 15, card_y), f"+{len(tasks) - 5} more tasks", fill=text_secondary, font=small_font)
    
    return img

# =============================================================================
# EMBED CREATION
# =============================================================================

def create_sprint_standup_embed(project, sprint, sprint_tasks, sprint_tasks_by_status):
    """Create Discord embed with just sprint progress"""
    
    project_url = project.get('url', f"https://tree.taiga.io/project/{PROJECT_SLUG}")
    sprint_total = len([t for t in sprint_tasks if t is not None])
    sprint_done = len(sprint_tasks_by_status.get('Done', []))
    sprint_name = sprint['name'] if sprint else 'No Active Sprint'
    
    description = f"**{datetime.now().strftime('%A, %B %d, %Y')}** • [Open Project]({project_url})\n\n"
    description += (
        "Hey team, this is your daily reminder to head to the most recent "
        "[Sprints page](https://discord.com/channels/1401686577629106246/1407869050050314311) "
        "and check in with the team. Please comment on the sprint post what you will get done today, "
        "or if you are too busy, just let the team know you are not available today. Thank you!"
    )
    
    # Only show sprint progress, no task details
    fields = []
    
    if sprint and sprint_total > 0:
        sprint_completion = (sprint_done / sprint_total * 100) if sprint_total > 0 else 0
        
        # Progress bar
        def progress_bar(percentage, length=15):
            filled = int(percentage / (100 / length))
            return '█' * filled + '░' * (length - filled)
        
        # Count by status
        not_started = len(sprint_tasks_by_status.get('Not Started', []))
        in_progress = len(sprint_tasks_by_status.get('In Progress', []))
        
        fields.append({
            "name": f"🏃 {sprint_name}",
            "value": (
                #f"{progress_bar(sprint_completion)}\n"
                f"**{sprint_done}/{sprint_total}** tasks complete ({sprint_completion:.0f}%)\n\n"
                f"⏸️ Not Started: **{not_started}** | "
                f"🔄 In Progress: **{in_progress}** | "
                f"✅ Done: **{sprint_done}**"
            ),
            "inline": False
        })
    
    return {
        "title": f"🌅 Daily Standup • {project['name']}",
        "description": description,
        "color": 0x5865F2,
        "fields": fields,
        "thumbnail": {"url": "https://tree.taiga.io/images/logo-color.png"},
        "footer": {"text": "🏃 Sprint Tasks Board • See visual board below", "icon_url": "https://tree.taiga.io/images/logo-color.png"},
        "timestamp": datetime.now().isoformat()
    }

# =============================================================================
# DISCORD SENDING
# =============================================================================

def send_to_discord_with_image(embeds, sprint_name, sprint_tasks_by_status, sprint_done, sprint_total):
    """Send embed first, then image to Discord"""
    
    try:
        # STEP 1: Send embed first
        print("📨 Sending embed...")
        response = requests.post(DISCORD_WEBHOOK, json={'content': '@everyone', 'embeds': embeds})
        print(f"📬 Embed status: {response.status_code}")
        response.raise_for_status()
        print("✅ Embed sent!")
        
        # STEP 2: Generate and send image
        print("🎨 Generating image...")
        img = create_sprint_board_image(sprint_name, sprint_tasks_by_status, sprint_done, sprint_total)
        print(f"✅ Image created: {img.size[0]}x{img.size[1]} pixels")
        
        print("📦 Converting to bytes...")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        file_size = len(img_bytes.getvalue())
        print(f"✅ File size: {file_size / 1024:.1f} KB")
        
        print("📨 Sending image...")
        files = {'file': ('sprint_board.png', img_bytes, 'image/png')}
        
        response = requests.post(DISCORD_WEBHOOK, files=files)
        print(f"📬 Image status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Error response: {response.text}")
        
        response.raise_for_status()
        print("✅ Image sent!")
        
    except Exception as e:
        print(f"❌ Send failed: {e}")
        import traceback
        traceback.print_exc()

# =============================================================================
# MAIN
# =============================================================================

def main():
    try:
        print("🔐 Authenticating...")
        auth_token = get_taiga_auth_token()
        
        print("📊 Fetching project...")
        project = get_project_data(auth_token)
        
        print("🏃 Fetching sprints...")
        sprints = get_sprints(auth_token, project['id'])
        current_sprint = get_current_sprint(sprints)
        
        if not current_sprint:
            print("⚠️ No active sprint!")
            return
        
        print(f"📋 Sprint: {current_sprint['name']}")
        
        print("📋 Fetching tasks...")
        sprint_tasks = get_sprint_tasks(auth_token, project['id'], current_sprint['id'])
        sprint_tasks_by_status = organize_tasks_by_status(sprint_tasks)
        
        sprint_done = len(sprint_tasks_by_status.get('Done', []))
        sprint_total = len([t for t in sprint_tasks if t is not None])
        
        print("🎨 Creating embed...")
        sprint_embed = create_sprint_standup_embed(project, current_sprint, sprint_tasks, sprint_tasks_by_status)
        
        print("📨 Sending standup...")
        send_to_discord_with_image([sprint_embed], current_sprint['name'], sprint_tasks_by_status, sprint_done, sprint_total)
        
        print("✅ Standup complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            error_embed = {"title": "⚠️ Standup Failed", "description": f"```{str(e)}```", "color": 0xE74C3C}
            requests.post(DISCORD_WEBHOOK, json={'embeds': [error_embed]})
        except:
            pass
        raise

if __name__ == "__main__":
    main()