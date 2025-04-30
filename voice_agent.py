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

    # Done phrases — auto confirm and hang up
    done_words = ["yes", "yeah", "that's it", "that’s it", "that's all", "done", "i’m good", "nothing else", "thank you"]

    session = voice_session_store.get(From, {"items": [], "stage": "ordering"})

    # If user says something like "yes" or "that's it" at any time
    if any(phrase in SpeechResult.lower() for phrase in done_words):
        item_summary = ", ".join(session["items"])
        final_reply = f"Perfect! Your order for {item_summary} is confirmed. Thanks for calling Gen Z Burger!"

        save_order(From, item_summary, final_reply)
        send_order_email(From, item_summary, final_reply)
        voice_session_store.pop(From, None)

        response = VoiceResponse()
        response.say(final_reply, voice="Polly.Joanna", language="en-US")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

    # Fuzzy match the item
    cleaned_input = fuzzy_match_menu_item(SpeechResult)
    session["items"].append(cleaned_input)
    voice_session_store[From] = session

    # Simple and fast GPT prompt
    prompt = f"""
You're a casual Gen Z Burger assistant. Talk chill and helpful.

Customer said: "{SpeechResult}"
Current order: {session['items']}

Reply in 1 short sentence. Be natural.
"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            timeout=5
        )
        reply = completion.choices[0].message.content.strip()
        print("🤖 GPT reply:", reply)

        response = VoiceResponse()
        response.say(reply, voice="Polly.Joanna", language="en-US")
        gather = Gather(input='speech', action='/process_voice', method='POST', timeout=5)
        response.append(gather)
        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        print("❌ GPT error:", e)
        fallback = VoiceResponse()
        fallback.say("Sorry, something glitched. Try again soon.", voice="Polly.Joanna", language="en-US")
        return Response(content=str(fallback), media_type="application/xml")
