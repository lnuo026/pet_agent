from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.services import session, gemini, triage

router = APIRouter()

class ChatRequest(BaseModel):
     # Field(..., 其他规则) = "必填 + 附加这些规则"
     message: str = Field(..., max_length=2000)
     sessionId: str

class ChatResponse(BaseModel):
     reply: str
     triageLevel: str
     sessionId: str

@router.post("/api/chat/message",response_model=ChatResponse)
def chat(req: ChatRequest):
     history = session.get_history(req.sessionId)
     contents = history + [{"role": "user", "parts":[{"text": req.message}] }]
     
     print(f"[DEBUG] history 里面 {len(history)} 条消息，当前用户输入 {len(contents)} 条消息")
     print(f"[debug] constents = {contents}")
     raw = gemini.call_gemini(contents)
     parsed = triage.parse_triage(raw)

     session.add_message(req.sessionId, "user", req.message)
     session.add_message(req.sessionId, "model", raw)

     return ChatResponse(
          reply=parsed["clean_text"],
          triageLevel=parsed["triage_level"],
          sessionId=req.sessionId
     )
