import os
import json
from groq import Groq

client = Groq()

def analyze_email(email_text, subject, sender):
    prompt = f"Analyze this email.\n\nFrom: {sender}\nSubject: {subject}\nBody: {email_text}"
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system", 
                "content": """You are an expert AI email assistant. You MUST output ONLY valid JSON.
                Use this exact schema:
                {
                    "category": "string (e.g., Work, Personal, Newsletter, Alert)",
                    "priority_score": 1, 
                    "summary": "string (1 sentence)",
                    "action_items": ["string"],
                    "suggested_reply": "string",
                    "calendar_event": {
                        "event_title": "string",
                        "event_start": "YYYYMMDDTHHmmssZ",
                        "event_end": "YYYYMMDDTHHmmssZ",
                        "event_details": "string"
                    }
                }
                If no calendar event is needed, leave the calendar_event object as null."""
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.2
    )
    
    return json.loads(response.choices[0].message.content)