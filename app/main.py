from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

from .config import print_config, NAMESPACE
from .retriever import retrieve, build_filter
from .generator import generate_card_summaries, generate_action_plan
from .needs import extract_needs, FALLBACK_RESPONSE
from .candidates import multi_need_retrieve

# Admin DS import (added in section 3)
from .datastore import ds, require_admin

print(">>> [main] Starting FastAPI app w/ UI + per-card summaries...")
print_config()

app = FastAPI(title="Community Resources RAG (Results + Admin)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/")
def home(request: Request):
    print(">>> [main] GET / (index)")
    return templates.TemplateResponse("index.html", {"request": request})

class Ask(BaseModel):
    query: str
    city: Optional[str] = None
    county: Optional[str] = None
    zip_code: Optional[str] = None
    language: Optional[str] = None
    free_only: Optional[bool] = None
    top_k: int = 8
    top_results: int = 5
    namespace: Optional[str] = None


class NeedRequest(BaseModel):
    user_story: str

@app.get("/healthz")
def healthz():
    print(">>> [main] /healthz called.")
    return {"ok": True, "namespace": NAMESPACE}

@app.post("/ask")
def ask(payload: Ask):
    print(f">>> [main] /ask called with: {payload.model_dump()}")
    filt = build_filter(
        city=payload.city, county=payload.county, zip_code=payload.zip_code,
        language=payload.language, free_only=payload.free_only
    )

    story = (payload.query or "").strip()

    if not story:
        print(">>> [main] Empty query provided.")
        return {
            "action_plan": "",
            "grouped_results": {},
            "counts": {"total_results": 0, "needs": 0},
        }

    extracted = extract_needs(story)
    needs = extracted.get("needs") if isinstance(extracted, dict) else []

    retrieve_kwargs = {
        "metadata_filters": filt,
        "namespace": payload.namespace,
    }

    display_limit = max(1, min(max(payload.top_results, 3), 5))

    grouped_results = multi_need_retrieve(
        story,
        needs,
        retrieve_fn=retrieve,
        full_top_k=payload.top_k,
        per_need_top_k=payload.top_k,
        max_candidates=max(payload.top_k, payload.top_results),
        retrieve_kwargs=retrieve_kwargs,
        grouped_top_k=display_limit,
    )

    def _deduplicate_grouped_results(grouped):
        if not isinstance(grouped, dict):
            return {}

        theme_order = list(grouped.keys())
        occurrences = {}

        for idx, theme in enumerate(theme_order):
            resources = grouped.get(theme) or []
            for resource in resources:
                rid = _resource_identifier(resource)
                if not rid:
                    continue
                try:
                    score = float(resource.get("score", 0.0))
                except (TypeError, ValueError):
                    score = 0.0
                occurrences.setdefault(rid, []).append((score, idx, theme, resource))

        best_theme_by_rid = {}
        best_resource_by_rid = {}
        for rid, entries in occurrences.items():
            entries.sort(key=lambda item: (-item[0], item[1]))
            _, _, theme, resource = entries[0]
            best_theme_by_rid[rid] = theme
            best_resource_by_rid[rid] = resource

        deduped = {}
        for theme in theme_order:
            resources = []
            for resource in grouped.get(theme) or []:
                rid = _resource_identifier(resource)
                if rid:
                    if best_theme_by_rid.get(rid) != theme:
                        continue
                    resource = best_resource_by_rid.get(rid, resource)
                resources.append(resource)
            if resources:
                deduped[theme] = resources
        return deduped

    grouped_results = _deduplicate_grouped_results(grouped_results)

    total_results = sum(len(v or []) for v in grouped_results.values())
    if total_results == 0:
        print(">>> [main] No matches found after fanout search.")
        response = {
            "action_plan": "",
            "grouped_results": grouped_results,
            "counts": {"total_results": 0, "needs": len(grouped_results)},
            "needs": extracted,
        }
        return response

    def _resource_identifier(resource: dict) -> str:
        metadata = resource.get("metadata") or {}
        rid = (
            resource.get("id")
            or metadata.get("resource_id")
            or resource.get("service_id")
        )
        if rid:
            rid_str = str(rid)
            if not resource.get("id"):
                resource["id"] = rid_str
            return rid_str
        return ""

    unique_resources = []
    seen_ids = set()
    for resources in grouped_results.values():
        for resource in resources or []:
            rid = _resource_identifier(resource)
            if rid and rid in seen_ids:
                continue
            if rid:
                seen_ids.add(rid)
            unique_resources.append(resource)

    summaries = generate_card_summaries(story, unique_resources)
    for resources in grouped_results.values():
        for resource in resources or []:
            rid = _resource_identifier(resource)
            resource["model_summary"] = summaries.get(rid, "") if rid else ""

    action_plan = generate_action_plan(story, grouped_results)

    response = {
        "action_plan": action_plan,
        "grouped_results": grouped_results,
        "counts": {"total_results": total_results, "needs": len(grouped_results)},
        "needs": extracted,
    }
    return response


@app.post("/needs")
def needs(payload: NeedRequest):
    story = (payload.user_story or "").strip()
    print(f">>> [main] /needs called. Story length: {len(story)}")
    if not story:
        empty = dict(FALLBACK_RESPONSE)
        empty["candidates"] = []
        return empty

    extracted = extract_needs(story)
    candidates = multi_need_retrieve(story, extracted.get("needs"))
    response = dict(extracted)
    response["candidates"] = candidates
    return response

# ---------- Admin UI (section 3 will add the template and JS) ----------
@app.get("/admin")
def admin_ui(request: Request):
    print(">>> [main] GET /admin")
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/api/admin/summary")
def admin_summary():
    return ds.summary()

@app.get("/api/admin/record")
def admin_record(index: int = 0):
    return ds.get_combined_by_index(index)

@app.post("/api/admin/update")
def admin_update(payload: dict, x_admin_token: str = Header(default="")):
    require_admin(x_admin_token)
    return ds.update_record(payload)

@app.post("/api/admin/save")
def admin_save(x_admin_token: str = Header(default="")):
    require_admin(x_admin_token)
    return ds.save_all()

@app.post("/api/admin/upsert")
def admin_upsert(only_dirty: bool = True, x_admin_token: str = Header(default="")):
    require_admin(x_admin_token)
    return ds.reembed_and_upsert(only_dirty=only_dirty)
