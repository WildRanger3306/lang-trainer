#!/usr/bin/env python3
"""Load entry JSON into Postgres.

Default: replace all entries.
--append: upsert by (language, lower(form), part_of_speech) — merge translations
and textbook/topic tags into the existing row (JSON dumps may still contain
cross-book duplicates; uniqueness lives in the DB).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import connect


def _merge_translations(existing: list[str], incoming: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for text in existing + incoming:
        k = text.casefold().strip()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(text.strip())
    return out


def _ensure_tags(conn, table: str, names: set[str]) -> None:
    for name in sorted(names):
        conn.execute(
            f"INSERT INTO {table} (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
            (name,),
        )


def _link_tags(
    conn,
    entry_id: int,
    *,
    topics: list[str],
    textbooks: list[str],
) -> None:
    for name in topics:
        conn.execute(
            """
            INSERT INTO entry_topics (entry_id, topic_id)
            SELECT %s, id FROM topics WHERE name = %s
            ON CONFLICT DO NOTHING
            """,
            (entry_id, name),
        )
    for name in textbooks:
        conn.execute(
            """
            INSERT INTO entry_textbooks (entry_id, textbook_id)
            SELECT %s, id FROM textbooks WHERE name = %s
            ON CONFLICT DO NOTHING
            """,
            (entry_id, name),
        )


def _rewrite_translations(conn, entry_id: int, translations: list[str]) -> None:
    conn.execute("DELETE FROM entry_translations WHERE entry_id = %s", (entry_id,))
    for position, text in enumerate(translations, start=1):
        conn.execute(
            """
            INSERT INTO entry_translations (entry_id, position, text)
            VALUES (%s, %s, %s)
            """,
            (entry_id, position, text),
        )


def _upsert_entry(conn, entry: dict) -> str:
    """Insert or merge. Returns 'insert' | 'merge'."""
    existing = conn.execute(
        """
        SELECT id FROM entries
        WHERE language = %s
          AND lower(form) = lower(%s)
          AND part_of_speech = %s
        """,
        (entry["language"], entry["form"], entry["partOfSpeech"]),
    ).fetchone()

    topics = list(entry.get("topics") or [])
    textbooks = list(entry.get("textbooks") or [])
    incoming_tr = list(entry["translations"])

    if existing is None:
        row = conn.execute(
            """
            INSERT INTO entries (
              language, form, part_of_speech, part_of_speech_code,
              transcription, gender, level
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                entry["language"],
                entry["form"],
                entry["partOfSpeech"],
                entry.get("partOfSpeechCode"),
                entry.get("transcription"),
                entry.get("gender"),
                entry.get("level"),
            ),
        ).fetchone()
        entry_id = row[0]
        _rewrite_translations(conn, entry_id, incoming_tr)
        _link_tags(conn, entry_id, topics=topics, textbooks=textbooks)
        return "insert"

    entry_id = existing[0]
    old_tr = [
        r[0]
        for r in conn.execute(
            """
            SELECT text FROM entry_translations
            WHERE entry_id = %s ORDER BY position
            """,
            (entry_id,),
        ).fetchall()
    ]
    merged = _merge_translations(old_tr, incoming_tr)
    _rewrite_translations(conn, entry_id, merged)

    # Fill empty scalars from incoming.
    conn.execute(
        """
        UPDATE entries SET
          part_of_speech_code = COALESCE(part_of_speech_code, %s),
          transcription = COALESCE(transcription, %s),
          gender = COALESCE(gender, %s::noun_gender),
          level = COALESCE(level, %s::cefr_level)
        WHERE id = %s
        """,
        (
            entry.get("partOfSpeechCode"),
            entry.get("transcription"),
            entry.get("gender"),
            entry.get("level"),
            entry_id,
        ),
    )
    _link_tags(conn, entry_id, topics=topics, textbooks=textbooks)
    return "merge"


def load_entries(entries: list[dict], *, replace: bool = True) -> dict[str, int]:
    topics: set[str] = set()
    textbooks: set[str] = set()
    for entry in entries:
        if not entry.get("translations"):
            raise SystemExit(f"entry {entry.get('form')!r} has no translations")
        topics.update(entry.get("topics") or [])
        textbooks.update(entry.get("textbooks") or [])

    inserted = merged = 0
    with connect() as conn:
        with conn.transaction():
            if replace:
                conn.execute("TRUNCATE entries RESTART IDENTITY CASCADE")
            _ensure_tags(conn, "topics", topics)
            _ensure_tags(conn, "textbooks", textbooks)
            for entry in entries:
                action = _upsert_entry(conn, entry)
                if action == "insert":
                    inserted += 1
                else:
                    merged += 1
    return {"inserted": inserted, "merged": merged, "total": len(entries)}


def collect_entries(paths: list[Path]) -> list[dict]:
    entries: list[dict] = []
    for path in paths:
        if path.is_dir():
            files = sorted(path.glob("*.json"))
            if not files:
                raise SystemExit(f"no JSON files in {path}")
            for file in files:
                payload = json.loads(file.read_text())
                entries.extend(payload["entries"])
        else:
            payload = json.loads(path.read_text())
            entries.extend(payload["entries"])
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="JSON file(s) or directory of JSON files",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="upsert without truncating (merge translations/tags on conflict)",
    )
    args = parser.parse_args()
    entries = collect_entries(args.paths)
    stats = load_entries(entries, replace=not args.append)
    mode = "appended" if args.append else "loaded"
    print(
        f"{mode} {stats['total']} JSON rows → "
        f"inserted {stats['inserted']}, merged {stats['merged']}"
    )


if __name__ == "__main__":
    main()
