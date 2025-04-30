import requests
import os

VAPI_API_KEY = os.getenv("VAPI_API_KEY")

headers = {
    "Authorization": f"Bearer {VAPI_API_KEY}",
    "Content-Type": "application/json"
}

data = {
    "phone_number": "+1xxxxxxxxxx",  # 👈 customer's number
    "voice": "nova",  # or try 'paige', 'dave', etc.
    "assistant": {
        "prompt": """
You are an AI voice assistant for Gen Z Burger. Take orders for burgers, sides, drinks. Be friendly, brief, and casual.
When the order is complete, confirm it.
""",
        "model": "gpt-4",
        "temperature": 0.7,
        "transient": True
    },
    "actions": {
        "conversation_end_webhook": "https://yourdomain.com/vapi/order"
    }
}

response = requests.post("https://api.vapi.ai/v1/calls", headers=headers, json=data)
print(response.status_code)
print(response.json())
