"""
Email sender for NED — reads SMTP credentials from Redis.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import redis

REDIS_HOST = "10.117.65.11"
REDIS_PORT = 6379
SMTP_HOST = "smtp-us.ser.proofpoint.com"
SMTP_PORT = 465
MAIL_FROM = "noreply-onetruidentity@transunionapps.com"


def _get_smtp_credentials():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    username = r.hget("SMTP_CREDENTIALS", "SMTP_USERNAME")
    password = r.hget("SMTP_CREDENTIALS", "SMTP_PASSWORD")
    if not username or not password:
        raise RuntimeError("SMTP credentials not found in Redis under SMTP_CREDENTIALS")
    return username, password


def send_email(to: list[str], subject: str, body_html: str) -> str:
    """
    Send an HTML email.

    Args:
        to: list of email addresses
        subject: email subject
        body_html: HTML body content

    Returns:
        "sent" on success, error message on failure
    """
    try:
        username, password = _get_smtp_credentials()

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = MAIL_FROM
        msg["To"] = ", ".join(to)
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(username, password)
            server.send_message(msg)

        return "sent"
    except Exception as e:
        return f"Error: {str(e)}"