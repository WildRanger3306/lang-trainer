"""Human titles for topic codes and compact ranges like "M1–M3"."""

from __future__ import annotations

import re

SL7_MODULES = {
    1: "Work & Play",
    2: "Culture & Stories",
    3: "Mother Nature",
    4: "Healthy mind, healthy body",
    5: "Life experiences",
    6: "Crime & community",
}

_SERIES = (
    (re.compile(r"^sl7_m(\d+)$"), "M"),
    (re.compile(r"^lb6_u(\d+)$"), "U"),
)

WHOLE_BANK = {"frt_all", "lb5_all"}

_FIXED = {
    "bridge_sl5": "Мост: слова SL5",
    "bridge_sl6": "Мост: слова SL6",
    "lb5_all": "Весь LB5",
    "frt_all": "Весь FR Trainer",
    "irr_sl6": "Таблица глаголов SL6",
}


def _series(code: str) -> tuple[str, int] | None:
    for pattern, prefix in _SERIES:
        match = pattern.match(code)
        if match:
            return prefix, int(match.group(1))
    return None


def topic_title(code: str) -> str:
    """Chip label: "M1 Work & Play", "U3", or the code itself when unknown."""
    series = _series(code)
    if series:
        prefix, number = series
        name = SL7_MODULES.get(number) if prefix == "M" else None
        return f"{prefix}{number} {name}" if name else f"{prefix}{number}"
    return _FIXED.get(code, code)


def compress_topics(codes: list[str]) -> str:
    """"M1–M3, M5" for consecutive numbered topics; other topics keep their titles."""
    numbered: dict[str, list[int]] = {}
    others: list[str] = []
    for code in codes:
        series = _series(code)
        if series:
            numbered.setdefault(series[0], []).append(series[1])
        else:
            others.append(_FIXED.get(code, code))
    parts: list[str] = []
    for prefix, numbers in numbered.items():
        numbers = sorted(set(numbers))
        start = prev = numbers[0]
        for n in [*numbers[1:], None]:
            if n is not None and n == prev + 1:
                prev = n
                continue
            parts.append(
                f"{prefix}{start}" if start == prev else f"{prefix}{start}–{prefix}{prev}"
            )
            if n is not None:
                start = prev = n
    return ", ".join([*parts, *others])


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", "\u00a0")


def words_label(count: int) -> str:
    """"1 слово", "3 слова", "1 885 слов"."""
    tail = count % 100
    if 11 <= tail <= 14:
        word = "слов"
    elif count % 10 == 1:
        word = "слово"
    elif 2 <= count % 10 <= 4:
        word = "слова"
    else:
        word = "слов"
    return f"{format_number(count)}\u00a0{word}"
