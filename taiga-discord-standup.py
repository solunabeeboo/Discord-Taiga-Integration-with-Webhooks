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
    return colors.get(status_name, 0x34495E)  # Default dark blue

def create_kanban_embeds(project, user_stories, tasks):
    """Create Discord embeds that look like a kanban board"""
    
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
    
    # Create main header embed
    project_url = project.get('url', f"https://tree.taiga.io/project/{PROJECT_SLUG}")
    
    embeds = [{
        "title": "🌅 Daily Standup",
        "description": f"**{project['name']}**\n{datetime.now().strftime('%A, %B %d, %Y')}",
        "color": 0x5865F2,  # Discord Blurple
        "url": project_url,
        "thumbnail": {
            "url": "https://tree.taiga.io/images/logo-color.png"
        },
        "footer": {
            "text": f"Total Stories: {len([s for s in user_stories if s is not None])}"
        }
    }]
    
    # Create an embed for each status column (like kanban columns)
    for status, stories in sorted(stories_by_status.items()):
        if not stories:
            continue
            
        emoji = STATUS_EMOJIS.get(status, '📌')
        
        # Build the fields for this status
        fields = []
        
        for story in stories[:10]:  # Limit to 10 per status
            if story is None:
                continue
            
            subject = story.get('subject', 'No title')
            story_ref = story.get('ref', '')
            
            # Get assigned user
            assigned_info = story.get('assigned_to_extra_info')
            if assigned_info and isinstance(assigned_info, dict):
                assigned = assigned_info.get('full_name_display', 'Unassigned')
            else:
                assigned = 'Unassigned'
            
            # Get story tasks
            story_tasks = tasks_by_story.get(story.get('id'), [])
            tasks_info = ""
            if story_tasks:
                completed_tasks = len([t for t in story_tasks if t.get('is_closed', False)])
                total_tasks = len(story_tasks)
                tasks_info = f"\n└ Tasks: {completed_tasks}/{total_tasks} ✓"
            
            # Create story field
            story_title = f"#{story_ref} {subject[:50]}" if story_ref else subject[:50]
            story_value = f"👤 {assigned}{tasks_info}"
            
            fields.append({
                "name": story_title,
                "value": story_value,
                "inline": False
            })
        
        # Add "and X more" if there are too many
        if len(stories) > 10:
            fields.append({
                "name": "➕ More items",
                "value": f"... and {len(stories) - 10} more stories",
                "inline": False
            })
        
        # Create the status embed
        embed = {
            "title": f"{emoji} {status}",
            "color": get_status_color(status),
            "fields": fields,
            "footer": {
                "text": f"{len(stories)} {'story' if len(stories) == 1 else 'stories'}"
            }
        }
        
        embeds.append(embed)
    
    return embeds

def create_team_summary_embed(user_stories):
    """Create a summary showing what each team member is working on"""
    
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
        
        # Only count non-done stories
        status_info = story.get('status_extra_info', {})
        status = status_info.get('name', '') if status_info else ''
        
        if status not in ['Done', 'Archived']:
            if user not in stories_by_user:
                stories_by_user[user] = []
            stories_by_user[user].append(story)
    
    # Create fields for each user
    fields = []
    for user, stories in sorted(stories_by_user.items()):
        if user == 'Unassigned':
            continue
            
        story_list = []
        for story in stories[:3]:  # Show top 3 per person
            status_info = story.get('status_extra_info', {})
            status = status_info.get('name', 'Unknown') if status_info else 'Unknown'
            emoji = STATUS_EMOJIS.get(status, '📌')
            subject = story.get('subject', 'No title')[:40]
            story_list.append(f"{emoji} {subject}")
        
        if len(stories) > 3:
            story_list.append(f"*+{len(stories) - 3} more*")
        
        fields.append({
            "name": f"👤 {user}",
            "value": "\n".join(story_list) if story_list else "No active tasks",
            "inline": True
        })
    
    # Add unassigned if any
    if 'Unassigned' in stories_by_user:
        unassigned_count = len(stories_by_user['Unassigned'])
        fields.append({
            "name": "⚠️ Unassigned",
            "value": f"{unassigned_count} {'story needs' if unassigned_count == 1 else 'stories need'} assignment",
            "inline": True
        })
    
    return {
        "title": "👥 Team Workload",
        "color": 0xFEE75C,  # Yellow
        "fields": fields
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
        
        print("✍️ Creating kanban board embeds...")
        kanban_embeds = create_kanban_embeds(project, user_stories, tasks)
        
        print("👥 Creating team summary...")
        team_embed = create_team_summary_embed(user_stories)
        
        # Combine all embeds (Discord allows up to 10 embeds per message)
        all_embeds = kanban_embeds[:9]  # Leave room for team summary
        all_embeds.append(team_embed)
        
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