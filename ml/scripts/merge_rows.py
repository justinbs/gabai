"""Merge the per-writer row files into one dataset.

    python scripts/merge_rows.py
    python scripts/merge_rows.py --skip jean

Each writer works in their own `data/rows-<name>.csv` so three people are not
editing one file in git. They came back in three different shapes, so this
normalises before merging rather than asking anyone to re-edit a spreadsheet.

What it normalises, and why each one is safe:

- Category and urgency are lowercased to the slugs in `common.CATEGORIES`. One
  writer used display names. The mapping is one to one, so no label changes
  meaning.
- `source` is forced to `synthetic`. The barangay declined to share records, so
  every row here is authored. One file carried intake channels in this column,
  which would have claimed a provenance the dataset does not have.
- `author` becomes a1, a2, a3 by source file. The QA check asks whether one
  person's phrasing dominates a category, and it can only answer that if author
  identifies a person.
- `flag` becomes empty or `unsure`. One file used TRUE and FALSE.

Nothing here rewrites `text`. A row is kept as written or not kept at all.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

from common import CATEGORIES, DATA, URGENCIES

# a1, a2, a3 is the code the labelling guide asks writers to use.
WRITERS = {"justin": "a1", "jean": "a2", "daniel": "a3"}

# Display names one writer used. Every value maps onto exactly one slug.
CATEGORY_ALIASES = {
    "road & infrastructure": "road_infrastructure",
    "public health & sanitation": "public_health_sanitation",
    "public safety & peace and order": "public_safety",
    "utilities": "utilities",
    "social welfare & assistance": "social_welfare",
    "neighbor dispute & nuisance": "neighbor_dispute",
    "other / general inquiry": "other",
}

COLUMNS = ["text", "category", "urgency", "source", "author", "flag", "lang"]


def norm_category(raw: str) -> str | None:
    value = raw.strip().lower()
    if value in CATEGORIES:
        return value
    return CATEGORY_ALIASES.get(value)


def norm_urgency(raw: str) -> str | None:
    value = raw.strip().lower()
    return value if value in URGENCIES else None


def norm_flag(raw: str) -> str:
    value = raw.strip().lower()
    if value in ("", "false", "no", "0"):
        return ""
    if value in ("true", "yes", "1"):
        return "unsure"
    return raw.strip()


def dedupe_key(text: str) -> str:
    # Case and punctuation insensitive. The same sentence either side of the
    # train/test line inflates every number we report, and a trailing "po" or a
    # comma is not a different row.
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def read_rows(path: Path, code: str, problems: list[str]) -> list[dict]:
    out = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for line_no, raw in enumerate(csv.DictReader(handle), start=2):
            text = (raw.get("text") or "").strip()
            if not text:
                problems.append(f"{path.name}:{line_no} blank text")
                continue

            category = norm_category(raw.get("category") or "")
            urgency = norm_urgency(raw.get("urgency") or "")
            if category is None:
                problems.append(f"{path.name}:{line_no} unknown category {raw.get('category')!r}")
                continue
            if urgency is None:
                problems.append(f"{path.name}:{line_no} unknown urgency {raw.get('urgency')!r}")
                continue

            out.append(
                {
                    "text": text,
                    "category": category,
                    "urgency": urgency,
                    "source": "synthetic",
                    "author": code,
                    "flag": norm_flag(raw.get("flag") or ""),
                    "lang": (raw.get("lang") or "").strip(),
                }
            )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--skip", nargs="*", default=[], help="writer names to leave out of the merge"
    )
    args = parser.parse_args()
    out_path = args.out or (args.data / "requests.csv")

    problems: list[str] = []
    merged: list[dict] = []
    seen: dict[str, str] = {}
    dropped_dupes = 0

    for name, code in WRITERS.items():
        if name in args.skip:
            print(f"{name:7} skipped")
            continue
        path = args.data / f"rows-{name}.csv"
        if not path.exists():
            print(f"{name:7} no file at {path.name}")
            continue

        rows = read_rows(path, code, problems)
        kept = 0
        for row in rows:
            key = dedupe_key(row["text"])
            if key in seen:
                dropped_dupes += 1
                continue
            seen[key] = code
            merged.append(row)
            kept += 1
        print(f"{name:7} {code}  read {len(rows):5}  kept {kept:5}")

    if problems:
        print(f"\n{len(problems)} rows dropped:")
        for line in problems[:25]:
            print(f"  {line}")
        if len(problems) > 25:
            print(f"  ... and {len(problems) - 25} more")

    if dropped_dupes:
        print(f"\n{dropped_dupes} duplicate texts dropped, first occurrence kept")

    if not merged:
        sys.exit("nothing to write")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(merged)

    print(f"\n{len(merged)} rows -> {out_path.relative_to(out_path.parents[1])}")
    print("\nper category")
    counts = Counter(r["category"] for r in merged)
    for slug in CATEGORIES:
        print(f"  {slug:26} {counts[slug]:5}")
    print("\nper writer")
    for code in sorted(set(r["author"] for r in merged)):
        print(f"  {code}  {sum(1 for r in merged if r['author'] == code):5}")


if __name__ == "__main__":
    main()
