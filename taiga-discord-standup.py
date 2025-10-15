import os
import requests
from datetime import datetime, timedelta

# Configuration from environment variables
TAIGA_URL = os.environ.get('TAIGA_URL', 'https://api.taiga.io/api/v1')
TAIGA_USERNAME = os.environ['TAIGA_USERNAME']
TAIGA_PASSWORD = os.environ['TAIGA_PASSWORD']
PROJECT_SLUG = os.environ['PROJECT_SLUG']
DISCORD_WEBHOOK = os.environ['DISCORD_WEBHOOK']

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

def format_standup_message(project, user_stories):
    """Format the standup message for Discord"""
    
    # Filter out None values and group stories by status
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
    
    # Build the message
    message = f"**🌅 Daily Standup - {datetime.now().strftime('%A, %B %d, %Y')}**\n\n"
    message += f"**Project:** {project['name']}\n\n"
    
    for status, stories in stories_by_status.items():
        if stories:
            message += f"**{status}** ({len(stories)})\n"
            for story in stories[:5]:  # Limit to 5 per status to avoid huge messages
                if story is None:
                    continue
                    
                subject = story.get('subject', 'No title')
                assigned_info = story.get('assigned_to_extra_info')
                
                if assigned_info and isinstance(assigned_info, dict):
                    assigned = assigned_info.get('full_name_display', 'Unassigned')
                else:
                    assigned = 'Unassigned'
                    
                message += f"  • {subject} - *{assigned}*\n"
            if len(stories) > 5:
                message += f"  • ... and {len(stories) - 5} more\n"
            message += "\n"
    
    # Add project link
    project_url = project.get('url', f"https://tree.taiga.io/project/{PROJECT_SLUG}")
    message += f"\n🔗 [View Project]({project_url})"
    
    return message

def send_to_discord(message):
    """Send message to Discord via webhook"""
    response = requests.post(
        DISCORD_WEBHOOK,
        json={'content': message}
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
        
        print("✍️ Formatting standup message...")
        message = format_standup_message(project, user_stories)
        
        print("📨 Sending to Discord...")
        send_to_discord(message)
        
        print("✅ Standup sent successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        # Send error to Discord so you know if something breaks
        try:
            send_to_discord(f"⚠️ Standup automation failed: {str(e)}")
        except:
            pass
        raise

if __name__ == "__main__":
    main()