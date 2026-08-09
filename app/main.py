from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from app.spam_filter import HybridSpamFlagger
from app.database import email_collection
from app.schemas import EmailRequest, EmailResponse, TagRequest, TagResponse
from app.ai_tagger import analyze_email_context
from fastapi import HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from app.schemas import UserCreate, Token
from app.database import user_collection
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user
from app.gmail import fetch_unread_emails
from app.ml_model import predict_spam
from app.ai_processor import analyze_email
from app.database import email_collection
from fastapi.middleware.cors import CORSMiddleware
import time
import json
import asyncio
from fastapi.responses import StreamingResponse
import urllib.parse

app = FastAPI(title="AI Email Assistant API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
import os

# --- GOOGLE OAUTH CONFIGURATION ---

# 1. Dynamically set the domain (defaults to localhost for testing)
DOMAIN = os.getenv("DOMAIN", "http://127.0.0.1:8000")
REDIRECT_URI = f"{DOMAIN}/auth/google/callback"

# 2. Security Check: Only allow insecure HTTP for local testing
if DOMAIN.startswith("http://127"):
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# 3. Define the exact permissions we are asking Google for
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# ----------------------------------
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# NEW: Temporary memory to hold the OAuth flow state
oauth_state_store = {}
flagger = HybridSpamFlagger()

@app.post("/analyze", response_model=EmailResponse)
async def analyze_and_save_email(email: EmailRequest):
    # 1. Run the ML Model
    analysis = flagger.analyze(email.body, email.sender)

    # 2. Package for MongoDB
    email_document = email.model_dump()
    email_document["is_spam"] = analysis["is_spam"]
    email_document["reason"] = analysis["reason"]

    # 3. Save to MongoDB
    new_record = await email_collection.insert_one(email_document)

    # 4. Return result
    return EmailResponse(
        id=str(new_record.inserted_id),
        message="Email successfully analyzed and saved to database.",
        is_spam=analysis["is_spam"],
        reason=analysis["reason"]
    )
@app.post("/tags", response_model=TagResponse)
async def get_email_tags(req: TagRequest):
    # 1. Ask Gemini to analyze context + calendar event
    analysis = analyze_email_context(req.body)
    
    # 2. Return unpacked dictionary matching TagResponse schema
    return TagResponse(**analysis)

@app.post("/signup", status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate):
    # 1. Check if user already exists
    existing_user = await user_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # 2. Hash the password and save
    hashed_password = get_password_hash(user.password)
    new_user = {
        "email": user.email,
        "hashed_password": hashed_password,
        "google_refresh_token": None # Will be filled later
    }
    await user_collection.insert_one(new_user)
    return {"message": "User created successfully!"}

@app.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # 1. Find user in database
    user = await user_collection.find_one({"email": form_data.username})
    
    # 2. Verify password
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 3. Generate token
    access_token = create_access_token(data={"sub": user["email"]})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/google/login")
async def login_with_google(current_user: dict = Depends(get_current_user)):
    flow = Flow.from_client_secrets_file(
        'client_secrets.json',
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent',
        state=current_user["email"]
    )
    
    # NEW: Save this specific flow object in memory using the user's email!
    oauth_state_store[current_user["email"]] = flow
    
    return {"auth_url": authorization_url}


@app.get("/auth/google/callback")
async def google_callback(request: Request, code: str, state: str):
    user_email = state
    
    # NEW: Retrieve the EXACT SAME flow object instead of creating a new one
    flow = oauth_state_store.get(user_email)
    
    if not flow:
        return {"error": "OAuth session expired or invalid. Please try logging in again."}
        
    # This will now succeed because it remembers the secret code_verifier!
    flow.fetch_token(code=code)
    credentials = flow.credentials
    
    # Save the refresh token to MongoDB
    if credentials.refresh_token:
        await user_collection.update_one(
            {"email": user_email},
            {"$set": {"google_refresh_token": credentials.refresh_token}}
        )
        
    # NEW: Clean up the memory so it doesn't get cluttered
    del oauth_state_store[user_email]

    return {
        "message": f"Gmail successfully connected for {user_email}!",
        "has_refresh_token": credentials.refresh_token is not None
    }


@app.get("/sync-emails")
async def sync_emails(date: str):
    
    async def process_emails_one_by_one():
        import os
        refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
        
        if not refresh_token:
            yield json.dumps({"error": "Google Refresh Token is missing from .env!"}) + "\n"
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
                    "gmail_id": email["id"],
                    "sender": email["sender"],
                    "subject": email["subject"],
                    "status": "spam"
                }
                await email_collection.update_one(
                    {"gmail_id": email["id"]},
                    {"$set": spam_doc}, upsert=True
                )
                yield json.dumps(spam_doc) + "\n"
                
            else:
                # --- BULLETPROOF GEMINI API CALL ---
                success = False
                ai_analysis = {}
                attempts = 0
                
                while not success and attempts < 3:
                    try:
                        attempts += 1
                        # Try to analyze the email
                        ai_analysis = analyze_email(email_text=clean_text, subject=email["subject"], sender=email["sender"])
                        
                        # Check if the AI returned empty data (meaning it failed silently)
                        if not ai_analysis:
                            raise Exception("AI returned empty result.")
                            
                        success = True
                        
                    except Exception as e:
                        print(f"AI Attempt {attempts} failed. Error: {e}")
                        if attempts < 3:
                            print("Auto-pausing for 60 seconds to cool down the API...")
                            await asyncio.sleep(60)
                        else:
                            print("Skipping this email after 3 failed attempts.")
                
                # If it successfully analyzed, save and stream it to the frontend
                if success:
                    good_doc = {
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
                        {"gmail_id": email["id"]},
                        {"$set": good_doc}, upsert=True
                    )
                    yield json.dumps(good_doc) + "\n"
                    
                    # 6 SECOND PAUSE: Keeps you safely at 10 requests per minute!
                    await asyncio.sleep(6)

    return StreamingResponse(process_emails_one_by_one(), media_type="application/x-ndjson") # <--- Notice I removed the security lock here
    
    async def process_emails_one_by_one():
        import os
        # Pull the master key directly from your .env file
        refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
        
        if not refresh_token:
            yield json.dumps({"error": "Google Refresh Token is missing from .env!"}) + "\n"
            return
            
        # Fetch raw emails using the date passed from React
        raw_emails = fetch_unread_emails(refresh_token, date)
        
        if not raw_emails:
            yield json.dumps({"error": f"No emails found after {date}"}) + "\n"
            return # Stop if no emails found
        
        for email in raw_emails:
            clean_text = email["body"]
            is_spam = predict_spam(clean_text)
            
            if is_spam:
                spam_doc = {
                    "gmail_id": email["id"],
                    "sender": email["sender"],
                    "subject": email["subject"],
                    "status": "spam"
                }
                await email_collection.update_one(
                    {"gmail_id": email["id"]},
                    {"$set": spam_doc}, upsert=True
                )
                # YIELD TO FRONTEND INSTANTLY
                yield json.dumps(spam_doc) + "\n"
                
            else:
                ai_analysis = analyze_email(email_text=clean_text, subject=email["subject"], sender=email["sender"])
                
                good_doc = {
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
                    {"gmail_id": email["id"]},
                    {"$set": good_doc}, upsert=True
                )
                # YIELD TO FRONTEND INSTANTLY
                yield json.dumps(good_doc) + "\n"
                
                # 4 SECOND PAUSE: Protects your Gemini API Free Tier limit!
                await asyncio.sleep(4)

    # Returns the stream connection
    return StreamingResponse(process_emails_one_by_one(), media_type="application/x-ndjson")


