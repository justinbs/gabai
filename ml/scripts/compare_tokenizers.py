"""Check how well candidate models handle our actual text, before training any.

    python scripts/compare_tokenizers.py data/requests.csv

Reports, per model: tokens per word, how often a word gets split, and the share
of characters the tokenizer cannot represent at all.

Why this is worth running first. Barangay requests are code-switched Taglish, not
pure Tagalog and not pure English. A model whose tokenizer never saw that mix
shreds words into fragments, and a model learning from fragments needs far more
examples to reach the same accuracy. On a few hundred rows that difference
decides the result.

This costs a few seconds and no training. It does not tell you which model will
score best, only which ones can read the text at all, which is a different and
cheaper question.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from transformers import AutoTokenizer

from common import load_csv

CANDIDATES = [
    "bert-base-multilingual-cased",
    "distilbert-base-multilingual-cased",
    "jcblaise/roberta-tagalog-base",
    "xlm-roberta-base",
]


def measure(model_name: str, texts: list[str]) -> dict:
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    tokens = words = split_words = 0
    unknown = 0
    unk = tokenizer.unk_token

    for text in texts:
        for word in text.split():
            pieces = tokenizer.tokenize(word)
            if not pieces:
                continue
            words += 1
            tokens += len(pieces)
            if len(pieces) > 1:
                split_words += 1
            if unk and unk in pieces:
                unknown += 1

    return {
        "model": model_name,
        "vocab": tokenizer.vocab_size,
        "tokens_per_word": tokens / max(words, 1),
        "split_rate": split_words / max(words, 1),
        "unknown_rate": unknown / max(words, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--models", nargs="*", default=CANDIDATES)
    args = parser.parse_args()

    texts = load_csv(args.csv)["text"].tolist()
    print(f"{len(texts)} requests from {args.csv.name}\n")

    print(f"{'model':38} {'vocab':>7} {'tok/word':>9} {'split %':>8} {'unknown %':>10}")
    rows = []
    for name in args.models:
        try:
            row = measure(name, texts)
        except Exception as error:
            print(f"{name:38} could not load: {error}")
            continue
        rows.append(row)
        print(
            f"{row['model']:38} {row['vocab']:>7} {row['tokens_per_word']:>9.2f} "
            f"{100 * row['split_rate']:>7.1f}% {100 * row['unknown_rate']:>9.1f}%"
        )

    if rows:
        best = min(rows, key=lambda r: r["tokens_per_word"])
        print(f"\nfewest pieces per word: {best['model']} at {best['tokens_per_word']:.2f}")
        print("Lower is better. Near 1.0 means the tokenizer mostly knows these words.")
        print("Above about 2.0 means it is spelling them out, and the model will need")
        print("more examples to learn anything from them.")
        print("\nThis measures reading, not accuracy. Train the top two and compare.")


if __name__ == "__main__":
    main()
