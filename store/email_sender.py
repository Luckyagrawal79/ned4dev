import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
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


def _md_table_to_html(md_text):
    """Convert markdown tables in text to styled HTML tables."""
    lines = md_text.split("\n")
    result = []
    table_rows = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        if "|" in stripped and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            # Skip separator rows like |---|---|
            if all(re.match(r'^[-:]+$', c) for c in cells):
                continue
            table_rows.append(cells)
            in_table = True
        else:
            if in_table and table_rows:
                result.append(_build_html_table(table_rows))
                table_rows = []
                in_table = False
            result.append(stripped)

    if table_rows:
        result.append(_build_html_table(table_rows))

    return "<br>".join(result)


def _build_html_table(rows):
    """Build a styled HTML table from rows."""
    if not rows:
        return ""
    html = '<table style="border-collapse:collapse; margin:10px 0; font-family:Arial;">'
    for i, row in enumerate(rows):
        if i == 0:
            html += '<tr style="background:#00A2D1; color:white;">'
            for cell in row:
                html += f'<th style="padding:8px 12px; border:1px solid #ddd; text-align:left;">{cell}</th>'
        else:
            bg = "#f9f9f9" if i % 2 == 0 else "#ffffff"
            html += f'<tr style="background:{bg};">'
            for cell in row:
                html += f'<td style="padding:8px 12px; border:1px solid #ddd;">{cell}</td>'
        html += '</tr>'
    html += '</table>'
    return html


def _wrap_html(content):
    return f"""
    <html><body style="font-family: Arial, sans-serif; color: #2E3644;">
    <div style="padding: 20px;">
        <p>Hi All,</p>
        {content}
        <br><p>Thanks,<br><b>NED</b><br>
        <span style="font-size:12px; color:#888;">Neural Executive Dashboard — OneTru Identity & Data Services</span></p>
    </div>
    </body></html>
    """


def send_email(to: list[str], subject: str, body_html: str, important: bool = False, image_bytes: bytes = None) -> str:
    try:
        username, password = _get_smtp_credentials()

        msg = MIMEMultipart("related")
        msg["Subject"] = subject
        msg["From"] = MAIL_FROM
        msg["To"] = ", ".join(to)
        if important:
            msg["X-Priority"] = "1"
            msg["Importance"] = "High"

        html_part = MIMEMultipart("alternative")
        html_part.attach(MIMEText(body_html, "html"))
        msg.attach(html_part)

        if image_bytes:
            img = MIMEImage(image_bytes, _subtype="png")
            img.add_header("Content-ID", "<chart_image>")
            img.add_header("Content-Disposition", "inline", filename="chart.png")
            msg.attach(img)

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(username, password)
            server.send_message(msg)

        return "sent"
    except Exception as e:
        return f"Error: {str(e)}"


def send_ned_report(to: list[str], content: str, subject: str = None, important: bool = False, chart_fig=None) -> str:
    """Send a formatted NED email."""
    if subject is None:
        subject = f"NED Report — {datetime.utcnow().strftime('%Y-%m-%d')}"

    html_content = _md_table_to_html(content)
    # Clean remaining markdown
    html_content = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html_content)

    image_bytes = None
    if chart_fig:
        try:
            image_bytes = chart_fig.to_image(format="png", width=900, height=500)
            html_content += '<br><img src="cid:chart_image" style="max-width:100%;">'
        except Exception as e:
            html_content += f"<br><p>(Chart could not be attached: {str(e)})</p>"

    full_html = _wrap_html(html_content)
    return send_email(to, subject, full_html, important, image_bytes)