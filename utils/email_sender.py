import smtplib
from email.mime.text import MIMEText


def send_email(
    recipient,
    subject,
    body,
    sender_email,
    sender_password,
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 465,
):
    """
    Send a plain-text email via SMTP.

    Defaults target Gmail's SMTP (Workspace or consumer). For other providers,
    pass the appropriate `smtp_server` and `smtp_port`.
    - Port 465: implicit SSL (SMTP_SSL)
    - Port 587: STARTTLS
    - Other ports: plain SMTP (if provider allows)
    """

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [recipient], msg.as_string())
    else:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            if smtp_port == 587:
                server.starttls()
                server.ehlo()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [recipient], msg.as_string())
