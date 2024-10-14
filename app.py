import os
from flask import Flask, render_template, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "a secret key"

# Initialize Slack client
slack_token = os.environ.get("SLACK_BOT_TOKEN")
slack_client = WebClient(token=slack_token)
slack_channel_id = os.environ.get("SLACK_CHANNEL_ID")

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

        return jsonify({"success": True, "message": "You have been added to the Slack channel successfully!"}), 200
    except SlackApiError as e:
        # You'll want to handle different error cases here
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
