from pydantic import BaseModel, Field

# 1. Incoming payload schema from React / Client
class EmailRequest(BaseModel):
    sender: str = Field(..., description="The sender's email address")
    subject: str = Field(..., description="The email subject")
    body: str = Field(..., description="The main text of the email")

# 2. Outgoing response schema sent back to Client
class EmailResponse(BaseModel):
    id: str
    message: str
    is_spam: bool
    reason: str

# 3. Request schema for the AI Tagger
class TagRequest(BaseModel):
    body: str = Field(..., description="The email text to analyze")

# 4. Response schema including Calendar Event details
class TagResponse(BaseModel):
    tags: list[str]
    is_urgent: bool
    priority: str
    has_event: bool
    event_title: str | None = None
    event_date: str | None = None
    calendar_prompt: str | None = None

#5. User schema for authentication

class UserCreate(BaseModel):
    email: str
    password: str

#6. Token schema for authentication responses
class Token(BaseModel):
    access_token: str
    token_type: str