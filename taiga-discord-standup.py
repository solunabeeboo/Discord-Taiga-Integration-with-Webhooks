import os
import requests
from datetime import datetime, timedelta

# Configuration from environment variables
TAIGA_URL = os.environ.get('TAIGA_URL', 'https://api.taiga.io/api/v1')
TAIGA_USERNAME = os.environ['TAIGA_USERNAME']
TAIGA_PASSWORD = os.environ['TAIGA_PASSWORD']
PROJECT_SLUG = os.environ['PROJECT_SLUG']
DISCORD_WEBHOOK = os.environ['DISCORD_WEBHOOK']

# Status emoji mapping for visual appeal
STATUS_EMOJIS = {
    'New': '🆕',
    'Ready': '📋',
    'In progress': '🔄',
    'In Progress': '🔄',
    'Ready for test': '🧪',
    'Done': '✅',
    'Archived': '📦',
    'Blocked': '🚫',
}

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

def get_user_stories(auth_token, project_id):
    """Get all user stories for the project"""
    headers = {'Authorization': f'Bearer {auth_token}'}
    response = requests.get(
        f'{TAIGA_URL}/userstories?project={project_id}',
        headers=headers
    )
    response.raise_for_status()
    return response.json()

def get_tasks(auth_token, project_id):
    """Get all tasks for the project"""
    headers = {'Authorization': f'Bearer {auth_token}'}
    response = requests.get(
        f'{TAIGA_URL}/tasks?project={project_id}',
        headers=headers
    )
    response.raise_for_status()
    return response.json()

def get_status_color(status_name):
    """Get Discord color for status"""
    colors = {
        'New': 0x95A5A6,           # Gray
        'Ready': 0x3498DB,         # Blue
        'In progress': 0xF39C12,   # Orange
        'In Progress': 0xF39C12,   # Orange
        'Ready for test': 0x9B59B6, # Purple
        'Done': 0x2ECC71,          # Green
        'Archived': 0x7F8C8D,      # Dark Gray
        'Blocked': 0xE74C3C,       # Red
    }
    return colors.get(status_name, 0x34495E)

def create_horizontal_kanban_embed(project, user_stories, tasks):
    """Create a single embed with horizontal-style kanban columns using inline fields"""
    
    # Filter and organize stories by status
    stories_by_status = {}
    for story in user_stories:
        if story is None:
            continue
            
        status_info = story.get('status_extra_info')
        if status_info and isinstance(status_info, dict):
            status = status_info.get('name', 'Unknown')
        else:
            status = 'Unknown'
            
        if status not in stories_by_status:
            stories_by_status[status] = []
        stories_by_status[status].append(story)
    
    # Organize tasks by user story
    tasks_by_story = {}
    for task in tasks:
        if task is None:
            continue
        story_id = task.get('user_story')
        if story_id:
            if story_id not in tasks_by_story:
                tasks_by_story[story_id] = []
            tasks_by_story[story_id].append(task)
    
    # Create fields for each status column (inline = True makes them side-by-side)
    fields = []
    
    # Define the order of statuses for workflow
    status_order = ['New', 'Ready', 'In progress', 'In Progress', 'Ready for test', 'Blocked', 'Done']
    
    for status in status_order:
        if status not in stories_by_status:
            continue
            
        stories = stories_by_status[status]
        emoji = STATUS_EMOJIS.get(status, '📌')
        
        # Build compact story list for this column
        story_lines = []
        for story in stories[:4]:  # Max 4 per column for horizontal layout
            if story is None:
                continue
            
            subject = story.get('subject', 'No title')[:25]  # Shorter for horizontal
            story_ref = story.get('ref', '')
            
            # Get assigned user (just first name or initials)
            assigned_info = story.get('assigned_to_extra_info')
            if assigned_info and isinstance(assigned_info, dict):
                full_name = assigned_info.get('full_name_display', '?')
                # Get first name or initials
                assigned = full_name.split()[0] if full_name else '?'
            else:
                assigned = '?'
            
            # Task progress
            story_tasks = tasks_by_story.get(story.get('id'), [])
            task_indicator = ""
            if story_tasks:
                completed = len([t for t in story_tasks if t.get('is_closed', False)])
                total = len(story_tasks)
                task_indicator = f" `{completed}/{total}`"
            
            story_lines.append(f"**#{story_ref}** {assigned}{task_indicator}\n{subject}...")
        
        if len(stories) > 4:
            story_lines.append(f"*+{len(stories) - 4} more*")
        
        column_value = "\n\n".join(story_lines) if story_lines else "*Empty*"
        
        fields.append({
            "name": f"{emoji} **{status}** ({len(stories)})",
            "value": column_value,
            "inline": True  # This makes columns appear side-by-side
        })
    
    project_url = project.get('url', f"https://tree.taiga.io/project/{PROJECT_SLUG}")
    
    return {
        "title": "📊 Kanban Board",
        "description": f"**{project['name']}** • {datetime.now().strftime('%B %d, %Y')}",
        "url": project_url,
        "color": 0x5865F2,
        "fields": fields,
        "footer": {
            "text": f"💡 Tip: Scroll right to see all columns"
        }
    }

