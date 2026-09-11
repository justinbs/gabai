"""Check a labelled dataset before it is used for anything.

    python scripts/check_dataset.py data/requests.csv
    python scripts/check_dataset.py data/a1.csv --against data/a2.csv

Reports duplicates, class balance, the category by urgency spread, and who wrote
what. With `--against`, compares two people who labelled the same rows and
reports Cohen's kappa.

**This reports, it does not clean.** Nothing here rewrites or drops a row, and
that is deliberate. A dataset needs genuinely hard cases or the accuracy comes
out suspiciously high, so a script that tidies ambiguity away would delete the
thing that makes the numbers believable. Read the output and decide.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

from common import CATEGORIES, HEADS, URGENCIES, load_csv

# Below this, a category has too few rows for a per-class F1 that means anything.
# Roughly fifteen in a 15% test split, so roughly a hundred overall.
THIN_CATEGORY = 100


def _duplicates(df: pd.DataFrame) -> None:
    print("\n== duplicates ==")
    exact = df[df["text"].duplicated(keep=False)].sort_values("text")
    if exact.empty:
        print("  none")
        return
    print(f"  {df['text'].duplicated().sum()} repeated texts, {len(exact)} rows involved")
    for text, group in exact.groupby("text"):
        authors = ", ".join(sorted(group["author"])) if "author" in group else "?"
        print(f"    {len(group)}x [{authors}] {text[:70]}")


def _balance(df: pd.DataFrame) -> None:
    print("\n== category balance ==")
    counts = df["category"].value_counts()
    for slug in CATEGORIES:
        n = int(counts.get(slug, 0))
        share = 100 * n / len(df)
        note = "  THIN" if n < THIN_CATEGORY else ""
        print(f"  {slug:26} {n:5}  {share:5.1f}%{note}")
    missing = [c for c in CATEGORIES if c not in counts.index]
    if missing:
        print(f"  MISSING ENTIRELY: {missing}")

    spread = counts.max() / max(counts.min(), 1)
    print(f"  largest / smallest = {spread:.1f}x")
    if spread > 3:
        print("  lopsided enough that macro F1 will be dominated by the big classes")
    elif spread < 1.2 and len(df) > 200:
        print("  almost exactly equal, which reads as manufactured to anyone who checks")


def _cross_tab(df: pd.DataFrame) -> None:
    # The check behind "spread urgency inside every category". If a category is
    # all one urgency, the model can learn the category from the urgency and both
    # numbers stop meaning anything.
    print("\n== category by urgency ==")
    table = pd.crosstab(df["category"], df["urgency"])
    for urgency in URGENCIES:
        if urgency not in table.columns:
            table[urgency] = 0
    table = table[URGENCIES].reindex(CATEGORIES, fill_value=0)
    print(table.to_string())

    print()
    for slug, row in table.iterrows():
        total = int(row.sum())
        if total == 0:
            continue
        top = int(row.max()) / total
        if top > 0.8:
            worst = row.idxmax()
            print(f"  {slug}: {100 * top:.0f}% is '{worst}'. Needs the other two.")


def _authors(df: pd.DataFrame) -> None:
    if "author" not in df.columns:
        return
    print("\n== who wrote what ==")
    table = pd.crosstab(df["category"], df["author"])
    print(table.to_string())
    print()
    for slug, row in table.iterrows():
        total = int(row.sum())
        if total < 10:
            continue
        top = int(row.max()) / total
        if top > 0.8:
            print(f"  {slug}: {100 * top:.0f}% by {row.idxmax()}. One person's phrasing.")


def _flagged(df: pd.DataFrame) -> None:
    if "flag" not in df.columns:
        return
    flagged = df[df["flag"].notna() & (df["flag"].astype(str).str.strip() != "")]
    print(f"\n== flagged as hard: {len(flagged)} ==")
    print("  Keep these. Where labellers hesitate is where the taxonomy is unclear,")
    print("  and that belongs in the paper rather than in the bin.")


def _agreement(a: pd.DataFrame, b: pd.DataFrame) -> None:
    print("\n== agreement between two labellers ==")
    merged = a.merge(b, on="text", suffixes=("_a", "_b"))
    if merged.empty:
        print("  no shared texts. Both files have to label the same rows.")
        return
    print(f"  {len(merged)} rows labelled by both")
    for head in HEADS:
        left, right = merged[f"{head}_a"], merged[f"{head}_b"]
        agreed = (left == right).mean()
        kappa = cohen_kappa_score(left, right)
        print(f"  {head:9} raw agreement {100 * agreed:5.1f}%   kappa {kappa:.3f}")
        if kappa < 0.6:
            print(f"    weak. The guide is unclear somewhere on {head}.")
        disagreed = merged[left != right]
        for _, row in disagreed.head(8).iterrows():
            print(f"      {row[f'{head}_a']:>24} vs {row[f'{head}_b']:<24} {row['text'][:44]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--against", type=Path, help="second labeller's file")
    args = parser.parse_args()

    df = load_csv(args.csv)
    print(f"{len(df)} rows from {args.csv.name}")

    _duplicates(df)
    _balance(df)
    _cross_tab(df)
    _authors(df)
    _flagged(df)

    if args.against:
        _agreement(df, load_csv(args.against))


if __name__ == "__main__":
    main()
