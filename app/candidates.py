from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set

from .retriever import retrieve

DEFAULT_FULL_TOP_K = 10
DEFAULT_PER_NEED_TOP_K = 10
DEFAULT_GROUPED_RESULTS_PER_NEED = 5
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
    grouped_top_k: Optional[int] = None,
) -> Dict[str, List[Dict[str, object]]]:
    """Run vector searches for the full story and optionally each need."""

    story_query = (user_story or "").strip()
    if not story_query:
        return {}

    buckets: Dict[str, Dict[str, object]] = {}

    retrieve_opts = dict(retrieve_kwargs or {})

    full_hits = retrieve_fn(story_query, top_k=full_top_k, **retrieve_opts)
    for hit in full_hits or []:
        if isinstance(hit, dict):
            _add_hit(buckets, hit)

    needs = list(needs or [])
    grouped_limit = max(
        1, int(grouped_top_k) if grouped_top_k else DEFAULT_GROUPED_RESULTS_PER_NEED
    )

    if not needs:
        candidates = _finalize_candidates(buckets, max_candidates)
        limit = min(grouped_limit, len(candidates))
        if limit == 0:
            return {}
        return {"general": candidates[:limit]}

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

    candidates = _finalize_candidates(buckets, max_candidates)
    return _group_candidates_by_need(candidates, needs, grouped_limit)


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


def _group_candidates_by_need(
    candidates: Sequence[Dict[str, object]],
    needs: Sequence[Need],
    per_need_limit: int,
) -> Dict[str, List[Dict[str, object]]]:
    per_need_limit = max(1, int(per_need_limit or DEFAULT_GROUPED_RESULTS_PER_NEED))
    groups: Dict[str, List[Dict[str, object]]] = {}
    seen: Dict[str, Set[str]] = {}

    ordered_needs: List[str] = []
    for need in needs:
        if not isinstance(need, dict):
            continue
        slug = (need.get("slug") or "").strip()
        if not slug:
            continue
        if slug not in groups:
            groups[slug] = []
            seen[slug] = set()
            ordered_needs.append(slug)

    if not ordered_needs:
        limit = min(per_need_limit, len(candidates))
        if limit == 0:
            return {}
        return {"general": list(candidates[:limit])}

    unmatched: List[Dict[str, object]] = []

    for candidate in candidates:
        matched_needs = [
            slug for slug in candidate.get("matched_needs", []) if slug in groups
        ]
        service_id = str(candidate.get("service_id") or candidate.get("id") or "")

        if matched_needs:
            for slug in matched_needs:
                if len(groups[slug]) >= per_need_limit:
                    continue
                if service_id and service_id in seen[slug]:
                    continue
                groups[slug].append(candidate)
                if service_id:
                    seen[slug].add(service_id)
        else:
            unmatched.append(candidate)

    for candidate in unmatched:
        service_id = str(candidate.get("service_id") or candidate.get("id") or "")
        for slug in ordered_needs:
            if len(groups[slug]) >= per_need_limit:
                continue
            if service_id and service_id in seen[slug]:
                continue
            groups[slug].append(candidate)
            if service_id:
                seen[slug].add(service_id)
            break

    for slug in ordered_needs:
        groups.setdefault(slug, [])

    return groups
