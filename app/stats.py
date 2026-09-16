"""Corpus / load / performance summary for load-tuning."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

import psycopg
from psycopg.rows import dict_row

from app.load_limits import (
    AdaptResult,
    HYSTERESIS_DAYS,
    advice_streak,
    clamp_new_per_day,
    ensure_load_limit,
    fetch_advice_series,
    get_new_per_day,
    record_advice_day,
    try_apply_hysteresis,
)


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
    mature_reviews_7: int
    mature_again_rate_7: float | None
    rating_again: int
    rating_hard: int
    rating_good: int
    rating_easy: int
    rating_unrated: int

    @property
    def rating_total(self) -> int:
        return (
            self.rating_again
            + self.rating_hard
            + self.rating_good
            + self.rating_easy
            + self.rating_unrated
        )

    def rating_stack(self) -> tuple[dict[str, float | int | str], ...]:
        total = max(self.rating_total, 1)
        parts = (
            ("again", "Again", self.rating_again),
            ("hard", "Hard", self.rating_hard),
            ("good", "Good", self.rating_good),
            ("easy", "Easy", self.rating_easy),
            ("unrated", "без рейтинга", self.rating_unrated),
        )
        return tuple(
            {
                "key": key,
                "label": label,
                "count": count,
                "pct": round(100.0 * count / total, 1),
            }
            for key, label, count in parts
            if count > 0 or key != "unrated"
        )


@dataclass(frozen=True)
class AutoloadStatus:
    new_per_day: int
    base_new_per_day: int
    updated_via: str
    last_change_on: date | None
    advice_status: str
    streak_status: str | None
    streak_days: int
    needed_days: int
    note: str | None
    advice_days: tuple[tuple[date, str | None], ...]

    @property
    def streak_label(self) -> str:
        if self.streak_status is None or self.streak_days <= 0:
            return "серия не копится"
        return f"{self.streak_status} {self.streak_days}/{self.needed_days}"


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
class QualityDay:
    day: date
    label: str
    reviews: int
    again_rate: float | None
    pass_rate: float | None  # Good+Easy among rated


@dataclass(frozen=True)
class StatsCharts:
    corpus: CorpusSegments
    activity: tuple[ActivityDay, ...]
    quality: tuple[QualityDay, ...]

    @property
    def activity_max(self) -> int:
        peak = max((max(d.answers, d.introduced) for d in self.activity), default=0)
        return peak or 1

    def corpus_stack(self) -> tuple[dict[str, float | int | str], ...]:
        total = max(self.corpus.total, 1)
        parts = (
            ("new", "новые", self.corpus.new),
            ("learning", "повтор ≤6 дн", self.corpus.learning),
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

    def quality_svg(
        self, *, width: float = 600.0, height: float = 160.0, pad: float = 18.0
    ) -> dict[str, str | float | list[dict[str, float | str | None]]]:
        n = len(self.quality)
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
            for i, day in enumerate(self.quality):
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
        q_label_indices: list[int] = list(range(0, n, 7))
        if n:
            qlast = n - 1
            if qlast not in q_label_indices and q_label_indices and qlast - q_label_indices[-1] >= 4:
                q_label_indices.append(qlast)
        labels = [
            {
                "x": xs[i],
                "label": self.quality[i].label,
            }
            for i in q_label_indices
        ]
        return {
            "width": width,
            "height": height,
            "again": polyline("again_rate"),
            "pass": polyline("pass_rate"),
            "ticks": ticks,
            "labels": labels,
        }

    def activity_svg(
        self,
        *,
        width: float = 600.0,
        height: float = 180.0,
        pad_x: float = 10.0,
        pad_top: float = 10.0,
        pad_bottom: float = 28.0,
    ) -> dict[str, float | list[dict[str, float | int | str]]]:
        """SVG bar chart: answers + introduced aligned to a shared baseline."""
        n = len(self.activity)
        peak = self.activity_max
        plot_top = pad_top
        plot_bottom = height - pad_bottom
        plot_h = max(plot_bottom - plot_top, 1.0)
        inner_w = width - 2 * pad_x
        slot = inner_w / n if n else inner_w
        gap = min(1.2, slot * 0.08)
        bar_w = max((slot - gap) / 2.0, 0.8)

        def bar_h(value: int) -> float:
            if value <= 0:
                return 0.0
            return plot_h * (value / peak)

        bars: list[dict[str, float | int | str]] = []
        for i, day in enumerate(self.activity):
            x0 = pad_x + slot * i + gap / 2.0
            for kind, value, css, fill in (
                ("answers", day.answers, "bar-answers", "var(--accent)"),
                ("introduced", day.introduced, "bar-intro", "var(--doubt)"),
            ):
                h = bar_h(value)
                if h <= 0:
                    continue
                x = x0 if kind == "answers" else x0 + bar_w
                bars.append(
                    {
                        "x": round(x, 2),
                        "y": round(plot_bottom - h, 2),
                        "w": round(bar_w, 2),
                        "h": round(h, 2),
                        "class": css,
                        "fill_style": f"fill:{fill}",
                        "title": (
                            f"{day.label}: ответов {day.answers}, "
                            f"новых {day.introduced}"
                        ),
                    }
                )

        label_indices: list[int] = list(range(0, n, 7))
        if n:
            last = n - 1
            if last not in label_indices and label_indices and last - label_indices[-1] >= 4:
                label_indices.append(last)
        labels = [
            {
                "x": round(pad_x + slot * i + slot / 2.0, 2),
                "label": self.activity[i].label,
            }
            for i in label_indices
        ]
        return {
            "width": width,
            "height": height,
            "baseline": plot_bottom,
            "pad_x": pad_x,
            "bars": bars,
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
    autoload: AutoloadStatus
    answers_yesterday: int
    adapt_note: str | None = None


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
            "«Освоить» = первый показ оставшихся карточек при ежедневных занятиях. "
            "Удержание (повтор ≥ 21 дн) у последних — примерно ещё +3 недели после этого; "
            "повторы после ввода новых продолжаются всегда. Лимит может менять авто."
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
    *,
    new_per_day: int | None = None,
) -> LoadStats:
    today = today or date.today()
    limit = (
        new_per_day
        if new_per_day is not None
        else get_new_per_day(conn, user_id, language)
    )
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
        new_per_day=limit,
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
              count(*) FILTER (WHERE NOT was_new AND interval_before >= 21) AS mature,
              count(*) FILTER (
                WHERE NOT was_new AND interval_before >= 21 AND NOT remembered
              ) AS mature_again,
              count(*) FILTER (WHERE rating = 1) AS rating_again,
              count(*) FILTER (WHERE rating = 2) AS rating_hard,
              count(*) FILTER (WHERE rating = 3) AS rating_good,
              count(*) FILTER (WHERE rating = 4) AS rating_easy,
              count(*) FILTER (WHERE rating IS NULL) AS rating_unrated
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
        mature_reviews_7=mature,
        mature_again_rate_7=_rate(int(row["mature_again"]), mature),
        rating_again=int(row["rating_again"]),
        rating_hard=int(row["rating_hard"]),
        rating_good=int(row["rating_good"]),
        rating_easy=int(row["rating_easy"]),
        rating_unrated=int(row["rating_unrated"]),
    )


def advise_load(
    corpus: CorpusStats,
    load: LoadStats,
    performance: PerformanceStats,
    *,
    language: str = "en",
) -> LoadAdvice:
    review_ok = performance.remember_rate_review_7
    again = performance.again_rate_7
    due = load.due_today

    # Need some review signal; otherwise keep.
    if performance.reviews_7 >= 20 and (
        (review_ok is not None and review_ok < 0.80)
        or (again is not None and again > 0.20)
        or due >= max(40, load.median_answers_per_day_7 * 1.5)
    ):
        suggested = clamp_new_per_day(language, load.new_per_day - 5)
        if suggested == load.new_per_day:
            return LoadAdvice(
                status="keep",
                label="Лимит на минимуме",
                detail="Сигналы к снижению есть, но ниже рамки языка уже нельзя.",
                suggested_new_per_day=load.new_per_day,
            )
        return LoadAdvice(
            status="lower",
            label="Авто склонно снизить",
            detail="Again/Hard или повторы давят. Лимит новых снизится после 3 дней подряд.",
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
        suggested = clamp_new_per_day(language, load.new_per_day + 5)
        if suggested == load.new_per_day:
            return LoadAdvice(
                status="keep",
                label="Лимит на максимуме",
                detail="Сигналы к усилению есть, но выше рамки языка уже нельзя.",
                suggested_new_per_day=load.new_per_day,
            )
        return LoadAdvice(
            status="raise",
            label="Авто склонно усилить",
            detail="Повторы стабильны, очередь небольшая. Лимит вырастет после 3 дней подряд.",
            suggested_new_per_day=suggested,
        )

    return LoadAdvice(
        status="keep",
        label="Лимит без изменений",
        detail="Очередь и Again в норме — авто оставляет квоту как есть.",
        suggested_new_per_day=load.new_per_day,
    )


def refresh_adaptive_load(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    today: date | None = None,
) -> AdaptResult:
    """Record today's advice and maybe change the user×language limit."""
    today = today or date.today()
    current = get_new_per_day(conn, user_id, language)
    corpus = fetch_corpus_stats(conn, user_id, language)
    load = fetch_load_stats(conn, user_id, language, today, new_per_day=current)
    performance = fetch_performance_stats(conn, user_id, language, today)
    advice = advise_load(corpus, load, performance, language=language)
    record_advice_day(
        conn, user_id, language, today, advice.status, advice.suggested_new_per_day
    )
    result = try_apply_hysteresis(
        conn,
        user_id,
        language,
        today,
        current=current,
        today_suggested=advice.suggested_new_per_day,
    )
    conn.commit()
    return result


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


