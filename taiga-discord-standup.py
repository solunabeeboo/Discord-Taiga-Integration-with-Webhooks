import os
import requests
from datetime import datetime, timedelta

# Configuration from environment variables
TAIGA_URL = os.environ.get('TAIGA_URL', 'https://api.taiga.io/api/v1')
TAIGA_USERNAME = os.environ['TAIGA_USERNAME']
TAIGA_PASSWORD = os.environ['TAIGA_PASSWORD']
PROJECT_SLUG = os.environ['PROJECT_SLUG']
DISCORD_WEBHOOK = os.environ['DISCORD_WEBHOOK']

# Status emoji and workflow order
STATUS_CONFIG = [
    ('New', '🆕', 0x95A5A6),
    ('Ready', '📋', 0x3498DB),
    ('In progress', '🔄', 0xF39C12),
    ('In Progress', '🔄', 0xF39C12),
    ('Ready for test', '🧪', 0x9B59B6),
    ('Blocked', '🚫', 0xE74C3C),
    ('Done', '✅', 0x2ECC71),
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

def get_emoji_for_status(status_name):
    """Get emoji for a status"""
    for name, emoji, _ in STATUS_CONFIG:
        if name == status_name:
            return emoji
    return '📌'

def get_color_for_status(status_name):
    """Get color for a status"""
    for name, _, color in STATUS_CONFIG:
        if name == status_name:
            return color
    return 0x34495E

def create_header_embed(project):
    """Create beautiful header with quick stats"""
    project_url = project.get('url', f"https://tree.taiga.io/project/{PROJECT_SLUG}")
    
    return {
        "author": {
            "name": "Daily Standup Report",
            "icon_url": "https://tree.taiga.io/images/logo-color.png"
        },
        "title": f"🌅 {project['name']}",
        "description": f"**{datetime.now().strftime('%A, %B %d, %Y')}**\n\n*Three questions: What's done? What's next? What's blocking?*",
        "color": 0x5865F2,
        "url": project_url,
        "timestamp": datetime.now().isoformat()
    }

def organize_stories_by_status(user_stories):
    """Organize stories by status in workflow order"""
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
    
    return stories_by_status

def create_kanban_flow_embed(stories_by_status, tasks_by_story):
    """Create workflow-focused embed showing the flow of work"""
    
    # Build description showing workflow flow
    flow_parts = []
    total_active = 0
    
    for status_name, emoji, color in STATUS_CONFIG:
        if status_name not in stories_by_status:
            continue
        
        count = len(stories_by_status[status_name])
        if status_name not in ['Done', 'Archived']:
            total_active += count
        
        # Create visual flow indicator
        bar_length = min(count, 20)  # Max 20 for visual
        bar = '█' * bar_length
        flow_parts.append(f"{emoji} **{status_name}**: {bar} `{count}`")
    
    fields = []
    
    # Add critical blockers section
    if 'Blocked' in stories_by_status and stories_by_status['Blocked']:
        blocker_lines = []
        for story in stories_by_status['Blocked'][:3]:
            if story is None:
                continue
            ref = story.get('ref', '')
            subject = story.get('subject', 'No title')[:40]
            assigned_info = story.get('assigned_to_extra_info', {})
            assigned = assigned_info.get('username', '?') if assigned_info else '?'
            blocker_lines.append(f"🚨 **#{ref}** {subject}\n   └ @{assigned}")
        
        if blocker_lines:
            fields.append({
                "name": "⚠️ BLOCKERS - Needs Attention",
                "value": "\n\n".join(blocker_lines),
                "inline": False
            })
    
    # Add aging items (items in progress for too long)
    in_progress_stories = stories_by_status.get('In progress', []) + stories_by_status.get('In Progress', [])
    if in_progress_stories:
        # Sort by creation date to find oldest
        aging_items = []
        for story in in_progress_stories[:3]:
            if story is None:
                continue
            ref = story.get('ref', '')
            subject = story.get('subject', 'No title')[:40]
            assigned_info = story.get('assigned_to_extra_info', {})
            assigned = assigned_info.get('username', '?') if assigned_info else '?'
            
            # Get task progress
            story_tasks = tasks_by_story.get(story.get('id'), [])
            task_info = ""
            if story_tasks:
                completed = len([t for t in story_tasks if t.get('is_closed', False)])
                total = len(story_tasks)
                task_info = f"`{completed}/{total}✓`"
            
            aging_items.append(f"⏱️ **#{ref}** {subject} {task_info}\n   └ @{assigned}")
        
        if aging_items:
            fields.append({
                "name": "🔄 In Progress - Keep Moving",
                "value": "\n\n".join(aging_items),
                "inline": False
            })
    
    return {
        "title": "📊 Workflow Status",
        "description": "\n".join(flow_parts),
        "color": 0xF39C12,
        "fields": fields,
        "footer": {
            "text": f"{total_active} active stories across workflow"
        }
    }

def create_team_focus_embed(user_stories, tasks_by_story):
    """Create team focus showing what each person is working on"""
    
    # Group by assigned user (only active work)
    stories_by_user = {}
    
    for story in user_stories:
        if story is None:
            continue
            
        # Only count active work
        status_info = story.get('status_extra_info', {})
        status = status_info.get('name', '') if status_info else ''
        if status in ['Done', 'Archived']:
            continue
        
        assigned_info = story.get('assigned_to_extra_info')
        if assigned_info and isinstance(assigned_info, dict):
            user = assigned_info.get('username', 'Unassigned')
        else:
            user = 'Unassigned'
        
        if user not in stories_by_user:
            stories_by_user[user] = []
        stories_by_user[user].append(story)
    
    fields = []
    
    for user, stories in sorted(stories_by_user.items()):
        if user == 'Unassigned':
            continue
        
        # Show top priorities for each person
        story_lines = []
        for story in stories[:2]:  # Top 2 per person
            status_info = story.get('status_extra_info', {})
            status = status_info.get('name', 'Unknown') if status_info else 'Unknown'
            emoji = get_emoji_for_status(status)
            
            ref = story.get('ref', '')
            subject = story.get('subject', 'No title')[:30]
            
            # Task progress
            story_tasks = tasks_by_story.get(story.get('id'), [])
            task_badge = ""
            if story_tasks:
                completed = len([t for t in story_tasks if t.get('is_closed', False)])
                total = len(story_tasks)
                task_badge = f" `{completed}/{total}`"
            
            story_lines.append(f"{emoji} **#{ref}** {subject}{task_badge}")
        
        if len(stories) > 2:
            story_lines.append(f"*+{len(stories) - 2} more*")
        
        # Add workload indicator
        workload = "🟢 Light" if len(stories) <= 2 else "🟡 Moderate" if len(stories) <= 4 else "🔴 Heavy"
        
        fields.append({
            "name": f"👤 @{user} ({len(stories)}) {workload}",
            "value": "\n".join(story_lines) if story_lines else "*No active tasks*",
            "inline": True
        })
    
    # Add unassigned warning
    if 'Unassigned' in stories_by_user:
        count = len(stories_by_user['Unassigned'])
        fields.append({
            "name": "⚠️ Unassigned",
            "value": f"**{count}** {'story needs' if count == 1 else 'stories need'} assignment",
            "inline": True
        })
    
    return {
        "title": "👥 Team Focus & Workload",
        "description": "*Current priorities and capacity*",
        "color": 0xFEE75C,
        "fields": fields
    }

def create_velocity_metrics_embed(user_stories, tasks):
    """Create metrics showing team velocity and progress"""
    
    total_stories = len([s for s in user_stories if s is not None])
    total_tasks = len([t for t in tasks if t is not None])
    
    # Calculate completion stats
    done_stories = 0
    in_progress_stories = 0
    blocked_stories = 0
    ready_stories = 0
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
        elif status == 'Ready':
            ready_stories += 1
    
    for task in tasks:
        if task and task.get('is_closed', False):
            completed_tasks += 1
    
    # Calculate percentages
    story_completion = (done_stories / total_stories * 100) if total_stories > 0 else 0
    task_completion = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Create compact progress bars
    def mini_bar(percentage, length=10):
        filled = int(percentage / 10)
        return '█' * filled + '░' * (length - filled)
    
    # Health indicator
    if blocked_stories == 0 and in_progress_stories > 0:
        health = "🟢 Healthy"
    elif blocked_stories > 0 and blocked_stories < 3:
        health = "🟡 Watch"
    else:
        health = "🔴 Attention Needed"
    
    fields = [
        {
            "name": "📈 Sprint Progress",
            "value": f"{mini_bar(story_completion)}\n**{done_stories}** of **{total_stories}** stories complete\n({story_completion:.0f}%)",
            "inline": True
        },
        {
            "name": "✓ Task Completion",
            "value": f"{mini_bar(task_completion)}\n**{completed_tasks}** of **{total_tasks}** tasks done\n({task_completion:.0f}%)",
            "inline": True
        },
        {
            "name": "🏥 Health Status",
            "value": f"{health}\n🔄 {in_progress_stories} active\n🚫 {blocked_stories} blocked\n📋 {ready_stories} ready",
            "inline": True
        }
    ]
    
    return {
        "title": "📊 Velocity & Metrics",
        "color": 0x3498DB,
        "fields": fields
    }

def create_action_items_embed(stories_by_status):
    """Create actionable next steps"""
    
    actions = []
    
    # Check for blockers
    if 'Blocked' in stories_by_status and stories_by_status['Blocked']:
        actions.append(f"🚨 **{len(stories_by_status['Blocked'])}** blocked items need resolution")
    
    # Check for ready items
    if 'Ready' in stories_by_status and stories_by_status['Ready']:
        actions.append(f"📋 **{len(stories_by_status['Ready'])}** stories ready to start")
    
    # Check for review
    if 'Ready for test' in stories_by_status and stories_by_status['Ready for test']:
        actions.append(f"🧪 **{len(stories_by_status['Ready for test'])}** items ready for testing")
    
    if not actions:
        actions.append("✅ All clear! Keep up the momentum")
    
    return {
        "title": "🎯 Action Items",
        "description": "\n".join(actions),
        "color": 0xE67E22,
        "footer": {
            "text": "💬 Discuss blockers in daily sync • 🔗 Update board as you progress"
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
        
        print("✍️ Creating workflow-focused standup...")
        
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
        
        # Create embeds in priority order
        embeds = [
            create_header_embed(project),
            create_kanban_flow_embed(stories_by_status, tasks_by_story),
            create_team_focus_embed(user_stories, tasks_by_story),
            create_velocity_metrics_embed(user_stories, tasks),
            create_action_items_embed(stories_by_status)
        ]
        
        print("📨 Sending to Discord...")
        send_to_discord(embeds)
        
        print("✅ Standup sent successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        # Send error to Discord
        try:
            error_embed = [{
                "title": "⚠️ Standup Automation Error",
                "description": f"```{str(e)}```",
                "color": 0xE74C3C,
                "footer": {
                    "text": "Check GitHub Actions logs for details"
                }
            }]
            send_to_discord(error_embed)
        except:
            pass
        raise

if __name__ == "__main__":
    main()