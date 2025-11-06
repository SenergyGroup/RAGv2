from typing import Dict, List
from openai import OpenAI

from .config import OPENAI_API_KEY, GEN_MODEL

print(">>> [generator] Initializing OpenAI client for generation...")
client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """You are a helpful assistant that routes people to local community resources.
Use ONLY the provided resources. If info is missing, say so.
List 3–5 resources, each with: Name — Org; 1–2 sentence summary; then Phone / Website / Address from metadata if it exists.
Keep it concise and factual. Do not fabricate details."""

def _slice(s: str | None, n: int = 1300) -> str:
    if not s:
        return ""
    s = s.strip()
    return s if len(s) <= n else s[:n] + "..."

def _make_context(resources: List[Dict]) -> str:
    blocks = []
    for r in resources:
        md = r.get("metadata", {})
        header = f"{md.get('resource_name','Unknown')} — {md.get('organization_name','')}".strip()
        # Prefer the human-readable chunk text you upserted (metadata["text"])
        body = md.get("text") or ""
        if not body:
            # fallback: synthesize a brief from individual fields
            body_parts = []
            if md.get("categories"):
                body_parts.append(f"Services: {', '.join(md['categories'])}")
            if md.get("fees"):
                body_parts.append(f"Cost: {md['fees']}")
            if md.get("languages"):
                body_parts.append(f"Languages: {', '.join(md['languages'])}")
            if md.get("hours_notes") or (md.get("hours") and md["hours"].get("notes")):
                h = md.get("hours_notes") or md["hours"].get("notes")
                body_parts.append(f"When: {h}")
            body = ". ".join([p for p in body_parts if p]) or "No descriptive text provided."
        blocks.append(header + "\n" + _slice(body))
    return "\n\n---\n\n".join(blocks)

def generate_answer(user_query: str, retrieved: List[Dict]) -> str:
    print(f">>> [generator] Generating answer for query: {user_query}")
    ctx = _make_context(retrieved)

    prompt = f"""User question:
{user_query}

Use ONLY these resources (context):
{ctx}

For each resource, output:
- Name — Org
- 1–2 sentence summary (what it is / who it's for / how to access if obvious)
- Then show: Phone / Website / Address (exactly as given; say 'Not provided' if missing)
End with: "If this doesn’t look right, tell me your city/ZIP, language, and whether you need free options."
"""

    # Responses API (recommended for new apps); simple text output path  :contentReference[oaicite:10]{index=10}
    resp = client.responses.create(
        model=GEN_MODEL,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
    )
    print(">>> [generator] Model responded. Converting to text...")
    answer_text = resp.output_text  # SDK convenience property
    print(">>> [generator] Answer length (chars):", len(answer_text))
    return answer_text
