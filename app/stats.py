"""Corpus / load / performance summary for load-tuning."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

import psycopg
from psycopg.rows import dict_row

from app.scheduler import new_per_day


@dataclass(frozen=True)
class CorpusStats:
    total_cards: int
    new_cards: int
    in_system: int
    interval_ge_7: int
    interval_ge_21: int

    @property
    def in_system_pct(self) -> float:
        return _pct(self.in_system, self.total_cards)

    @property
    def ge7_pct(self) -> float:
        return _pct(self.interval_ge_7, self.total_cards)

    @property
    def ge21_pct(self) -> float:
        return _pct(self.interval_ge_21, self.total_cards)


@dataclass(frozen=True)
class LoadStats:
    due_today: int
    due_tomorrow: int
    due_in_3_days: int
    introduced_today: int
    new_per_day: int
    answers_last_7: int
    answers_last_30: int
    median_answers_per_day_7: float
    median_answers_per_day_30: float
    active_days_7: int
    active_days_30: int


@dataclass(frozen=True)
class PerformanceStats:
    reviews_7: int
    remember_rate_all_7: float | None
    remember_rate_new_7: float | None
    remember_rate_review_7: float | None
    again_rate_7: float | None
    reset_to_one_7: int
    mature_reviews_7: int
    mature_again_rate_7: float | None


@dataclass(frozen=True)
class LoadAdvice:
    status: str  # lower | keep | raise
    label: str
    detail: str
    suggested_new_per_day: int


@dataclass(frozen=True)
class HorizonStats:
    """ETA for remaining new cards (first pass through the corpus)."""

    remaining_new: int
    days_at_limit: int | None
    label_at_limit: str
    introduced_last_7: int
    pace_new_per_day_7: float
    days_at_pace: int | None
    label_at_pace: str | None
    days_to_mature_lag: int
    label_first_pass_plus_mature: str
    note: str


@dataclass(frozen=True)
class CorpusSegments:
    """Part-to-whole slices for the corpus stacked bar."""

    new: int
    learning: int  # in system, interval < 7
    young: int  # 7 ≤ interval < 21
    mature: int  # interval ≥ 21

    @property
    def total(self) -> int:
        return self.new + self.learning + self.young + self.mature


@dataclass(frozen=True)
class ActivityDay:
    day: date
    label: str
    answers: int
    introduced: int


@dataclass(frozen=True)
class RememberDay:
    day: date
    label: str
    rate_all: float | None
    rate_review: float | None
    reviews: int
    review_reviews: int


@dataclass(frozen=True)
class StatsCharts:
    corpus: CorpusSegments
    activity: tuple[ActivityDay, ...]
    remember: tuple[RememberDay, ...]

    @property
    def activity_max(self) -> int:
        peak = max((max(d.answers, d.introduced) for d in self.activity), default=0)
        return peak or 1

    def corpus_stack(self) -> tuple[dict[str, float | int | str], ...]:
        total = max(self.corpus.total, 1)
        parts = (
            ("new", "новые", self.corpus.new),
            ("learning", "< 7 дн", self.corpus.learning),
            ("young", "7–20 дн", self.corpus.young),
            ("mature", "≥ 21 дн", self.corpus.mature),
        )
        return tuple(
            {
                "key": key,
                "label": label,
                "count": count,
                "pct": round(100.0 * count / total, 1),
                "width": round(100.0 * count / total, 2),
            }
            for key, label, count in parts
        )

    def remember_svg(
        self, *, width: float = 600.0, height: float = 160.0, pad: float = 18.0
    ) -> dict[str, str | float | list[dict[str, float | str | None]]]:
        n = len(self.remember)
        inner_w = width - 2 * pad
        inner_h = height - 2 * pad
        xs = [
            pad + (inner_w * i / (n - 1) if n > 1 else inner_w / 2)
            for i in range(n)
        ]

        def y_of(rate: float | None) -> float | None:
            if rate is None:
                return None
            return pad + inner_h * (1.0 - rate)

        def polyline(attr: str) -> str:
            parts: list[str] = []
            pen_down = False
            for i, day in enumerate(self.remember):
                rate = getattr(day, attr)
                if rate is None:
                    pen_down = False
                    continue
                cmd = "L" if pen_down else "M"
                parts.append(f"{cmd}{xs[i]:.1f},{y_of(rate):.1f}")
                pen_down = True
            return " ".join(parts)

        ticks = [
            {"y": pad, "label": "100%"},
            {"y": pad + inner_h * 0.5, "label": "50%"},
            {"y": pad + inner_h, "label": "0%"},
        ]
        labels = [
            {
                "x": xs[i],
                "label": day.label,
                "y_all": y_of(day.rate_all),
                "y_review": y_of(day.rate_review),
            }
            for i, day in enumerate(self.remember)
            if i % 7 == 0 or i == n - 1
        ]
        return {
            "width": width,
            "height": height,
            "all": polyline("rate_all"),
            "review": polyline("rate_review"),
            "ticks": ticks,
            "labels": labels,
        }


@dataclass(frozen=True)
class LanguageSummary:
    language: str
    corpus: CorpusStats
    load: LoadStats
    performance: PerformanceStats
    advice: LoadAdvice
    horizon: HorizonStats
    charts: StatsCharts


def _pct(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return 100.0 * part / whole


def _rate(success: int, total: int) -> float | None:
    if total <= 0:
        return None
    return success / total


def days_to_finish(remaining: int, per_day: float) -> int | None:
    if remaining <= 0:
        return 0
    if per_day <= 0:
        return None
    return int(math.ceil(remaining / per_day))


def format_horizon(days: int | None) -> str:
    if days is None:
        return "нужен темп > 0"
    if days <= 0:
        return "готово"
    if days < 14:
        return f"≈ {days} дн"
    weeks = days / 7
    if days < 60:
        w = int(round(weeks))
        return f"≈ {w} нед"
    months = days / 30.44
    if months < 10:
        return f"≈ {months:.1f} мес"
    return f"≈ {int(round(months))} мес"


def build_horizon(
    remaining_new: int,
    new_per_day: int,
    introduced_last_7: int,
    *,
    mature_lag_days: int = 21,
) -> HorizonStats:
    days_limit = days_to_finish(remaining_new, float(new_per_day))
    pace = introduced_last_7 / 7.0
    days_pace = days_to_finish(remaining_new, pace)
    label_limit = format_horizon(days_limit)
    first_plus_mature = (
        None if days_limit is None else days_limit + mature_lag_days
    )
    return HorizonStats(
        remaining_new=remaining_new,
        days_at_limit=days_limit,
        label_at_limit=label_limit,
        introduced_last_7=introduced_last_7,
        pace_new_per_day_7=pace,
        days_at_pace=days_pace,
        label_at_pace=format_horizon(days_pace) if pace > 0 or remaining_new <= 0 else None,
        days_to_mature_lag=mature_lag_days,
        label_first_pass_plus_mature=format_horizon(first_plus_mature),
        note=(
            "«Освоить» здесь = первый показ всех оставшихся карточек при ежедневных занятиях. "
            "Удержание (interval ≥ 21) у последних карточек — примерно ещё +3 недели после этого; "
            "повторы после ввода новых продолжаются всегда."
        ),
    )


def fetch_introduced_last_days(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    today: date,
    days: int = 7,
) -> int:
    since = today - timedelta(days=days - 1)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*)
            FROM card_progress p
            JOIN entries e ON e.id = p.entry_id
            WHERE p.user_id = %s
              AND e.language = %s
              AND p.introduced_on >= %s
              AND p.introduced_on <= %s
              AND p.introduced_via = 'train'
            """,
            (user_id, language, since, today),
        )
        return int(cur.fetchone()[0])


