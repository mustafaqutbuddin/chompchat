from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from utils import save_order, send_order_email
import json, os, datetime

load_dotenv()

app = FastAPI()

ORDERS_FILE = "orders.json"

@app.post("/sms", response_class=PlainTextResponse)
async def sms_reply(Body: str = Form(...), From: str = Form(...)):
    # If you're still supporting SMS flow
    save_order(From, Body, "Received via SMS")
    send_order_email(From, Body, "Received via SMS")
    return "Thanks for your order! We'll be in touch soon."

@app.get("/orders", response_class=HTMLResponse)
async def view_orders():
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "r") as f:
            orders = json.load(f)
    else:
        orders = []

    html = """
    <html>
    <head><title>Orders</title></head>
    <body><h1>Gen Z Burger - Orders</h1>
    """
    for order in reversed(orders[-20:]):
        html += f"""
        <div>
            <p><strong>Time:</strong> {order['timestamp']}</p>
            <p><strong>From:</strong> {order['from']}</p>
            <p><strong>Message:</strong> {order['message']}</p>
            <p><strong>AI Reply:</strong> {order['response']}</p>
        </div><hr>
        """
    html += "</body></html>"
    return HTMLResponse(content=html)

@app.post("/vapi/order")
async def vapi_webhook(request: Request):
    data = await request.json()
    caller = data.get("phone", {}).get("number", "unknown")
    messages = data.get("messages", [])
    latest_msg = messages[-1]["content"] if messages else ""

    save_order(caller, latest_msg, "Handled by Vapi Assistant")
    send_order_email(caller, latest_msg, "Handled by Vapi Assistant")

    # Don't respond with anything. Vapi takes care of replies.
    return {"status": "ok"}
