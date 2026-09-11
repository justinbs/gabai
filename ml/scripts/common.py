"""Shared pieces: paths, the label sets, loading, and the metrics.

The transformer run imports the same functions as the baseline so the two are
scored identically. If they diverge here, the comparison in Chapter 4 is not a
comparison.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

ML_ROOT = Path(__file__).resolve().parents[1]
DATA = ML_ROOT / "data"
RESULTS = ML_ROOT / "results"

# Every run uses this. Committed splits plus a fixed seed is what makes a number
# in the paper reproducible a month later.
SEED = 20260911

# Must match categories.slug in the seed migration exactly. These become database
# rows, so a typo here is a row that never joins.
CATEGORIES = [
    "road_infrastructure",
    "public_health_sanitation",
    "public_safety",
    "utilities",
    "social_welfare",
    "neighbor_dispute",
    "other",
]

URGENCIES = ["low", "medium", "high"]

HEADS = {"category": CATEGORIES, "urgency": URGENCIES}


@dataclass
class HeadScores:
    head: str
    n: int
    accuracy: float
    macro_f1: float
    weighted_f1: float
    per_class: dict
    confusion: list
    labels: list


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = {"text", "category", "urgency"} - set(df.columns)
    if missing:
        raise SystemExit(f"{path.name} is missing columns: {sorted(missing)}")

    if "source" not in df.columns:
        df["source"] = "synthetic"

    df["text"] = df["text"].astype(str).str.strip()
    blanks = int((df["text"] == "").sum())
    if blanks:
        print(f"{path.name}: dropped {blanks} blank rows")
    df = df[df["text"] != ""]

    # Exact duplicates only. Hand-authored rows reuse phrasings, and the same
    # text either side of the train/test line inflates every number downstream.
    duplicates = int(df["text"].duplicated().sum())
    if duplicates:
        print(f"{path.name}: {duplicates} duplicate texts")

    for head, allowed in HEADS.items():
        bad = sorted(set(df[head]) - set(allowed))
        if bad:
            raise SystemExit(f"unknown {head} values in {path.name}: {bad}")

    return df.reset_index(drop=True)


def score(head: str, y_true, y_pred) -> HeadScores:
    labels = HEADS[head]
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    per_class = {
        label: {
            "precision": round(float(precision[i]), 4),
            "recall": round(float(recall[i]), 4),
            "f1": round(float(f1[i]), 4),
            "support": int(support[i]),
        }
        for i, label in enumerate(labels)
    }
    return HeadScores(
        head=head,
        n=len(y_true),
        accuracy=round(float(accuracy_score(y_true, y_pred)), 4),
        # Macro, not weighted. Weighted hides a category the model never gets
        # right if that category is small, which is the failure worth seeing.
        macro_f1=round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4),
        weighted_f1=round(
            float(f1_score(y_true, y_pred, average="weighted", zero_division=0)), 4
        ),
        per_class=per_class,
        confusion=confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        labels=labels,
    )


def print_scores(title: str, scores: HeadScores, y_true=None, y_pred=None) -> None:
    print(f"\n{title} [{scores.head}]  n={scores.n}")
    print(f"  accuracy  {scores.accuracy:.4f}")
    print(f"  macro F1  {scores.macro_f1:.4f}")
    if y_true is not None and y_pred is not None:
        print(
            classification_report(
                y_true, y_pred, labels=scores.labels, zero_division=0, digits=3
            )
        )


def write_results(name: str, payload: dict) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ML_ROOT)}")
    return path


def scores_to_dict(scores: HeadScores) -> dict:
    return asdict(scores)
