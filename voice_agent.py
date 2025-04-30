from fastapi import APIRouter, Form
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI
from main import save_order, send_order_email  # reuse SMS functions
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

router = APIRouter()

# Very basic in-memory session tracker
voice_session_store = {}

@router.post("/voice")
async def start_call():
    response = VoiceResponse()
    gather = Gather(input='speech', action='/process_voice', method='POST', timeout=5)
    gather.say("Welcome to Gen Z Burger. Please tell me your order after the beep.")
    response.append(gather)
    response.say("Sorry, I didn't hear anything. Please try again later.")
    return Response(content=str(response), media_type="application/xml")


@router.post("/process_voice")
async def process_voice(SpeechResult: str = Form(...), From: str = Form(...)):
    print(f"📞 From {From} said:", SpeechResult)

    # Get or create session
    session = voice_session_store.get(From, {"items": [], "stage": "ordering"})

    # If user confirms, finalize order
    if session["stage"] == "confirming" and "yes" in SpeechResult.lower():
        item_summary = ", ".join(session["items"])
        final_reply = f"Thank you! Your order for {item_summary} is confirmed. Goodbye!"

        save_order(From, item_summary, final_reply)
        send_order_email(From, item_summary, final_reply)
        voice_session_store.pop(From, None)

        response = VoiceResponse()
        response.say(final_reply)
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

    # Else, continue collecting items
    session["items"].append(SpeechResult)

    prompt = f"""
You are an AI assistant helping customers place food orders at Gen Z Burger.
Here is the order so far: {session['items']}

The caller said: "{SpeechResult}"

If the customer seems done, summarize the order and ask: 'Is that correct?'
Otherwise, ask what else they'd like in a friendly tone.
"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            timeout=5
        )
        reply = completion.choices[0].message.content.strip()
        print("🤖 GPT reply:", reply)

        # Update stage if bot is asking for confirmation
        if "is that correct" in reply.lower():
            session["stage"] = "confirming"

        voice_session_store[From] = session

        response = VoiceResponse()
        response.say(reply)

        gather = Gather(input='speech', action='/process_voice', method='POST', timeout=5)
        gather.say("You can say yes to confirm, or continue your order.")
        response.append(gather)

        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        print("❌ GPT error:", e)
        fallback = VoiceResponse()
        fallback.say("Sorry, I had trouble understanding. Please try again later.")
        return Response(content=str(fallback), media_type="application/xml")