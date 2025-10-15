import os
import requests
from datetime import datetime

# Configuration from environment variables
TAIGA_URL = os.environ.get('TAIGA_URL', 'https://api.taiga.io/api/v1')
TAIGA_USERNAME = os.environ['TAIGA_USERNAME']
TAIGA_PASSWORD = os.environ['TAIGA_PASSWORD']
PROJECT_SLUG = os.environ['PROJECT_SLUG']
DISCORD_WEBHOOK = os.environ['DISCORD_WEBHOOK']

# Kanban columns in order - ALL will be shown even if empty
KANBAN_COLUMNS = [
    ('New', '🆕'),
    ('Ready', '📋'),
    ('In Progress', '🔄'),
    ('Ready for test', '🧪'),
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

def organize_stories_by_status(user_stories):
    """Organize stories by status"""
    stories_by_status = {}
    
    for story in user_stories:
        if story is None:
            continue
            
        status_info = story.get('status_extra_info')
        if status_info and isinstance(status_info, dict):
            status = status_info.get('name', 'Unknown')
        else:
            status = 'Unknown'
        
        # Normalize "In progress" vs "In Progress"
        if status.lower() == 'in progress':
            status = 'In Progress'
            
        if status not in stories_by_status:
            stories_by_status[status] = []
        stories_by_status[status].append(story)
    
    return stories_by_status

def create_mega_standup_embed(project, user_stories, tasks, stories_by_status, tasks_by_story):
    """Create ONE massive embed with everything"""
    
    project_url = project.get('url', f"https://tree.taiga.io/project/{PROJECT_SLUG}")
    
    # Calculate metrics
    total_stories = len([s for s in user_stories if s is not None])
    done_stories = len(stories_by_status.get('Done', []))
    blocked_count = len(stories_by_status.get('Blocked', []))
    
    # Build the main description with overview
    description = f"**{datetime.now().strftime('%A, %B %d, %Y')}** • [Open Project]({project_url})\n\n"
    
    # Add quick metrics line
    completion = (done_stories / total_stories * 100) if total_stories > 0 else 0
    health = "🟢" if blocked_count == 0 else "🟡" if blocked_count < 3 else "🔴"
    description += f"{health} **{done_stories}/{total_stories}** complete ({completion:.0f}%) • "
    if blocked_count > 0:
        description += f"🚫 **{blocked_count}** blocked • "
    description += f"📊 **{total_stories}** total stories\n\n"
    description += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Create kanban board fields - ALL COLUMNS, left to right, using inline
    fields = []
    
    for status_name, emoji in KANBAN_COLUMNS:
        stories = stories_by_status.get(status_name, [])
        count = len(stories)
        
        # Build column content
        column_lines = []
        
        # Show top 3 stories per column
        for story in stories[:3]:
            if story is None:
                continue
            
            ref = story.get('ref', '')
            subject = story.get('subject', 'No title')[:25]
            
            # Get assignee username
            assigned_info = story.get('assigned_to_extra_info')
            if assigned_info and isinstance(assigned_info, dict):
                assigned = assigned_info.get('username', '?')
            else:
                assigned = '?'
            
            # Task progress
            story_tasks = tasks_by_story.get(story.get('id'), [])
            task_badge = ""
            if story_tasks:
                completed = len([t for t in story_tasks if t.get('is_closed', False)])
                total_t = len(story_tasks)
                task_badge = f" `{completed}/{total_t}`"
            
            column_lines.append(f"**#{ref}** @{assigned}{task_badge}\n{subject}...")
        
        if len(stories) > 3:
            column_lines.append(f"\n*+{len(stories) - 3} more*")
        
        # If empty column
        if not column_lines:
            column_lines.append("*—*")
        
        column_value = "\n\n".join(column_lines)
        
        fields.append({
            "name": f"{emoji} {status_name} ({count})",
            "value": column_value,
            "inline": True  # This makes them horizontal!
        })
    
    # Add separator row (empty field to break to next line)
    fields.append({
        "name": "\u200B",  # Zero-width space
        "value": "\u200B",
        "inline": False
    })
    
    # Add BLOCKERS section if any (full width for visibility)
    if 'Blocked' in stories_by_status and stories_by_status['Blocked']:
        blocker_lines = []
        for story in stories_by_status['Blocked']:
            if story is None:
                continue
            ref = story.get('ref', '')
            subject = story.get('subject', 'No title')[:50]
            assigned_info = story.get('assigned_to_extra_info', {})
            assigned = assigned_info.get('username', '?') if assigned_info else '?'
            blocker_lines.append(f"🚨 **#{ref}** {subject} • @{assigned}")
        
        fields.append({
            "name": "⚠️ BLOCKED - Needs Immediate Attention",
            "value": "\n".join(blocker_lines[:5]),  # Top 5 blockers
            "inline": False
        })
    
    # Add team workload section (using inline for side-by-side)
    stories_by_user = {}
    for story in user_stories:
        if story is None:
            continue
        
        # Only active work
        status_info = story.get('status_extra_info', {})
        status = status_info.get('name', '') if status_info else ''
        if status in ['Done', 'Archived']:
            continue
        
        assigned_info = story.get('assigned_to_extra_info')
        if assigned_info and isinstance(assigned_info, dict):
            user = assigned_info.get('username', 'unassigned')
        else:
            user = 'unassigned'
        
        if user not in stories_by_user:
            stories_by_user[user] = []
        stories_by_user[user].append(story)
    
    # Add team members (inline for horizontal layout)
    team_count = 0
    for user, stories in sorted(stories_by_user.items()):
        if user == 'unassigned':
            continue
        
        team_count += 1
        count = len(stories)
        
        # Workload emoji
        if count <= 2:
            workload = "🟢"
        elif count <= 4:
            workload = "🟡"
        else:
            workload = "🔴"
        
        # Status breakdown
        status_counts = {}
        for story in stories:
            status_info = story.get('status_extra_info', {})
            status = status_info.get('name', 'Unknown') if status_info else 'Unknown'
            if status.lower() == 'in progress':
                status = 'In Progress'
            
            for col_name, col_emoji in KANBAN_COLUMNS:
                if status == col_name:
                    status_counts[col_emoji] = status_counts.get(col_emoji, 0) + 1
                    break
        
        breakdown = " ".join([f"{emoji}{cnt}" for emoji, cnt in status_counts.items()])
        
        fields.append({
            "name": f"{workload} @{user}",
            "value": f"**{count}** active\n{breakdown}",
            "inline": True
        })
        
        # Break to new row after every 3 team members
        if team_count % 3 == 0:
            fields.append({
                "name": "\u200B",
                "value": "\u200B", 
                "inline": False
            })
    
    # Add unassigned warning if needed
    if 'unassigned' in stories_by_user:
        count = len(stories_by_user['unassigned'])
        fields.append({
            "name": "⚠️ Unassigned",
            "value": f"**{count}** stories",
            "inline": True
        })
    
    # Single massive embed
    return {
        "title": f"🌅 Daily Standup • {project['name']}",
        "description": description,
        "color": 0x5865F2,  # Discord blurple
        "fields": fields,
        "thumbnail": {
            "url": "https://tree.taiga.io/images/logo-color.png"
        },
        "footer": {
            "text": "📋 Kanban Board | 👥 Team Workload | Updated automatically",
            "icon_url": "https://tree.taiga.io/images/logo-color.png"
        },
        "timestamp": datetime.now().isoformat()
    }

def send_to_discord(embed):
    """Send single embed to Discord via webhook"""
    response = requests.post(
        DISCORD_WEBHOOK,
        json={'embeds': [embed]}
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
        
        print("🎨 Building mega standup embed...")
        
        # Organize data
        stories_by_status = organize_stories_by_status(user_stories)
        
        # Organize tasks by story
        tasks_by_story = {}
        for task in tasks:
            if task is None:
                continue
            story_id = task.get('user_story')
            if story_id:
                if story_id not in tasks_by_story:
                    tasks_by_story[story_id] = []
                tasks_by_story[story_id].append(task)
        
        # Create the ONE mega embed
        mega_embed = create_mega_standup_embed(
            project, 
            user_stories, 
            tasks, 
            stories_by_status, 
            tasks_by_story
        )
        
        print("📨 Sending to Discord...")
        send_to_discord(mega_embed)
        
        print("✅ Standup sent successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        # Send error to Discord
        try:
            error_embed = {
                "title": "⚠️ Standup Automation Failed",
                "description": f"```{str(e)}```",
                "color": 0xE74C3C
            }
            send_to_discord(error_embed)
        except:
            pass
        raise

if __name__ == "__main__":
    main()