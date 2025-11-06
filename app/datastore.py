import os, json, time, traceback
from typing import Dict, Any, List
import orjson

from pinecone import Pinecone
from openai import OpenAI

from .config import (
    OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_INDEX_NAME, NAMESPACE, EMBED_MODEL
)

# --------- simple env-driven security ----------
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

def require_admin(token: str):
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise PermissionError("ADMIN token missing or invalid")

# --------- paths ----------
DATA_DIR = os.getenv("DATA_DIR", "data")
DOCS_PATH = os.getenv("DOCS_PATH", os.path.join(DATA_DIR, "prepared_documents.jsonl"))
META_PATH = os.getenv("META_PATH", os.path.join(DATA_DIR, "prepared_metadata.jsonl"))
PROG_PATH = os.getenv("PROG_PATH", os.path.join(DATA_DIR, "progress.json"))

os.makedirs(DATA_DIR, exist_ok=True)

def _coalesce(*vals):
    for v in vals:
        if v is None:
            continue
        if isinstance(v, str):
            if v.strip():
                return v
            else:
                continue
        if isinstance(v, (list, dict)) and not v:
            continue
        return v
    return None

def _as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        parts = [p.strip() for p in v.split(",")]
        return [p for p in parts if p]
    return [v]

def _flatten_metadata(md: dict) -> dict:
    """
    Turn potentially nested metadata (contact/location/hours/service_details)
    into flat fields the Admin UI expects. Keep originals if they already exist.
    """
    md = md or {}
    out = dict(md)  # start with a shallow copy

    # Contact
    contact = md.get("contact", {}) or {}
    out["phone"]   = _coalesce(md.get("phone"),   contact.get("phone"))
    out["website"] = _coalesce(md.get("website"), contact.get("website"))
    out["email"]   = _coalesce(md.get("email"),   contact.get("email"))

    # Location
    loc = md.get("location", {}) or {}
    out["full_address"] = _coalesce(md.get("full_address"), loc.get("full_address"))
    out["street"]       = _coalesce(md.get("street"),       loc.get("street"))
    out["city"]         = _coalesce(md.get("city"),         loc.get("city"))
    out["state"]        = _coalesce(md.get("state"),        loc.get("state"))
    out["zip_code"]     = _coalesce(md.get("zip_code"),     loc.get("zip_code"))
    out["county"]       = _coalesce(md.get("county"),       loc.get("county"))

    # Hours
    hours = md.get("hours", {}) or {}
    out["hours_notes"] = _coalesce(md.get("hours_notes"), hours.get("notes"))

    # Service details
    sd = md.get("service_details", {}) or {}
    out["fees"]        = _coalesce(md.get("fees"),        sd.get("fees"))
    out["eligibility"] = _coalesce(md.get("eligibility"), sd.get("eligibility"))
    out["application_process"] = _coalesce(md.get("application_process"), sd.get("application_process"))
    out["languages"]   = _as_list(_coalesce(md.get("languages"), sd.get("languages")))

    # Categories
    out["categories"] = _as_list(md.get("categories"))

    # Common IDs / provenance
    out["resource_id"] = _coalesce(md.get("resource_id"), md.get("id"))
    out["last_updated"] = md.get("last_updated")
    out["source_file"]  = md.get("source_file")

    # Ensure expected flat keys exist (even if None) so front-end can render 'Unknown'
    expected_keys = [
        "resource_name", "organization_name", "categories", "fees", "languages",
        "hours_notes", "street", "city", "state", "zip_code", "county",
        "phone", "website", "email", "last_updated", "source_file", "resource_id", "full_address",
        "eligibility", "application_process"
    ]
    for k in expected_keys:
        out.setdefault(k, None)
    return out



def _read_jsonl(path: str) -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(path): return {}
    out = {}
    with open(path, "rb") as f:
        for line in f:
            if not line.strip(): continue
            obj = orjson.loads(line)
            rid = str(obj.get("id") or obj.get("resource_id"))
            if rid: out[rid] = obj
    return out

def _write_jsonl(path: str, rows: List[Dict[str, Any]]):
    with open(path, "wb") as f:
        for row in rows:
            f.write(orjson.dumps(row))
            f.write(b"\n")

def _read_progress() -> Dict[str, Any]:
    if not os.path.exists(PROG_PATH): return {"reviewed": [], "dirty": []}
    with open(PROG_PATH, "rb") as f: return orjson.loads(f.read())

def _write_progress(p: Dict[str, Any]):
    with open(PROG_PATH, "wb") as f: f.write(orjson.dumps(p))

