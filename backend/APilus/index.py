import hashlib
import logging
import os
import shutil
from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .rag_config import (
    INDEX_SCHEMA_VERSION,
    EMBEDDING_MODEL,
    EMBEDDING_DEVICE,
    CORPUS_SUBDIR,
    ACU_DATA_FILENAME,
    BOLOGNA_DATA_FILENAME,
    FAISS_INDEX_SUBDIR,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)
from .loader import _load_documents

logger = logging.getLogger(__name__)

# Bumped whenever the embedded text shape OR Document.metadata schema
# changes in a way that makes the persisted FAISS index stale. This is
# concatenated with the data-file fingerprint and stored in
# faiss_index_store/version.txt; a mismatch triggers a rebuild.
_INDEX_SCHEMA_VERSION = INDEX_SCHEMA_VERSION

_vector_db = None  # module-level singleton


def _index_fingerprint(json_files: list[str]) -> str:
    """Compose a fingerprint for the persisted FAISS index.

    Combines the schema version (bumped in code whenever the embedded
    text shape or metadata schema changes) with each data file's path,
    size, and mtime. Cheap to compute on every startup; reliably detects
    when the data has been re-scraped or the loader logic has been
    revised. We deliberately avoid SHA-256 of multi-MB JSONs to keep
    cold-start latency low.
    """
    parts = [_INDEX_SCHEMA_VERSION]
    for path in json_files:
        try:
            st = os.stat(path)
            parts.append(f"{path}:{st.st_size}:{int(st.st_mtime)}")
        except OSError:
            parts.append(f"{path}:missing")
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"{_INDEX_SCHEMA_VERSION}|{digest}"


def _resolve_paths() -> tuple[Path, Path, list[str]]:
    """Resolve BASE_DIR, INDEX_PATH, and json_files from the current file location."""
    current_path = Path(__file__).resolve().parent

    BASE_DIR = None
    for path in [current_path] + list(current_path.parents):
        if (path / "scraper_and_data").exists():
            BASE_DIR = path
            break
    if BASE_DIR is None:
        raise RuntimeError("Could not find project root containing 'scraper_and_data' folder.")

    INDEX_PATH = BASE_DIR / FAISS_INDEX_SUBDIR
    json_files = [
        str(BASE_DIR / CORPUS_SUBDIR / ACU_DATA_FILENAME)
    ]
    return BASE_DIR, INDEX_PATH, json_files

# str(BASE_DIR / CORPUS_SUBDIR / BOLOGNA_DATA_FILENAME)

def build_index() -> None:
    """Build (or force-rebuild) the FAISS index and persist it to disk.

    Intended to be called from the ``build_rag_index`` management command —
    NOT from inside a request-handling worker.  Invalidates any stale
    on-disk index via the fingerprint mechanism before writing the new one.
    """
    global _vector_db

    _BASE_DIR, INDEX_PATH, json_files = _resolve_paths()
    VERSION_FILE = INDEX_PATH / "version.txt"
    expected_fingerprint = _index_fingerprint(json_files)

    # Wipe whatever is on disk so save_local writes a clean index.
    if INDEX_PATH.exists():
        logger.info("Removing existing FAISS index at %s before rebuild.", INDEX_PATH)
        shutil.rmtree(INDEX_PATH, ignore_errors=True)

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={'device': EMBEDDING_DEVICE},
    )

    docs = []
    for file in json_files:
        docs.extend(_load_documents(file))

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = text_splitter.split_documents(docs)

    print(f"Building NEW Vector DB with {len(chunks)} chunks...")
    db = FAISS.from_documents(chunks, embeddings)
    db.save_local(str(INDEX_PATH))
    try:
        VERSION_FILE.write_text(expected_fingerprint, encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to write FAISS version sentinel: %s", exc)
    print(f"Vector DB saved to {INDEX_PATH}")

    # Refresh the in-process singleton so the same worker can use it immediately.
    _vector_db = db


def get_vector_db():
    """Load the FAISS index from disk and return it (load-only).

    Raises ``RuntimeError`` if the index has not been built yet.  Build it
    with::

        python manage.py build_rag_index
    """
    global _vector_db
    if _vector_db is not None:
        return _vector_db

    _BASE_DIR, INDEX_PATH, json_files = _resolve_paths()
    VERSION_FILE = INDEX_PATH / "version.txt"
    expected_fingerprint = _index_fingerprint(json_files)

    # Require an up-to-date index to exist on disk.
    if not (INDEX_PATH.exists() and (INDEX_PATH / "index.faiss").exists()):
        raise RuntimeError(
            "RAG index not found. Run: python manage.py build_rag_index"
        )

    on_disk_fingerprint = ""
    if VERSION_FILE.exists():
        try:
            on_disk_fingerprint = VERSION_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            on_disk_fingerprint = ""

    if on_disk_fingerprint != expected_fingerprint:
        raise RuntimeError(
            f"RAG index is stale (fingerprint mismatch). "
            f"Run: python manage.py build_rag_index"
        )

    print("Loading existing Vector DB from disk...")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={'device': EMBEDDING_DEVICE},
    )
    _vector_db = FAISS.load_local(
        str(INDEX_PATH),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    return _vector_db
