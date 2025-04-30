from fastapi import FastAPI, Form
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import json
import os
import datetime

# Load environment variables
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
app = FastAPI()

ORDERS_FILE = "orders.json"

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

@app.post("/sms", response_class=PlainTextResponse)
async def sms_reply(Body: str = Form(...), From: str = Form(...)):
    print(f"Incoming from {From}: {Body}")

    # Map known restaurant numbers to IDs
    restaurant_map = {
        "+1978775898": "genzburger"  # 🔁 Replace with Gen Z Burger's Twilio number
    }

    # Default to genzburger for now
    restaurant_id = restaurant_map.get(From, "genzburger")
    menu_path = f"static/menus/{restaurant_id}.json"

    try:
        with open(menu_path, "r") as f:
            menu = json.load(f)
    except Exception as e:
        print("Failed to load menu:", e)
        return PlainTextResponse("Sorry, the menu is currently unavailable.", status_code=500)

    prompt = f"""
You are the AI ordering assistant for Gen Z Burger in Langley, BC.

Here is the menu:

{json.dumps(menu, indent=2)}

When a customer sends a message, understand their order and confirm what they want in a friendly, helpful tone.

Customer: {Body}
AI:"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )

        reply = completion.choices[0].message.content.strip()
        save_order(From, Body, reply)
        send_order_email(From, Body, reply)
        
        twiml = MessagingResponse()
        twiml.message(reply)
        return str(twiml)

    except Exception as e:
        print("OpenAI error:", e)
        return PlainTextResponse("Oops, something went wrong. Please try again.", status_code=500)


@app.get("/orders", response_class=HTMLResponse)
async def view_orders():
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "r") as f:
            orders = json.load(f)
    else:
        orders = []

    # Build basic HTML
    html = """
    <html>
    <head>
        <title>Gen Z Burger Orders</title>
        <meta http-equiv="refresh" content="10"> <!-- Auto refresh every 10s -->
        <style>
            body { font-family: sans-serif; padding: 2rem; background: #fefefe; }
            h2 { margin-top: 2rem; }
            .order { background: #f1f1f1; padding: 1rem; margin-bottom: 1rem; border-radius: 8px; }
            .order p { margin: 0.3rem 0; }
        </style>
    </head>
    <body>
        <h1>📋 Gen Z Burger - Live Orders</h1>
    """

    for order in reversed(orders[-20:]):  # show latest 20
        html += f"""
        <div class="order">
            <p><strong>Time:</strong> {order["timestamp"]}</p>
            <p><strong>From:</strong> {order["from"]}</p>
            <p><strong>Message:</strong> {order["message"]}</p>
            <p><strong>AI Reply:</strong> {order["response"]}</p>
        </div>
        """

    html += "</body></html>"
    return HTMLResponse(content=html)

def send_order_email(from_number, message, reply):
    try:
        email_body = f"""
        <p><strong>New Order from:</strong> {from_number}</p>
        <p><strong>Message:</strong> {message}</p>
        <p><strong>AI Reply:</strong> {reply}</p>
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
        print("❌ Failed to send email:", e)
