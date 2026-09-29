"""Evaluate the classifier that is actually deployed, for Chapter 4.

    python scripts/evaluate_deployed.py

Loads the int8 ONNX heads from backend/models, the same files the live system
serves, and scores them with the same tokenizer and softmax the backend uses.
Then, on the same splits:

1. Reproduces the test scores reported in finetune_*.json and baseline.json, so
   there is proof these are the same models.
2. McNemar's exact test, transformer against baseline, per head. The category
   gap is a handful of test rows, and a difference that size can be chance.
3. The confidence threshold sweep, on the validation split, for the transformer.
   The earlier threshold_sweep.json swept the baseline by mistake; this one
   sweeps the model whose confidence the live routing rule reads.
4. Scores per writer, since the rows came from three people with different
   styles. A model that only works on one person's phrasing would show here.
5. Near-duplicates across the split. merge_rows.py removes exact repeats only,
   so a sentence that differs by a street name can sit in both train and test.
   Every test row gets its closest training row by word overlap (Jaccard), and
   the results are reported again on the rows with no close match, which is the
   honest estimate for wording the model has not seen.

Test is only read for reporting. The threshold is chosen on val.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
from onnxruntime import InferenceSession
from tokenizers import Tokenizer

from baseline import build_pipeline
from common import DATA, HEADS, ML_ROOT, RESULTS, SEED, load_csv, score, scores_to_dict

MODELS = ML_ROOT.parent / "backend" / "models"
THRESHOLDS = [round(0.30 + 0.05 * i, 2) for i in range(14)]  # 0.30 to 0.95
DEPLOYED_THRESHOLD = 0.70
# Word-overlap level treated as "the same sentence with a detail swapped".
NEAR_DUPLICATE = 0.6


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def closest_overlap(text: str, pool: list[set[str]]) -> float:
    mine = words(text)
    best = 0.0
    for other in pool:
        union = mine | other
        if union:
            best = max(best, len(mine & other) / len(union))
    return best


class DeployedHead:
    """Mirrors backend/app/inference/classifier.py _Head.predict exactly."""

    def __init__(self, directory: Path):
        config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
        self.labels = [config["id2label"][str(i)] for i in range(len(config["id2label"]))]
        self.session = InferenceSession(
            str(directory / "model_quantized.onnx"), providers=["CPUExecutionProvider"]
        )
        self.inputs = {i.name for i in self.session.get_inputs()}
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=128)
        self.version = (directory / "VERSION").read_text(encoding="utf-8").strip()

    def predict(self, text: str) -> tuple[str, float]:
        encoded = self.tokenizer.encode(text)
        feed = {
            "input_ids": np.array([encoded.ids], dtype=np.int64),
            "attention_mask": np.array([encoded.attention_mask], dtype=np.int64),
        }
        if "token_type_ids" in self.inputs:
            feed["token_type_ids"] = np.array([encoded.type_ids], dtype=np.int64)
        logits = self.session.run(None, {k: v for k, v in feed.items() if k in self.inputs})[0][0]
        shifted = logits - logits.max()
        probabilities = np.exp(shifted) / np.exp(shifted).sum()
        best = int(probabilities.argmax())
        return self.labels[best], float(probabilities[best])


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value. b, c are the discordant pair counts."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)


def main() -> None:
    train = load_csv(DATA / "train.csv")
    val = load_csv(DATA / "val.csv")
    test = load_csv(DATA / "test.csv")
    heads = {h: DeployedHead(MODELS / f"{h}-onnx") for h in HEADS}
    print("deployed versions:", {h: x.version for h, x in heads.items()})

    def run(frame):
        out = {}
        for h, head in heads.items():
            pairs = [head.predict(t) for t in frame["text"]]
            out[h] = ([p for p, _ in pairs], np.array([c for _, c in pairs]))
        return out

    xval, xtest = run(val), run(test)

    payload: dict = {
        "models": {h: x.version for h, x in heads.items()},
        "precision": "onnx int8, as deployed",
        "seed": SEED,
        "n": {"train": len(train), "val": len(val), "test": len(test)},
        "heads": {},
    }

    # 1 and 2: reproduce, then compare against the baseline on the same rows
    for h in HEADS:
        truth = test[h].tolist()
        pipeline = build_pipeline()
        pipeline.fit(train["text"], train[h])
        base_pred = pipeline.predict(test["text"]).tolist()
        xlmr_pred = xtest[h][0]

        base_right = [p == t for p, t in zip(base_pred, truth)]
        xlmr_right = [p == t for p, t in zip(xlmr_pred, truth)]
        only_base = sum(1 for b, x in zip(base_right, xlmr_right) if b and not x)
        only_xlmr = sum(1 for b, x in zip(base_right, xlmr_right) if x and not b)

        xs, bs = score(h, truth, xlmr_pred), score(h, truth, base_pred)
        payload["heads"][h] = {
            "transformer": scores_to_dict(xs),
            "baseline": scores_to_dict(bs),
            "mcnemar": {
                "only_baseline_right": only_base,
                "only_transformer_right": only_xlmr,
                "both_right": sum(1 for b, x in zip(base_right, xlmr_right) if b and x),
                "both_wrong": sum(1 for b, x in zip(base_right, xlmr_right) if not b and not x),
                "p_value": round(mcnemar_exact(only_base, only_xlmr), 4),
            },
        }
        print(f"\n[{h}] transformer acc {xs.accuracy:.4f} macroF1 {xs.macro_f1:.4f} | "
              f"baseline acc {bs.accuracy:.4f} macroF1 {bs.macro_f1:.4f}")
        print(f"  McNemar: only baseline right {only_base}, only transformer right {only_xlmr}, "
              f"p = {payload['heads'][h]['mcnemar']['p_value']}")

    # 3: threshold sweep on val, the live rule min(category, urgency) >= threshold
    def sweep(frame, preds):
        conf = np.minimum(preds["category"][1], preds["urgency"][1])
        cat_ok = np.array([p == t for p, t in zip(preds["category"][0], frame["category"])])
        urg_ok = np.array([p == t for p, t in zip(preds["urgency"][0], frame["urgency"])])
        rows = []
        for t in THRESHOLDS:
            auto = conf >= t
            n_auto = int(auto.sum())
            rows.append({
                "threshold": t,
                "auto_routed": n_auto,
                "auto_pct": round(100 * n_auto / len(frame), 1),
                "review_pct": round(100 * (len(frame) - n_auto) / len(frame), 1),
                "category_acc_on_auto": round(float(cat_ok[auto].mean()), 4) if n_auto else None,
                "both_acc_on_auto": round(float((cat_ok & urg_ok)[auto].mean()), 4) if n_auto else None,
                "wrong_category_auto_routed": int((~cat_ok & auto).sum()),
            })
        return rows

    payload["threshold_sweep_val"] = sweep(val, xval)
    payload["deployed_threshold_on_test"] = next(
        r for r in sweep(test, xtest) if r["threshold"] == DEPLOYED_THRESHOLD
    )
    print("\nthreshold sweep on val (transformer, live rule):")
    print(" thresh  auto%  review%  cat acc on auto  both acc on auto  wrong-category auto-routed")
    for r in payload["threshold_sweep_val"]:
        print(f"  {r['threshold']:.2f}  {r['auto_pct']:5.1f}  {r['review_pct']:6.1f}  "
              f"{r['category_acc_on_auto']!s:>15}  {r['both_acc_on_auto']!s:>16}  {r['wrong_category_auto_routed']:>6}")
    d = payload["deployed_threshold_on_test"]
    print(f"\nat the deployed {DEPLOYED_THRESHOLD} on TEST: {d['auto_pct']}% auto-routed, "
          f"category acc on those {d['category_acc_on_auto']}, {d['wrong_category_auto_routed']} wrong-category auto-routed")

    # 4: per writer, on test
    per_writer: dict = defaultdict(dict)
    for h in HEADS:
        pipeline = build_pipeline()
        pipeline.fit(train["text"], train[h])
        base_all = pipeline.predict(test["text"]).tolist()
        for writer in sorted(test["author"].unique()):
            idx = [i for i, a in enumerate(test["author"]) if a == writer]
            truth = [test[h].iloc[i] for i in idx]
            pred = [xtest[h][0][i] for i in idx]
            base = [base_all[i] for i in idx]
            s = score(h, truth, pred)
            only_b = sum(1 for b, x, t in zip(base, pred, truth) if b == t and x != t)
            only_x = sum(1 for b, x, t in zip(base, pred, truth) if x == t and b != t)
            per_writer[writer][h] = {
                "n": len(idx),
                "accuracy": s.accuracy,
                "macro_f1": s.macro_f1,
                "baseline_accuracy": round(sum(b == t for b, t in zip(base, truth)) / len(idx), 4),
                "mcnemar_p": round(mcnemar_exact(only_b, only_x), 4),
                "only_baseline_right": only_b,
                "only_transformer_right": only_x,
            }
    payload["per_writer_test"] = per_writer
    print("\nper writer on test (transformer):")
    for writer, d in per_writer.items():
        print(f"  {writer}: n={d['category']['n']}  category acc {d['category']['accuracy']:.4f}  "
              f"urgency acc {d['urgency']['accuracy']:.4f}")

    # 5: near-duplicates across the train/test line
    pool = [words(t) for t in train["text"]]
    overlap = [closest_overlap(t, pool) for t in test["text"]]
    unseen = [i for i, o in enumerate(overlap) if o < NEAR_DUPLICATE]
    leak = {
        "threshold_jaccard": NEAR_DUPLICATE,
        "test_rows_with_close_train_match": len(test) - len(unseen),
        "by_writer": {
            w: {
                "close": sum(1 for i, a in enumerate(test["author"]) if a == w and overlap[i] >= NEAR_DUPLICATE),
                "total": int((test["author"] == w).sum()),
            }
            for w in sorted(test["author"].unique())
        },
        "no_close_match": {"n": len(unseen)},
    }
    for h in HEADS:
        truth = [test[h].iloc[i] for i in unseen]
        pipeline = build_pipeline()
        pipeline.fit(train["text"], train[h])
        base_all = pipeline.predict(test["text"]).tolist()
        base = [base_all[i] for i in unseen]
        xlmr = [xtest[h][0][i] for i in unseen]
        only_b = sum(1 for b, x, t in zip(base, xlmr, truth) if b == t and x != t)
        only_x = sum(1 for b, x, t in zip(base, xlmr, truth) if x == t and b != t)
        leak["no_close_match"][h] = {
            "transformer_accuracy": round(sum(x == t for x, t in zip(xlmr, truth)) / len(truth), 4),
            "baseline_accuracy": round(sum(b == t for b, t in zip(base, truth)) / len(truth), 4),
            "transformer_macro_f1": score(h, truth, xlmr).macro_f1,
            "baseline_macro_f1": score(h, truth, base).macro_f1,
            "only_baseline_right": only_b,
            "only_transformer_right": only_x,
            "mcnemar_p": round(mcnemar_exact(only_b, only_x), 4),
        }
    payload["near_duplicates"] = leak
    print(f"\nnear-duplicates: {leak['test_rows_with_close_train_match']} of {len(test)} test rows have a "
          f"training row with word overlap >= {NEAR_DUPLICATE}; by writer {leak['by_writer']}")
    for h in HEADS:
        r = leak["no_close_match"][h]
        print(f"  no close match (n={len(unseen)}) [{h}]: transformer {r['transformer_accuracy']:.4f} "
              f"baseline {r['baseline_accuracy']:.4f}  McNemar {r['only_baseline_right']}/{r['only_transformer_right']} p={r['mcnemar_p']}")

    # Every test prediction, for error analysis in the discussion. Kept in its own
    # file because it carries the request text, and the dataset isn't published.
    predictions = [
        {
            "text": test["text"].iloc[i],
            "author": test["author"].iloc[i],
            **{f"true_{h}": test[h].iloc[i] for h in HEADS},
            **{f"pred_{h}": xtest[h][0][i] for h in HEADS},
            **{f"conf_{h}": round(float(xtest[h][1][i]), 4) for h in HEADS},
            "closest_train_overlap": round(overlap[i], 3),
        }
        for i in range(len(test))
    ]

    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / "deployed_evaluation.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nwrote {path.relative_to(ML_ROOT)}")
    path = RESULTS / "deployed_test_predictions.json"
    path.write_text(json.dumps(predictions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ML_ROOT)}")


if __name__ == "__main__":
    main()
