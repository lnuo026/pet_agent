import re

def parse_triage(raw: str) -> dict:
     if "[TRIAGE:RED]" in raw:
          triage_level = "red"
     elif "[TRIAGE:YELLOW]" in raw:
          triage_level = "yellow"     
     elif "[TRIAGE:GREEN]" in raw:
          triage_level = "green"     
     else:
          triage_level = "unknown"

     city_match = re.search(r"\[CITY:([^\]]+)\]", raw)
     city = city_match.group(1).strip() if city_match else None

     clean_text = re.sub(r"\[TRIAGE:[A-Z]+\]", "", raw)
     clean_text = re.sub(r"\[CITY:[^\]]+\]", "", clean_text).strip()

     return {"triage_level": triage_level, "city": city, "clean_text": clean_text}

