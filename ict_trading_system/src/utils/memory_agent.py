import chromadb
from chromadb.config import Settings
from openai import OpenAI
import os
import requests
from ict_trading_system.config import settings
import logging

# Initialize ChromaDB client (local, persistent)
chroma_client = chromadb.Client(Settings(
    persist_directory=".chromadb"
))

# Create or get a collection for trade memory
collection = chroma_client.get_or_create_collection("trade_memory")


# Embedding utility using OpenAI or Gemini
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or getattr(settings, 'OPENAI_API_KEY', None)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or getattr(settings, 'GEMINI_API_KEY', None)
EMBEDDING_PROVIDER_ENV = os.getenv("EMBEDDING_PROVIDER")
EMBEDDING_PROVIDER_SETTINGS = getattr(settings, 'EMBEDDING_PROVIDER', None)
print(f"[MEMORY AGENT][IMPORT DEBUG] ENV: EMBEDDING_PROVIDER={EMBEDDING_PROVIDER_ENV} | GEMINI_API_KEY set={bool(GEMINI_API_KEY)} | OPENAI_API_KEY set={bool(OPENAI_API_KEY)}")
print(f"[MEMORY AGENT][IMPORT DEBUG] SETTINGS: EMBEDDING_PROVIDER={EMBEDDING_PROVIDER_SETTINGS}")
logger = logging.getLogger(__name__)
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

def get_openai_embedding(text: str) -> list:
    logger.info("[MEMORY AGENT] Using OpenAI for embeddings.")
    resp = openai_client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return resp.data[0].embedding

def get_gemini_embedding(text: str) -> list:
    logger.info("[MEMORY AGENT] Using Gemini for embeddings.")
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set.")
    url = "https://generativelanguage.googleapis.com/v1beta/models/embedding-001:embedContent"
    headers = {"Content-Type": "application/json", "X-goog-api-key": GEMINI_API_KEY}
    data = {"content": {"parts": [{"text": text}]}}
    resp = requests.post(url, headers=headers, json=data, timeout=10)
    resp.raise_for_status()
    result = resp.json()
    # Gemini returns embedding as a flat list under 'embedding'
    return result.get("embedding", {}).get("values", [])

def get_embedding(text: str) -> list:
    print(f"[MEMORY AGENT][CALL DEBUG] ENV: EMBEDDING_PROVIDER={os.getenv('EMBEDDING_PROVIDER')} | GEMINI_API_KEY set={bool(os.getenv('GEMINI_API_KEY'))} | OPENAI_API_KEY set={bool(os.getenv('OPENAI_API_KEY'))}")
    print(f"[MEMORY AGENT][CALL DEBUG] SETTINGS: EMBEDDING_PROVIDER={getattr(settings, 'EMBEDDING_PROVIDER', None)}")
    # FORCE GEMINI for debug
    provider = 'gemini'
    print(f"[MEMORY AGENT][FORCE DEBUG] Forcing provider to: {provider}")
    if provider == 'gemini':
        if not GEMINI_API_KEY:
            logger.error("[MEMORY AGENT] GEMINI_API_KEY not set, cannot use Gemini for embeddings.")
            raise RuntimeError("GEMINI_API_KEY not set.")
        return get_gemini_embedding(text)
    elif provider == 'openai':
        if not openai_client:
            logger.error("[MEMORY AGENT] OpenAI client not initialized, cannot use OpenAI for embeddings.")
            raise RuntimeError("OpenAI client not initialized.")
        return get_openai_embedding(text)
    else:
        logger.error(f"[MEMORY AGENT] Invalid EMBEDDING_PROVIDER: '{provider}'. Must be 'openai' or 'gemini'.")
        raise RuntimeError(f"Invalid EMBEDDING_PROVIDER: '{provider}'. Must be 'openai' or 'gemini'.")

def add_to_memory(id: str, text: str, metadata: dict = None):
    embedding = get_embedding(text)
    collection.add(
        ids=[id],
        embeddings=[embedding],
        documents=[text],
        metadatas=[metadata or {}]
    )

def query_memory(query: str, n_results: int = 5):
    embedding = get_embedding(query)
    results = collection.query(
        query_embeddings=[embedding],
        n_results=n_results
    )
    return results