def create_team_workload_embed(user_stories, tasks):
    """Create team workload breakdown with inline fields"""
    
    # Group by assigned user
    stories_by_user = {}
    
    for story in user_stories:
        if story is None:
            continue
            
        assigned_info = story.get('assigned_to_extra_info')
        if assigned_info and isinstance(assigned_info, dict):
            user = assigned_info.get('full_name_display', 'Unassigned')
        else:
            user = 'Unassigned'
        
        # Only count active stories
        status_info = story.get('status_extra_info', {})
        status = status_info.get('name', '') if status_info else ''
        
        if status not in ['Done', 'Archived']:
            if user not in stories_by_user:
                stories_by_user[user] = []
            stories_by_user[user].append(story)
    
    # Create inline fields for each person
    fields = []
    for user, stories in sorted(stories_by_user.items()):
        if user == 'Unassigned':
            continue
        
        # Count by status
        status_counts = {}
        for story in stories:
            status_info = story.get('status_extra_info', {})
            status = status_info.get('name', 'Unknown') if status_info else 'Unknown'
            emoji = STATUS_EMOJIS.get(status, '📌')
            status_counts[emoji] = status_counts.get(emoji, 0) + 1
        
        status_breakdown = " • ".join([f"{emoji} {count}" for emoji, count in status_counts.items()])
        
        fields.append({
            "name": f"👤 {user}",
            "value": f"**{len(stories)}** active\n{status_breakdown}",
            "inline": True
        })
    
    # Add unassigned
    if 'Unassigned' in stories_by_user:
        unassigned_count = len(stories_by_user['Unassigned'])
        fields.append({
            "name": "⚠️ Unassigned",
            "value": f"**{unassigned_count}** {'story' if unassigned_count == 1 else 'stories'}",
            "inline": True
        })
    
    return {
        "title": "👥 Team Workload",
        "color": 0xFEE75C,
        "fields": fields
    }

def create_metrics_embed(user_stories, tasks):
    """Create project metrics and insights"""
    
    total_stories = len([s for s in user_stories if s is not None])
    total_tasks = len([t for t in tasks if t is not None])
    
    # Calculate completion stats
    done_stories = 0
    in_progress_stories = 0
    blocked_stories = 0
    completed_tasks = 0
    
    for story in user_stories:
        if story is None:
            continue
        status_info = story.get('status_extra_info', {})
        status = status_info.get('name', '') if status_info else ''
        
        if status == 'Done':
            done_stories += 1
        elif status in ['In progress', 'In Progress']:
            in_progress_stories += 1
        elif status == 'Blocked':
            blocked_stories += 1
    
    for task in tasks:
        if task and task.get('is_closed', False):
            completed_tasks += 1
    
    # Calculate percentages
    story_completion = (done_stories / total_stories * 100) if total_stories > 0 else 0
    task_completion = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Create progress bars
    def progress_bar(percentage, length=10):
        filled = int(percentage / 10)
        return '█' * filled + '░' * (length - filled)
    
    fields = [
        {
            "name": "📈 Story Progress",
            "value": f"{progress_bar(story_completion)}\n**{done_stories}/{total_stories}** complete ({story_completion:.0f}%)",
            "inline": True
        },
        {
            "name": "✓ Task Progress",
            "value": f"{progress_bar(task_completion)}\n**{completed_tasks}/{total_tasks}** complete ({task_completion:.0f}%)",
            "inline": True
        },
        {
            "name": "🔄 Active Work",
            "value": f"**{in_progress_stories}** in progress\n**{blocked_stories}** blocked",
            "inline": True
        }
    ]
    
    return {
        "title": "📊 Project Metrics",
        "color": 0x5865F2,
        "fields": fields
    }

def create_header_embed(project):
    """Create beautiful header"""
    project_url = project.get('url', f"https://tree.taiga.io/project/{PROJECT_SLUG}")
    
    return {
        "title": "🌅 Daily Standup",
        "description": f"## {project['name']}\n{datetime.now().strftime('%A, %B %d, %Y')}",
        "color": 0x5865F2,
        "url": project_url,
        "thumbnail": {
            "url": "https://tree.taiga.io/images/logo-color.png"
        }
    }

def send_to_discord(embeds):
    """Send embeds to Discord via webhook"""
    response = requests.post(
        DISCORD_WEBHOOK,
        json={'embeds': embeds}
    )
    response.raise_for_status()

def main():
    try:
        print("🔐 Authenticating with Taiga...")
        auth_token = get_taiga_auth_token()
        
        print("📊 Fetching project data...")
        project = get_project_data(auth_token)
        
        print("📋 Fetching user stories...")
        user_stories = get_user_stories(auth_token, project['id'])
        
        print("✅ Fetching tasks...")
        tasks = get_tasks(auth_token, project['id'])
        
        print("✍️ Creating layered standup...")
        
        # Layer 1: Header
        header = create_header_embed(project)
        
        # Layer 2: Horizontal Kanban Board
        kanban = create_horizontal_kanban_embed(project, user_stories, tasks)
        
        # Layer 3: Team Workload (side-by-side people)
        workload = create_team_workload_embed(user_stories, tasks)
        
        # Layer 4: Metrics Dashboard
        metrics = create_metrics_embed(user_stories, tasks)
        
        # Combine in layers
        all_embeds = [header, kanban, workload, metrics]
        
        print("📨 Sending to Discord...")
        send_to_discord(all_embeds)
        
        print("✅ Standup sent successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        # Send error to Discord
        try:
            error_embed = [{
                "title": "⚠️ Standup Automation Error",
                "description": f"```{str(e)}```",
                "color": 0xE74C3C
            }]
            send_to_discord(error_embed)
        except:
            pass
        raise

if __name__ == "__main__":
    main()