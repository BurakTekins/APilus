import json

from django.test import TestCase
from django.urls import reverse


class ChatMessagesApiContractTests(TestCase):
	def setUp(self):
		# Keep server errors in responses so contract assertions fail clearly.
		self.client.raise_request_exception = False
		self.url = reverse("chat-messages")

	def test_post_question_returns_201_and_message_payload(self):
		response = self.client.post(
			self.url,
			data=json.dumps({"question": "What are your clinic opening hours?"}),
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 201)

		payload = response.json()
		self.assertIn("session_id", payload)
		self.assertIn("user_message", payload)
		self.assertIn("assistant_message", payload)
		self.assertEqual(payload["user_message"]["role"], "user")
		self.assertEqual(payload["assistant_message"]["role"], "assistant")

	def test_post_requires_question_field(self):
		response = self.client.post(
			self.url,
			data=json.dumps({}),
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn("question", response.json())

	def test_post_rejects_blank_question(self):
		response = self.client.post(
			self.url,
			data=json.dumps({"question": ""}),
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn("question", response.json())
