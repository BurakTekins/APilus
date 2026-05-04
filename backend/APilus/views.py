import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
import json
import hashlib

from .models import ChatSession, ChatMessage
from .llm import chat


@csrf_exempt
def chat_messages(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed."}, status=405)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    question = body.get("question", "").strip()
    if not question:
        return JsonResponse({"error": "question is required and cannot be blank."}, status=400)

    session_id = body.get("session_id")
    if session_id:
        try:
            session_uuid = uuid.UUID(str(session_id))
            session, _ = ChatSession.objects.get_or_create(id=session_uuid)
        except ValueError:
            return JsonResponse({"error": "Invalid session_id format."}, status=400)
    else:
        session = ChatSession.objects.create()

    # Pull the last few messages from this session for follow-up context.
    # Fetch BEFORE creating the new user message so we don't include the
    # current question itself.
    recent_messages = list(
        session.messages.order_by("-created_at").values("role", "content")[:6]
    )
    history_list = [
        {"role": m["role"], "content": m["content"]}
        for m in reversed(recent_messages)
    ]

    user_msg = ChatMessage.objects.create(
        session=session,
        role="user",
        content=question,
    )

    # Generate a cache key directly from the question + history
    cache_payload = json.dumps({"q": question, "h": history_list}, sort_keys=True).encode("utf-8")
    cache_key = "llm_answer_" + hashlib.md5(cache_payload).hexdigest()

    answer = cache.get(cache_key)
    if not answer:
        answer = chat(question, history=history_list)
        # Cache the result for 24 hours (86400 seconds)
        cache.set(cache_key, answer, 86400)

    assistant_msg = ChatMessage.objects.create(
        session=session,
        role="assistant",
        content=answer,
    )

    return JsonResponse({
        "session_id": str(session.id),
        "user_message": {
            "id": str(user_msg.id),
            "role": user_msg.role,
            "content": user_msg.content,
            "created_at": user_msg.created_at.isoformat(),
        },
        "assistant_message": {
            "id": str(assistant_msg.id),
            "role": assistant_msg.role,
            "content": assistant_msg.content,
            "created_at": assistant_msg.created_at.isoformat(),
        },
    }, status=201)