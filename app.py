import os
import logging
import random
import string
from flask import Flask, render_template, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "a secret key"

# Initialize Slack client
slack_token = os.environ.get("SLACK_BOT_TOKEN")
if not slack_token:
    logger.warning("SLACK_BOT_TOKEN is not set in the environment variables.")
else:
    logger.info("SLACK_BOT_TOKEN is set.")

slack_client = WebClient(token=slack_token)

@app.route('/')
def index():
    return render_template('index.html')

def generate_channel_name():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

@app.route('/submit', methods=['POST'])
def submit():
    name = request.form.get('name')
    email = request.form.get('email')

    if not name or not email:
        return jsonify({"success": False, "message": "Name and email are required"}), 400

    if not slack_token:
        logger.error("Slack configuration is incomplete. Please check SLACK_BOT_TOKEN.")
        return jsonify({"success": False, "message": "Slack configuration is incomplete. Please contact the administrator."}), 500

    try:
        logger.info(f"Attempting to invite user: {email}")

        # Step 1: Invite user to Slack workspace
        invite_response = slack_client.admin_users_invite(
            email=email,
            team_id='T07RAUVR1ST',
            channel_ids=[],  # We'll add the user to a new channel later
            custom_message=f"Welcome {name}! You've been invited to join our Slack workspace.",
            real_name=name
        )
        
        if not invite_response["ok"]:
            raise SlackApiError(response=invite_response, message=f"Failed to invite user: {invite_response.get('error', 'Unknown error')}")

        # Step 2: Create a new channel with a random name
        channel_name = generate_channel_name()
        create_channel_response = slack_client.conversations_create(
            name=channel_name,
            is_private=False
        )
        
        if not create_channel_response["ok"]:
            raise SlackApiError(response=create_channel_response, message=f"Failed to create channel: {create_channel_response.get('error', 'Unknown error')}")

        new_channel_id = create_channel_response["channel"]["id"]

        # Step 3: Add the user to the newly created channel
        invite_to_channel_response = slack_client.conversations_invite(
            channel=new_channel_id,
            users=[invite_response["user"]["id"]]
        )
        
        if not invite_to_channel_response["ok"]:
            raise SlackApiError(response=invite_to_channel_response, message=f"Failed to add user to channel: {invite_to_channel_response.get('error', 'Unknown error')}")

        # Send a welcome message to the new channel
        slack_client.chat_postMessage(
            channel=new_channel_id,
            text=f"Welcome {name} ({email}) to the channel!"
        )

        logger.info(f"Successfully invited user: {email} to workspace and channel: {channel_name}")
        return jsonify({"success": True, "message": f"You have been invited to the Slack workspace and added to channel #{channel_name}!"}), 200

    except SlackApiError as e:
        error_message = str(e)
        logger.error(f"Slack API Error: {error_message}")
        if "already_invited" in error_message:
            return jsonify({"success": False, "message": "You have already been invited to this Slack workspace."}), 400
        elif "already_in_team" in error_message:
            return jsonify({"success": False, "message": "You are already a member of this Slack workspace."}), 400
        elif "invalid_auth" in error_message:
            return jsonify({"success": False, "message": "Authentication failed. Please contact the administrator to check the Slack Bot Token."}), 500
        elif "missing_scope" in error_message:
            return jsonify({"success": False, "message": "The bot doesn't have the necessary permissions. Please contact the administrator to check the bot's scope."}), 500
        else:
            return jsonify({"success": False, "message": "An error occurred while processing your request. Please try again later or contact the administrator."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
