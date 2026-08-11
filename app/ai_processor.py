import json
import os
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")

load_dotenv(dotenv_path=ENV_PATH)

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print(f"❌ ERROR: Could not find GEMINI_API_KEY inside {ENV_PATH}")
else:
    print("✅ GEMINI_API_KEY loaded successfully from .env!")

client = genai.Client(api_key=api_key) 

class CalendarEvent(BaseModel):
    event_title: str = Field(description="The name of the event")
    event_start: str = Field(description="Start date/time in YYYYMMDDTHHMMSS format in IST local time (Converted from email timezone if specified, otherwise assumed IST. Example: 20260810T150000)")
    event_end: str = Field(description="End date/time in YYYYMMDDTHHMMSS format in IST local time (Example: 20260810T160000)")
    event_details: str = Field(description="A short description of the event")

class EmailAnalysis(BaseModel):
    category: str = Field(description="Main category: Work, Personal, Invoice/Receipt, Alert, Meeting Request")
    priority_score: int = Field(description="Priority score from 1 (Lowest) to 10 (Urgent/Critical)")
    tags: list[str] = Field(description="3-5 descriptive tags for filtering")
    summary: str = Field(description="1-2 sentence executive summary")
    action_required: bool = Field(description="True if reply or physical action is needed")
    action_items: list[str] = Field(description="List of specific tasks requested in the email")
    calendar_event: Optional[CalendarEvent] = Field(description="Extract event details ONLY if the email contains a specific date/time for an event, meeting, or schedule. Otherwise leave null.")

def analyze_email(email_text: str, subject: str = "", sender: str = "") -> dict:
    """Analyzes non-spam emails with Gemini AI to generate metadata, priority, and tags."""
    
    today = datetime.now().strftime("%A, %B %d, %Y")
    
    prompt = f"""
    CRITICAL CONTEXT: 
    - Today's date is {today}.
    - The user's local timezone is IST (Indian Standard Time). 
    - DATE FORMAT: Always interpret dates with the Day first (DD-MM-YYYY or DD.MM.YYYY). For example, 09.08.2026 is August 9th, NOT September 8th.
    - TIMEZONE HANDLING: 
      1. If no timezone or region is specified in the email, assume the time is in IST.
      2. If a specific timezone or region IS mentioned (e.g., EST, PST, UTC, GMT, or a foreign country), convert that time into the user's local timezone (IST).
      3. Output the final calculated start and end timestamps in `YYYYMMDDTHHMMSS` format (in IST local time, with NO 'Z' at the end).

    Analyze the following legitimate email and extract structured metadata:
    
    Sender: {sender}
    Subject: {subject}
    Body:
    {email_text}
    """

    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=EmailAnalysis,
                temperature=0.1
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return {
            "category": "Uncategorized",
            "priority_score": 1,
            "tags": [],
            "summary": "AI processing failed.",
            "action_required": False,
            "action_items": [],
            "calendar_event": None
        }