import logging

import httpx

from .rag_config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)


def call_ollama(
    messages: list[dict],
    *,
    max_tokens: int,
    temperature: float = 0.3,
    top_p: float = 0.95,
    top_k: int = 64,
) -> str:
    """Send a single chat-completion request to Ollama and return the response text.

    Uses OLLAMA_BASE_URL and OLLAMA_MODEL from rag_config (which reads the
    environment variables with the same defaults).  Raises on HTTP errors so
    callers can decide how to handle them.
    """
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/chat/completions"
    model = OLLAMA_MODEL

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
    }

    response = httpx.post(url, json=payload, timeout=120.0)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()
