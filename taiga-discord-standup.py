def create_story_board_section(title, columns, stories_by_status, tasks_by_story):
    """Create a story board section with fields (for Kanban)"""
    fields = []
    
    for status_name, emoji in columns:
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
            "inline": True
        })
    
    return fieldsimport os
import requests
from datetime import datetime

# Configuration from environment variables
TAIGA_URL = os.environ.get('TAIGA_URL', 'https://api.taiga.io/api/v1')
TAIGA_USERNAME = os.environ['TAIGA_USERNAME']
TAIGA_PASSWORD = os.environ['TAIGA_PASSWORD']
PROJECT_SLUG = os.environ['PROJECT_SLUG']
DISCORD_WEBHOOK = os.environ['DISCORD_WEBHOOK']

# Kanban columns - these are your actual Taiga statuses
KANBAN_COLUMNS = [
    ('Not Started', '⏸️'),
    ('In Progress', '🔄'),
    ('Ready for Test', '🧪'),
    ('Ready for Review', '👀'),
    ('Done', '✅'),
]

# Sprint/Scrum board columns - only task statuses
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
    """Get the current active sprint"""
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

def get_user_stories(auth_token, project_id, milestone_id=None):
    """Get user stories, optionally filtered by sprint/milestone"""
    headers = {'Authorization': f'Bearer {auth_token}'}
    params = {'project': project_id}
    if milestone_id:
        params['milestone'] = milestone_id
    
    response = requests.get(
        f'{TAIGA_URL}/userstories',
        headers=headers,
        params=params
    )
    response.raise_for_status()
    return response.json()

def get_all_user_stories(auth_token, project_id):
    """Get ALL user stories (for Kanban)"""
    headers = {'Authorization': f'Bearer {auth_token}'}
    response = requests.get(
        f'{TAIGA_URL}/userstories?project={project_id}',
        headers=headers
    )
    response.raise_for_status()
    return response.json()

def get_tasks(auth_token, project_id, milestone_id=None):
    """Get all tasks for the project, optionally filtered by sprint/milestone"""
    headers = {'Authorization': f'Bearer {auth_token}'}
    params = {'project': project_id}
    if milestone_id:
        params['milestone'] = milestone_id
    
    response = requests.get(
        f'{TAIGA_URL}/tasks',
        headers=headers,
        params=params
    )
    response.raise_for_status()
    return response.json()

def get_all_tasks(auth_token, project_id):
    """Get ALL tasks (for overall metrics)"""
    headers = {'Authorization': f'Bearer {auth_token}'}
    response = requests.get(
        f'{TAIGA_URL}/tasks?project={project_id}',
        headers=headers
    )
    response.raise_for_status()
    return response.json()

def organize_tasks_by_status(tasks):
    """Organize tasks by status"""
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
            
        if status not in stories_by_status:
            stories_by_status[status] = []
        stories_by_status[status].append(story)
    
    return stories_by_status

def create_task_board_section(title, columns, tasks_by_status):
    """Create a task board section with fields"""
    fields = []
    
    for status_name, emoji in columns:
        tasks = tasks_by_status.get(status_name, [])
        count = len(tasks)
        
        # Build column content
        column_lines = []
        
        # Show top 3 tasks per column
        for task in tasks[:3]:
            if task is None:
                continue
            
            ref = task.get('ref', '')
            subject = task.get('subject', 'No title')[:25]
            
            # Get assignee username
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
        
        # If empty column
        if not column_lines:
            column_lines.append("*—*")
        
        column_value = "\n\n".join(column_lines)
        
        fields.append({
            "name": f"{emoji} {status_name} ({count})",
            "value": column_value,
            "inline": True
        })
    
    return fields

