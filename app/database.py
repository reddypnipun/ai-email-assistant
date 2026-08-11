import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from app.config import get_all_secrets

GEMINI_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,MONGODB_URI = get_all_secrets()


client = AsyncIOMotorClient(MONGODB_URI)

database = client.ai_email_assistant

email_collection = database.get_collection("emails")

user_collection = database.get_collection("users")