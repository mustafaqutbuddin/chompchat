import os
import datetime
import json
from openai import OpenAI
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

ORDERS_FILE = "orders.json"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def save_order(from_number: str, message: str, ai_reply: str):
    order_data = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "from": from_number,
        "message": message,
        "response": ai_reply
    }

    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "r") as f:
            orders = json.load(f)
    else:
        orders = []

    orders.append(order_data)

    with open(ORDERS_FILE, "w") as f:
        json.dump(orders, f, indent=2)


def send_order_email(from_number: str, message: str, ai_reply: str):
    try:
        email_body = f"""
        <p><strong>New Order from:</strong> {from_number}</p>
        <p><strong>Message:</strong> {message}</p>
        <p><strong>AI Reply:</strong> {ai_reply}</p>
        <p><em>Check your dashboard for full order list.</em></p>
        """
        email = Mail(
            from_email=os.getenv("ALERT_EMAIL_FROM"),
            to_emails=os.getenv("ALERT_EMAIL_TO"),
            subject="📥 New Order Received - Gen Z Burger",
            html_content=email_body
        )

        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        sg.send(email)
        print("✅ Order email sent")
    except Exception as e:
        print("❌ Email send failed:", e)
