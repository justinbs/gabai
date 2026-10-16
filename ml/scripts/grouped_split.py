"""Random versus grouped split, baseline only, 10 seeds each.

    python scripts/grouped_split.py

A random split can put two near-identical entries (one sentence pattern with a
street name changed) on both sides of the split. Here every pair of entries with
a word overlap (Jaccard) of at least 0.60 is linked, linked entries form one
group, and a grouped split keeps each group whole. Both splits are drawn with
10 seeds, about 70/15/15, and the TF-IDF baseline is trained on train and scored
on test. The transformer is not retrained. Writes results/grouped_split.json.
"""

from __future__ import annotations

import statistics

from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedGroupKFold, train_test_split

from baseline import build_pipeline
from common import DATA, HEADS, SEED, load_csv, write_results
from evaluate_deployed import NEAR_DUPLICATE, words

SEEDS = [SEED + i for i in range(10)]


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def near_duplicate_groups(texts: list[str]) -> list[int]:
    """Group id per entry; entries linked by J >= 0.60 share a group."""
    sets = [words(t) for t in texts]
    parent = list(range(len(sets)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            if jaccard(sets[i], sets[j]) >= NEAR_DUPLICATE:
                parent[find(i)] = find(j)
    return [find(i) for i in range(len(sets))]


def close_matches(test_texts, train_texts) -> int:
    pool = [words(t) for t in train_texts]
    return sum(any(jaccard(words(t), p) >= NEAR_DUPLICATE for p in pool) for t in test_texts)


def random_split(df, seed):
    key = df["category"] + "|" + df["urgency"]
    train, rest = train_test_split(df, test_size=0.30, random_state=seed, stratify=key)
    rest_key = rest["category"] + "|" + rest["urgency"]
    _, test = train_test_split(rest, test_size=0.50, random_state=seed, stratify=rest_key)
    return train, test


def grouped_split(df, groups, seed):
    # 20 folds of about 5% each: 3 for test, 3 left for validation (unused here), 14 for train.
    key = df["category"] + "|" + df["urgency"]
    folds = list(StratifiedGroupKFold(n_splits=20, shuffle=True, random_state=seed).split(df, key, groups))
    test_idx = [i for _, f in folds[:3] for i in f]
    train_idx = [i for _, f in folds[6:] for i in f]
    return df.iloc[train_idx], df.iloc[test_idx]


def run(train, test) -> dict:
    out = {"n_train": len(train), "n_test": len(test),
           "close_matches": close_matches(list(test["text"]), list(train["text"]))}
    for head in HEADS:
        model = build_pipeline()
        model.fit(train["text"], train[head])
        pred = model.predict(test["text"])
        out[head] = {"accuracy": round(accuracy_score(test[head], pred), 4),
                     "macro_f1": round(f1_score(test[head], pred, average="macro"), 4)}
    return out


def summary(runs: list[dict]) -> dict:
    s = {"close_matches_mean": round(statistics.mean(r["close_matches"] for r in runs), 1),
         "n_test_mean": round(statistics.mean(r["n_test"] for r in runs), 1)}
    for head in HEADS:
        for m in ("accuracy", "macro_f1"):
            vals = [r[head][m] for r in runs]
            s[f"{head}_{m}_mean"] = round(statistics.mean(vals), 4)
            s[f"{head}_{m}_sd"] = round(statistics.stdev(vals), 4)
    return s


def main() -> None:
    df = load_csv(DATA / "requests.csv").drop_duplicates(subset="text").reset_index(drop=True)
    groups = near_duplicate_groups(list(df["text"]))
    sizes = {}
    for g in groups:
        sizes[g] = sizes.get(g, 0) + 1
    grouped_entries = sum(n for n in sizes.values() if n > 1)
    multi = [n for n in sizes.values() if n > 1]
    print(f"{len(df)} entries; {grouped_entries} in {len(multi)} groups of {min(multi)} to {max(multi)}")

    random_runs, grouped_runs = [], []
    for seed in SEEDS:
        random_runs.append({"seed": seed, **run(*random_split(df, seed))})
        grouped_runs.append({"seed": seed, **run(*grouped_split(df, groups, seed))})
        print(seed, "random", random_runs[-1]["category"], random_runs[-1]["urgency"],
              "| grouped", grouped_runs[-1]["category"], grouped_runs[-1]["urgency"])

    payload = {
        "model": "tfidf+linearsvc", "threshold_jaccard": NEAR_DUPLICATE, "seeds": SEEDS,
        "entries": len(df), "grouped_entries": grouped_entries, "groups": len(multi),
        "group_size_min": min(multi), "group_size_max": max(multi),
        "random": {"summary": summary(random_runs), "runs": random_runs},
        "grouped": {"summary": summary(grouped_runs), "runs": grouped_runs},
    }
    print("random ", payload["random"]["summary"])
    print("grouped", payload["grouped"]["summary"])
    write_results("grouped_split", payload)


if __name__ == "__main__":
    main()
