# Pet Triage API

> An AI-assisted pet emergency triage backend built with Python and FastAPI.

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)
![Gemini](https://img.shields.io/badge/Google_Gemini-AI-4285F4?logo=google&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Logging-47A248?logo=mongodb&logoColor=white)

Pet Triage API helps pet owners decide the urgency of a reported symptom. It returns one of three triage levels—**RED**, **YELLOW**, or **GREEN**—with safety-focused next steps in English.

> **Important:** This is an educational project, not a veterinary diagnostic tool. It does not diagnose conditions, prescribe medication, or replace a licensed veterinarian. If a pet may be in immediate danger, contact an emergency veterinary clinic straight away.

## Current status

**Backend MVP — in progress.** The FastAPI service, Gemini integration, session memory, rate limiting, and MongoDB logging code are in place. End-to-end verification and automated tests are still being completed.

## What it does

- Accepts a pet-symptom message through a REST API.
- Uses Gemini with a constrained emergency-triage system prompt.
- Categorises the response as:
  - `red`: immediate emergency care is needed.
  - `yellow`: see a veterinarian today.
  - `green`: monitor carefully at home and arrange routine care if needed.
- Removes internal triage tags before returning the user-facing reply.
- Retains the latest 10 messages for each `sessionId`, enabling multi-turn conversations.
- Limits each IP address to 10 requests per minute.
- Writes user and assistant messages to MongoDB when `MONGO_URI` is configured and reachable.



## Tech stack

- Python 3.14
- FastAPI and Uvicorn
- Google Gemini API (`google-genai`)
- Pydantic Settings for environment configuration
- Motor for asynchronous MongoDB access
- SlowAPI for IP-based rate limiting

## Project structure

```text
pet-triage/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Environment-based settings
│   ├── limiter.py              # SlowAPI rate-limit configuration
│   ├── routers/
│   │   └── chat.py             # POST /api/chat/message endpoint
│   └── services/
│       ├── gemini.py           # Gemini client and system prompt
│       ├── triage.py           # Extracts triage tags from model output
│       ├── session.py          # Per-session conversation memory
│       └── db.py               # MongoDB chat-log writer
├── test_triage.py              # Early manual Gemini experiment
├── .env                        # Local secrets; never commit this file
└── README.md
```

## Run locally

### 1. Open the project and activate its virtual environment

```bash
cd /Users/a11111/WorkSpace/python/agent/pet-triage
source .venv/bin/activate
```

### 2. Configure environment variables

Create or update the local `.env` file. Never paste a real API key into this README, Git commits, screenshots, or chat messages.

```env
GEMINI_API_KEY=your_google_ai_studio_key
MONGO_URI=your_mongodb_connection_string
```

`GEMINI_API_KEY` is required when the application starts. `MONGO_URI` is needed for successful database logging during a chat request.

### 3. Start the development server

```bash
uvicorn app.main:app --reload
```

When startup succeeds, open the interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

## API

### `POST /api/chat/message`

Send a symptom description and a stable session identifier.

```json
{
  "message": "My dog vomited once this morning but is energetic and playing normally.",
  "sessionId": "demo-session-001"
}
```

Successful responses follow this shape:

```json
{
  "reply": "Safe to Monitor at Home ...",
  "triageLevel": "green",
  "sessionId": "demo-session-001"
}
```

Use the same `sessionId` for follow-up messages so the service can include the previous conversation. The `message` field is required and limited to 2,000 characters.

If Gemini raises an error, the endpoint returns HTTP `503` with a safety-first fallback message. Requests exceeding the limit return HTTP `429`.

## Safety and security

- Treat every `GEMINI_API_KEY` and MongoDB connection string as a secret.
- Keep `.env` in `.gitignore`.
- If a key was ever committed, deleting it from the latest file is not enough: revoke it in the provider console and clean the Git history before making the repository public.
- Do not present the service output as a medical or veterinary diagnosis.

## Roadmap

- [ ] Add automated unit tests for triage parsing, session history, and API validation.
- [ ] Verify MongoDB log records, `429` rate limiting, and `503` fallback behaviour end to end.
- [ ] Make external Gemini calls non-blocking for concurrent requests.
- [ ] Add Docker-based local development.
- [ ] Build a user-facing frontend and an authenticated API gateway.

## Learning goals

This project is being built to practise:

- Python backend development with FastAPI.
- REST API design and request validation with Pydantic.
- Safe use of generative AI in a constrained domain.
- Session state, rate limiting, and database logging.
- Production-minded handling of secrets and error states.

## License

This project is currently for learning and portfolio purposes. A licence will be selected before public distribution.
