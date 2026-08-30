import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from app.config import get_all_secrets

GEMINI_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,MONGODB_URI = get_all_secrets()

class EmailAnalysis(BaseModel):
    tags: list[str] = Field(description="1 to 4 relevant tags (e.g. 'classroom', 'assignment', 'meeting')")
    is_urgent: bool = Field(description="True if the email requires immediate action or has a looming deadline")
    priority: str = Field(description="Must be exactly: 'High', 'Medium', or 'Low'")
    has_event: bool = Field(description="True if the email contains a deadline, meeting, lab, or scheduled event")
    event_title: str = Field(default="", description="Short title for the calendar entry (e.g., 'Lab 2 Submission of Subject X')")
    event_date: str = Field(default="", description="The extracted due date or event time mentioned in the email")
    calendar_prompt: str = Field(default="", description="A question asking the user to add it, e.g., 'Would you like to add Lab 2 due Aug 11 to Google Calendar?'")

def analyze_email_context(body: str) -> dict:
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    Analyze this email text carefully:
    1. Categorize with relevant tags.
    2. Assess urgency and priority level.
    3. Check if there is an actionable event or deadline (e.g. lab submission, meeting, assignment due date).
    4. If an event is found, set has_event=True, extract event_title with the relevant information and event_date, and draft a clear calendar_prompt asking the user if they'd like to add it to Google Calendar.
    
    Email body:
    "{body}"
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema=EmailAnalysis,
            )
        )
        
        return json.loads(response.text)
        
    except Exception as e:
        print(f"\n❌ FATAL GenAI Error: {str(e)}\n") 
        return {
            "tags": ["unclassified"], 
            "is_urgent": False, 
            "priority": "Low",
            "has_event": False,
            "event_title": "",
            "event_date": "",
            "calendar_prompt": ""
        }