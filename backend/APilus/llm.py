import httpx
from django.conf import settings


def generate_answer(question: str) -> str:
    """
    Sends question to Ollama and returns the generated answer.
    Falls back to placeholder if Ollama is unavailable.
    """
    try:
        url = f"{settings.OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": question,
            "stream": False,
        }
        response = httpx.post(url, json=payload, timeout=60.0)
        response.raise_for_status()
        return response.json().get("response", "No response from model.")
    except Exception:
        return "LLM service is currently unavailable. Please try again later."