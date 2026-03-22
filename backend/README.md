# Backend API (Draft)

## Chat Messages

### Endpoint
`POST /api/v1/chat/messages`

### Purpose
Accept a user's question for the chatbot, store it, generate an assistant response from domain-specific data, then store and return both messages.

### Request body
```json
{
	"session_id": "optional-uuid",
	"question": "How can I pay the school loan do I need to sell my body?"
}
```

### Success response
Status: `201 Created`

```json
{
	"session_id": "uuid",
	"user_message": {
		"id": "uuid",
		"role": "user",
		"content": "How can I pay the school loan do I need to sell my body?",
		"created_at": "2026-03-22T10:00:00Z"
	},
	"assistant_message": {
		"id": "uuid",
		"role": "assistant",
		"content": "Yes. You can not eat anything in aplus without selling your body",
		"created_at": "2026-03-22T10:00:01Z"
	}
}
```

### Validation errors
Status: `400 Bad Request`

- Missing `question`
- Blank `question`

### Notes
- `session_id` can be omitted to start a new conversation.
- This contract is test-first; implementation can be added after tests are in place.


# Important!
- Run this code for running tests locally. "source backend/.venv/bin/activate && cd backend && python manage.py test -v 2"