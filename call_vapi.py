from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from difflib import get_close_matches
from utils import save_order, send_order_email
import os, json

router = APIRouter()

# In-memory session store for orders per caller
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
    try:
        data = await request.json()
        caller = data.get("phone", {}).get("number", "unknown")
        messages = data.get("messages", [])
        user_input = messages[-1]["content"] if messages else ""

        print(f"📞 {caller} said: {user_input}")

        # Get or create session
        session = session_store.get(caller, {"items": []})
        order = session["items"]

        done_words = [
            "that's all", "done", "no thanks", "nothing else",
            "i'm good", "that's it", "yes", "yeah", "nope", "confirmed", "thank you"
        ]

        # Finish order
        if any(phrase in user_input.lower() for phrase in done_words):
            if not order:
                return JSONResponse(content={"reply": "You haven’t ordered anything yet. Want to try?"})

            summary = ", ".join(order)
            final_reply = f"Perfect! Your order is: {summary}. It'll be ready soon. Thanks for calling Gen Z Burger!"

            save_order(caller, summary, final_reply)
            send_order_email(caller, summary, final_reply)
            session_store.pop(caller, None)

            return JSONResponse(content={"reply": final_reply})

        # Fuzzy match against menu items
        matches = get_close_matches(user_input.lower(), [item.lower() for item in MENU_ITEMS], n=1, cutoff=0.6)

        if matches:
            matched = next(item for item in MENU_ITEMS if item.lower() == matches[0])
            order.append(matched)
            session["items"] = order
            session_store[caller] = session

            return JSONResponse(content={"reply": f"Got it — {matched}. Anything else you'd like?"})
        else:
            return JSONResponse(content={"reply": "Hmm, I didn’t quite catch that. Can you say it again?"})

    except Exception as e:
        print("❌ Error in /vapi/order:", e)
        return JSONResponse(status_code=500, content={"reply": "Oops! Something broke. Try again later."})
