from fastapi import APIRouter, Form
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI
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
    session = voice_session_store.get(From, {"items": []})

    prompt = f"""
You are an AI voice assistant for Gen Z Burger in Langley, BC.
The caller said: "{SpeechResult}"
Order so far: {session['items']}

Reply in a helpful, casual tone. Confirm items, suggest add-ons, or ask for clarification.
Limit to 1–2 short sentences only.
"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            timeout=5
        )
        reply = completion.choices[0].message.content.strip()

        # Save message to session
        session['items'].append(SpeechResult)
        voice_session_store[From] = session

        print("🤖 AI Response:", reply)

        response = VoiceResponse()
        response.say(reply)
        # Re-gather input after saying reply
        gather = Gather(input='speech', action='/process_voice', method='POST', timeout=5)
        gather.say("You can say more or confirm your order.")
        response.append(gather)
        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        print("❌ Error in voice GPT:", e)
        fallback = VoiceResponse()
        fallback.say("Sorry, something went wrong. Please try again later.")
        return Response(content=str(fallback), media_type="application/xml")
