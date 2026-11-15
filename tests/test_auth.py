import inspect
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from anthropic.resources import Messages
from fastapi.testclient import TestClient

from app.main import app


class AskAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.question = {"question": "What is a chargeback?"}

    @patch("app.main.Anthropic")
    def test_missing_and_incorrect_keys_are_rejected(self, anthropic):
        with patch.dict(os.environ, {"APP_API_KEY": "test-key"}):
            for headers in ({}, {"X-API-Key": "wrong-key"}):
                with self.subTest(headers=headers):
                    response = self.client.post("/ask", json=self.question, headers=headers)
                    self.assertEqual(response.status_code, 401)
        anthropic.assert_not_called()

    @patch("app.main.Anthropic")
    def test_missing_server_key_rejects_requests(self, anthropic):
        with patch.dict(os.environ, {"APP_API_KEY": ""}):
            response = self.client.post(
                "/ask", json=self.question, headers={"X-API-Key": "test-key"}
            )
        self.assertEqual(response.status_code, 503)
        anthropic.assert_not_called()

    @patch("app.main.API_KEY", "test-anthropic-key")
    @patch("app.main.Anthropic")
    def test_correct_key_allows_request(self, anthropic):
        anthropic.return_value.messages.create.return_value = SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"answer":"An answer","source":"A source"}')],
            usage=SimpleNamespace(input_tokens=50, output_tokens=120),
        )
        with patch.dict(os.environ, {"APP_API_KEY": "test-key"}):
            response = self.client.post(
                "/ask", json=self.question, headers={"X-API-Key": "test-key"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "An answer")
        anthropic.return_value.messages.create.assert_called_once()
        call = anthropic.return_value.messages.create.call_args
        inspect.signature(Messages.create).bind(None, **call.kwargs)

    def test_health_remains_public(self):
        with patch.dict(os.environ, {"APP_API_KEY": ""}):
            self.assertEqual(self.client.get("/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
