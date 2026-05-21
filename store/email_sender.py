import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import redis
from datetime import datetime

REDIS_HOST = "10.117.65.11"
REDIS_PORT = 6379
SMTP_HOST = "smtp-us.ser.proofpoint.com"
SMTP_PORT = 465
MAIL_FROM = "noreply-onetruidentity@transunionapps.com"

TEAM_EMAILS = [
    "Aman.Kaushik@transunion.com",
    "Puja.Kumari@transunion.com",
    "Ramyashree.S@transunion.com",
    "Ankit.Mittal@transunion.com",
    "Lucky.Agrawal@transunion.com",
    "Sandeep.Mishra2@transunion.com",
]


def _get_smtp_credentials():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    username = r.hget("SMTP_CREDENTIALS", "SMTP_USERNAME")
    password = r.hget("SMTP_CREDENTIALS", "SMTP_PASSWORD")
    if not username or not password:
        raise RuntimeError("SMTP credentials not found in Redis")
    return username, password


def _wrap_html(content, subject="NED Report"):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return f"""
    <html><body style="font-family: Arial, sans-serif; color: #2E3644;">
    <div style="background: #00A2D1; padding: 15px 20px; color: white;">
        <h2 style="margin:0;">{subject}</h2>
        <p style="margin:4px 0 0 0; font-size:13px;">{today}</p>
    </div>
    <div style="padding: 20px;">
        <p>Hi All,</p>
        {content}
        <br><p>Thanks,<br><b>NED</b><br>
        <span style="font-size:12px; color:#888;">Neural Executive Dashboard — OneTru Identity & Data Services</span></p>
    </div>
    </body></html>
    """


def send_email(to: list[str], subject: str, body_html: str, important: bool = False) -> str:
    try:
        username, password = _get_smtp_credentials()

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = MAIL_FROM
        msg["To"] = ", ".join(to)
        if important:
            msg["X-Priority"] = "1"
            msg["Importance"] = "High"
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(username, password)
            server.send_message(msg)

        return "sent"
    except Exception as e:
        return f"Error: {str(e)}"


def send_ned_report(to: list[str], content: str, subject: str = "NED Report", important: bool = False) -> str:
    """Send a formatted NED email with content wrapped in template."""
    # Convert markdown-ish content to basic HTML
    html_content = content.replace("\n", "<br>")
    html_content = html_content.replace("**", "")  # strip bold markers
    full_html = _wrap_html(html_content, subject)
    return send_email(to, subject, full_html, important)