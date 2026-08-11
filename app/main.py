import os
import time
import json
import asyncio
import urllib.parse
import urllib.request
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from google_auth_oauthlib.flow import Flow

from app.schemas import EmailRequest, EmailResponse, TagRequest, TagResponse, UserCreate, Token
from app.database import user_collection, email_collection
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user
from app.gmail import fetch_unread_emails
from app.ml_model import predict_spam
from app.ai_processor import analyze_email

app = FastAPI(title="AI Email Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- GOOGLE OAUTH CONFIGURATION ---
DOMAIN = os.getenv("DOMAIN", "http://127.0.0.1:8000")
REDIRECT_URI = f"{DOMAIN}/auth/google/callback"

if DOMAIN.startswith("http://127"):
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

SCOPES = [
    'openid', 
    'https://www.googleapis.com/auth/userinfo.email', 
    'https://www.googleapis.com/auth/gmail.readonly'
]

oauth_state_store = {}

# ==========================================
# PUBLIC ROUTES (NO LOGIN REQUIRED)
# ==========================================

@app.get("/auth/google/login")
async def login_with_google():
    flow = Flow.from_client_secrets_file(
        'client_secrets.json', scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    authorization_url, state = flow.authorization_url(access_type='offline', prompt='consent')
    oauth_state_store[state] = flow
    return RedirectResponse(url=authorization_url)

@app.get("/auth/google/callback")
async def google_callback(request: Request, code: str, state: str):
    flow = oauth_state_store.get(state)
    if not flow:
        raise HTTPException(status_code=400, detail="Session expired.")

    flow.fetch_token(code=code)
    credentials = flow.credentials

    req = urllib.request.Request(f"https://www.googleapis.com/oauth2/v1/userinfo?access_token={credentials.token}")
    with urllib.request.urlopen(req) as response:
        user_info = json.loads(response.read().decode())
        user_email = user_info.get("email")

    user = await user_collection.find_one({"email": user_email})
    if not user:
        await user_collection.insert_one({
            "email": user_email, "hashed_password": "", "google_refresh_token": credentials.refresh_token
        })
    elif credentials.refresh_token:
        await user_collection.update_one({"email": user_email}, {"$set": {"google_refresh_token": credentials.refresh_token}})

    access_token = create_access_token(data={"sub": user_email})
    
    FRONTEND_URL = os.getenv("FRONTEND_URL", "https://nipun-ai-email-assistant.netlify.app")
    return RedirectResponse(url=f"{FRONTEND_URL}?token={access_token}")


# ==========================================
# PROTECTED ROUTES (REQUIRES FRONTEND JWT)
# ==========================================

@app.get("/sync-emails")
async def sync_emails(date: str, current_user: dict = Depends(get_current_user)):
    
    async def process_emails_one_by_one():
        user = await user_collection.find_one({"email": current_user["email"]})
        refresh_token = user.get("google_refresh_token")
        
        if not refresh_token:
            yield json.dumps({"error": "No Google connection found. Please log in with Google."}) + "\n"
            return
            
        raw_emails = fetch_unread_emails(refresh_token, date)
        
        if not raw_emails:
            yield json.dumps({"error": f"No emails found after {date}"}) + "\n"
            return 
        
        for email in raw_emails:
            clean_text = email["body"]
            is_spam = predict_spam(clean_text)
            
            if is_spam:
                spam_doc = {
                    "user_email": current_user["email"],
                    "gmail_id": email["id"],
                    "sender": email["sender"],
                    "subject": email["subject"],
                    "status": "spam"
                }
                await email_collection.update_one(
                    {"gmail_id": email["id"], "user_email": current_user["email"]},
                    {"$set": spam_doc}, upsert=True
                )
                yield json.dumps(spam_doc) + "\n"
                
            else:
                success = False
                ai_analysis = {}
                attempts = 0
                
                while not success and attempts < 3:
                    try:
                        attempts += 1
                        ai_analysis = analyze_email(email_text=clean_text, subject=email["subject"], sender=email["sender"])
                        if not ai_analysis:
                            raise Exception("AI returned empty result.")
                        success = True
                    except Exception as e:
                        print(f"AI Attempt {attempts} failed. Error: {e}")
                        if attempts < 3:
                            await asyncio.sleep(20)
                        else:
                            print("Skipping this email after 3 failed attempts.")
                
                if success:
                    good_doc = {
                        "user_email": current_user["email"],
                        "gmail_id": email["id"],
                        "sender": email["sender"],
                        "subject": email["subject"],
                        "body": clean_text,
                        "category": ai_analysis.get("category", "General"),
                        "priority_score": ai_analysis.get("priority_score", 1),
                        "ai_analysis": ai_analysis,
                        "status": "inbox"
                    }
                    await email_collection.update_one(
                        {"gmail_id": email["id"], "user_email": current_user["email"]},
                        {"$set": good_doc}, upsert=True
                    )
                    yield json.dumps(good_doc) + "\n"
                    await asyncio.sleep(4)

    return StreamingResponse(process_emails_one_by_one(), media_type="application/x-ndjson")


@app.get("/emails")
async def get_saved_emails(current_user: dict = Depends(get_current_user)):
    cursor = email_collection.find({"user_email": current_user["email"]}, {"_id": 0})
    emails = await cursor.to_list(length=100)
    return {"emails": emails}


@app.put("/emails/{gmail_id}/not-spam")
async def mark_not_spam(gmail_id: str, current_user: dict = Depends(get_current_user)):
    email = await email_collection.find_one({"gmail_id": gmail_id, "user_email": current_user["email"]})
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
        
    clean_text = email.get("body", "")
    
    try:
        ai_analysis = analyze_email(email_text=clean_text, subject=email.get("subject"), sender=email.get("sender"))
    except Exception as e:
        raise HTTPException(status_code=429, detail="AI is processing another task. Try again in 2 seconds.")
        
    update_data = {
        "category": ai_analysis.get("category", "General"),
        "priority_score": ai_analysis.get("priority_score", 1),
        "ai_analysis": ai_analysis,
        "status": "inbox",
    }
    
    await email_collection.update_one(
        {"gmail_id": gmail_id, "user_email": current_user["email"]},
        {"$set": update_data}
    )
    
    full_response_doc = {
        "gmail_id": email.get("gmail_id"),
        "subject": email.get("subject"),
        "sender": email.get("sender"),
        "body": clean_text,
        "category": update_data["category"],
        "priority_score": update_data["priority_score"],
        "ai_analysis": ai_analysis,
        "status": "inbox"
    }
    
    return {"message": "Email rescued from spam and summarized!", "data": full_response_doc}


@app.post("/emails/{gmail_id}/calendar")
async def generate_calendar_link(gmail_id: str, current_user: dict = Depends(get_current_user)):
    email = await email_collection.find_one({"gmail_id": gmail_id, "user_email": current_user["email"]})
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
        
    ai_data = email.get("ai_analysis", {})
    cal_data = ai_data.get("calendar_event")
    
    if not cal_data:
        raise HTTPException(status_code=400, detail="No calendar event found in this email.")
        
    base_url = "https://calendar.google.com/calendar/render?action=TEMPLATE"
    title = urllib.parse.quote(cal_data.get("event_title", "New Event"))
    dates = f"{cal_data.get('event_start')}/{cal_data.get('event_end')}"
    details = urllib.parse.quote(cal_data.get("event_details", ""))
    
    calendar_url = f"{base_url}&text={title}&dates={dates}&details={details}"
    
    return {"calendar_url": calendar_url}