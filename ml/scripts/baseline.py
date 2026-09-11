"""TF-IDF + linear SVM. The number the transformer has to beat.

    python scripts/baseline.py

This one genuinely trains from scratch, which is why the paper calls it
"trained" and the transformer "fine-tuned". Word and character n-grams together,
because character n-grams hold up better on misspelt, code-switched text where
the same word appears three different ways.

On a few hundred rows this sometimes beats the transformer. That is a real
finding about data scarcity, not a failure, and it gets reported either way.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline, make_union
from sklearn.svm import LinearSVC

from common import DATA, HEADS, SEED, load_csv, print_scores, score, scores_to_dict, write_results


def build_pipeline() -> Pipeline:
    features = make_union(
        TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True, min_df=1),
        TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1),
    )
    # LinearSVC has no predict_proba, and the threshold sweep needs a confidence.
    # Calibration wraps it to give one without changing the decision rule.
    classifier = CalibratedClassifierCV(
        LinearSVC(class_weight="balanced", random_state=SEED), cv=3
    )
    return Pipeline([("features", features), ("clf", classifier)])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DATA)
    args = parser.parse_args()

    train = load_csv(args.data / "train.csv")
    test = load_csv(args.data / "test.csv")
    print(f"train {len(train)}  test {len(test)}")

    payload = {"model": "tfidf+linearsvc", "seed": SEED, "n_train": len(train), "heads": {}}

    for head in HEADS:
        pipeline = build_pipeline()
        pipeline.fit(train["text"], train[head])
        predictions = pipeline.predict(test["text"])

        scores = score(head, test[head], predictions)
        print_scores("baseline", scores, test[head], predictions)
        payload["heads"][head] = scores_to_dict(scores)

    write_results("baseline", payload)


if __name__ == "__main__":
    main()
