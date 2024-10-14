
import os
import logging
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
slack_channel_id = os.environ.get("SLACK_CHANNEL_ID")
if not slack_channel_id:
    logger.warning("SLACK_CHANNEL_ID is not set in the environment variables.")
else:
    logger.info("SLACK_CHANNEL_ID is set.")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    name = request.form.get('name')
    email = request.form.get('email')

    if not name or not email:
        return jsonify({"success": False, "message": "Name and email are required"}), 400

    try:
        logger.info(f"Attempting to invite user: {email}")
        
        # Invite user to Slack channel
        response = slack_client.conversations_invite(
            channel=slack_channel_id,
            users=[email]
        )
        
        # If successful, send a message to the channel
        slack_client.chat_postMessage(
            channel=slack_channel_id,
            text=f"Welcome {name} ({email}) to the channel!"
        )

        logger.info(f"Successfully invited user: {email}")
        return jsonify({"success": True, "message": "You have been added to the Slack channel successfully!"}), 200
    except SlackApiError as e:
        error_message = str(e)
        logger.error(f"Slack API Error: {error_message}")
        if "already_in_channel" in error_message:
            return jsonify({"success": False, "message": "You are already a member of this Slack channel."}), 400
        elif "not_in_channel" in error_message:
            return jsonify({"success": False, "message": "The bot is not in the specified channel. Please add the bot to the channel and try again."}), 500
        elif "invalid_auth" in error_message:
            return jsonify({"success": False, "message": "Authentication failed. Please check the Slack Bot Token."}), 500
        elif "missing_scope" in error_message:
            return jsonify({"success": False, "message": "The bot doesn't have the necessary permissions. Please check the bot's scope and try again."}), 500
        else:
            return jsonify({"success": False, "message": f"An error occurred: {error_message}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