def create_sprint_standup_embed(project, sprint, sprint_tasks, sprint_tasks_by_status):
    """Create FIRST embed with Sprint board and team message"""
    
    project_url = project.get('url', f"https://tree.taiga.io/project/{PROJECT_SLUG}")
    
    # Calculate sprint metrics
    sprint_total = len([t for t in sprint_tasks if t is not None])
    sprint_done = len(sprint_tasks_by_status.get('Done', []))
    
    # Build the main description
    sprint_name = sprint['name'] if sprint else 'No Active Sprint'
    description = f"**{datetime.now().strftime('%A, %B %d, %Y')}** • [Open Project]({project_url})\n\n"
    
    # Add @everyone message
    description += (
        "@everyone Hey team, this is your daily reminder to head to the most recent "
        "[Sprints page](https://discord.com/channels/1401686577629106246/1407869050050314311) "
        "and check in with the team. Please comment on the sprint post what you will get done today, "
        "or if you are too busy, just let the team know you are not available today. Thank you!\n\n"
    )
    
    # Sprint info
    if sprint:
        sprint_completion = (sprint_done / sprint_total * 100) if sprint_total > 0 else 0
        description += f"🏃 **{sprint_name}**: {sprint_done}/{sprint_total} tasks complete ({sprint_completion:.0f}%)\n\n"
    
    description += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    fields = []
    
    # SPRINT BOARD SECTION (TASKS ONLY)
    if sprint and sprint_total > 0:
        fields.append({
            "name": f"🏃 {sprint_name} (Sprint Tasks)",
            "value": f"Active sprint with **{sprint_total}** tasks",
            "inline": False
        })
        
        sprint_fields = create_task_board_section(
            f"Sprint: {sprint_name}",
            SPRINT_COLUMNS,
            sprint_tasks_by_status
        )
        fields.extend(sprint_fields)
    
    # Single embed
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

def create_kanban_and_metrics_embed(project, all_stories, all_tasks, all_stories_by_status, tasks_by_story, sprint, sprint_tasks):
    """Create SECOND embed with Kanban board, blockers, team workload, and metrics"""
    
    # Calculate metrics
    kanban_total = len([s for s in all_stories if s is not None])
    kanban_done = len(all_stories_by_status.get('Done', []))
    blocked_count = len(all_stories_by_status.get('Blocked', []))
    
    # Kanban info
    kanban_completion = (kanban_done / kanban_total * 100) if kanban_total > 0 else 0
    health = "🟢" if blocked_count == 0 else "🟡" if blocked_count < 3 else "🔴"
    
    description = f"📋 **Kanban**: {kanban_done}/{kanban_total} stories complete ({kanban_completion:.0f}%) {health}\n"
    
    if blocked_count > 0:
        description += f"🚫 **{blocked_count}** blocked items\n"
    
    description += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    fields = []
    
    # KANBAN BOARD SECTION - DISABLED FOR NOW
    # fields.append({
    #     "name": "📋 Kanban Board (All Work)",
    #     "value": f"Overall project status with **{kanban_total}** stories",
    #     "inline": False
    # })
    # 
    # kanban_fields = create_story_board_section(
    #     "Kanban Board",
    #     KANBAN_COLUMNS,
    #     all_stories_by_status,
    #     tasks_by_story
    # )
    # fields.extend(kanban_fields)
    
    # Separator
    # fields.append({
    #     "name": "\u200B",
    #     "value": "\u200B",
    #     "inline": False
    # })
    
    # BLOCKERS section if any
    if 'Blocked' in all_stories_by_status and all_stories_by_status['Blocked']:
        blocker_lines = []
        for story in all_stories_by_status['Blocked'][:5]:
            if story is None:
                continue
            ref = story.get('ref', '')
            subject = story.get('subject', 'No title')[:50]
            assigned_info = story.get('assigned_to_extra_info', {})
            assigned = assigned_info.get('username', '?') if assigned_info else '?'
            blocker_lines.append(f"🚨 **#{ref}** {subject} • @{assigned}")
        
        fields.append({
            "name": "⚠️ BLOCKED - Needs Immediate Attention",
            "value": "\n".join(blocker_lines),
            "inline": False
        })
    
    # TEAM WORKLOAD section
    stories_by_user = {}
    for story in all_stories:
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
    
    # Add unassigned warning
    if 'unassigned' in stories_by_user:
        count = len(stories_by_user['unassigned'])
        fields.append({
            "name": "⚠️ Unassigned",
            "value": f"**{count}** stories",
            "inline": True
        })
    
    # Calculate task metrics
    total_tasks = len([t for t in all_tasks if t is not None])
    completed_tasks = sum(1 for t in all_tasks if t and t.get('is_closed', False))
    task_completion = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Sprint metrics
    sprint_total = len([t for t in sprint_tasks if t is not None]) if sprint_tasks else 0
    sprint_done = sum(1 for t in sprint_tasks if t and t.get('is_closed', False)) if sprint_tasks else 0
    sprint_completion = (sprint_done / sprint_total * 100) if sprint_total > 0 else 0
    
    # Progress bars
    def progress_bar(percentage, length=10):
        filled = int(percentage / 10)
        return '█' * filled + '░' * (length - filled)
    
    # Add separator before metrics
    fields.append({
        "name": "\u200B",
        "value": "\u200B",
        "inline": False
    })
    
    # Metrics section
    metric_fields = []
    
    if sprint and sprint_total > 0:
        metric_fields.append({
            "name": "🏃 Sprint Progress",
            "value": f"{progress_bar(sprint_completion)}\n**{sprint_done}/{sprint_total}** tasks\n({sprint_completion:.0f}%)",
            "inline": True
        })
    
    metric_fields.extend([
        {
            "name": "📈 Story Progress",
            "value": f"{progress_bar(kanban_completion)}\n**{kanban_done}/{kanban_total}** stories\n({kanban_completion:.0f}%)",
            "inline": True
        },
        {
            "name": "✓ Task Completion",
            "value": f"{progress_bar(task_completion)}\n**{completed_tasks}/{total_tasks}** tasks\n({task_completion:.0f}%)",
            "inline": True
        },
    ])
    
    fields.extend(metric_fields)
    
    # Single embed with everything
    return {
        "title": "📊 Team Metrics & Workload",
        "description": description,
        "color": 0x3498DB,
        "fields": fields,
        "footer": {
            "text": "👥 Team Workload | 📊 Velocity Metrics",
        },
        "timestamp": datetime.now().isoformat()
    }

