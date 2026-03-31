import httpx
from django.conf import settings


def generate_answer(question: str) -> str:
    try:
        url = f"{settings.OLLAMA_BASE_URL}/chat/completions"  # ← only this changes
        payload = {
            "model": settings.OLLAMA_MODEL,                   # ← and this
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
        response = httpx.post(url, json=payload, timeout=120.0)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return "LLM service is currently unavailable. Please try again later."