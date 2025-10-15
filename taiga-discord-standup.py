import os
import io
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

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
    response = requests.post(
        f'{TAIGA_URL}/auth',
        json={'type': 'normal', 'username': TAIGA_USERNAME, 'password': TAIGA_PASSWORD}
    )
    response.raise_for_status()
    return response.json()['auth_token']

def get_project_data(auth_token):
    headers = {'Authorization': f'Bearer {auth_token}'}
    response = requests.get(f'{TAIGA_URL}/projects/by_slug?slug={PROJECT_SLUG}', headers=headers)
    response.raise_for_status()
    return response.json()

def get_sprints(auth_token, project_id):
    headers = {'Authorization': f'Bearer {auth_token}'}
    response = requests.get(f'{TAIGA_URL}/milestones?project={project_id}', headers=headers)
    response.raise_for_status()
    return response.json()

def get_current_sprint(sprints):
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
    headers = {'Authorization': f'Bearer {auth_token}'}
    params = {'project': project_id, 'milestone': milestone_id}
    response = requests.get(f'{TAIGA_URL}/tasks', headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def organize_tasks_by_status(tasks):
    tasks_by_status = {}
    for task in tasks:
        if task is None:
            continue
        status_info = task.get('status_extra_info')
        status = status_info.get('name', 'Unknown') if status_info else 'Unknown'
        if status not in tasks_by_status:
            tasks_by_status[status] = []
        tasks_by_status[status].append(task)
    return tasks_by_status

def create_sprint_standup_embed(project, sprint, sprint_tasks, sprint_tasks_by_status):
    project_url = project.get('url', f"https://tree.taiga.io/project/{PROJECT_SLUG}")
    sprint_total = len([t for t in sprint_tasks if t is not None])
    sprint_done = len(sprint_tasks_by_status.get('Done', []))
    sprint_name = sprint['name'] if sprint else 'No Active Sprint'
    description = f"**{datetime.now().strftime('%A, %B %d, %Y')}** • [Open Project]({project_url})\n\n"
    description += (
        "Hey team, this is your daily reminder to head to the most recent "
        "[Sprints page](https://discord.com/channels/1401686577629106246/1407869050050314311) "
        "and check in with the team."
    )
    fields = []

    if sprint and sprint_total > 0:
        sprint_completion = (sprint_done / sprint_total * 100) if sprint_total > 0 else 0
        fields.append({
            "name": f"🏃 {sprint_name} - {sprint_done}/{sprint_total} tasks complete ({sprint_completion:.0f}%)",
            "value": f"Active sprint with **{sprint_total}** tasks",
            "inline": False
        })

        for status_name, emoji in SPRINT_COLUMNS:
            tasks = sprint_tasks_by_status.get(status_name, [])
            count = len(tasks)
            column_lines = []
            for task in tasks[:3]:
                if task is None:
                    continue
                ref = task.get('ref', '')
                subject = task.get('subject', 'No title')[:25]
                assigned_info = task.get('assigned_to_extra_info')
                assigned = assigned_info.get('username', '?') if assigned_info else '?'
                us_ref = f" (US#{task['user_story_extra_info'].get('ref', '')})" if task.get('user_story_extra_info') else ""
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
        "thumbnail": {"url": "https://tree.taiga.io/images/logo-color.png"},
        "footer": {
            "text": "🏃 Sprint Tasks Board",
            "icon_url": "https://tree.taiga.io/images/logo-color.png"
        },
        "timestamp": datetime.now().isoformat()
    }

def generate_sprint_card(sprint_name, sprint_total, sprint_done, sprint_status_counts):
    width, height = 600, 400
    bg_color = (248, 250, 252)
    text_color = (33, 37, 41)
    accent_color = (88, 101, 242)
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype("arial.ttf", 32)
        small_font = ImageFont.truetype("arial.ttf", 18)
    except:
        title_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    draw.text((20, 20), f"🏃 Sprint: {sprint_name}", font=title_font, fill=text_color)
    pct_done = int((sprint_done / sprint_total) * 100) if sprint_total else 0
    draw.text((20, 70), f"{sprint_done}/{sprint_total} tasks complete ({pct_done}%)", font=small_font, fill=accent_color)
    bar_x, bar_y = 20, 110
    bar_width, bar_height = 560, 30
    draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], fill=(220, 220, 220))
    draw.rectangle([bar_x, bar_y, bar_x + int(bar_width * (pct_done / 100)), bar_y + bar_height], fill=accent_color)
    y_start = 170
    spacing = 180
    for idx, (status, emoji) in enumerate(SPRINT_COLUMNS):
        x = 20 + idx * spacing
        count = sprint_status_counts.get(status, 0)
        draw.text((x, y_start), f"{emoji} {status}", font=small_font, fill=text_color)
        draw.text((x, y_start + 25), f"{count} tasks", font=small_font, fill=accent_color)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

def send_image_to_discord(image_buffer, message="📊 Sprint Overview"):
    files = {'file': ('sprint_card.png', image_buffer, 'image/png')}
    data = {'content': message}
    response = requests.post(DISCORD_WEBHOOK, data=data, files=files)
    response.raise_for_status()

def generate_ascii_kanban(tasks_by_status):
    col_titles = ["NOT STARTED", "IN PROGRESS", "DONE"]
    col_width = 15
    max_rows = 5
    columns = []
    for status in col_titles:
        tasks = tasks_by_status.get(status.title(), [])[:max_rows]
        lines = [f"#{t.get('ref', '??')}" for t in tasks]
        lines += [""] * (max_rows - len(lines))
        columns.append(lines)
    board = "┌" + "┬".join(["─" * col_width] * 3) + "┐\n"
    board += "│" + "│".join([title.center(col_width) for title in col_titles]) + "│\n"
    board += "├" + "┼".join(["─" * col_width] * 3) + "┤\n"
    for i in range(max_rows):
        row = [columns[j][i].ljust(col_width) for j in range(3)]
        board += "│" + "│".join(row) + "│\n"
    board += "└" + "┴".join(["─" * col_width] * 3) + "┘"
    return f"```{board}```"

def send_ascii_kanban_to_discord(ascii_kanban):
    response = requests.post(DISCORD_WEBHOOK, json={'content': ascii_kanban})
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
        sprint_tasks_by_status = organize_tasks_by_status(sprint_tasks)

        print("🎨 Building and sending embed...")
        sprint_embed = create_sprint_standup_embed(
            project, current_sprint, sprint_tasks, sprint_tasks_by_status
        )
        send_to_discord([sprint_embed])

        print("🖼️ Generating and sending image card...")
        sprint_card_img = generate_sprint_card(
            current_sprint['name'],
            len(sprint_tasks),
            len(sprint_tasks_by_status.get('Done', [])),
            {k: len(v) for k, v in sprint_tasks_by_status.items()}
        )
        send_image_to_discord(sprint_card_img)

        print("🧱 Generating and sending ASCII kanban...")
        ascii_kanban = generate_ascii_kanban(sprint_tasks_by_status)
        send_ascii_kanban_to_discord(ascii_kanban)

        print("✅ Standup and visuals sent successfully!")

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

def send_to_discord(embeds):
    response = requests.post(
        DISCORD_WEBHOOK,
        json={
            'content': '@everyone',
            'embeds': embeds
        }
    )
    response.raise_for_status()

if __name__ == "__main__":
    main()
