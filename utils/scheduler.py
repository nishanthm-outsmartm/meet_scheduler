import datetime
import json
import os
import socket

import dateparser

from utils.email_sender import send_email
from utils.contact_map import resolve_emails_from_names

# Load config
with open("config.json") as f:
    config = json.load(f)

SENDER_EMAIL = config["sender_email"]
SENDER_PASSWORD = config["sender_password"]
SMTP_SERVER = config.get("smtp_server", "smtp.gmail.com")
SMTP_PORT = int(config.get("smtp_port", 465))
LOG_FILE = "logs/meeting_logs.json"
FLASK_PORT = int(config.get("flask_port", 5001))
RSVP_BASE_URL = config.get("rsvp_base_url")


def _get_local_ip():
    """Return the LAN IP so links work for devices on same network."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _build_base_url():
    if RSVP_BASE_URL:
        return RSVP_BASE_URL.rstrip("/")
    return f"http://{_get_local_ip()}:{FLASK_PORT}"

def schedule_meetings(recipients, date, time, days):
    logs = []

    # Accept either direct emails or contact names
    emails = []
    unresolved = []
    for item in recipients:
        target = item.strip()
        if not target:
            continue
        if "@" in target:
            emails.append(target)
        else:
            resolved = resolve_emails_from_names([target])
            if resolved:
                emails.extend(resolved)
            else:
                unresolved.append(target)

    if not emails:
        print("No valid recipients. Provide email addresses or known contact names.")
        return

    if unresolved:
        print(f"Warning: no email mapping for {', '.join(unresolved)}")

    # Parse the date (supports relative like 'tomorrow', 'next Monday')
    parsed_date = dateparser.parse(date)
    if not parsed_date:
        print("❌ Error parsing date:", date)
        return

    failures = []

    base_url = _build_base_url()

    for i in range(days):
        scheduled_date = (
            parsed_date + datetime.timedelta(days=i)
        ).strftime("%Y-%m-%d")

        for email in emails:
            accept_link = f"{base_url}/rsvp/accept/{email}"
            decline_link = f"{base_url}/rsvp/decline/{email}"

            message = f"""\
Hi {email},

You're invited to a meeting on {scheduled_date} at {time}.

Please RSVP below:
✅ Accept: {accept_link}
❌ Decline: {decline_link}

Best,
AI Scheduler Bot
"""

            try:
                send_email(
                    email,
                    "Meeting Invite with RSVP",
                    message,
                    SENDER_EMAIL,
                    SENDER_PASSWORD,
                    SMTP_SERVER,
                    SMTP_PORT,
                )
            except Exception as e:
                failures.append({"email": email, "error": str(e)})
                print(f"Failed to send email to {email}: {e}")

        logs.append({
            "emails": emails,
            "date": scheduled_date,
            "time": time,
            "rsvp": {email: None for email in emails}
        })

    # Save logs
    os.makedirs("logs", exist_ok=True)
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r+") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []
            existing.extend(logs)
            f.seek(0)
            json.dump(existing, f, indent=4)
            f.truncate()
    else:
        with open(LOG_FILE, "w") as f:
            json.dump(logs, f, indent=4)

    # If any failures, raise to surface in UI
    if failures:
        details = ", ".join([f"{f['email']} ({f['error']})" for f in failures])
        raise RuntimeError(f"Failed to send to: {details}")


def update_rsvp_status(email, response, reason=None):
    """ Update RSVP status in logs; store reason for declines. """
    if not os.path.exists(LOG_FILE):
        print("No meeting logs found to update.")
        return

    with open(LOG_FILE, "r") as f:
        try:
            meeting_logs = json.load(f)
        except json.JSONDecodeError:
            print("❌ Could not parse meeting log file.")
            return

    for log in meeting_logs:
        if email in log.get("emails", []):
            if response == "accept":
                log["rsvp"][email] = "Accepted"
            elif response == "decline":
                log["rsvp"][email] = {"status": "Declined", "reason": reason}

    with open(LOG_FILE, "w") as f:
        json.dump(meeting_logs, f, indent=4)
