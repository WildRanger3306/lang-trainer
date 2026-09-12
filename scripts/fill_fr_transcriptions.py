#!/usr/bin/env python3
"""Fill French entry transcriptions from ipa-dict (fr_FR).

Default: skip phrases (same policy as EN Starlight fill).
Handles forms like `petit, petite` (first lemma) and trailing punctuation.

Usage:
  python3 scripts/fill_fr_transcriptions.py docs/words/json/loiseau_blue_5 --skip-pos phrase
  python3 scripts/fill_fr_transcriptions.py docs/words/json/loiseau_blue_6 docs/words/json/fr_trainer --skip-pos phrase
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEXICON = ROOT / "docs" / "words" / "ipa" / "fr_FR.txt"


def load_lexicon(path: Path) -> dict[str, str]:
    lex: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or "\t" not in line:
            continue
        word, ipa = line.split("\t", 1)
        lex[word.casefold()] = ipa.strip()
    return lex


def normalize_ipa(raw: str) -> str:
    first = raw.split(",")[0].strip()
    if first.startswith("/") and first.endswith("/") and len(first) > 2:
        first = first[1:-1]
    # Keep French ʁ; only normalize IPA g glyph.
    return first.strip().replace("ɡ", "g")


def form_candidates(form: str) -> list[str]:
    """Lookup keys to try for a JSON form."""
    f = form.strip().replace("’", "'")
    f = f.rstrip(" !.?;:…")
    out: list[str] = []
    seen: set[str] = set()

    def add(x: str) -> None:
        x = x.strip()
        if not x:
            return
        k = x.casefold()
        if k not in seen:
            seen.add(k)
            out.append(x)

    add(f)
    if "," in f:
        add(f.split(",", 1)[0])
    # "diriger (se)" / "endormir (s')" → try lemma + reflexive
    m = re.match(r"^(.+?)\s*\((se|s')\)\s*$", f, flags=re.I)
    if m:
        lemma = m.group(1).strip()
        add(lemma)
        add(f"se {lemma}")
        add(f"s'{lemma}" if lemma[:1].lower() in "aeiouyhàâäéèêëîïôùûüœ" else f"se {lemma}")
    return out


def lookup(lex: dict[str, str], form: str, *, compose: bool) -> str | None:
    for cand in form_candidates(form):
        key = cand.casefold()
        if key in lex:
            return normalize_ipa(lex[key])
    if not compose:
        return None
    key = form_candidates(form)[0].casefold() if form_candidates(form) else ""
    tokens = re.findall(r"[a-zàâäéèêëïîôùûüçœæ0-9']+", key, flags=re.I)
    if len(tokens) < 2:
        return None
    parts: list[str] = []
    for tok in tokens:
        if tok.casefold() not in lex:
            return None
        parts.append(normalize_ipa(lex[tok.casefold()]))
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
        if entry.get("language") != "fr":
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
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--lexicon", type=Path, default=DEFAULT_LEXICON)
    parser.add_argument("--compose", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-pos", action="append", default=[], metavar="POS")
    parser.add_argument("--dry-run", action="store_true")
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
        rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        print(
            f"{rel}: filled {stats['filled']}, miss {stats['miss']}, "
            f"skip_pos {stats['skipped_pos']}, keep {stats['skipped_existing']} "
            f"/ {stats['total']}"
        )

    mode = "dry-run" if args.dry_run else "wrote"
    eligible = totals["total"] - totals["skipped_pos"]
    print(
        f"{mode} filled {totals['filled']}/{eligible} eligible "
        f"({100 * totals['filled'] / max(1, eligible):.1f}%), "
        f"miss {totals['miss']}, skipped pos {totals['skipped_pos']}"
    )


if __name__ == "__main__":
    main()
