"""
Query-understanding helpers: k selection, filter extraction, subpage detection,
and program-alias resolution.

Depends on: rag_config (for RAG_DATA_DIR), normalize (for _normalize,
_normalize_for_search), and the YAML dictionaries loaded at module level.
"""

import yaml
from .rag_config import RAG_DATA_DIR
from .normalize import _normalize, _normalize_for_search  # noqa: F401 — re-exported

# Canonical -> distinguishing alias substrings. Aliases are matched after
# _normalize() (lowercased, ASCII-folded). The first match wins, so order
# matters when two canonicals share a root word: more specific (longer)
# names should come before their shorter cousins. Aliases are deliberately
# hand-curated rather than auto-derived from program_name to avoid
# silent collisions like "ingilizce" or "hemsirelik" mapping to many
# different programs. The post-retrieval reranker matches program_name as
# a substring, so listing one canonical (e.g. "Hemşirelik") still surfaces
# its tezli/tezsiz/doktora variants from the index.
with open(RAG_DATA_DIR / "program_aliases.yaml", encoding="utf-8") as _f:
    _PROGRAM_ALIASES: dict[str, list[str]] = yaml.safe_load(_f)["aliases"]

# _CORPUS_KEYWORDS source dict keeps Turkish diacritics for readability
# ("müfredat", "rektör", "kampüs", ...). Normalization is applied at
# match time via _normalize(kw) in _extract_filters().
with open(RAG_DATA_DIR / "corpus_keywords.yaml", encoding="utf-8") as _f:
    _CORPUS_KEYWORDS: dict[str, list[str]] = yaml.safe_load(_f)["keywords"]

# Subpage routing — when a query mentions courses/curriculum or graduation
# requirements, narrow Bologna retrieval to the matching subpage. Only
# applied when the source filter is already acibadem_obs_bologna (acu_data
# pages have subpage="" and would otherwise be excluded by the AND filter).
with open(RAG_DATA_DIR / "subpage_keywords.yaml", encoding="utf-8") as _f:
    _SUBPAGE_KEYWORDS: dict[str, list[str]] = yaml.safe_load(_f)["keywords"]


def _pick_k(query: str) -> int:
    """Return the number of documents to retrieve for this query."""
    q = _normalize(query)
    # Keywords are normalized on the fly so the literal list stays
    # readable in Turkish orthography; without _normalize() here,
    # diacritic-bearing entries like "tüm", "müfredat", "dönem",
    # "yarıyıl" would never match the ASCII-folded query.
    broad_keywords = ["liste", "tüm", "all", "hangi", "müfredat",
                      "dönem", "semester", "yarıyıl", "curriculum"]
    if any(_normalize(w) in q for w in broad_keywords):
        return 10
    if len(q.split()) <= 5:
        return 3
    return 5


def _detect_subpage(q_normalized: str) -> str | None:
    """Pick a Bologna `subpage` value implied by the query, if any.

    `q_normalized` must already be passed through `_normalize`. Returns
    None when no subpage signal is present, or when the query implies
    multiple subpages (in which case routing back to the broader source
    is safer than guessing). Keywords are themselves normalized on the
    fly so the source dict stays readable in Turkish orthography.
    """
    matches = []
    for subpage, kws in _SUBPAGE_KEYWORDS.items():
        if any(_normalize(kw) in q_normalized for kw in kws):
            matches.append(subpage)
    if len(matches) == 1:
        return matches[0]
    return None


def _extract_filters(query: str) -> tuple[dict, str | None]:
    """Return (metadata_filters, detected_program) for a query string."""
    q = _normalize(query)
    # _PROGRAM_ALIASES is matched against the normalized (ASCII-folded)
    # query, so its aliases must be ASCII-folded too. We pre-normalize on
    # the fly here rather than at module load to keep the dict readable
    # in source.
    detected_program = None
    for canonical, aliases in _PROGRAM_ALIASES.items():
        if any(_normalize(alias) in q for alias in aliases):
            detected_program = canonical
            break
    filters: dict = {}
    if detected_program:
        filters["source"] = "acibadem_obs_bologna"
    # _CORPUS_KEYWORDS source dict keeps Turkish diacritics for
    # readability ("müfredat", "rektör", "kampüs", ...), but `q` has
    # already been ASCII-folded by _normalize(). Without this on-the-fly
    # normalization, every diacritic-bearing keyword is dead code — it
    # can never match. Match via `_normalize(kw) in q` to align both
    # sides.
    elif any(_normalize(kw) in q for kw in _CORPUS_KEYWORDS["bologna"]):
        filters["source"] = "acibadem_obs_bologna"
    elif any(_normalize(kw) in q for kw in _CORPUS_KEYWORDS["acu"]):
        filters["source"] = "acibadem_main"

    # Subpage routing is only safe when the source is already pinned to
    # Bologna; acu_data pages have subpage="" and an AND filter on
    # subpage would otherwise exclude them entirely. The FAISS retrieval
    # already falls back to the unfiltered query when the filtered call
    # returns nothing, so an over-narrow subpage filter degrades to the
    # source-only filter rather than to an empty result.
    if filters.get("source") == "acibadem_obs_bologna":
        subpage = _detect_subpage(q)
        if subpage:
            filters["subpage"] = subpage
    return filters, detected_program
