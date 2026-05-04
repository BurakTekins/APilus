"""
FAISS retrieval: filter ladder with MMR fallback, score thresholding,
and program reranking.

Depends on: rag_config (RAG_SCORE_THRESHOLD), query (_pick_k,
_extract_filters, _normalize_for_search), index (get_vector_db),
normalize (_normalize for reranking).

Score semantics (FAISS L2): lower score = more similar.
  retrieve_with_scores() returns raw (doc, score) pairs — NO threshold
  filtering — so the caller can apply routing logic on the best score.
  retrieve() applies RAG_SCORE_THRESHOLD and returns docs only, for
  callers that already decided to use the RAG path.
"""

import logging

from .rag_config import RAG_SCORE_THRESHOLD
from .normalize import _normalize
from .query import _pick_k, _extract_filters, _normalize_for_search
from .index import get_vector_db

logger = logging.getLogger(__name__)


def _filter_ladder(active: dict) -> list[dict | None]:
    """Return a sequence of progressively-relaxed filter dicts to try in order.

    Strategy: full filters -> source-only (drop subpage) -> no filter.
    This ensures an over-narrow subpage constraint degrades gracefully
    rather than returning an empty result set.
    """
    rungs: list[dict | None] = []
    if active:
        rungs.append(dict(active))
        if "subpage" in active:
            relaxed = {k: v for k, v in active.items() if k != "subpage"}
            if relaxed:
                rungs.append(relaxed)
        rungs.append(None)
    else:
        rungs.append(None)
    return rungs


def _run_scored_search(prompt: str) -> tuple[list, str | None]:
    """Run MMR (with similarity fallback) and return (scored_pairs, detected_program).

    scored_pairs is a list of (Document, float) — raw FAISS L2 scores,
    NOT filtered by RAG_SCORE_THRESHOLD.  The caller decides what to do
    with the scores.
    """
    vector_db = get_vector_db()
    k = _pick_k(prompt)
    filters, detected_program = _extract_filters(prompt)

    # Normalize the query for retrieval only; the LLM still receives the
    # original prompt so it can answer in the user's exact wording/language.
    search_query = _normalize_for_search(prompt)

    scored: list = []
    try:
        query_vector = vector_db.embedding_function.embed_query(search_query)
        for flt in _filter_ladder(filters):
            scored = vector_db.max_marginal_relevance_search_with_score_by_vector(
                query_vector,
                k=k,
                fetch_k=max(k * 4, 20),
                lambda_mult=0.5,
                filter=flt,
            )
            if scored:
                break
    except (AttributeError, NotImplementedError) as exc:
        logger.warning("MMR retrieval unavailable, falling back to similarity search: %s", exc)
        for flt in _filter_ladder(filters):
            scored = vector_db.similarity_search_with_score(search_query, k=k, filter=flt)
            if scored:
                break

    return scored, detected_program


def retrieve_with_scores(prompt: str) -> list[tuple]:
    """Return raw (Document, score) pairs for *prompt*, best-first.

    Scores are FAISS L2 distances — lower means more similar.
    No threshold filtering is applied; the full result set is returned so
    the caller can inspect the best score for routing decisions.

    Raises ``RuntimeError`` (propagated from ``get_vector_db``) if the
    index has not been built yet.
    """
    scored, detected_program = _run_scored_search(prompt)

    logger.debug(
        "RAG retrieve_with_scores: prompt=%r pairs=%d best_score=%s",
        prompt[:60],
        len(scored),
        scored[0][1] if scored else "n/a",
    )

    return scored


def retrieve(prompt: str) -> list:
    """Return a reranked, threshold-filtered list of Documents for *prompt*.

    Uses MMR retrieval when available, falls back to similarity search.
    Program-matched documents are floated to the top of the result list.
    """
    scored, detected_program = _run_scored_search(prompt)

    retrieved_docs = [doc for doc, score in scored if score < RAG_SCORE_THRESHOLD]

    logger.debug(
        "RAG: docs_after_threshold=%d program=%s",
        len(retrieved_docs), detected_program,
    )

    # Float program-matched documents to the top so the most relevant
    # chunk appears first in the context block sent to the LLM.
    if detected_program:
        # Match on _normalize() output (ASCII-folded, lowercased) so
        # canonicals like "İlk ve Acil Yardım" or "Tıp Fakültesi"
        # actually align with the program_name strings. A naive
        # str.lower() drops "İ" but leaves "Ş", "Ç" intact and the
        # substring check fails on legitimate matches.
        prog_norm = _normalize(detected_program)
        matched = [d for d in retrieved_docs
                   if prog_norm in _normalize(d.metadata.get("program_name", ""))]
        others = [d for d in retrieved_docs if d not in matched]
        retrieved_docs = matched + others

    return retrieved_docs
