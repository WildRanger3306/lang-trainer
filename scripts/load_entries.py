#!/usr/bin/env python3
"""Load entry JSON into Postgres. Replaces all entries, keeps tag dictionaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import connect


def load_entries(entries: list[dict], *, replace: bool = True) -> int:
    topics: set[str] = set()
    textbooks: set[str] = set()
    for entry in entries:
        if not entry.get("translations"):
            raise SystemExit(f"entry {entry.get('form')!r} has no translations")
        topics.update(entry.get("topics") or [])
        textbooks.update(entry.get("textbooks") or [])

    with connect() as conn:
        with conn.transaction():
            if replace:
                conn.execute("TRUNCATE entries RESTART IDENTITY CASCADE")
            for name in sorted(topics):
                conn.execute(
                    "INSERT INTO topics (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                    (name,),
                )
            for name in sorted(textbooks):
                conn.execute(
                    "INSERT INTO textbooks (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                    (name,),
                )
            for entry in entries:
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
                for position, text in enumerate(entry["translations"], start=1):
                    conn.execute(
                        """
                        INSERT INTO entry_translations (entry_id, position, text)
                        VALUES (%s, %s, %s)
                        """,
                        (entry_id, position, text),
                    )
                for name in entry.get("topics") or []:
                    conn.execute(
                        """
                        INSERT INTO entry_topics (entry_id, topic_id)
                        SELECT %s, id FROM topics WHERE name = %s
                        """,
                        (entry_id, name),
                    )
                for name in entry.get("textbooks") or []:
                    conn.execute(
                        """
                        INSERT INTO entry_textbooks (entry_id, textbook_id)
                        SELECT %s, id FROM textbooks WHERE name = %s
                        """,
                        (entry_id, name),
                    )
    return len(entries)


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
        help="add entries without truncating the table",
    )
    args = parser.parse_args()
    entries = collect_entries(args.paths)
    count = load_entries(entries, replace=not args.append)
    mode = "appended" if args.append else "loaded"
    print(f"{mode} {count} entries from {len(args.paths)} path(s)")


if __name__ == "__main__":
    main()