def fetch_quality_series(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    today: date,
    days: int = 30,
) -> tuple[QualityDay, ...]:
    since = today - timedelta(days=days - 1)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
              answered_on AS day,
              count(*) AS reviews,
              count(*) FILTER (WHERE rating = 1 OR (rating IS NULL AND NOT remembered))
                AS again_n,
              count(*) FILTER (WHERE rating IN (3, 4)) AS pass_n,
              count(*) FILTER (WHERE rating IS NOT NULL) AS rated_n
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

    out: list[QualityDay] = []
    for i in range(days):
        day = since + timedelta(days=i)
        row = by_day.get(day)
        if row is None:
            out.append(
                QualityDay(
                    day=day,
                    label=_day_label(day),
                    reviews=0,
                    again_rate=None,
                    pass_rate=None,
                )
            )
            continue
        reviews = int(row["reviews"])
        rated = int(row["rated_n"])
        out.append(
            QualityDay(
                day=day,
                label=_day_label(day),
                reviews=reviews,
                again_rate=_rate(int(row["again_n"]), reviews),
                pass_rate=_rate(int(row["pass_n"]), rated) if rated else None,
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
        quality=fetch_quality_series(conn, user_id, language, today),
    )


def build_autoload_status(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    today: date,
    advice: LoadAdvice,
    *,
    note: str | None,
) -> AutoloadStatus:
    row = ensure_load_limit(conn, user_id, language)
    streak_status, streak_days = advice_streak(conn, user_id, language, today)
    return AutoloadStatus(
        new_per_day=row.new_per_day,
        base_new_per_day=row.base_new_per_day,
        updated_via=row.updated_via,
        last_change_on=row.last_change_on,
        advice_status=advice.status,
        streak_status=streak_status,
        streak_days=streak_days,
        needed_days=HYSTERESIS_DAYS,
        note=note,
        advice_days=fetch_advice_series(conn, user_id, language, today),
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
    adapt = refresh_adaptive_load(conn, user_id, language, today)
    current = adapt.new_per_day
    corpus = fetch_corpus_stats(conn, user_id, language)
    load = fetch_load_stats(conn, user_id, language, today, new_per_day=current)
    performance = fetch_performance_stats(conn, user_id, language, today)
    advice = advise_load(corpus, load, performance, language=language)
    introduced_7 = fetch_introduced_last_days(conn, user_id, language, today, 7)
    horizon = build_horizon(corpus.new_cards, load.new_per_day, introduced_7)
    charts = build_stats_charts(conn, user_id, language, corpus, today)
    autoload = build_autoload_status(
        conn, user_id, language, today, advice, note=adapt.note
    )
    yesterday = today - timedelta(days=1)
    answers_yesterday = next(
        (d.answers for d in charts.activity if d.day == yesterday), 0
    )
    return LanguageSummary(
        language=language,
        corpus=corpus,
        load=load,
        performance=performance,
        advice=advice,
        horizon=horizon,
        charts=charts,
        autoload=autoload,
        answers_yesterday=answers_yesterday,
        adapt_note=adapt.note,
    )
