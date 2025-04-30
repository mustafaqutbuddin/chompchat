from fastapi import APIRouter, Form
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI
from utils import save_order, send_order_email
from difflib import get_close_matches
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
router = APIRouter()

voice_session_store = {}

# Alias map to fix common mishearings
ALIAS_MAP = {
    "gangster": "Zingster",
    "ring store": "Zingster",
    "english ring store": "Zingster",
    "inkster": "Zingster",
    "zing star": "Zingster",
    "tony and duane": "Onion Rings",
    "chunky race": "Chunky Rice Delight",
    "chiken tikka": "Chicken Tikka Rice"
}

def fuzzy_match_menu_item(text):
    cleaned = text.lower()

    # Try manual alias fix first
    for alias, actual in ALIAS_MAP.items():
        if alias in cleaned:
            return actual

    menu_items = [
        "Zingster", "Cruncho", "Thicc Beef", "Mango Shake",
        "Fries", "Poutine", "Chicken Tikka Rice", "Peri Peri Rice Platter",
        "Onion Rings"
    ]
    match = get_close_matches(cleaned, [item.lower() for item in menu_items], n=1, cutoff=0.6)
    return match[0].title() if match else text

@router.api_route("/voice", methods=["GET", "POST"])
async def start_call():
    response = VoiceResponse()
    gather = Gather(
        input='speech',
        action='/process_voice',
        method='POST',
        timeout=5,
        speech_model='phone_call',
        hints="Zingster, Cruncho, Thicc Beef, Mango Shake, Fries, Chicken Tikka Rice, Poutine, Onion Rings"
    )
    gather.say("Hey! Welcome to Gen Z Burger. What can I get started for you today?", voice="Polly.Joanna", language="en-US")
    response.append(gather)
    response.say("Oops, I didn’t catch that. Let’s try again later.", voice="Polly.Joanna", language="en-US")
    return Response(content=str(response), media_type="application/xml")

@router.post("/process_voice")
async def process_voice(SpeechResult: str = Form(...), From: str = Form(...)):
    print(f"📞 From {From} said:", SpeechResult)

    session = voice_session_store.get(From, {"items": [], "stage": "ordering"})

    # Final confirmation
    if session["stage"] == "confirming" and "yes" in SpeechResult.lower():
        item_summary = ", ".join(session["items"])
        final_reply = f"Awesome! Your order for {item_summary} is confirmed. Catch you later!"

        save_order(From, item_summary, final_reply)
        send_order_email(From, item_summary, final_reply)
        voice_session_store.pop(From, None)

        response = VoiceResponse()
        response.say(final_reply, voice="Polly.Joanna", language="en-US")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

    # Match misheard items
    cleaned_input = fuzzy_match_menu_item(SpeechResult)
    session["items"].append(cleaned_input)

    # Smart confirmation detection
    done_words = ["that's it", "done", "no, that’s all", "that’s all", "i’m good", "nothing else"]
    if any(done_word in SpeechResult.lower() for done_word in done_words) or len(session["items"]) >= 2:
        ask_confirmation = True
    else:
        ask_confirmation = False

    prompt = f"""
You are a friendly Gen Z Burger order assistant. Talk like a real, casual person.

Customer just said: "{SpeechResult}"
Matched item: "{cleaned_input}"
Order so far: {session['items']}

{"Summarize the order and ask 'Is that correct?'" if ask_confirmation else "Acknowledge the item and ask if they want anything else."}
Limit response to 1–2 casual, friendly lines.
"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            timeout=5
        )
        reply = completion.choices[0].message.content.strip()
        print("🤖 GPT reply:", reply)

        if "is that correct" in reply.lower():
            session["stage"] = "confirming"

        voice_session_store[From] = session

        response = VoiceResponse()
        response.say(reply, voice="Polly.Joanna", language="en-US")
        response.pause(length=1)
        gather = Gather(input='speech', action='/process_voice', method='POST', timeout=5)
        gather.say("You can say yes to confirm, or add more items.", voice="Polly.Joanna", language="en-US")
        response.append(gather)
        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        print("❌ GPT error:", e)
        fallback = VoiceResponse()
        fallback.say("Sorry, something glitched. Try again in a bit.", voice="Polly.Joanna", language="en-US")
        return Response(content=str(fallback), media_type="application/xml")
