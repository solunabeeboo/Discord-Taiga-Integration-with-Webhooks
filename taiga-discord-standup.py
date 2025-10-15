import os
import requests
from datetime import datetime

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
        
        sprint_embed = create_sprint_standup_embed(
            project,
            current_sprint,
            sprint_tasks,
            sprint_tasks_by_status
        )
        
        print("📨 Sending to Discord...")
        send_to_discord([sprint_embed])
        
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
            send_to_discord([error_embed])
        except:
            pass
        raise

if __name__ == "__main__":
    main()