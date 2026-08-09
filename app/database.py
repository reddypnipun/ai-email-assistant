import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

# If you have a MongoDB Atlas URL, you can swap it here. 
# Otherwise, it defaults to your local MongoDB compass installation.
MONGO_DETAILS = os.getenv("MONGO_URL", "mongodb://localhost:27017")

client = AsyncIOMotorClient(MONGO_DETAILS)

# Create a database called "ai_email_assistant"
database = client.ai_email_assistant

# Create a collection (like a table) called "emails"
email_collection = database.get_collection("emails")

# NEW: Add the users collection for authentication
user_collection = database.get_collection("users")