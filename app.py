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

@app.route('/')
def index():
    return render_template('index.html')

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

        # Invite user to Slack workspace
        invite_response = slack_client.admin_users_invite(
            email=email,
            team_id='T07RAUVR1ST',
            channel_ids=[],
            custom_message=f"Welcome {name}! You've been invited to join our Slack workspace.",
            real_name=name
        )

        if not invite_response["ok"]:
            raise SlackApiError(response=invite_response, message=f"Failed to invite user: {invite_response.get('error', 'Unknown error')}")

        logger.info(f"Successfully invited user: {email} to the Slack workspace")
        return jsonify({
            "success": True, 
            "message": f"You have been invited to the Slack workspace. Please check your email for an invitation."
        }), 200

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
