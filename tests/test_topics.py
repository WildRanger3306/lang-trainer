from __future__ import annotations

import unittest

from app.repository import WordProgress
from app.session import NO_TOPIC, SessionFilter, make_pick, split_pick
from app.topics import compress_topics, topic_title, words_label
from app.user_filters import filter_summary


class TopicTitleTests(unittest.TestCase):
    def test_titles(self) -> None:
        self.assertEqual(topic_title("sl7_m1"), "M1 Work & Play")
        self.assertEqual(topic_title("lb6_u03"), "U3")
        self.assertEqual(topic_title("bridge_sl6"), "Мост: слова SL6")
        self.assertEqual(topic_title("something_new"), "something_new")

    def test_compress(self) -> None:
        self.assertEqual(compress_topics(["sl7_m3", "sl7_m1", "sl7_m2"]), "M1–M3")
        self.assertEqual(compress_topics(["sl7_m1", "sl7_m3"]), "M1, M3")
        self.assertEqual(compress_topics(["lb6_u01", "lb6_u02", "bridge_sl6"]), "U1–U2, Мост: слова SL6")

    def test_words_label(self) -> None:
        self.assertEqual(words_label(1), "1 слово")
        self.assertEqual(words_label(3), "3 слова")
        self.assertEqual(words_label(11), "11 слов")
        self.assertEqual(words_label(1885), "1 885 слов")


class WordProgressTests(unittest.TestCase):
    def test_started_and_cumulative_shares(self) -> None:
        progress = WordProgress(words=200, known=20, consolidating=40, learning=20)
        self.assertEqual(progress.started, 80)
        self.assertEqual(progress.shares(), (10.0, 30.0, 40.0))

    def test_empty_textbook(self) -> None:
        self.assertEqual(WordProgress(0, 0, 0, 0).shares(), (0.0, 0.0, 0.0))


class PickTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        pick = make_pick("Starlight 7", "sl7_m1")
        self.assertEqual(split_pick(pick), ("Starlight 7", "sl7_m1"))
        self.assertEqual(split_pick(make_pick("Starlight 7", NO_TOPIC))[1], NO_TOPIC)


class SummaryTests(unittest.TestCase):
    def test_no_textbook_selected(self) -> None:
        self.assertEqual(filter_summary(SessionFilter(language="en")), "учебник не выбран")

    def test_textbook_with_range_and_untopiced(self) -> None:
        flt = SessionFilter(
            language="en",
            textbooks=("Starlight 7", "Starlight 6"),
            topics=(
                make_pick("Starlight 7", "sl7_m1"),
                make_pick("Starlight 7", "sl7_m2"),
                make_pick("Starlight 7", NO_TOPIC),
            ),
        )
        self.assertEqual(
            filter_summary(flt), "Starlight 7 (M1–M2, без темы) · Starlight 6"
        )

    def test_whole_bank_topic_shows_textbook_only(self) -> None:
        flt = SessionFilter(
            language="fr",
            textbooks=("Loiseau Blue 5",),
            topics=(make_pick("Loiseau Blue 5", "lb5_all"),),
        )
        self.assertEqual(filter_summary(flt), "Loiseau Blue 5")


if __name__ == "__main__":
    unittest.main()