def create_velocity_metrics_embed(sprint, sprint_tasks, all_stories, all_tasks):
    """REMOVED - metrics now in second embed"""
    pass

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
        
        print("🏃 Fetching sprints...")
        sprints = get_sprints(auth_token, project['id'])
        current_sprint = get_current_sprint(sprints)
        
        print(f"📋 Current sprint: {current_sprint['name'] if current_sprint else 'None'}")
        
        # Get sprint tasks (if there's an active sprint)
        sprint_tasks = []
        if current_sprint:
            print("📋 Fetching sprint tasks...")
            sprint_tasks = get_tasks(auth_token, project['id'], current_sprint['id'])
        
        # Get ALL stories for Kanban
        print("📋 Fetching all stories (Kanban)...")
        all_stories = get_all_user_stories(auth_token, project['id'])
        
        print("✅ Fetching all tasks...")
        all_tasks = get_all_tasks(auth_token, project['id'])
        
        print("🎨 Building standup embeds...")
        
        # Organize data
        sprint_tasks_by_status = organize_tasks_by_status(sprint_tasks)
        all_stories_by_status = organize_stories_by_status(all_stories)
        
        # Organize tasks by story
        tasks_by_story = {}
        for task in all_tasks:
            if task is None:
                continue
            story_id = task.get('user_story')
            if story_id:
                if story_id not in tasks_by_story:
                    tasks_by_story[story_id] = []
                tasks_by_story[story_id].append(task)
        
        # Create the TWO embeds
        sprint_embed = create_sprint_standup_embed(
            project,
            current_sprint,
            sprint_tasks,
            sprint_tasks_by_status
        )
        
        kanban_metrics_embed = create_kanban_and_metrics_embed(
            project,
            all_stories,
            all_tasks,
            all_stories_by_status,
            tasks_by_story,
            current_sprint,
            sprint_tasks
        )
        
        print("📨 Sending to Discord...")
        send_to_discord([sprint_embed, kanban_metrics_embed])
        
        print("✅ Standup sent successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        # Send error to Discord
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