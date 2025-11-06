import json
import traceback
from typing import Any, Dict, List, Optional

from openai import OpenAI
from pinecone import Pinecone

from .config import (
    OPENAI_API_KEY, PINECONE_API_KEY,
    PINECONE_INDEX_NAME, NAMESPACE, EMBED_MODEL
)

# Initialize clients
print(">>> [retriever] Initializing OpenAI and Pinecone clients...")
oai = OpenAI(api_key=OPENAI_API_KEY)  # OpenAI Python SDK, Responses/Embeddings APIs
pc = Pinecone(api_key=PINECONE_API_KEY)  # Pinecone Python SDK (modern)  :contentReference[oaicite:6]{index=6}

# Get index handle (by name)
index = pc.Index(name=PINECONE_INDEX_NAME)
print(f">>> [retriever] Using Pinecone index: {PINECONE_INDEX_NAME}")

def embed_query(text: str) -> List[float]:
    """Embed the user query with the same model used to build the index."""
    print(f">>> [retriever] Embedding query: {text[:120]}...")
    # OpenAI Embeddings API call  :contentReference[oaicite:7]{index=7}
    e = oai.embeddings.create(model=EMBED_MODEL, input=text)
    vec = e.data[0].embedding
    print(f">>> [retriever] Embedding length: {len(vec)} (should match index dimension)")
    return vec

def build_filter(
    city: Optional[str] = None,
    county: Optional[str] = None,
    zip_code: Optional[str] = None,
    language: Optional[str] = None,
    free_only: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Construct a Pinecone metadata filter.
    Pinecone supports operators like $eq, $in, $and, $or; arrays can be matched with bare field or $in.  :contentReference[oaicite:8]{index=8}
    """
    f: Dict[str, Any] = {}

    # strings (exact matches)
    if city:
        f["city"] = {"$eq": city}
    if county:
        f["county"] = {"$eq": county}
    if zip_code:
        f["zip_code"] = {"$eq": zip_code}

    # arrays: "languages": ["English","Spanish"] can be matched with a bare value or $in
    if language:
        # either {"languages": "Spanish"} or {"languages": {"$in": ["Spanish"]}}
        f["languages"] = language

    if free_only is True:
        f["free_or_low_cost"] = {"$eq": True}

    print(f">>> [retriever] Built metadata filter: {json.dumps(f)}")
    return f

def retrieve(
    user_query: str,
    top_k: int = 8,
    metadata_filters: Optional[Dict[str, Any]] = None,
    namespace: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Vector search in Pinecone with optional metadata filter.
    Uses the Query API to return matches with metadata.  :contentReference[oaicite:9]{index=9}
    """
    try:
        qvec = embed_query(user_query)
        ns = namespace or NAMESPACE
        print(f">>> [retriever] Querying Pinecone (namespace='{ns}', top_k={top_k}) ...")

        res = index.query(
            namespace=ns,
            vector=qvec,
            top_k=top_k,
            filter=metadata_filters or {},
            include_values=False,
            include_metadata=True
        )

        matches = getattr(res, "matches", []) or []
        print(f">>> [retriever] Retrieved {len(matches)} matches.")
        if matches:
            print(">>> [retriever] Top match (debug):")
            md = matches[0].metadata or {}
            print("    id:", matches[0].id, "score:", matches[0].score)
            print("    name/org:", md.get("resource_name"), "/", md.get("organization_name"))
            print("    city/zip:", md.get("city"), "/", md.get("zip_code"))

        # Normalize
        results = [{"id": m.id, "score": m.score, "metadata": m.metadata} for m in matches]
        return results

    except Exception as e:
        print(">>> [retriever] ERROR during retrieve():", e)
        print(traceback.format_exc())
        return []
