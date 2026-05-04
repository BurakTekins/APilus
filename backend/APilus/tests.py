import json
import uuid
from unittest.mock import MagicMock, patch
from django.test import TestCase, Client

URL = "/api/v1/chat/messages"


class ChatMessagesTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.mock_answer = patch("APilus.views.chat", return_value="mocked answer")
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


class ScoreBasedRoutingTests(TestCase):
    """Verify that chat() routes based on FAISS retrieval scores, not keywords.

    FAISS L2 semantics: lower score = more similar.
      best_score < RAG_SCORE_THRESHOLD  →  RAG pipeline
      best_score >= RAG_SCORE_THRESHOLD →  plain Ollama
    """

    def _make_doc(self, text="chunk text"):
        doc = MagicMock()
        doc.page_content = text
        doc.metadata = {}
        return doc

    def test_low_score_routes_to_rag(self):
        """best_score below threshold → ask_acibadem_ollama called."""
        doc = self._make_doc()
        # Score 1.0 is well below the default threshold of 12.0
        docs_with_scores = [(doc, 1.0)]

        with patch("APilus.pipeline.retrieve_with_scores", return_value=docs_with_scores), \
             patch("APilus.pipeline.ask_acibadem_ollama", return_value="rag answer") as mock_rag, \
             patch("APilus.pipeline.ask_ollama_plain") as mock_plain:
            from APilus.pipeline import chat
            result = chat("What programs does Acıbadem offer?")

        mock_rag.assert_called_once()
        mock_plain.assert_not_called()
        self.assertEqual(result, "rag answer")

    def test_high_score_routes_to_plain(self):
        """best_score above threshold → ask_ollama_plain called."""
        doc = self._make_doc()
        # Score 99.0 is well above the default threshold of 12.0
        docs_with_scores = [(doc, 99.0)]

        with patch("APilus.pipeline.retrieve_with_scores", return_value=docs_with_scores), \
             patch("APilus.pipeline.ask_acibadem_ollama") as mock_rag, \
             patch("APilus.pipeline.ask_ollama_plain", return_value="plain answer") as mock_plain:
            from APilus.pipeline import chat
            result = chat("How many records does Postgres support?")

        mock_plain.assert_called_once()
        mock_rag.assert_not_called()
        self.assertEqual(result, "plain answer")

    def test_no_docs_routes_to_plain(self):
        """Empty retrieval result → ask_ollama_plain called."""
        with patch("APilus.pipeline.retrieve_with_scores", return_value=[]), \
             patch("APilus.pipeline.ask_acibadem_ollama") as mock_rag, \
             patch("APilus.pipeline.ask_ollama_plain", return_value="plain answer") as mock_plain:
            from APilus.pipeline import chat
            result = chat("Something completely unrelated")

        mock_plain.assert_called_once()
        mock_rag.assert_not_called()

    def test_missing_index_falls_back_to_plain(self):
        """RuntimeError from get_vector_db → graceful fallback to plain Ollama."""
        with patch("APilus.pipeline.retrieve_with_scores", side_effect=RuntimeError("index missing")), \
             patch("APilus.pipeline.ask_acibadem_ollama") as mock_rag, \
             patch("APilus.pipeline.ask_ollama_plain", return_value="plain answer") as mock_plain:
            from APilus.pipeline import chat
            result = chat("Any question")

        mock_plain.assert_called_once()
        mock_rag.assert_not_called()
        self.assertEqual(result, "plain answer")

    def test_rag_receives_only_relevant_docs(self):
        """Only docs below threshold are forwarded to ask_acibadem_ollama."""
        doc_relevant = self._make_doc("relevant chunk")
        doc_irrelevant = self._make_doc("irrelevant chunk")
        # First doc is relevant (score 2.0 < 12.0), second is not (score 15.0 >= 12.0)
        docs_with_scores = [(doc_relevant, 2.0), (doc_irrelevant, 15.0)]

        with patch("APilus.pipeline.retrieve_with_scores", return_value=docs_with_scores), \
             patch("APilus.pipeline.ask_acibadem_ollama", return_value="rag answer") as mock_rag, \
             patch("APilus.pipeline.ask_ollama_plain"):
            from APilus.pipeline import chat
            chat("What is the nutrition program?")

        call_kwargs = mock_rag.call_args
        forwarded_docs = call_kwargs.kwargs.get("docs") or call_kwargs[1].get("docs")
        self.assertIn(doc_relevant, forwarded_docs)
        self.assertNotIn(doc_irrelevant, forwarded_docs)