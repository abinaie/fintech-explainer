import os
import unittest
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app, enforce_rate_limit


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.key = {"X-API-Key": "test-key"}
        self.question = {"question": "What is a chargeback?"}
        self.counter = patch("app.main.recent_requests", deque())
        self.counter.start()
        self.addCleanup(self.counter.stop)

    @patch("app.main.API_KEY", "test-anthropic-key")
    @patch("app.main.Anthropic")
    @patch("app.main.monotonic")
    def test_limit_and_rolling_window(self, clock, anthropic):
        clock.return_value = 100.0
        anthropic.return_value.messages.create.return_value = SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"answer":"ok","source":"test"}')],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )
        with patch.dict(os.environ, {"APP_API_KEY": "test-key"}):
            for _ in range(5):
                response = self.client.post("/ask", json=self.question, headers=self.key)
                self.assertEqual(response.status_code, 200)

            response = self.client.post("/ask", json=self.question, headers=self.key)
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers["Retry-After"], "60")
            self.assertEqual(anthropic.return_value.messages.create.call_count, 5)

            clock.return_value = 159.5
            response = self.client.post("/ask", json=self.question, headers=self.key)
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers["Retry-After"], "1")

            clock.return_value = 160.0
            response = self.client.post("/ask", json=self.question, headers=self.key)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(anthropic.return_value.messages.create.call_count, 6)

    @patch("app.main.API_KEY", "test-anthropic-key")
    @patch("app.main.Anthropic")
    @patch("app.main.monotonic", return_value=100.0)
    def test_invalid_key_and_health_do_not_consume_limit(self, clock, anthropic):
        anthropic.return_value.messages.create.return_value = SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"answer":"ok","source":"test"}')],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )
        with patch.dict(os.environ, {"APP_API_KEY": "test-key"}):
            for _ in range(6):
                self.assertEqual(self.client.post("/ask", json=self.question).status_code, 401)
                self.assertEqual(self.client.get("/health").status_code, 200)
            for _ in range(5):
                response = self.client.post("/ask", json=self.question, headers=self.key)
                self.assertEqual(response.status_code, 200)

    @patch("app.main.monotonic", return_value=100.0)
    def test_simultaneous_requests_share_limit(self, clock):
        def attempt():
            try:
                enforce_rate_limit()
                return 200
            except HTTPException as exc:
                return exc.status_code

        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(lambda _: attempt(), range(20)))
        self.assertEqual(results.count(200), 5)
        self.assertEqual(results.count(429), 15)


if __name__ == "__main__":
    unittest.main()
