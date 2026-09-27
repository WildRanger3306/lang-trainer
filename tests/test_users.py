from __future__ import annotations

import unittest

from app.users import ALL_LANGUAGES, User, clean_languages


class CleanLanguagesTests(unittest.TestCase):
    def test_keeps_known_codes_in_stable_order(self) -> None:
        self.assertEqual(clean_languages(["fr", "en", "fr"]), ("en", "fr"))
        self.assertEqual(clean_languages(["fr"]), ("fr",))
        self.assertEqual(clean_languages([]), ())
        self.assertEqual(clean_languages(["de", "fr"]), ("fr",))


class UserLanguageTests(unittest.TestCase):
    def test_can_use_and_default(self) -> None:
        user = User(id=1, login="x", display_name=None, allowed_languages=("fr",))
        self.assertFalse(user.can_use("en"))
        self.assertTrue(user.can_use("fr"))
        self.assertEqual(user.default_language, "fr")

    def test_default_user_has_both_languages(self) -> None:
        user = User(id=1, login="x", display_name=None)
        self.assertEqual(user.allowed_languages, ALL_LANGUAGES)
        self.assertFalse(user.is_admin)


if __name__ == "__main__":
    unittest.main()
