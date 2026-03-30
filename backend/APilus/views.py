import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

from .models import ChatSession, ChatMessage
from .llm import generate_answer


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

    user_msg = ChatMessage.objects.create(
        session=session,
        role="user",
        content=question,
    )

    answer = generate_answer(question)

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