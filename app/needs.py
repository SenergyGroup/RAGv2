import json
import re
from typing import Callable, Dict, List, Tuple

from openai import OpenAI

from .config import OPENAI_API_KEY, GEN_MODEL

print(">>> [needs] Initializing OpenAI client for need extraction...")
_client = OpenAI(api_key=OPENAI_API_KEY)

FALLBACK_RESPONSE = {"needs": [], "confidence": 0.0}

SYSTEM_PROMPT = (
    "You extract the key information needs from short user stories about community assistance. "
    "Produce compact, factual labels only when the story clearly expresses a need."
)


def build_needs_prompt(user_story: str) -> Tuple[List[Dict[str, str]], Dict]:
    """Return the chat messages and JSON schema for the needs request."""
    schema = {
        "name": "needs_response",
        "schema": {
            "type": "object",
            "properties": {
                "needs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "slug": {"type": "string"},
                            "query": {"type": "string"},
                        },
                        "required": ["slug", "query"],
                        "additionalProperties": False,
                    },
                    "minItems": 0,
                    "maxItems": 5,
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
            },
            "required": ["needs", "confidence"],
            "additionalProperties": False,
        },
    }

    user_prompt = (
        "You will receive a single user story describing a person's situation. "
        "Identify up to five distinct, concrete information needs the story expresses. "
        "Return STRICT JSON only. Each need must have:\n"
        "- `slug`: 2-5 words, lowercase kebab-case label summarizing the need.\n"
        "- `query`: a short retrieval query (<= 12 words) you would use to look up resources.\n"
        "If the story is vague or you are unsure, return an empty list and confidence 0. "
        "Do not include explanations."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"{user_prompt}\n\nUser story: {user_story.strip()}\nRespond with strict JSON only.",
        },
        {"role": "assistant", "content": "Reminder: Output JSON with 'needs' and 'confidence'."},
    ]

    return messages, schema


def _call_model(messages: List[Dict[str, str]], schema: Dict) -> str:
    response = _client.responses.create(
        model=GEN_MODEL,
        input=messages,
        response_format={"type": "json_schema", "json_schema": schema},
    )
    return response.output_text


def _slugify(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:60]


def _sanitize_payload(data: Dict) -> Dict:
    needs = []
    raw_needs = data.get("needs") if isinstance(data, dict) else []
    if isinstance(raw_needs, list):
        for item in raw_needs:
            if not isinstance(item, dict):
                continue
            slug = item.get("slug") or ""
            query = (item.get("query") or "").strip()
            if not query:
                continue
            slug = _slugify(slug) or _slugify(query)
            if not slug:
                continue
            needs.append({"slug": slug, "query": query})
            if len(needs) >= 5:
                break

    conf = 0.0
    try:
        conf = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))

    return {"needs": needs, "confidence": conf}


def parse_needs_response(raw_text: str) -> Dict:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError("Model response was not valid JSON") from exc

    result = _sanitize_payload(data)
    if not isinstance(result.get("needs"), list) or "confidence" not in result:
        raise ValueError("Parsed response missing required fields")
    return result


def extract_needs(user_story: str, response_fetcher: Callable[[List[Dict[str, str]], Dict], str] | None = None) -> Dict:
    """Call the model and return structured needs. Falls back on failure."""
    response_fetcher = response_fetcher or _call_model
    messages, schema = build_needs_prompt(user_story)

    try:
        raw_text = response_fetcher(messages, schema)
        parsed = parse_needs_response(raw_text)
        print(f">>> [needs] Parsed {len(parsed['needs'])} needs with confidence {parsed['confidence']:.2f}")
        return parsed
    except Exception as exc:
        print(f">>> [needs] Failed to extract needs: {exc}")
        return dict(FALLBACK_RESPONSE)
