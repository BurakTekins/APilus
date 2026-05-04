import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL: str = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "gemma3:4b")

# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------
EMBEDDING_MODEL: str = "google/embeddinggemma-300m"
EMBEDDING_DEVICE: str = os.environ.get("EMBEDDING_DEVICE", "cpu")

# ---------------------------------------------------------------------------
# FAISS index schema version
# Bump whenever the embedded text shape OR Document.metadata schema changes
# in a way that makes the persisted FAISS index stale.
# ---------------------------------------------------------------------------
INDEX_SCHEMA_VERSION: str = "v3-desc+lang+subpage+menu_text+contenthash_dedup"

# ---------------------------------------------------------------------------
# Corpus data files
# Paths are relative to the project root that contains 'scraper_and_data/'.
# The absolute resolution happens at runtime inside get_vector_db().
# ---------------------------------------------------------------------------
ACU_DATA_FILENAME: str = "acu_data.json"
BOLOGNA_DATA_FILENAME: str = "bologna_data.json"
CORPUS_SUBDIR: str = "scraper_and_data"

# FAISS index store location relative to project root
FAISS_INDEX_SUBDIR: str = os.path.join("RAG", "faiss_index_store")

# ---------------------------------------------------------------------------
# RAG data directory
# Absolute path to the YAML data files under RAG/data/.
# llm.py uses this to load domain dictionaries at module level.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent  # .../backend/APilus (local) | /app/APilus (container)
# Walk up until we find the sibling RAG/ directory, which sits alongside
# the backend/ folder locally (/home/.../APilus/) or at /app/ in the container.
_RAG_ROOT = next(
    p for p in [_HERE] + list(_HERE.parents)
    if (p / "RAG").is_dir()
)
RAG_DATA_DIR: Path = _RAG_ROOT / "RAG" / "data"

# ---------------------------------------------------------------------------
# Retrieval thresholds
# ---------------------------------------------------------------------------
RAG_SCORE_THRESHOLD: float = float(os.environ.get("RAG_SCORE_THRESHOLD", "12.0"))
CHUNK_SIZE: int = 800
CHUNK_OVERLAP: int = 100
