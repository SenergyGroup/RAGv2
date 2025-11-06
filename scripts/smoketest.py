import os
from dotenv import load_dotenv

load_dotenv()

# Quick smoke test without spinning up FastAPI
from app.retriever import retrieve, build_filter
from app.generator import generate_answer

def main():
    print(">>> [smoketest] Starting smoke test...")

    q = "Where can I get free food in the area?"
    filt = build_filter(city="Waterloo")

    hits = retrieve(q, top_k=8, metadata_filters=filt)
    print(f">>> [smoketest] Got {len(hits)} hits.")
    for i, h in enumerate(hits[:3], 1):
        md = h["metadata"]
        print(f"    [{i}] {md.get('resource_name')} — {md.get('organization_name')}  score={h['score']}")
        print(f"        {md.get('city')}, {md.get('zip_code')}  langs={md.get('languages')}")

    if hits:
        print(">>> [smoketest] Generating answer from top 5...")
        answer = generate_answer(q, hits[:5])
        print("\n=== Model Answer ===\n")
        print(answer)
    else:
        print(">>> [smoketest] No hits; adjust filters or query.")

if __name__ == "__main__":
    main()
