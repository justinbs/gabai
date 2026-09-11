"""Pick the confidence threshold from data instead of picking it by feel.

    python scripts/threshold_sweep.py

For each candidate threshold, reports how much goes to a human and how accurate
the rest is. The routing rule under test is the one the backend implements:

    min(category_confidence, urgency_confidence) >= threshold  ->  auto-route

Lower of the two, because being sure of the category but not the urgency is
still not safe to route unattended.

Sweeps on the VALIDATION split, never on test. The threshold is a hyperparameter,
so choosing it on the split the final numbers come from would bias every figure
in Chapter 4 and invites one fatal question: "had you looked at the test set when
you picked it?" This is what `val.csv` is for.

The 0.70 currently in `.env.example` and `backend/app/core/config.py` is a
placeholder. This is what replaces it, and the table it prints is the answer to
"why 0.7 and not 0.8" at the defense.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from baseline import build_pipeline
from common import DATA, HEADS, SEED, load_csv, write_results

THRESHOLDS = [round(t, 2) for t in np.arange(0.50, 0.96, 0.05)]


def _confidences(train, test, head):
    pipeline = build_pipeline()
    pipeline.fit(train["text"], train[head])
    probabilities = pipeline.predict_proba(test["text"])
    classes = pipeline.named_steps["clf"].classes_
    best = probabilities.argmax(axis=1)
    return classes[best], probabilities.max(axis=1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--split", default="val", choices=["val", "test"])
    args = parser.parse_args()

    train = load_csv(args.data / "train.csv")
    # Validation, not test. See the module docstring.
    evaluation = load_csv(args.data / f"{args.split}.csv")

    predicted, confidence, correct = {}, {}, {}
    for head in HEADS:
        predicted[head], confidence[head] = _confidences(train, evaluation, head)
        correct[head] = predicted[head] == evaluation[head].to_numpy()

    joint_confidence = np.minimum(confidence["category"], confidence["urgency"])
    both_correct = correct["category"] & correct["urgency"]
    total = len(evaluation)

    rows = []
    print(f"\n {args.split} split, n={total}   rule: min(category, urgency) >= threshold\n")
    print(f"{'thresh':>7}  {'auto %':>7}  {'review %':>9}  {'cat acc':>8}  {'both acc':>9}")
    for threshold in THRESHOLDS:
        auto = joint_confidence >= threshold
        n_auto = int(auto.sum())
        row = {
            "threshold": threshold,
            "auto_routed": n_auto,
            "auto_routed_pct": round(100 * n_auto / total, 1),
            "manual_review_pct": round(100 * (total - n_auto) / total, 1),
            # Accuracy of what got routed without a human. Undefined when nothing
            # clears the bar, which is itself the finding at high thresholds.
            "auto_category_accuracy": (
                round(float(correct["category"][auto].mean()), 4) if n_auto else None
            ),
            "auto_both_accuracy": (
                round(float(both_correct[auto].mean()), 4) if n_auto else None
            ),
        }
        rows.append(row)
        cat = f"{row['auto_category_accuracy']:.4f}" if n_auto else "n/a"
        both = f"{row['auto_both_accuracy']:.4f}" if n_auto else "n/a"
        print(
            f"{threshold:>7.2f}  {row['auto_routed_pct']:>6.1f}%  "
            f"{row['manual_review_pct']:>8.1f}%  {cat:>8}  {both:>9}"
        )

    write_results(
        "threshold_sweep",
        {
            "model": "tfidf+linearsvc",
            "seed": SEED,
            "split": args.split,
            "n": total,
            "rule": "min(category_confidence, urgency_confidence) >= threshold",
            "rows": rows,
        },
    )
    print(
        f"\nPick the threshold on {args.split} where auto-routed accuracy is "
        "acceptable and the review load is bearable. Put that number in .env, "
        "not 0.70, then report it once on test."
    )


if __name__ == "__main__":
    main()
