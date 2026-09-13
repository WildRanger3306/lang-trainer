#!/usr/bin/env python3
"""Merge duplicate dictionary rows in Postgres by (language, lower(form), POS).

JSON wordlists stay as source dumps and are not modified.
Survivor prefers newer textbooks (Starlight 7 > 6, Loiseau Blue 6 > 5).
Creates unique index uq_entries_lang_form_pos when done.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import connect

TEXTBOOK_RANK = {
    "Starlight 7": 70,
    "Starlight 6": 60,
    "Loiseau Blue 6": 66,
    "Loiseau Blue 5": 55,
}


def _rank(textbooks: list[str] | None) -> int:
    if not textbooks:
        return 0
    return max(TEXTBOOK_RANK.get(name, 0) for name in textbooks)


def _merge_translations(*lists: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for lst in lists:
        for text in lst or []:
            k = text.casefold().strip()
            if not k or k in seen:
                continue
            seen.add(k)
            out.append(text.strip())
    return out


def _merge_tags(*lists: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for lst in lists:
        for name in lst or []:
            if name in seen:
                continue
            seen.add(name)
            out.append(name)
    return out


def dedupe_db() -> tuple[int, int]:
    with connect() as conn:
        groups = conn.execute(
            """
            SELECT language::text, lower(form), part_of_speech::text,
                   array_agg(id ORDER BY id)
            FROM entries
            GROUP BY 1, 2, 3
            HAVING count(*) > 1
            """
        ).fetchall()
        deleted = 0
        for _language, _form_key, _pos, ids in groups:
            rows = conn.execute(
                """
                SELECT e.id, e.part_of_speech_code, e.transcription,
                       e.gender::text, e.level::text,
                       coalesce(
                         (
                           SELECT array_agg(t.name ORDER BY t.name)
                           FROM entry_textbooks et
                           JOIN textbooks t ON t.id = et.textbook_id
                           WHERE et.entry_id = e.id
                         ),
                         ARRAY[]::text[]
                       ) AS books,
                       coalesce(
                         (
                           SELECT array_agg(tr.text ORDER BY tr.position)
                           FROM entry_translations tr
                           WHERE tr.entry_id = e.id
                         ),
                         ARRAY[]::text[]
                       ) AS translations
                FROM entries e
                WHERE e.id = ANY(%s)
                """,
                (list(ids),),
            ).fetchall()
            scored = sorted(
                rows,
                key=lambda r: (
                    -_rank(list(r[5] or [])),
                    -len(r[6] or []),
                    r[0],
                ),
            )
            survivor = scored[0]
            surv_id = survivor[0]
            all_books: list[str] = []
            all_tr: list[str] = []
            for r in scored:
                all_books = _merge_tags(all_books, list(r[5] or []))
                all_tr = _merge_translations(all_tr, list(r[6] or []))

            code, transcription, gender, level = (
                survivor[1],
                survivor[2],
                survivor[3],
                survivor[4],
            )
            for r in scored[1:]:
                if not code and r[1]:
                    code = r[1]
                if not transcription and r[2]:
                    transcription = r[2]
                if not gender and r[3]:
                    gender = r[3]
                if not level and r[4]:
                    level = r[4]

            conn.execute(
                """
                UPDATE entries SET
                  part_of_speech_code = %s,
                  transcription = %s,
                  gender = %s::noun_gender,
                  level = %s::cefr_level
                WHERE id = %s
                """,
                (code, transcription, gender, level, surv_id),
            )
            conn.execute(
                "DELETE FROM entry_translations WHERE entry_id = %s", (surv_id,)
            )
            for position, text in enumerate(all_tr, start=1):
                conn.execute(
                    """
                    INSERT INTO entry_translations (entry_id, position, text)
                    VALUES (%s, %s, %s)
                    """,
                    (surv_id, position, text),
                )
            for name in all_books:
                conn.execute(
                    "INSERT INTO textbooks (name) VALUES (%s) ON CONFLICT DO NOTHING",
                    (name,),
                )
                conn.execute(
                    """
                    INSERT INTO entry_textbooks (entry_id, textbook_id)
                    SELECT %s, id FROM textbooks WHERE name = %s
                    ON CONFLICT DO NOTHING
                    """,
                    (surv_id, name),
                )

            for loser_id in (r[0] for r in scored[1:]):
                conn.execute(
                    """
                    INSERT INTO card_progress (
                      user_id, entry_id, direction, due_on, interval_days,
                      stability, difficulty, fsrs_state, fsrs_step, last_review,
                      introduced_on, introduced_via
                    )
                    SELECT user_id, %s, direction, due_on, interval_days,
                           stability, difficulty, fsrs_state, fsrs_step, last_review,
                           introduced_on, introduced_via
                    FROM card_progress
                    WHERE entry_id = %s
                    ON CONFLICT (user_id, entry_id, direction) DO NOTHING
                    """,
                    (surv_id, loser_id),
                )
                conn.execute(
                    """
                    UPDATE card_reviews SET entry_id = %s
                    WHERE entry_id = %s
                    """,
                    (surv_id, loser_id),
                )
                conn.execute("DELETE FROM entries WHERE id = %s", (loser_id,))
                deleted += 1

        conn.commit()
        return len(groups), deleted


def ensure_unique_index() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_entries_lang_form_pos
            ON entries (language, lower(form), part_of_speech)
            """
        )
        conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="merge only; do not create unique index",
    )
    args = parser.parse_args()
    groups, deleted = dedupe_db()
    print(f"db: merged {groups} groups, deleted {deleted} entries")
    if not args.skip_index:
        ensure_unique_index()
        print("db: unique index uq_entries_lang_form_pos ensured")


if __name__ == "__main__":
    main()
