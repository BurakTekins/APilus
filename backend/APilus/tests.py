import json
import uuid
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse

URL = "/api/v1/chat/messages"


class ChatMessagesTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.mock_answer = patch("APilus.views.generate_answer", return_value="mocked answer")
        self.mock_answer.start()

    def tearDown(self):
        self.mock_answer.stop()

    def post(self, data):
        return self.client.post(
            URL,
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_missing_question(self):
        res = self.post({})
        self.assertEqual(res.status_code, 400)

    def test_blank_question(self):
        res = self.post({"question": ""})
        self.assertEqual(res.status_code, 400)

    def test_new_session_created(self):
        res = self.post({"question": "hello"})
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn("session_id", data)
        self.assertEqual(data["user_message"]["role"], "user")
        self.assertEqual(data["user_message"]["content"], "hello")
        self.assertEqual(data["assistant_message"]["role"], "assistant")
        self.assertEqual(data["assistant_message"]["content"], "mocked answer")

    def test_existing_session_reused(self):
        session_id = str(uuid.uuid4())
        res = self.post({"question": "hi", "session_id": session_id})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["session_id"], session_id)

    def test_new_session_when_no_session_id(self):
        res1 = self.post({"question": "first"})
        res2 = self.post({"question": "second"})
        self.assertEqual(res1.status_code, 201)
        self.assertEqual(res2.status_code, 201)
        self.assertNotEqual(res1.json()["session_id"], res2.json()["session_id"])