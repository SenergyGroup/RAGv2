import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "community-resources")
NAMESPACE = os.getenv("NAMESPACE", "__default__")

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
GEN_MODEL = os.getenv("GEN_MODEL", "gpt-4.1-mini")

def print_config():
    print(">>> [config] Loaded environment variables.")
    print(f">>> [config] PINECONE_INDEX_NAME = {PINECONE_INDEX_NAME}")
    print(f">>> [config] NAMESPACE = {NAMESPACE}")
    print(f">>> [config] EMBED_MODEL = {EMBED_MODEL}")
    print(f">>> [config] GEN_MODEL = {GEN_MODEL}")
    print(f">>> [config] OPENAI_API_KEY present? {'yes' if bool(OPENAI_API_KEY) else 'no'}")
    print(f">>> [config] PINECONE_API_KEY present? {'yes' if bool(PINECONE_API_KEY) else 'no'}")
