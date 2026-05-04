def _normalize(text: str) -> str:
    text = text.replace("İ", "i").replace("I", "ı")
    text = text.lower()
    return text.translate(str.maketrans("çğıöşü", "cgiosu"))


def _normalize_for_search(query: str) -> str:
    """Lowercase and strip Turkish diacritics for FAISS retrieval.

    The multilingual embedding model retrieves more reliably when
    diacritics are normalized. Use this for the FAISS query only;
    the original prompt should still be passed to the LLM.
    """
    return _normalize(query)
