from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

_client = AsyncIOMotorClient(settings.mongo_uri)
_db = _client["pet_triage"]
chat_logs = _db["chat_logs"]

async def log_message(session_id: str, role: str, content: str, triage_level: str = "unknown") -> None:
     await chat_logs.insert_one({
          "sessionId": session_id,
          "role": role,
          "content": content,
          "triageLevel": triage_level
     })