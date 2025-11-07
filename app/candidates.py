from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Sequence

from .retriever import retrieve

DEFAULT_FULL_TOP_K = 10
DEFAULT_PER_NEED_TOP_K = 10
MAX_NEEDS = 3
STORY_SLICE_CHARS = 200
MAX_CANDIDATES = 50

Hit = Dict[str, object]
Need = Dict[str, str]


def _normalize_service_id(hit: Hit) -> Optional[str]:
    metadata = hit.get("metadata") if isinstance(hit, dict) else None
    if isinstance(metadata, dict):
        service_id = (
            metadata.get("service_id")
            or metadata.get("resource_id")
            or metadata.get("id")
        )
        if service_id:
            return str(service_id)
    hit_id = hit.get("id") if isinstance(hit, dict) else None
    return str(hit_id) if hit_id else None


def _extract_name(hit: Hit) -> str:
    metadata = hit.get("metadata") if isinstance(hit, dict) else None
    if not isinstance(metadata, dict):
        return ""
    for key in ("resource_name", "name", "title", "organization_name"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _story_slice(user_story: str, limit: int = STORY_SLICE_CHARS) -> str:
    cleaned = " ".join((user_story or "").strip().split())
    return cleaned[:limit]


def _coerce_score(hit: Hit) -> float:
    try:
        return float(hit.get("score", 0.0))
    except (TypeError, ValueError):
        return 0.0

def _copy_hit(hit: Hit) -> Hit:
    """Return a shallow copy of the hit with metadata normalized to a dict."""
    copied: Hit = dict(hit)
    metadata = copied.get("metadata") if isinstance(copied.get("metadata"), dict) else {}
    copied["metadata"] = dict(metadata)
    return copied

def _add_hit(
    bucket: Dict[str, Dict[str, object]],
    hit: Hit,
    matched_need: Optional[str] = None,
) -> None:
    service_id = _normalize_service_id(hit)
    if not service_id:
        return

    current = bucket.get(service_id)
    score = _coerce_score(hit)
    name = _extract_name(hit)

    if current is None:
        bucket[service_id] = {
            "service_id": service_id,
            "name": name,
            "matched_needs": set([matched_need]) if matched_need else set(),
            "score": score,
            "hit": _copy_hit(hit),
        }
        return

    if name and not current["name"]:
        current["name"] = name

    if matched_need:
        current["matched_needs"].add(matched_need)

    if score >= current["score"]:
        current["score"] = score
        current["hit"] = _copy_hit(hit)


def multi_need_retrieve(
    user_story: str,
    needs: Optional[Iterable[Need]] = None,
    *,
    retrieve_fn: Callable[..., Sequence[Hit]] = retrieve,
    full_top_k: int = DEFAULT_FULL_TOP_K,
    per_need_top_k: int = DEFAULT_PER_NEED_TOP_K,
    per_need_limit: int = MAX_NEEDS,
    max_candidates: int = MAX_CANDIDATES,
    retrieve_kwargs: Optional[Dict[str, object]] = None,
) -> List[Dict[str, object]]:
    """Run vector searches for the full story and optionally each need."""

    story_query = (user_story or "").strip()
    if not story_query:
        return []

    buckets: Dict[str, Dict[str, object]] = {}

    retrieve_opts = dict(retrieve_kwargs or {})

    full_hits = retrieve_fn(story_query, top_k=full_top_k, **retrieve_opts)

    # Always run full story search
    full_hits = retrieve_fn(story_query, top_k=full_top_k)
    for hit in full_hits or []:
        if isinstance(hit, dict):
            _add_hit(buckets, hit)

    needs = list(needs or [])
    if not needs:
        return _finalize_candidates(buckets, max_candidates)

    context_slice = _story_slice(user_story)
    for need in needs[:per_need_limit]:
        if not isinstance(need, dict):
            continue
        query = (need.get("query") or "").strip()
        slug = (need.get("slug") or "").strip()
        if not query:
            continue
        per_need_query = query
        if context_slice:
            per_need_query = f"{query} Context: {context_slice}"
        hits = retrieve_fn(per_need_query, top_k=per_need_top_k, **retrieve_opts)
        for hit in hits or []:
            if isinstance(hit, dict):
                _add_hit(buckets, hit, matched_need=slug or None)

    return _finalize_candidates(buckets, max_candidates)


def _finalize_candidates(
    buckets: Dict[str, Dict[str, object]],
    max_candidates: int,
) -> List[Dict[str, object]]:
    candidates: List[Dict[str, object]] = []
    for entry in buckets.values():
        matched = entry.get("matched_needs", set())
        if isinstance(matched, set):
            matched_list = sorted(matched)
        else:
            matched_list = []
        hit = entry.get("hit") if isinstance(entry.get("hit"), dict) else {}
        candidate: Dict[str, object] = dict(hit)
        candidate.setdefault("metadata", {})
        candidate["service_id"] = entry.get("service_id")
        candidate["name"] = entry.get("name", "")
        candidate["score"] = entry.get("score", candidate.get("score", 0.0))
        candidate["matched_needs"] = matched_list
        candidates.append(candidate)

    candidates.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
    return candidates[:max_candidates]
