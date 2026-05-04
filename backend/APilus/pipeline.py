"""
Top-level pipeline functions: RAG path, plain path, score-based router.

Routing strategy (step 8 of RAG refactor):
  Always run retrieval first and inspect the best FAISS L2 score.
  FAISS L2: lower score = more similar.
  - best_score < RAG_SCORE_THRESHOLD  →  corpus has relevant content  →  RAG path
  - best_score >= RAG_SCORE_THRESHOLD →  corpus has nothing relevant  →  plain path
  - no docs returned / index missing  →  plain path (with warning log)

Depends on: retrieval, prompts, llm_client, normalize, rag_config.
"""

import logging

import httpx

from .llm_client import call_ollama
from .normalize import _normalize
from .prompts import build_plain_messages, build_rag_messages, format_context
from .rag_config import RAG_SCORE_THRESHOLD
from .retrieval import retrieve_with_scores

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DEPRECATED — kept for reference until score-based routing is validated
# in production.  No longer called by chat().
# ---------------------------------------------------------------------------
def is_university_query(text: str) -> bool:  # noqa: ARG001
    """Keyword-based university query detector.

    DEPRECATED: replaced by score-based routing in chat().  The function
    was prone to both under-firing (obscure program names missed) and
    over-firing (generic Turkish words like "kayıt" hit on non-university
    questions).  It is preserved here for comparison / A-B testing but is
    NOT called anywhere in the active code path.
    """
    keywords = [
        # University/institution
        "acibadem", "universite", "university",
        "fakulte", "faculty", "bolum", "department",
        "program", "kampus", "campus",
        # People/roles
        "rektor", "rector", "dekan", "dean",
        # Academic process
        "kayit", "enrollment", "mezuniyet", "graduation",
        "ders", "course", "sinav", "exam",
        "ogrenci", "student", "hoca", "akademik", "academic",
        # Bologna/accreditation
        "bologna", "akreditasyon", "accreditation",
        "mufredat", "curriculum",
        "vakif", "kurulus",
    ]
    lowered = _normalize(text)
    return any(kw in lowered for kw in keywords)


def ask_ollama_plain(prompt: str, history: list[dict] | None = None) -> str:
    """Calls Ollama directly without any RAG context, for non-university questions."""
    messages = build_plain_messages(prompt, history)
    try:
        return call_ollama(messages, max_tokens=512, temperature=0.7)
    except httpx.HTTPStatusError as e:
        logger.exception("Ollama returned %s: %s", e.response.status_code, e.response.text)
        return "LLM service is currently unavailable. Please check if Ollama is running."
    except Exception:
        logger.exception("Ollama call failed")
        return "LLM service is currently unavailable."


def ask_acibadem_ollama(
    prompt: str,
    history: list[dict] | None = None,
    docs: list | None = None,
) -> str:
    """Query Ollama with FAISS context, strictly preventing hallucination.

    If *docs* is provided (pre-fetched by the router), they are used
    directly and no second retrieval call is made.  When *docs* is None
    the function retrieves on its own — this preserves backward
    compatibility for callers that bypass chat().
    """
    if docs is None:
        # Fallback path: retrieve internally (used when called directly,
        # not via the score-based router in chat()).
        from .retrieval import retrieve  # local import to avoid circularity
        retrieved_docs = retrieve(prompt)
    else:
        retrieved_docs = docs

    if not retrieved_docs:
        return "I do not have enough information in my database to answer this."

    context = format_context(retrieved_docs)
    augmented_prompt = f"Context:\n{context}\n\nQuestion: {prompt}"
    messages = build_rag_messages(augmented_prompt, history)
    
    logger.info("========== AUGMENTED PROMPT ==========")
    logger.info("\n%s", augmented_prompt)
    logger.info("======================================")

    messages = build_rag_messages(augmented_prompt, history)

    try:
        return call_ollama(messages, max_tokens=1024)
    except httpx.HTTPStatusError as e:
        logger.exception("Ollama returned %s: %s", e.response.status_code, e.response.text)
        return "LLM service is currently unavailable. Please check if Ollama is running."
    except Exception:
        logger.exception("Ollama call failed")
        return "LLM service is currently unavailable."


def chat(prompt: str, history: list[dict] | None = None) -> str:
    """Route to RAG or plain Ollama based on FAISS retrieval scores.

    Routing logic (FAISS L2 — lower score = more similar):
      1. Attempt retrieval and inspect the best chunk score.
      2. best_score < RAG_SCORE_THRESHOLD  →  corpus is relevant  →  RAG path.
      3. best_score >= RAG_SCORE_THRESHOLD →  nothing relevant    →  plain path.
      4. No docs / index missing           →  plain path (logged as warning).

    The signature is unchanged from the keyword-based version so views.py
    requires no modification.
    """
    try:
        docs_with_scores = retrieve_with_scores(prompt)
    except RuntimeError:
        logger.warning(
            "RAG index unavailable — falling back to plain Ollama for prompt: %r",
            prompt[:80],
        )
        return ask_ollama_plain(prompt, history=history)

    if not docs_with_scores:
        logger.debug("No documents retrieved — using plain Ollama.")
        return ask_ollama_plain(prompt, history=history)

    best_score = docs_with_scores[0][1]
    logger.debug("Score-based routing: best_score=%.4f threshold=%.4f", best_score, RAG_SCORE_THRESHOLD)

    if best_score < RAG_SCORE_THRESHOLD:
        # Corpus has relevant content — pass pre-fetched docs to avoid a
        # second retrieval round-trip.  Only pass docs that cleared the
        # threshold so the RAG prompt stays clean.
        relevant_docs = [doc for doc, score in docs_with_scores if score < RAG_SCORE_THRESHOLD]
        logger.info("========== RETRIEVED CHUNKS ==========")
        for i, doc in enumerate(relevant_docs):
            # NOTE: Change 'page_content' to whatever attribute your 
            # Document object uses (e.g., 'text', 'content', etc.)
            content = getattr(doc, 'page_content', str(doc))
            # Find the score for this specific doc
            score = next(s for d, s in docs_with_scores if d == doc)
            logger.info("--- Chunk %d (Score: %.4f) ---\n%s", i + 1, score, content[:500] + "...") # Truncating to 500 chars for readability
        logger.info("======================================")
        return ask_acibadem_ollama(prompt, history=history, docs=relevant_docs)

    return ask_ollama_plain(prompt, history=history)
