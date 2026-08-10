import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from app.config import get_all_secrets

GEMINI_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,MONGODB_URI = get_all_secrets()

# If you have a MongoDB Atlas URL, you can swap it here. 
# Otherwise, it defaults to your local MongoDB compass installation.

client = AsyncIOMotorClient(MONGODB_URI)

# Create a database called "ai_email_assistant"
database = client.ai_email_assistant

# Create a collection (like a table) called "emails"
email_collection = database.get_collection("emails")

# NEW: Add the users collection for authentication
user_collection = database.get_collection("users")