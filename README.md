# AI Email Assistant

A high-performance full-stack web application that integrates Google OAuth, the Gmail API, and Groq's Llama 3 model to intelligently filter, summarize, and extract action items from unread emails in real-time.

## Project Overview

This application solves inbox overload by securely connecting to a user's Gmail account and utilizing a 70-billion parameter LLM to process unread threads. Instead of standard batch processing, it leverages asynchronous Python and Server-Sent Events (SSE) to stream AI-analyzed email summaries to a React frontend instantly.

**Live Demo:** [https://ai-email-assistant.vercel.app/](https://ai-email-assistant-zeta-pearl.vercel.app/)

## Core Features

* **Secure Google Authentication:** Implements OAuth 2.0 flows to safely request and manage restricted `gmail.readonly` access tokens.
* **Sub-Second LLM Inference:** Powered by the Groq API (Llama-3.3-70B-Versatile) running on custom LPU hardware for near-instant text analysis and JSON generation.
* **Concurrent Processing:** Utilizes `asyncio` to batch-process multiple emails simultaneously, bypassing standard API latency bottlenecks.
* **Automated Data Extraction:** The AI automatically categorizes emails (Work, Personal, Alert), generates one-sentence summaries, and extracts actionable dates into Google Calendar-ready formats.
* **Real-Time UI Streaming:** Server-Sent Events (SSE) push analyzed emails to the client the exact millisecond the backend finishes processing them.

## System Architecture

* **Frontend:** React.js, HTML5, CSS3 (Deployed via Vercel)
* **Backend:** FastAPI, Python, Asyncio (Deployed via Render)
* **Database:** MongoDB (User session and JWT management)
* **AI Engine:** Groq API
* **External APIs:** Google Identity, Gmail API

## Developer Note: OAuth Verification & Testing

Because this application requests the `gmail.readonly` scope, Google categorizes it under "Restricted Scopes," which requires a $15,000+ third-party security audit for public enterprise deployment.

As this is a developer portfolio project, the Google Cloud OAuth consent screen remains in "Testing Mode." When testing the live demo, you will encounter an "Unverified App" warning. 

**To bypass and test safely:** Click `Advanced` -> `Go to [App Name] (unsafe)`.

## Local Setup and Installation

### Prerequisites

* Python 3.9+
* Google Cloud Console account (OAuth credentials & Gmail API enabled)
* Groq API Key
* MongoDB Cluster URI

### Backend Setup

```bash
# Clone the repository
git clone [https://github.com/reddypnipun/ai-email-assistant.git](https://github.com/reddypnipun/ai-email-assistant.git)
cd ai-email-assistant/backend

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI server
uvicorn main:app --reload
