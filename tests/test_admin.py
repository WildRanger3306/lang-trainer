from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.db import connect
from app.main import app
from app.users import get_user_by_login, set_admin, set_allowed_languages
from tests.support import requires_test_db


@requires_test_db
class AdminAccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        with connect() as conn:
            pavel, _ = get_user_by_login(conn, "pavel")
            serafima, _ = get_user_by_login(conn, "serafima")
            self.pavel_id = pavel.id
            self.serafima_id = serafima.id
            set_admin(conn, "pavel", True)
            set_admin(conn, "serafima", False)
            set_allowed_languages(conn, self.pavel_id, ["en", "fr"])
            set_allowed_languages(conn, self.serafima_id, ["en", "fr"])

    def login(self, login: str, password: str) -> None:
        response = self.client.post(
            "/login",
            data={"login": login, "password": password},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)

    def test_non_admin_gets_404(self) -> None:
        self.login("serafima", "serafima123")
        self.assertEqual(self.client.get("/admin").status_code, 404)
        response = self.client.post(
            f"/admin/users/{self.pavel_id}/languages",
            data={"language": ["en"]},
        )
        self.assertEqual(response.status_code, 404)

    def test_admin_sees_the_page_and_saves_restriction(self) -> None:
        self.login("pavel", "pavel123")
        page = self.client.get("/admin")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Серафима", page.text)
        self.assertIn("Павел", page.text)
        self.assertIn("Админ", page.text)

        saved = self.client.post(
            f"/admin/users/{self.serafima_id}/languages",
            data={"language": ["en"]},
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json(), {"allowed_languages": ["en"]})
        with connect() as conn:
            user, _ = get_user_by_login(conn, "serafima")
        self.assertEqual(user.allowed_languages, ("en",))

    def test_cannot_clear_all_languages(self) -> None:
        self.login("pavel", "pavel123")
        response = self.client.post(
            f"/admin/users/{self.pavel_id}/languages", data={}
        )
        self.assertEqual(response.status_code, 400)
        with connect() as conn:
            user, _ = get_user_by_login(conn, "pavel")
        self.assertEqual(user.allowed_languages, ("en", "fr"))

    def test_admin_can_restrict_their_own_languages(self) -> None:
        self.login("pavel", "pavel123")
        self.client.post(
            f"/admin/users/{self.pavel_id}/languages", data={"language": ["en"]}
        )
        with connect() as conn:
            user, _ = get_user_by_login(conn, "pavel")
        self.assertEqual(user.allowed_languages, ("en",))


@requires_test_db
class LanguageEnforcementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        with connect() as conn:
            user, _ = get_user_by_login(conn, "serafima")
            self.user_id = user.id
            set_allowed_languages(conn, self.user_id, ["en"])
        login = self.client.post(
            "/login",
            data={"login": "serafima", "password": "serafima123"},
            follow_redirects=False,
        )
        self.assertEqual(login.status_code, 303)

    def tearDown(self) -> None:
        with connect() as conn:
            set_allowed_languages(conn, self.user_id, ["en", "fr"])

    def test_home_falls_back_from_disallowed_language(self) -> None:
        response = self.client.get("/?language=fr")
        self.assertEqual(response.status_code, 200)
        self.assertIn('value="en"', response.text)

    def test_language_switch_hidden_with_one_allowed_language(self) -> None:
        response = self.client.get("/")
        self.assertNotIn('class="seg"', response.text)

    def test_start_rejects_disallowed_language(self) -> None:
        response = self.client.post(
            "/start", data={"language": "fr"}, follow_redirects=False
        )
        self.assertEqual(response.status_code, 303)
        self.assertIn("error=", response.headers["location"])

    def test_stats_falls_back_from_disallowed_language(self) -> None:
        response = self.client.get("/stats?language=fr")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('class="seg"', response.text)

    def test_session_api_rejects_disallowed_language(self) -> None:
        response = self.client.get("/session?language=fr")
        self.assertEqual(response.status_code, 403)

    def test_filters_preview_rejects_disallowed_language(self) -> None:
        response = self.client.get("/filters/preview?language=fr")
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