def fetch_corpus_stats(
    conn: psycopg.Connection, user_id: int, language: str
) -> CorpusStats:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
              count(*) AS total_cards,
              count(*) FILTER (WHERE p.entry_id IS NULL) AS new_cards,
              count(*) FILTER (WHERE p.entry_id IS NOT NULL) AS in_system,
              count(*) FILTER (WHERE p.interval_days >= 7) AS interval_ge_7,
              count(*) FILTER (WHERE p.interval_days >= 21) AS interval_ge_21
            FROM entries e
            CROSS JOIN unnest(
              ARRAY['foreign_to_native','native_to_foreign']::card_direction[]
            ) AS d(direction)
            LEFT JOIN card_progress p
              ON p.entry_id = e.id AND p.direction = d.direction AND p.user_id = %s
            WHERE e.language = %s
            """,
            (user_id, language),
        )
        row = cur.fetchone()
    assert row is not None
    return CorpusStats(
        total_cards=int(row["total_cards"]),
        new_cards=int(row["new_cards"]),
        in_system=int(row["in_system"]),
        interval_ge_7=int(row["interval_ge_7"]),
        interval_ge_21=int(row["interval_ge_21"]),
    )


def fetch_load_stats(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    today: date | None = None,
) -> LoadStats:
    today = today or date.today()
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
              count(*) FILTER (WHERE p.due_on <= %s) AS due_today,
              count(*) FILTER (WHERE p.due_on <= %s) AS due_tomorrow,
              count(*) FILTER (WHERE p.due_on <= %s) AS due_in_3_days,
              count(*) FILTER (
                WHERE p.introduced_on = %s AND p.introduced_via = 'train'
              ) AS introduced_today
            FROM card_progress p
            JOIN entries e ON e.id = p.entry_id
            WHERE p.user_id = %s AND e.language = %s
            """,
            (
                today,
                today + timedelta(days=1),
                today + timedelta(days=3),
                today,
                user_id,
                language,
            ),
        )
        due_row = cur.fetchone()
        assert due_row is not None

        cur.execute(
            """
            SELECT answered_on AS day, count(*) AS n
            FROM card_reviews r
            JOIN entries e ON e.id = r.entry_id
            WHERE r.user_id = %s
              AND e.language = %s
              AND r.answered_on >= %s
              AND r.source = 'train'
            GROUP BY 1
            ORDER BY 1
            """,
            (user_id, language, today - timedelta(days=29)),
        )
        by_day = {row["day"]: int(row["n"]) for row in cur.fetchall()}

    days_7 = [today - timedelta(days=i) for i in range(7)]
    days_30 = [today - timedelta(days=i) for i in range(30)]
    vals_7 = [by_day.get(d, 0) for d in days_7]
    vals_30 = [by_day.get(d, 0) for d in days_30]
    active_7 = [v for v in vals_7 if v > 0]
    active_30 = [v for v in vals_30 if v > 0]

    return LoadStats(
        due_today=int(due_row["due_today"]),
        due_tomorrow=int(due_row["due_tomorrow"]),
        due_in_3_days=int(due_row["due_in_3_days"]),
        introduced_today=int(due_row["introduced_today"]),
        new_per_day=new_per_day(language),
        answers_last_7=sum(vals_7),
        answers_last_30=sum(vals_30),
        median_answers_per_day_7=float(median(active_7)) if active_7 else 0.0,
        median_answers_per_day_30=float(median(active_30)) if active_30 else 0.0,
        active_days_7=len(active_7),
        active_days_30=len(active_30),
    )


