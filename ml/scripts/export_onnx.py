"""Export a fine-tuned model to ONNX and quantize it to int8.

    python scripts/export_onnx.py --head category

Writes into `models/<head>-onnx/`, which is what the backend loads. The backend
never imports torch or transformers, only onnxruntime and a tokenizer, which is
most of why it fits a small instance.

Reports size, latency and accuracy before and after. "We quantized, here is the
citation, here is what it cost us in accuracy" answers the cost question with a
number instead of a claim, and the size delta is what makes a CPU-only box
defensible against the treasurer's objection.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

import numpy as np
from optimum.onnxruntime import ORTModelForSequenceClassification, ORTQuantizer
from optimum.onnxruntime.configuration import AutoQuantizationConfig
from transformers import AutoTokenizer

from common import DATA, HEADS, ML_ROOT, RESULTS, load_csv, score, scores_to_dict

MODELS_DIR = ML_ROOT / "models"


def file_size_mb(path: Path) -> float:
    # The model file alone, not the directory. After quantizing, the directory
    # holds both files, so measuring it would report the int8 model as larger
    # than the fp32 one. That size delta is the cost argument, so it has to be
    # the weights and nothing else.
    return path.stat().st_size / (1024 * 1024)


def predict(model, tokenizer, texts: list[str], labels: list[str]) -> tuple[list[str], float]:
    """Returns predictions and mean latency per request in milliseconds. One at a
    time on purpose: that is how the API serves them, so it is the number the
    paper's sub-two-second promise should be measured against."""
    out, elapsed = [], 0.0
    for text in texts:
        encoded = tokenizer(text, return_tensors="np", truncation=True, max_length=128)
        started = time.perf_counter()
        logits = model(**encoded).logits
        elapsed += time.perf_counter() - started
        out.append(labels[int(np.argmax(logits, axis=1)[0])])
    return out, 1000 * elapsed / max(len(texts), 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--head", choices=list(HEADS), required=True)
    parser.add_argument("--data", type=Path, default=DATA)
    args = parser.parse_args()

    labels = HEADS[args.head]
    source = MODELS_DIR / args.head
    if not source.exists():
        raise SystemExit(f"{source} does not exist. Run finetune.py --head {args.head} first.")

    target = MODELS_DIR / f"{args.head}-onnx"
    if target.exists():
        shutil.rmtree(target)

    tokenizer = AutoTokenizer.from_pretrained(source)
    test = load_csv(args.data / "test.csv")
    texts = test["text"].tolist()

    print("exporting to ONNX")
    model = ORTModelForSequenceClassification.from_pretrained(source, export=True)
    model.save_pretrained(target)
    tokenizer.save_pretrained(target)
    before_predictions, before_latency = predict(model, tokenizer, texts, labels)
    before_size = file_size_mb(target / "model.onnx")

    print("quantizing to int8")
    quantizer = ORTQuantizer.from_pretrained(target)
    # Dynamic quantization: weights only, no calibration set needed. AVX-512 VNNI
    # off, because the cheap instance this deploys to may not have it.
    quantizer.quantize(
        save_dir=target,
        quantization_config=AutoQuantizationConfig.avx2(is_static=False, per_channel=False),
    )

    quantized = ORTModelForSequenceClassification.from_pretrained(
        target, file_name="model_quantized.onnx"
    )
    after_predictions, after_latency = predict(quantized, tokenizer, texts, labels)
    after_size = file_size_mb(target / "model_quantized.onnx")

    before = score(args.head, test[args.head], before_predictions)
    after = score(args.head, test[args.head], after_predictions)

    print(f"\n{'':12} {'size MB':>9} {'ms/request':>11} {'accuracy':>9} {'macro F1':>9}")
    print(f"{'onnx fp32':12} {before_size:9.1f} {before_latency:11.1f} {before.accuracy:9.4f} {before.macro_f1:9.4f}")
    print(f"{'onnx int8':12} {after_size:9.1f} {after_latency:11.1f} {after.accuracy:9.4f} {after.macro_f1:9.4f}")
    print(f"\naccuracy cost of quantizing: {before.accuracy - after.accuracy:+.4f}")
    print(f"model directory: {target.relative_to(ML_ROOT)}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"quantization_{args.head}.json"
    path.write_text(
        json.dumps(
            {
                "head": args.head,
                "n_test": len(test),
                "fp32": {"size_mb": round(before_size, 1), "ms_per_request": round(before_latency, 1), **scores_to_dict(before)},
                "int8": {"size_mb": round(after_size, 1), "ms_per_request": round(after_latency, 1), **scores_to_dict(after)},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {path.relative_to(ML_ROOT)}")


if __name__ == "__main__":
    main()
