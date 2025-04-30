from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json, os
from difflib import get_close_matches

router = APIRouter()
session_store = {}

def load_menu():
    path = "static/menus/genzburger.json"
    with open(path, "r") as f:
        data = json.load(f)

    flat_items = []
    for category, items in data.items():
        flat_items.extend(items)
    return flat_items

MENU_ITEMS = load_menu()

@router.post("/vapi/order")
async def vapi_order_handler(request: Request):
    data = await request.json()
    caller = data.get("phone", {}).get("number", "unknown")
    messages = data.get("messages", [])
    user_input = messages[-1]["content"] if messages else ""

    session = session_store.get(caller, {"items": []})
    order = session["items"]

    done_words = ["that's all", "done", "no thanks", "nothing else", "i'm good", "that's it"]

    if any(phrase in user_input.lower() for phrase in done_words):
        if not order:
            return JSONResponse(content={"reply": "You haven’t ordered anything yet. Want to try?"})

        summary = ", ".join(order)
        reply = f"Perfect! Your order is: {summary}. It'll be ready soon. Thanks for calling Gen Z Burger!"
        session_store.pop(caller, None)
        return JSONResponse(content={"reply": reply})

    # Try fuzzy match
    matches = get_close_matches(user_input.lower(), [item.lower() for item in MENU_ITEMS], n=1, cutoff=0.6)
    if matches:
        matched = next(item for item in MENU_ITEMS if item.lower() == matches[0])
        order.append(matched)
        session["items"] = order
        session_store[caller] = session
        return JSONResponse(content={"reply": f"Got it — {matched}. Anything else you'd like?"})

    # First interaction → provide the assistant config dynamically
    if not messages:
        return JSONResponse(content={
            "assistant": {
                "model": "gpt-4o",
                "provider": "openai",
                "temperature": 0.6,
                "systemPrompt": """
You are a helpful and friendly voice ordering assistant for Gen Z Burger.
Greet customers casually and help them place their food orders.
You know the menu well. Only offer menu items. Summarize when they're done.
Speak like a real human — natural, fun, and concise.
""",
            },
            "firstMessage": "Hey! Welcome to Gen Z Burger 🍔. What can I get started for you today?"
        })

    return JSONResponse(content={"reply": "Hmm, I didn’t quite catch that. Can you repeat it?"})
