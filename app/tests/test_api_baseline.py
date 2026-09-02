from fastapi.testclient import TestClient 
from app.main import app
from app.routers import chat as chat_router

client = TestClient(app)

def test_root_returns_ok() -> None:
     response = client.get("/")

     assert response.status_code == 200
     assert response.json() == {"status" : "ok"}



def test_chat_red_contract_without_real_external_calls(monkeypatch) -> None:
     # Mock the external call to avoid real API calls during testing
     observed_contents: list[dict] = []
     database_writes:list[dict] =[]

     def fake_call_gemini(contents: list[dict]) -> str:
          observed_contents.extend(contents)
          return "[TRIAGE:RED]\nImmediate emergency."

     async def fake_log_message(
               session_id: str,
               role: str,
               content: str,
               triage_level: str = "unknown",
     ) -> None:
          database_writes.append(
               {
                    "session_id": session_id,
                    "role": role,
                    "content": content,
                    "triageLevel": triage_level,
               }
          )

     monkeypatch.setattr(
          chat_router.gemini,
          "call_gemini",
          fake_call_gemini,
     )

     monkeypatch.setattr(
          chat_router.db,
          "log_message",
          fake_log_message,
     )

     response = client.post(
          "/api/chat/message",
          json={
               "message":"My pet collapsed",
               "sessionId":"baseline-red-001",
          },
     )

     assert response.status_code == 200

     assert response.json() == {
          "reply": "Immediate emergency.",
          "triageLevel": "red",
          "sessionId": "baseline-red-001",
     }

     assert observed_contents == [
          {
               "role":"user",    
               "parts":[
                    {
                         "text":"My pet collapsed",
                    }
               ],
          }
     ]

     assert database_writes == [
          {
               "sessionId":"baseline-red-001",
               "role":"user",
               "content":"My pet collapsed",
               "triageLevel":"unknown",
          },
          {
               "sessionId": "baseline-red-001",
               "role": "assistant",
               "content": "Immediate emergency",
               "triageLevel": "red",
          },
     ]

