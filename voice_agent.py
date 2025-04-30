from fastapi import APIRouter, Form
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI
from utils import save_order, send_order_email
from difflib import get_close_matches
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
router = APIRouter()

# In-memory session tracking per caller
voice_session_store = {}

# Fuzzy matching for misheard items
def fuzzy_match_menu_item(text):
    menu_items = [
        "Zingster", "Cruncho", "Thicc Beef", "Mango Shake",
        "Fries", "Poutine", "Chicken Tikka Rice", "Peri Peri Rice Platter",
        "Chocolate Shake", "Strawberry Shake", "Vanilla Shake", "Onion Rings"
    ]
    match = get_close_matches(text.lower(), [item.lower() for item in menu_items], n=1, cutoff=0.6)
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
        hints="Zingster, Cruncho, Thicc Beef, Mango Shake, Fries, Chicken Tikka Rice, Poutine"
    )
    gather.say("Hey! Welcome to Gen Z Burger. What can I get started for you today?", voice="Polly.Joanna", language="en-US")
    response.append(gather)
    response.say("Oops, I didn’t catch that. Let’s try again later.", voice="Polly.Joanna", language="en-US")
    return Response(content=str(response), media_type="application/xml")

@router.post("/process_voice")
async def process_voice(SpeechResult: str = Form(...), From: str = Form(...)):
    print(f"📞 From {From} said:", SpeechResult)

    # Retrieve session or create new
    session = voice_session_store.get(From, {"items": [], "stage": "ordering"})

    # If user confirms
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

    # Fuzzy match and update order
    cleaned_input = fuzzy_match_menu_item(SpeechResult)
    session["items"].append(cleaned_input)

    prompt = f"""
You are a chill, friendly cashier at Gen Z Burger.
Speak like a human, short and casual.

Customer said: "{SpeechResult}"
Matched item: "{cleaned_input}"
Current order: {session['items']}

If it sounds like they're done, summarize and say: 'Is that correct?'
If not, respond like you're still taking their order.
Keep replies to 1–2 casual, friendly lines. Avoid sounding robotic.
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
        gather.say("You can say yes to confirm, or tell me what else you'd like.", voice="Polly.Joanna", language="en-US")
        response.append(gather)
        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        print("❌ GPT error:", e)
        fallback = VoiceResponse()
        fallback.say("Hmm, I’m having trouble right now. Can you call back in a few?", voice="Polly.Joanna", language="en-US")
        return Response(content=str(fallback), media_type="application/xml")
