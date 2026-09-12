#!/usr/bin/env python3
"""Fill English entry transcriptions from ipa-dict (default: en_UK for Starlight).

Phrases usually miss in the lexicon; skip with --skip-pos phrase.
Optional --compose joins per-word IPA for multiword forms.

Usage:
  python3 scripts/fill_en_transcriptions.py docs/words/json/starlight_6 --skip-pos phrase --overwrite
  python3 scripts/fill_en_transcriptions.py docs/words/json/starlight_6 --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEXICON = ROOT / "docs" / "words" / "ipa" / "en_UK.txt"


def load_lexicon(path: Path) -> dict[str, str]:
    lex: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or "\t" not in line:
            continue
        word, ipa = line.split("\t", 1)
        lex[word.casefold()] = ipa.strip()
    return lex


def normalize_ipa(raw: str) -> str:
    """Pick first variant; strip wrapping slashes; simplify for learners."""
    first = raw.split(",")[0].strip()
    if first.startswith("/") and first.endswith("/") and len(first) > 2:
        first = first[1:-1]
    return simplify_ipa(first.strip())


def simplify_ipa(ipa: str) -> str:
    """Academic IPA → school-friendly symbols (Starlight-style)."""
    return (
        ipa.replace("ɫ", "l")  # dark L → plain L
        .replace("ɹ", "r")  # alveolar approximant → r
        .replace("ɡ", "g")  # IPA g → latin g
    )


def lookup(lex: dict[str, str], form: str, *, compose: bool) -> str | None:
    key = form.strip().casefold().replace("’", "'")
    if key in lex:
        return normalize_ipa(lex[key])
    if not compose:
        return None
    # Multiword: join lookups of tokens (skip if any missing).
    tokens = re.findall(r"[a-z0-9']+", key)
    if len(tokens) < 2:
        return None
    parts: list[str] = []
    for tok in tokens:
        if tok not in lex:
            return None
        parts.append(normalize_ipa(lex[tok]))
    return " ".join(parts)


def collect_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for path in paths:
        if path.is_dir():
            out.extend(sorted(path.glob("*.json")))
        else:
            out.append(path)
    return out


def process_file(
    path: Path,
    lex: dict[str, str],
    *,
    compose: bool,
    overwrite: bool,
    dry_run: bool,
    skip_pos: set[str],
) -> dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    stats = {
        "filled": 0,
        "skipped_existing": 0,
        "skipped_pos": 0,
        "miss": 0,
        "total": 0,
    }
    changed = False
    for entry in data.get("entries") or []:
        if entry.get("language") != "en":
            continue
        stats["total"] += 1
        if entry.get("partOfSpeech") in skip_pos:
            stats["skipped_pos"] += 1
            continue
        existing = entry.get("transcription")
        if existing and not overwrite:
            stats["skipped_existing"] += 1
            continue
        ipa = lookup(lex, entry["form"], compose=compose)
        if not ipa:
            stats["miss"] += 1
            continue
        if existing != ipa:
            entry["transcription"] = ipa
            changed = True
        stats["filled"] += 1
    if changed and not dry_run:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="JSON file(s) or directories (e.g. starlight_6/0001.json)",
    )
    parser.add_argument(
        "--lexicon",
        type=Path,
        default=DEFAULT_LEXICON,
        help=f"ipa-dict TSV (default: {DEFAULT_LEXICON})",
    )
    parser.add_argument(
        "--compose",
        action="store_true",
        help="compose IPA for multiword forms from per-word lookups",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace non-null transcriptions",
    )
    parser.add_argument(
        "--skip-pos",
        action="append",
        default=[],
        metavar="POS",
        help="skip partOfSpeech (repeatable); e.g. --skip-pos phrase",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report coverage without writing JSON",
    )
    args = parser.parse_args()

    if not args.lexicon.is_file():
        raise SystemExit(f"lexicon not found: {args.lexicon}")

    lex = load_lexicon(args.lexicon)
    files = collect_paths(args.paths)
    if not files:
        raise SystemExit("no JSON files")

    skip_pos = set(args.skip_pos)
    totals = {
        "filled": 0,
        "skipped_existing": 0,
        "skipped_pos": 0,
        "miss": 0,
        "total": 0,
    }
    for path in files:
        stats = process_file(
            path,
            lex,
            compose=args.compose,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            skip_pos=skip_pos,
        )
        for k, v in stats.items():
            totals[k] += v
        print(
            f"{path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}: "
            f"filled {stats['filled']}, miss {stats['miss']}, "
            f"skip_pos {stats['skipped_pos']}, keep {stats['skipped_existing']} "
            f"/ {stats['total']}"
        )

    mode = "dry-run" if args.dry_run else "wrote"
    eligible = totals["total"] - totals["skipped_pos"]
    print(
        f"{mode} filled {totals['filled']}/{eligible} eligible "
        f"({100 * totals['filled'] / max(1, eligible):.1f}%), "
        f"miss {totals['miss']}, skipped phrases/pos {totals['skipped_pos']}"
    )


if __name__ == "__main__":
    main()
