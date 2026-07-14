from collections import defaultdict

MAX_HISTORY = 10
_session: dict[str, list[dict]] = defaultdict(list)

# _session[session_id] return only value content no key,
def get_history(session_id: str) -> list[dict]:
     return _session[session_id]

def add_message(session_id: str, role: str, text: str) -> None:
    history = _session[session_id]
    history.append({"role": role, "parts": [{"text": text}]})

    if len(history) > MAX_HISTORY:
     #     history[:N] -slice  [: N) ,del = delete
         del history[: len(history) - MAX_HISTORY]

