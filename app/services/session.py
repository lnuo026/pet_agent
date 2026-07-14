from collections import defaultdict

MAX_HISTORY = 10;
_session: dict[str, list[dict]] = defaultdict(list)

def get_history(session_id: str) -> list[dict]:
     return _session[session_id]

def add_message(session_id: str, role: str, text: str) -> None:
    history = _session[session_id]
    history.append({"role": role, "parts": [{"text": text}]})

    if len(history) > MAX_HISTORY:
         del history[: len(history) - MAX_HISTORY]

