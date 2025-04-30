from fastapi import APIRouter, Request, Header
from fastapi.responses import JSONResponse
from difflib import get_close_matches
import os
import json

router = APIRouter()
session_store = {}

# Map Twilio phone numbers to restaurant identifiers
RESTAURANT_MAP = {
    "+19787758988": "genzburger",       # Gen Z Burger Twilio number
    # Add more restaurant numbers here
    # "+12345678900": "pizzaheaven"
}

def load_menu_for_number(phone_number: str):
    path = f"static/{phone_number}.json"
    if not os.path.exists(path):
        raise FileNotFoundError(f"Menu file not found for number {phone_number}")
    
    with open(path, "r") as f:
        menu = json.load(f)

    flat_items = []
    for category, items in menu.items():
        flat_items.extend(items)
    return flat_items


@router.post("/vapi/order")
async def vapi_order_handler(request: Request, authorization: str = Header(None)):
    # Optional: validate webhook secret
    expected_token = os.getenv("VAPI_SECRET")
    if expected_token and authorization != f"Bearer {expected_token}":
        return JSONResponse(status_code=403, content={"error": "Unauthorized"})

    data = await request.json()
    caller = data.get("phone", {}).get("number", "unknown")
    to_number = data.get("phone", {}).get("toNumber", "unknown")
    messages = data.get("messages", [])
    user_input = messages[-1]["content"] if messages else ""

    print(f"📞 {caller} said: {user_input}")

    try:
        menu_items = load_menu_for_number(to_number)
    except Exception as e:
        print("❌ Menu load error:", e)
        return JSONResponse(content={"reply": "Sorry, there was a problem accessing the menu."})

    session = session_store.get(caller, {"items": []})
    order = session["items"]

    done_words = ["that's all", "done", "no thanks", "nothing else", "i'm good", "that's it"]

    if any(phrase in user_input.lower() for phrase in done_words):
        if not order:
            return JSONResponse(content={"reply": "You haven’t ordered anything yet. Want to try?"})

        summary = ", ".join(order)
        reply = f"Perfect! Your order is: {summary}. It'll be ready soon. Thanks for calling!"
        session_store.pop(caller, None)
        return JSONResponse(content={"reply": reply})

    # Try fuzzy match
    matches = get_close_matches(user_input.lower(), [item.lower() for item in menu_items], n=1, cutoff=0.6)
    if matches:
        matched = next(item for item in menu_items if item.lower() == matches[0])
        order.append(matched)
        session["items"] = order
        session_store[caller] = session
        return JSONResponse(content={"reply": f"Got it — {matched}. Anything else you'd like?"})
    else:
        return JSONResponse(content={"reply": "Hmm, I didn’t quite catch that. Can you repeat it?"})
