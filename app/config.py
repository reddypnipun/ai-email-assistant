import os
import json
from dotenv import load_dotenv

def get_all_secrets():
    """Fetches Gemini API Key from .env and Google Credentials from client_secrets.json"""
    
    # 1. Point to the root directory (one level up from app/)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 2. Grab the Gemini API Key from .env
    ENV_PATH = os.path.join(BASE_DIR, ".env")
    load_dotenv(dotenv_path=ENV_PATH)
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    # 3. Grab the Google Client ID & Secret from client_secrets.json
    SECRETS_PATH = os.path.join(BASE_DIR, "client_secrets.json")
    client_id, client_secret = None, None
    
    try:
        with open(SECRETS_PATH, 'r') as f:
            secrets_data = json.load(f)
        
        # Google JSONs use either "web" or "installed"
        creds_type = "web" if "web" in secrets_data else "installed"
        client_id = secrets_data[creds_type]["client_id"]
        client_secret = secrets_data[creds_type]["client_secret"]
        
    except FileNotFoundError:
        print(f"❌ ERROR: Could not find {SECRETS_PATH}")
    except KeyError:
        print("❌ ERROR: client_secrets.json is missing 'client_id' or 'client_secret'")

    return gemini_key, client_id, client_secret