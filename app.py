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
        logger.info(f"Attempting to create a channel for user: {email}")

        # Create a new channel with a random name
        channel_name = generate_channel_name()
        create_channel_response = slack_client.conversations_create(
            name=channel_name,
            is_private=False
        )
        
        if not create_channel_response["ok"]:
            raise SlackApiError(response=create_channel_response, message=f"Failed to create channel: {create_channel_response.get('error', 'Unknown error')}")

        new_channel_id = create_channel_response["channel"]["id"]

        # Send a welcome message to the new channel
        slack_client.chat_postMessage(
            channel=new_channel_id,
            text=f"Welcome {name} ({email})! An administrator will add you to this channel soon."
        )

        logger.info(f"Successfully created channel: {channel_name} for user: {email}")
        return jsonify({
            "success": True, 
            "message": f"A Slack channel has been created for you. An administrator will invite you to the workspace and add you to the channel soon. Please check your email for an invitation."
        }), 200

    except SlackApiError as e:
        error_message = str(e)
        logger.error(f"Slack API Error: {error_message}")
        return jsonify({
            "success": False, 
            "message": "An error occurred while processing your request. An administrator has been notified and will add you to the Slack workspace manually. Please check your email for an invitation soon."
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
