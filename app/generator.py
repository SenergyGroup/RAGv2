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


def generate_action_plan(user_query: str, grouped_results: Dict[str, List[Dict]]) -> str:
    """Return a short narrative action plan grounded in the grouped results."""

    story = (user_query or "").strip()
    if not story or not grouped_results:
        return ""

    print(">>> [generator] Generating action plan narrative...")

    plan_payload = []
    for slug, resources in grouped_results.items():
        label = str(slug or "support options").replace("-", " ").title()
        entries = []
        for resource in (resources or [])[:3]:
            md = resource.get("metadata") or {}
            entries.append({
                "name": md.get("resource_name") or resource.get("name") or "",
                "organization": md.get("organization_name") or "",
                "summary": resource.get("model_summary") or "",
                "categories": md.get("categories") or [],
            })
        plan_payload.append({"need": slug, "label": label, "resources": entries})

    prompt = (
        "Write a compassionate, empowering action plan for the person described in the user story. "
        "Use two to three paragraphs. The first paragraph should acknowledge their situation. "
        "Subsequent paragraph(s) should suggest concrete next steps, referencing the kinds of resources available "
        "for each need (e.g., food pantries, rental assistance). Stay factual and concise."
    )

    try:
        resp = client.responses.create(
            model=GEN_MODEL,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"User story: {story}\n"
                        f"Grouped results JSON: {json.dumps(plan_payload, ensure_ascii=False)}\n"
                        f"{prompt}"
                    ),
                },
            ],
        )
        text = resp.output_text.strip()
        if text:
            return text
    except Exception as exc:
        print(">>> [generator] Failed to generate action plan:", exc)

    print(">>> [generator] Using fallback action plan narrative.")

    parts = [
        "We understand your situation and are here to help connect you with nearby support.",
    ]
    for entry in plan_payload:
        resources = entry.get("resources") or []
        if not resources:
            continue
        need_label = str(entry.get("label") or entry.get("need") or "this need").replace("-", " ")
        names = [r.get("name") for r in resources if r.get("name")]
        categories = []
        for r in resources:
            cats = r.get("categories") or []
            if isinstance(cats, list):
                categories.extend([c for c in cats if isinstance(c, str)])
        cat_fragment = ", ".join(sorted(set(categories)))
        if names:
            parts.append(
                f"For {need_label}, consider reaching out to resources such as "
                f"{', '.join(names[:2])}."
            )
        elif cat_fragment:
            parts.append(
                f"For {need_label}, there are options offering {cat_fragment}."
            )
    parts.append(
        "Please contact these organizations to confirm details like hours, eligibility, and availability."
    )
    return "\n\n".join(parts)

