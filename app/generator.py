import os, json, traceback
from typing import Dict, List
from openai import OpenAI
from .config import OPENAI_API_KEY, GEN_MODEL

print(">>> [generator] Initializing OpenAI client for generation...")
client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """You are a helpful assistant that routes people to local community resources.
Use ONLY the provided resources. Keep summaries factual; do not invent contact details."""

def _slice(s: str | None, n: int = 900) -> str:
    if not s: return ""
    s = s.strip()
    return s if len(s) <= n else s[:n] + "..."

def generate_card_summaries(user_query: str, retrieved: List[Dict]) -> Dict[str, str]:
    """
    Return dict: {match_id: summary (1–2 sentences)} using structured outputs.
    Falls back to a deterministic summary if the model call fails.
    """
    print(f">>> [generator] Generating per-card summaries for {len(retrieved)} items")

    items = []
    for r in retrieved:
        md = r.get("metadata", {}) or {}
        items.append({
            "id": str(r.get("id") or md.get("resource_id") or ""),
            "name": md.get("resource_name") or "",
            "org": md.get("organization_name") or "",
            "text": _slice(md.get("text") or ""),
            "eligibility": (md.get("eligibility") or md.get("service_details", {}).get("eligibility") or ""),
            "fees": md.get("fees") or "",
            "languages": md.get("languages") or [],
            "categories": md.get("categories") or []
        })

    schema = {
      "name":"card_summaries",
      "schema":{
        "type":"object",
        "properties":{
          "cards":{
            "type":"array",
            "items":{
              "type":"object",
              "properties":{
                "id":{"type":"string"},
                "summary":{"type":"string"}
              },
              "required":["id","summary"],
              "additionalProperties":False
            }
          }
        },
        "required":["cards"],
        "additionalProperties":False
      }
    }

    # Build a super-compact prompt
    prompt = (
        "For each item, write a concise 1–2 sentence summary tailored to the user's question. "
        "Mention what it provides and any clear eligibility/cost/language. Respond in JSON only."
    )

    # Try structured output first
    try:
        resp = client.responses.create(
            model=GEN_MODEL,
            input=[
                {"role":"system","content":SYSTEM_PROMPT},
                {"role":"user","content": f"User question: {user_query}\nItems JSON:\n{json.dumps(items, ensure_ascii=False)}\n{prompt}"}
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema["name"],
                    "schema": schema["schema"] # <-- THIS IS CORRECT
                }
            },
        )
        data = json.loads(resp.output_text)
        summaries = {str(c["id"]): c["summary"].strip() for c in data.get("cards", []) if c.get("id")}
        print(f">>> [generator] Summaries generated for {len(summaries)} items.")
    except Exception as e:
        print(">>> [generator] Structured output failed; using fallback:", e)
        summaries = {}

    # Fallback: deterministic single-line summary using metadata
    if len(summaries) < len(items):
        for it in items:
            mid = it["id"]
            if not mid or mid in summaries:
                continue
            services = ", ".join(it.get("categories") or []) or "services"
            langs = ", ".join(it.get("languages") or []) or ""
            bits = [
                f"{it.get('name') or 'Resource'} — {it.get('org') or 'Organization'} provides {services.lower()}",
                f"({it['fees']})" if it.get("fees") else "",
                f"Languages: {langs}" if langs else "",
            ]
            summaries[mid] = " ".join([b for b in bits if b]).strip()

    return summaries