def fetch_performance_stats(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    today: date | None = None,
) -> PerformanceStats:
    today = today or date.today()
    since = today - timedelta(days=6)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
              count(*) AS reviews,
              count(*) FILTER (WHERE remembered) AS remembered,
              count(*) FILTER (WHERE was_new) AS new_reviews,
              count(*) FILTER (WHERE was_new AND remembered) AS new_remembered,
              count(*) FILTER (WHERE NOT was_new) AS review_reviews,
              count(*) FILTER (WHERE NOT was_new AND remembered) AS review_remembered,
              count(*) FILTER (WHERE NOT remembered) AS again,
              count(*) FILTER (
                WHERE NOT remembered AND interval_after <= 1
              ) AS reset_to_one,
              count(*) FILTER (WHERE NOT was_new AND interval_before >= 21) AS mature,
              count(*) FILTER (
                WHERE NOT was_new AND interval_before >= 21 AND NOT remembered
              ) AS mature_again
            FROM card_reviews r
            JOIN entries e ON e.id = r.entry_id
            WHERE r.user_id = %s
              AND e.language = %s
              AND r.answered_on >= %s
              AND r.source = 'train'
            """,
            (user_id, language, since),
        )
        row = cur.fetchone()
    assert row is not None
    reviews = int(row["reviews"])
    remembered = int(row["remembered"])
    new_reviews = int(row["new_reviews"])
    review_reviews = int(row["review_reviews"])
    again = int(row["again"])
    mature = int(row["mature"])
    return PerformanceStats(
        reviews_7=reviews,
        remember_rate_all_7=_rate(remembered, reviews),
        remember_rate_new_7=_rate(int(row["new_remembered"]), new_reviews),
        remember_rate_review_7=_rate(int(row["review_remembered"]), review_reviews),
        again_rate_7=_rate(again, reviews),
        reset_to_one_7=int(row["reset_to_one"]),
        mature_reviews_7=mature,
        mature_again_rate_7=_rate(int(row["mature_again"]), mature),
    )


def advise_load(
    corpus: CorpusStats,
    load: LoadStats,
    performance: PerformanceStats,
) -> LoadAdvice:
    review_ok = performance.remember_rate_review_7
    again = performance.again_rate_7
    due = load.due_today
    new_left = max(0, load.new_per_day - load.introduced_today)

    # Need some review signal; otherwise keep.
    if performance.reviews_7 >= 20 and (
        (review_ok is not None and review_ok < 0.80)
        or (again is not None and again > 0.20)
        or due >= max(40, load.median_answers_per_day_7 * 1.5)
    ):
        suggested = max(5, load.new_per_day - 5)
        return LoadAdvice(
            status="lower",
            label="Снизить нагрузку",
            detail="Много again по повторам или due давит. Убавьте порцию новых.",
            suggested_new_per_day=suggested,
        )

    if (
        performance.reviews_7 >= 20
        and review_ok is not None
        and review_ok >= 0.85
        and (again is None or again <= 0.10)
        and due <= 15
        and load.introduced_today < load.new_per_day
        and corpus.new_cards > 0
    ):
        suggested = min(30, load.new_per_day + 5)
        return LoadAdvice(
            status="raise",
            label="Можно усилить",
            detail="Повторы стабильны, due небольшой, квота новых недобирается.",
            suggested_new_per_day=suggested,
        )

    return LoadAdvice(
        status="keep",
        label="Оставить как есть",
        detail="Очередь и again в норме. Лимит новых менять не обязательно.",
        suggested_new_per_day=load.new_per_day,
    )


def corpus_segments(corpus: CorpusStats) -> CorpusSegments:
    learning = max(0, corpus.in_system - corpus.interval_ge_7)
    young = max(0, corpus.interval_ge_7 - corpus.interval_ge_21)
    return CorpusSegments(
        new=corpus.new_cards,
        learning=learning,
        young=young,
        mature=corpus.interval_ge_21,
    )


def _day_label(day: date) -> str:
    return day.strftime("%d.%m")


def fetch_activity_series(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    today: date,
    days: int = 30,
) -> tuple[ActivityDay, ...]:
    since = today - timedelta(days=days - 1)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT answered_on AS day, count(*) AS n
            FROM card_reviews r
            JOIN entries e ON e.id = r.entry_id
            WHERE r.user_id = %s
              AND e.language = %s
              AND r.answered_on >= %s
              AND r.answered_on <= %s
              AND r.source = 'train'
            GROUP BY 1
            """,
            (user_id, language, since, today),
        )
        answers = {row["day"]: int(row["n"]) for row in cur.fetchall()}

        cur.execute(
            """
            SELECT introduced_on AS day, count(*) AS n
            FROM card_progress p
            JOIN entries e ON e.id = p.entry_id
            WHERE p.user_id = %s
              AND e.language = %s
              AND p.introduced_on >= %s
              AND p.introduced_on <= %s
              AND p.introduced_via = 'train'
            GROUP BY 1
            """,
            (user_id, language, since, today),
        )
        introduced = {row["day"]: int(row["n"]) for row in cur.fetchall()}

    out: list[ActivityDay] = []
    for i in range(days):
        day = since + timedelta(days=i)
        out.append(
            ActivityDay(
                day=day,
                label=_day_label(day),
                answers=answers.get(day, 0),
                introduced=introduced.get(day, 0),
            )
        )
    return tuple(out)


