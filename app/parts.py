"""Parts of speech shown as filter chips (several DB values can share one chip)."""

from __future__ import annotations

# (key, full label, short label for the chip, part_of_speech values)
PART_GROUPS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("noun", "Существительные", "Сущ.", ("noun",)),
    ("verb", "Глаголы", "Гл.", ("verb",)),
    ("phrasal_verb", "Фразовые глаголы", "Фраз. гл.", ("phrasal_verb",)),
    ("adjective", "Прилагательные", "Прил.", ("adjective",)),
    ("adverb", "Наречия", "Нареч.", ("adverb",)),
    ("phrase", "Фразы", "Фразы", ("phrase",)),
    ("other", "Другое", "Другое", ("other", "pronoun", "numeral")),
)

GROUP_KEYS = tuple(key for key, *_rest in PART_GROUPS)
_VALUES = {key: values for key, _label, _short, values in PART_GROUPS}
_LABELS = {key: label for key, label, _short, _values in PART_GROUPS}
_GROUP_OF = {value: key for key, _label, _short, values in PART_GROUPS for value in values}


def clean_parts(keys) -> tuple[str, ...]:
    """Known group keys only, in chip order, without duplicates."""
    wanted = set(keys)
    return tuple(key for key in GROUP_KEYS if key in wanted)


def expand_parts(keys) -> list[str]:
    """Group keys -> part_of_speech values used in the query."""
    return [value for key in clean_parts(keys) for value in _VALUES[key]]


def group_of(part_of_speech: str) -> str:
    return _GROUP_OF.get(part_of_speech, "other")


def part_label(key: str) -> str:
    return _LABELS[key]
