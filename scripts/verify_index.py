import os
from dotenv import load_dotenv
from pinecone import Pinecone

from app.config import PINECONE_API_KEY, PINECONE_INDEX_NAME, NAMESPACE

load_dotenv()

def main():
    print(">>> [verify_index] Checking index connection and namespace...")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(name=PINECONE_INDEX_NAME)

    # Simple “ping” query with a tiny vector to confirm failure modes clearly
    # (You normally shouldn't query with random vectors—this is just a connectivity check.)
    try:
        print(f">>> [verify_index] Describing a query attempt in namespace '{NAMESPACE}'...")
        res = index.query(
            namespace=NAMESPACE,
            vector=[0.0] * 1536,  # Replace 1536 if your index dimension differs
            top_k=1,
            include_metadata=False
        )
        print(">>> [verify_index] Query executed (not meaningful). Usage:", getattr(res, "usage", {}))
    except Exception as e:
        print(">>> [verify_index] Expected error if dimension mismatched or permissions invalid.")
        print(">>> [verify_index] ERROR:", e)

if __name__ == "__main__":
    main()
