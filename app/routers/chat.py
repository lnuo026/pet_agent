from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from app.services import session, gemini, triage, db
from app.limiter import limiter


router = APIRouter()

FALLBACK_MESSAGE = (
     "The system is temporarily experiencing an issue and cannot process your request.\n\n"
     "If your pet is in an emergency, please call your local 24-hour emergency vet immediately — do not wait.\n\n"
     "We will restore service as soon as possible."
)

class ChatRequest(BaseModel):
     # Field(..., 其他规则) = "必填 + 附加这些规则"
     message: str = Field(..., max_length=2000)
     sessionId: str


class ChatResponse(BaseModel):
     reply: str
     triageLevel: str
     sessionId: str



@router.post("/api/chat/message",response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat(request:Request, req: ChatRequest):
     history = session.get_history(req.sessionId)
     contents = history + [{"role": "user", "parts":[{"text": req.message}] }]
     
     try:
          raw = gemini.call_gemini(contents)
     except Exception:
          await db.log_message(req.sessionId, "assistant", FALLBACK_MESSAGE,"unknown") 
          raise HTTPException(status_code=503, detail=FALLBACK_MESSAGE)
     
     parsed = triage.parse_triage(raw)

     session.add_message(req.sessionId, "user", req.message)
     session.add_message(req.sessionId, "model", raw)

     await db.log_message(req.sessionId, "user", req.message)
     await db.log_message(req.sessionId, "assistant", parsed["clean_text"], parsed["triage_level"])

     return ChatResponse(
          reply=parsed["clean_text"],
          triageLevel=parsed["triage_level"],
          sessionId=req.sessionId
     )
