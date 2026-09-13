"""Fine-tune a pretrained transformer on the labelled requests.

    python scripts/finetune.py --head category
    python scripts/finetune.py --head urgency

One model per head. Two separate fine-tunes rather than one shared encoder with
two heads: it is less code, each run is independently reproducible, and a bad
urgency model can be retrained without touching the category one. The cost is
memory at inference, two models loaded per worker, which is why the export step
quantizes and why the README caps workers at two.

Trains from a pretrained checkpoint. That is fine-tuning, not training from
scratch, which is the distinction the panel asked for. The TF-IDF + SVM baseline
in `baseline.py` is the one that genuinely trains from scratch.

Early stopping watches macro F1 on the validation split, never on test.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sklearn.metrics import f1_score
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)

from common import DATA, HEADS, ML_ROOT, RESULTS, SEED, load_csv, print_scores, score, scores_to_dict

# Gate 3 is open, so this is a default to override with --model, not a decision.
# It is mBERT rather than XLM-R because while the gate is open the default has to
# be the option that fails safest: XLM-R carries a 250k vocabulary, which is 69%
# of its weights and roughly 280 MB at int8, so two heads would not fit the
# instance. mBERT's 119k vocabulary lands near half that, and it matches the
# word "multilingual" the paper already uses throughout.
DEFAULT_MODEL = "bert-base-multilingual-cased"

MODELS_DIR = ML_ROOT / "models"


class Rows:
    """Minimal dataset. `datasets` is installed but this is clearer here and
    avoids an Arrow round trip for a few hundred rows."""

    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, i):
        item = {k: v[i] for k, v in self.encodings.items()}
        item["labels"] = self.labels[i]
        return item


def compute_macro_f1(eval_prediction):
    predictions = eval_prediction.predictions.argmax(axis=1)
    return {
        "macro_f1": f1_score(
            eval_prediction.label_ids, predictions, average="macro", zero_division=0
        )
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--head", choices=list(HEADS), required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--epochs", type=float, default=5)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--batch", type=int, default=16)
    # Barangay requests are short. 128 covers them with room to spare and keeps
    # CPU inference inside the paper's two second promise.
    parser.add_argument("--max-length", type=int, default=128)
    args = parser.parse_args()

    labels = HEADS[args.head]
    label_to_id = {label: i for i, label in enumerate(labels)}

    train = load_csv(args.data / "train.csv")
    val = load_csv(args.data / "val.csv")
    test = load_csv(args.data / "test.csv")
    print(f"model: {args.model}")
    print(f"{args.head}: train {len(train)}  val {len(val)}  test {len(test)}")

    tokenizer = AutoTokenizer.from_pretrained(args.model)

    def encode(frame):
        encodings = tokenizer(
            frame["text"].tolist(),
            truncation=True,
            max_length=args.max_length,
        )
        return Rows(encodings, [label_to_id[v] for v in frame[args.head]])

    model = AutoModelForSequenceClassification.from_pretrained(
        args.model,
        num_labels=len(labels),
        id2label={i: label for label, i in label_to_id.items()},
        label2id=label_to_id,
    )

    out_dir = MODELS_DIR / f"{args.head}"
    training_args = TrainingArguments(
        output_dir=str(out_dir / "checkpoints"),
        seed=SEED,
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=args.batch,
        num_train_epochs=args.epochs,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        save_total_limit=1,
        logging_steps=10,
        report_to=[],
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=encode(train),
        eval_dataset=encode(val),
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=compute_macro_f1,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )
    trainer.train()

    out_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    print(f"saved to {out_dir.relative_to(ML_ROOT)}")

    # Test is touched once, here, after training and model selection are done.
    predicted_ids = trainer.predict(encode(test)).predictions.argmax(axis=1)
    predicted = [labels[i] for i in predicted_ids]
    scores = score(args.head, test[args.head], predicted)
    print_scores(f"fine-tuned {args.model}", scores, test[args.head], predicted)

    RESULTS.mkdir(parents=True, exist_ok=True)
    run = {
        "model": args.model,
        "head": args.head,
        "seed": SEED,
        "epochs": args.epochs,
        "learning_rate": args.lr,
        "batch_size": args.batch,
        "max_length": args.max_length,
        "n_train": len(train),
        "n_test": len(test),
        "scores": scores_to_dict(scores),
    }
    path = RESULTS / f"finetune_{args.head}.json"
    path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ML_ROOT)}")
    print("\nEvery setting above is in that file. Chapter 4 wants the table and")
    print("reconstructing it from memory in week 9 is miserable.")


if __name__ == "__main__":
    main()
