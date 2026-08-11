import base64
import re
from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.config import get_all_secrets
GEMINI_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,MONGODB_URI = get_all_secrets()


def clean_email_text(raw_text: str) -> str:
    """Fallback cleaner for plain text emails using regex."""
    if not raw_text:
        return ""
    text = raw_text.replace('\r', ' ')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n+', '\n', text)
    return text.strip()


def clean_html_content(raw_html: str) -> str:
    """Uses BeautifulSoup to strip all HTML tags."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator="\n", strip=True)



def fetch_unread_emails(refresh_token: str, date_after: str):
    """
    Fetches unread emails from Gmail that arrived after a specific date.
    date_after should be formatted as YYYY/MM/DD
    """
    
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET
    )
    
    service = build('gmail', 'v1', credentials=creds)

    search_query = f"is:unread after:{date_after}"
    
    try:
        results = service.users().messages().list(
            userId='me', 
            q=search_query, 
            maxResults=30
        ).execute()
        
        messages = results.get('messages', [])
    except Exception as e:
        print(f"Error connecting to Gmail API: {e}")
        return []

    clean_emails = []

    if not messages:
        print(f"No new emails found after {date_after}.")
        return []

    for msg in messages:
        try:
            msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
            payload = msg_data.get('payload', {})
            headers = payload.get('headers', [])

            subject = next((header['value'] for header in headers if header['name'].lower() == 'subject'), "No Subject")
            sender = next((header['value'] for header in headers if header['name'].lower() == 'from'), "Unknown Sender")

            body_data = ""
            
            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        body_data = part['body'].get('data', '')
                        break 
                    elif part['mimeType'] == 'text/html':
                        body_data = part['body'].get('data', '')
            
            else:
                body_data = payload.get('body', {}).get('data', '')

            if body_data:
                decoded_bytes = base64.urlsafe_b64decode(body_data)
                raw_text = decoded_bytes.decode('utf-8', errors='ignore')
                
                if '<html' in raw_text.lower() or '<body' in raw_text.lower() or '<div' in raw_text.lower():
                    clean_text = clean_html_content(raw_text)
                else:
                    clean_text = clean_email_text(raw_text)
            else:
                clean_text = ""

            clean_emails.append({
                "id": msg['id'],
                "subject": subject,
                "sender": sender,
                "body": clean_text
            })
            
        except Exception as e:
            print(f"Failed to parse email {msg['id']}: {e}")
            continue

    return clean_emails