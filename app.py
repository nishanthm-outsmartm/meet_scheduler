from flask import Flask
import os
import json

from utils.email_sender import send_email

app = Flask(__name__)
LOG_FILE = "logs/meeting_logs.json"

with open("config.json") as f:
    CONFIG = json.load(f)

SENDER_EMAIL = CONFIG["sender_email"]
SENDER_PASSWORD = CONFIG["sender_password"]
SMTP_SERVER = CONFIG.get("smtp_server", "smtp.gmail.com")
SMTP_PORT = int(CONFIG.get("smtp_port", 465))
FLASK_HOST = CONFIG.get("flask_host", "0.0.0.0")
FLASK_PORT = int(CONFIG.get("flask_port", 5001))

def update_rsvp(email, response):
    if not os.path.exists(LOG_FILE):
        return

    with open(LOG_FILE, 'r+') as f:
        data = json.load(f)
        for meeting in data:
            if email in meeting.get("emails", []) and meeting.get("rsvp", {}).get(email) is None:
                if "rsvp" not in meeting:
                    meeting["rsvp"] = {}
                meeting["rsvp"][email] = response
                break
        f.seek(0)
        json.dump(data, f, indent=4)
        f.truncate()

@app.route('/rsvp/accept/<email>')
def rsvp_accept(email):
    update_rsvp(email, "Accepted")

    # Load the latest meeting link from logs
    if not os.path.exists(LOG_FILE):
        return f"RSVP recorded, but no meeting logs found."

    with open(LOG_FILE, "r") as f:
        logs = json.load(f)
        # Find the latest meeting this user is part of
        for meeting in reversed(logs):
            if email in meeting["emails"]:
                meeting_link = meeting.get("meet_link", "https://calendly.com/22cs101-kpriet/30min")
                break
        else:
            meeting_link = "https://calendly.com/22cs101-kpriet/30min"  # fallback

    # Send follow-up email with link
    subject = "Your Meeting Link"
    message = f"Hi,\n\nThanks for RSVPing YES! Here's your meeting link:\n{meeting_link}\n\nBest,\nAI Scheduler"

    send_email(email, subject, message, SENDER_EMAIL, SENDER_PASSWORD, SMTP_SERVER, SMTP_PORT)

    return f"✅ Thanks {email}, your RSVP was recorded and the meeting link has been sent to your inbox!"


@app.route('/rsvp/decline/<email>')
def rsvp_decline(email):
    update_rsvp(email, "Declined")
    return f"Thanks, {email}, your RSVP has been recorded as: ❌ Declined"

if __name__ == '__main__':
    app.run(debug=True, host=FLASK_HOST, port=FLASK_PORT)
