from pydantic import BaseModel, Field

class EmailRequest(BaseModel):
    sender: str = Field(..., description="The sender's email address")
    subject: str = Field(..., description="The email subject")
    body: str = Field(..., description="The main text of the email")

class EmailResponse(BaseModel):
    id: str
    message: str
    is_spam: bool
    reason: str

class TagRequest(BaseModel):
    body: str = Field(..., description="The email text to analyze")

class TagResponse(BaseModel):
    tags: list[str]
    is_urgent: bool
    priority: str
    has_event: bool
    event_title: str | None = None
    event_date: str | None = None
    calendar_prompt: str | None = None


class UserCreate(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str