def fetch_remember_series(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    today: date,
    days: int = 30,
) -> tuple[RememberDay, ...]:
    since = today - timedelta(days=days - 1)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
              answered_on AS day,
              count(*) AS reviews,
              count(*) FILTER (WHERE remembered) AS remembered,
              count(*) FILTER (WHERE NOT was_new) AS review_reviews,
              count(*) FILTER (WHERE NOT was_new AND remembered) AS review_remembered
            FROM card_reviews r
            JOIN entries e ON e.id = r.entry_id
            WHERE r.user_id = %s
              AND e.language = %s
              AND r.answered_on >= %s
              AND r.answered_on <= %s
              AND r.source = 'train'
            GROUP BY 1
            """,
            (user_id, language, since, today),
        )
        by_day = {row["day"]: row for row in cur.fetchall()}

    out: list[RememberDay] = []
    for i in range(days):
        day = since + timedelta(days=i)
        row = by_day.get(day)
        if row is None:
            out.append(
                RememberDay(
                    day=day,
                    label=_day_label(day),
                    rate_all=None,
                    rate_review=None,
                    reviews=0,
                    review_reviews=0,
                )
            )
            continue
        reviews = int(row["reviews"])
        review_reviews = int(row["review_reviews"])
        out.append(
            RememberDay(
                day=day,
                label=_day_label(day),
                rate_all=_rate(int(row["remembered"]), reviews),
                rate_review=_rate(int(row["review_remembered"]), review_reviews),
                reviews=reviews,
                review_reviews=review_reviews,
            )
        )
    return tuple(out)


def build_stats_charts(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    corpus: CorpusStats,
    today: date,
) -> StatsCharts:
    return StatsCharts(
        corpus=corpus_segments(corpus),
        activity=fetch_activity_series(conn, user_id, language, today),
        remember=fetch_remember_series(conn, user_id, language, today),
    )


def build_language_summary(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    today: date | None = None,
) -> LanguageSummary:
    if language not in ("en", "fr"):
        raise ValueError("language must be en or fr")
    today = today or date.today()
    corpus = fetch_corpus_stats(conn, user_id, language)
    load = fetch_load_stats(conn, user_id, language, today)
    performance = fetch_performance_stats(conn, user_id, language, today)
    advice = advise_load(corpus, load, performance)
    introduced_7 = fetch_introduced_last_days(conn, user_id, language, today, 7)
    horizon = build_horizon(corpus.new_cards, load.new_per_day, introduced_7)
    charts = build_stats_charts(conn, user_id, language, corpus, today)
    return LanguageSummary(
        language=language,
        corpus=corpus,
        load=load,
        performance=performance,
        advice=advice,
        horizon=horizon,
        charts=charts,
    )
