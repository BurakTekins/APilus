import logging
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


def generate_answer(question: str) -> str:
    url = f"{settings.OLLAMA_BASE_URL}/chat/completions"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant for Acibadem University."
            },
            {
                "role": "user",
                "content": question
            }
        ],
        "max_tokens": 512,
        "temperature": 0.7,
    }
    try:
        response = httpx.post(url, json=payload, timeout=120.0)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as e:
        logger.exception("Ollama returned %s: %s", e.response.status_code, e.response.text)
        return "LLM service is currently unavailable. Please try again later."
    except Exception:
        logger.exception("Ollama call failed")
        return "LLM service is currently unavailable. Please try again later."
