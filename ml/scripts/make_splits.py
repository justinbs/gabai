"""Split the dataset 70/15/15, stratified, and write the three files.

    python scripts/make_splits.py data/requests.csv

Stratifies on category and urgency together, so a rare pairing like a low-urgency
dispute does not end up entirely in train. Falls back to category alone when a
pairing is too small to split, and says so.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sklearn.model_selection import train_test_split

from common import DATA, SEED, load_csv


def _stratify_key(df):
    pairs = df["category"] + "|" + df["urgency"]
    # train_test_split needs at least 2 of every class in the column it
    # stratifies on. Below that, fall back rather than crash.
    if pairs.value_counts().min() >= 2:
        return pairs, "category+urgency"
    if df["category"].value_counts().min() >= 2:
        return df["category"], "category only (some category+urgency pairs are too rare)"
    return None, "none (dataset too small to stratify)"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--out", type=Path, default=DATA)
    args = parser.parse_args()

    df = load_csv(args.csv)
    before = len(df)
    df = df.drop_duplicates(subset="text").reset_index(drop=True)
    if len(df) < before:
        print(f"dropped {before - len(df)} duplicate texts")
    print(f"{len(df)} rows from {args.csv.name}")

    strat, how = _stratify_key(df)
    print(f"stratifying on {how}")

    train, rest = train_test_split(
        df, test_size=0.30, random_state=SEED, stratify=strat
    )
    rest_strat, rest_how = _stratify_key(rest)
    if rest_how != how:
        print(f"val/test split stratifying on {rest_how}")
    val, test = train_test_split(
        rest, test_size=0.50, random_state=SEED, stratify=rest_strat
    )

    args.out.mkdir(parents=True, exist_ok=True)
    for name, part in (("train", train), ("val", val), ("test", test)):
        path = args.out / f"{name}.csv"
        part.to_csv(path, index=False)
        print(f"  {name:5} {len(part):5} rows -> {path.name}")

    # Both heads, because both are stratified on and both are reported in the
    # dataset card.
    for head in ("category", "urgency"):
        print(f"\n{head} counts per split")
        for name, part in (("train", train), ("val", val), ("test", test)):
            print(f"  {name:5} {part[head].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
