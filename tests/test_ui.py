import unittest

from fastapi.testclient import TestClient

from app.main import app


class UserInterfaceTests(unittest.TestCase):
    def test_home_serves_question_form(self):
        response = TestClient(app).get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn('id="ask-form"', response.text)
        self.assertIn('id="app-key"', response.text)


if __name__ == "__main__":
    unittest.main()