class DataStore:
    def __init__(self):
        print(">>> [datastore] Loading JSONL datasets...")
        self.docs = _read_jsonl(DOCS_PATH)   # id -> {id,text}
        self.meta = _read_jsonl(META_PATH)   # id -> {...}
        self.ids = sorted(set(self.docs) | set(self.meta), key=lambda x: str(x))
        self.progress = _read_progress()
        self.dirty = set(self.progress.get("dirty", []))
        self.reviewed = set(self.progress.get("reviewed", []))
        print(f">>> [datastore] Loaded {len(self.ids)} ids. docs={len(self.docs)} meta={len(self.meta)}")

        # clients
        self.pc = Pinecone(api_key=PINECONE_API_KEY)
        self.index = self.pc.Index(PINECONE_INDEX_NAME)
        self.oai = OpenAI(api_key=OPENAI_API_KEY)

    # ---------- public helpers ----------
    def summary(self) -> Dict[str, Any]:
        return {
            "total": len(self.ids),
            "reviewed_count": len(self.reviewed),
            "dirty_count": len(self.dirty),
            "docs_path": DOCS_PATH,
            "meta_path": META_PATH,
            "progress_path": PROG_PATH
        }

    def get_combined_by_index(self, index: int) -> Dict[str, Any]:
        index = max(0, min(index, len(self.ids)-1))
        rid = self.ids[index]

        # Local on-disk
        doc_local = self.docs.get(rid, {"id": rid, "text": ""})
        md_local  = self.meta.get(rid, {"id": rid})

        # Pinecone (for hydration/fallback)
        pine_doc_text = None
        pine_md = {}
        try:
            fetched = self.index.fetch(ids=[rid], namespace=NAMESPACE or "")
            vec = (getattr(fetched, "vectors", None) or {}).get(rid)
            # Some SDKs return dict; some return object
            if isinstance(vec, dict):
                pine_md = vec.get("metadata") or {}
            else:
                pine_md = getattr(vec, "metadata", {}) or {}
            pine_doc_text = (pine_md or {}).get("text") or None
        except Exception as e:
            print(f">>> [datastore] Pinecone fetch failed for id={rid}: {e}")

        # Merge pinecone + local, then FLATTEN
        merged_md_raw = {**(pine_md or {}), **(md_local or {})}  # local overrides
        merged_md = _flatten_metadata(merged_md_raw)

        merged_doc_text = _coalesce(doc_local.get("text"), pine_doc_text, "")

        # Fill 'Unknown' for any empty input fields (so UI shows something editable)
        def _u(v): return v if (v is not None and (not isinstance(v, str) or v.strip())) else "Unknown"
        for k in list(merged_md.keys()):
            if k in ("categories", "languages"):  # lists handled separately in UI
                merged_md[k] = merged_md[k] if merged_md[k] else []
            else:
                merged_md[k] = _u(merged_md[k])

        out = {
            "index": index,
            "id": rid,
            "reviewed": rid in self.reviewed,
            "dirty": rid in self.dirty,
            "document": {"id": rid, "text": merged_doc_text or "Unknown"},
            "metadata": merged_md,
            "total": len(self.ids)
        }
        return out


    def update_record(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        rid = str(payload.get("id"))
        if not rid: return {"ok": False, "error": "id required"}
        print(f">>> [datastore] Updating record {rid}")
        # update doc text
        text = (payload.get("text") or "").strip()
        if rid not in self.docs: self.docs[rid] = {"id": rid, "text": text}
        else: self.docs[rid]["text"] = text
        # update metadata (store everything except 'text' & 'document')
        md = payload.get("metadata") or {}
        md["id"] = rid
        self.meta[rid] = md
        # update progress flags
        if payload.get("reviewed") is True: self.reviewed.add(rid)
        self.dirty.add(rid)
        self._flush_progress()
        return {"ok": True, "id": rid, "dirty_count": len(self.dirty), "reviewed_count": len(self.reviewed)}

    def save_all(self) -> Dict[str, Any]:
        print(">>> [datastore] Saving JSONL files...")
        _write_jsonl(DOCS_PATH, [self.docs[i] for i in self.ids])
        _write_jsonl(META_PATH, [self.meta.get(i, {"id": i}) for i in self.ids])
        self._flush_progress()
        return {"ok": True, "docs_path": DOCS_PATH, "meta_path": META_PATH}

    def reembed_and_upsert(self, only_dirty: bool = True) -> Dict[str, Any]:
        targets = list(self.dirty) if only_dirty else list(self.ids)
        print(f">>> [datastore] Upserting {len(targets)} items to Pinecone (only_dirty={only_dirty})")
        count = 0; errors = 0
        for rid in targets:
            try:
                text = self.docs.get(rid, {}).get("text", "")
                md   = self.meta.get(rid, {})
                if not text:
                    print(f"!!! [datastore] Skipping {rid} (no text)")
                    continue

                emb = self.oai.embeddings.create(model=EMBED_MODEL, input=text).data[0].embedding
                vector = {
                    "id": rid,
                    "values": emb,
                    "metadata": md | {"text": text}
                }
                self.index.upsert(vectors=[vector], namespace=NAMESPACE or "")
                count += 1
            except Exception as e:
                print(f"!!! [datastore] ERROR upserting {rid}: {e}")
                errors += 1

        if only_dirty:
            self.dirty.clear()
            self._flush_progress()
        return {"ok": True, "upserted": count, "errors": errors}

    # ---------- internal ----------
    def _flush_progress(self):
        _write_progress({"reviewed": sorted(self.reviewed), "dirty": sorted(self.dirty)})

# singleton
ds = DataStore()
