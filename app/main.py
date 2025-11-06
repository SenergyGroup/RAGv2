from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

from .config import print_config, NAMESPACE
from .retriever import retrieve, build_filter
from .generator import generate_card_summaries
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

    hits = retrieve(payload.query, top_k=payload.top_k, metadata_filters=filt, namespace=payload.namespace)
    if not hits:
        print(">>> [main] No matches found.")
        return {"results": [], "counts": {"retrieved": 0, "shown": 0}}

    # Bound the number of cards we display by both top_results and top_k
    shown = max(1, min(payload.top_results, payload.top_k, len(hits)))
    to_show = hits[:shown]
    print(f">>> [main] Displaying {shown} of {len(hits)} retrieved results.")

    # Generate per-card summaries for items we actually show
    summaries = generate_card_summaries(payload.query, to_show)
    for r in to_show:
        rid = (r.get("id") or (r.get("metadata") or {}).get("resource_id") or "")
        r["model_summary"] = summaries.get(rid, "")

    return {"results": to_show, "counts": {"retrieved": len(hits), "shown": shown}}


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
