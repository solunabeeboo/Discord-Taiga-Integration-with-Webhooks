ADD These files to any repository, preferably the one your working projecting is being developed in, or not!

These uses a simple python script to pull a Sprint page from the Scrum board in Taiga.io. It will create a nifty little sprint 
image as well as a standup message with an @everyone, feel free to edit the contents of either with the python file!

TO SETUP:
1. Go to your Discord Server > Server Settings > Integrations > Webhooks > Create a Webhook Bot for the channel, copy and save it's URL!
2. In your GitHub Repo, go to Settings > Scroll Down and Click Secrets and Variables > Actions
3. Create these EXACT Secrets in the project (or create your own and edit the Python file to accomadate)
   a. DISCORD_WEBHOOK
   b. PROJECT_SLUG
   c. TAIGA_PASSWORD
   d. TAIGA_USERNAME
4. Then, fill out the variables with the related content:
   a. DISCORD_WEBHOOK should contain the URL gotten from the bot!
   b. PROJECT_SLUG is the identifier Taiga.io gives your project. Go to your projects page and go to the URL at the top. Find the content between project/.../[otherthing]. thats the Slug!
   c. TAIGA_PASSWORD is the literal passwword from the taiga platform that your Action will login with. This can be a personal account or one created explicitly for the action.
   d. TAIGA_USERNAME is the same as above but the username.
5. EDIT The time the bot triggers! This is done in .github/Workflows/standup.yml
   a. Find the schedule: ... -cron: '# # # # #' to edit. Go to cronguru to find out what to put here, its a UTC based schedule.

6. Have fun!


<img width="400" height="478" alt="image" align="center" src="https://github.com/user-attachments/assets/88bcc73a-bba7-4a9b-99f9-b5f318d4fe80" />