@app.get("/emails")
async def get_saved_emails():
    # Returns an empty list for now until you connect a database later
    return {"emails": []}



@app.put("/emails/{gmail_id}/not-spam")
async def mark_not_spam(gmail_id: str):
    # 1. Find the email in MongoDB
    email = await email_collection.find_one({"gmail_id": gmail_id})
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
        
    clean_text = email.get("body", "")
    
    # 2. Run the AI Summary
    try:
        ai_analysis = analyze_email(email_text=clean_text, subject=email.get("subject"), sender=email.get("sender"))
    except Exception as e:
        raise HTTPException(status_code=429, detail="AI is processing another task. Try again in 2 seconds.")
        
    # 3. Update the database record
    update_data = {
        "category": ai_analysis.get("category", "General"),
        "priority_score": ai_analysis.get("priority_score", 1),
        "ai_analysis": ai_analysis,
        "status": "inbox",
    }
    
    await email_collection.update_one(
        {"gmail_id": gmail_id},
        {"$set": update_data}
    )
    
    # 4. Construct a complete response object including subject and sender!
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
async def generate_calendar_link(gmail_id: str):
    import urllib.parse
    
    email = await email_collection.find_one({"gmail_id": gmail_id})
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
        
    ai_data = email.get("ai_analysis", {})
    cal_data = ai_data.get("calendar_event") # Grab the nested object!
    
    # Check if the nested object actually exists
    if not cal_data:
        raise HTTPException(status_code=400, detail="No calendar event found in this email.")
        
    base_url = "https://calendar.google.com/calendar/render?action=TEMPLATE"
    title = urllib.parse.quote(cal_data.get("event_title", "New Event"))
    dates = f"{cal_data.get('event_start')}/{cal_data.get('event_end')}"
    details = urllib.parse.quote(cal_data.get("event_details", ""))
    
    calendar_url = f"{base_url}&text={title}&dates={dates}&details={details}"
    
    return {"calendar_url": calendar_url}