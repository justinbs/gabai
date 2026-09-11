"""Classify without training anything, to find out whether fine-tuning is needed.

    python scripts/zero_shot.py --method embed
    python scripts/zero_shot.py --method nli

Scored with the same `score()` the baseline and any fine-tuned run use, on the
same held-out split, so the three are comparable.

Two methods, because neither is a safe bet on Tagalog and the point is to measure
rather than assume:

`embed`   Encode each request and each category description with a multilingual
          sentence encoder, then take the nearest description by cosine
          similarity. Nothing is trained. Smaller model, and mean pooling over
          `AutoModel` avoids adding a dependency.

`nli`     Ask a model already trained on natural language inference whether
          "this request is about X" follows from the text. Larger, and Tagalog is
          not among the languages it was trained on, so treat any result as a
          test of cross-lingual transfer rather than a like-for-like number.

A note for the write-up: this does NOT evaluate `roberta-tagalog-base` without
fine-tuning. That model is a base masked-language model with no classification
head, so using it would need either fine-tuning or a masked-token prompting
scheme we did not pursue. Whatever runs here is a different model, and calling it
"the same model untuned" would not survive a follow-up.

`nli` runs roughly seven forward passes per row against a 0.3B model. On CPU that
is slow, not hung.

Written before the first run, so that a result confirming it means something:

- **Urgency will score worse than category.** A sentence encoder matches topics,
  and urgency is not a topic. It is a judgement about what happens if nobody
  acts, which two requests about the same subject can differ on. If urgency comes
  out near chance while category does not, that is the method's limit showing,
  not the model's.
- **Neither method reaches the trained baseline on category.** Zero-shot has
  never seen a barangay request.
- If either of those turns out wrong, the surprise is the finding and it gets
  written up as one.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer, pipeline

from common import CATEGORIES, DATA, URGENCIES, load_csv, print_scores, score, scores_to_dict, write_results

# Sharpens cosine similarities into something the threshold sweep can read. It
# changes the confidence spread only, never the prediction, because argmax of a
# row-wise softmax is argmax of the similarities. So it cannot move accuracy or
# macro F1. It CAN move the manual-review rate, which is why a zero-shot sweep
# must not put a number in .env: these are not calibrated probabilities.
TEMPERATURE = 0.05

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
NLI_MODEL = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"

# What each label means, in words, since the model has only these to go on. The
# slug itself carries almost no meaning to an encoder.
CATEGORY_TEXT = {
    "road_infrastructure": "sirang kalsada, butas sa daan, tulay, poste, streetlight, kanal. Damaged road, pothole, bridge, street light, drainage structure.",
    "public_health_sanitation": "basura, kalinisan, lamok, baradong tubig, health center. Garbage collection, sanitation, pests, stagnant water, health centre.",
    "public_safety": "peace and order, tambay, away, nakaw, ligtas, aso sa kalye, sunog. Public safety, disturbance, crime, fire, stray animals.",
    "utilities": "walang tubig, brownout, kuryente, baha. No water supply, power interruption, electricity, flooding.",
    "social_welfare": "ayuda, tulong, senior citizen, PWD, indigency, scholarship. Financial assistance, welfare, aid for seniors and persons with disability.",
    "neighbor_dispute": "kapitbahay, away sa kapitbahay, ingay, hangganan ng lote, umuupa. Dispute with a neighbour, noise complaint, boundary or tenancy conflict.",
    "other": "tanong, katanungan, clearance, dokumento, iba pa. General inquiry, requesting a document or certificate, anything else.",
}

URGENCY_TEXT = {
    "high": "delikado, emergency, may nasaktan, kailangan ngayon din. Dangerous, someone may be hurt, needs action today.",
    "medium": "kailangan ayusin pero hindi emergency. A real problem that should be handled soon but is not an emergency.",
    "low": "tanong lang, hindi urgent, pwedeng maghintay. Just a question, not urgent, can wait.",
}

# NLI degrades on long hypotheses, so it gets short phrases while the encoder
# gets the rich text above. Sharing one set would compare prompt formats rather
# than models.
NLI_CATEGORY_TEXT = {
    "road_infrastructure": "sirang kalsada o imprastraktura",
    "public_health_sanitation": "basura at kalinisan",
    "public_safety": "kaligtasan at kapayapaan",
    "utilities": "tubig, kuryente, o baha",
    "social_welfare": "ayuda at tulong panlipunan",
    "neighbor_dispute": "away sa kapitbahay",
    "other": "ibang katanungan",
}

NLI_URGENCY_TEXT = {
    "high": "kailangan ng agarang aksyon",
    "medium": "kailangan ayusin pero hindi agaran",
    "low": "hindi urgent, tanong lang",
}

LABEL_TEXT = {"category": CATEGORY_TEXT, "urgency": URGENCY_TEXT}
NLI_LABEL_TEXT = {"category": NLI_CATEGORY_TEXT, "urgency": NLI_URGENCY_TEXT}
LABELS = {"category": CATEGORIES, "urgency": URGENCIES}


def _mean_pool(output, mask):
    hidden = output.last_hidden_state
    expanded = mask.unsqueeze(-1).expand(hidden.size()).float()
    return (hidden * expanded).sum(1) / expanded.sum(1).clamp(min=1e-9)


def _encode(texts: list[str], tokenizer, model) -> np.ndarray:
    vectors = []
    for start in range(0, len(texts), 32):
        batch = tokenizer(
            texts[start : start + 32],
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt",
        )
        with torch.no_grad():
            out = model(**batch)
        pooled = _mean_pool(out, batch["attention_mask"])
        vectors.append(torch.nn.functional.normalize(pooled, dim=1).numpy())
    return np.vstack(vectors)


def run_embed(texts: list[str]) -> dict:
    tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL)
    model = AutoModel.from_pretrained(EMBED_MODEL).eval()
    request_vectors = _encode(texts, tokenizer, model)

    predictions = {}
    for head, labels in LABELS.items():
        label_vectors = _encode([LABEL_TEXT[head][label] for label in labels], tokenizer, model)
        similarity = request_vectors @ label_vectors.T
        predictions[head] = [labels[i] for i in similarity.argmax(axis=1)]
        predictions[f"{head}_confidence"] = _softmax_rows(similarity).max(axis=1).tolist()
    return predictions


def _softmax_rows(matrix: np.ndarray) -> np.ndarray:
    shifted = matrix - matrix.max(axis=1, keepdims=True)
    exponentiated = np.exp(shifted / TEMPERATURE)
    return exponentiated / exponentiated.sum(axis=1, keepdims=True)


def run_nli(texts: list[str], template: str) -> dict:
    tokenizer = AutoTokenizer.from_pretrained(NLI_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(NLI_MODEL)
    classifier = pipeline("zero-shot-classification", model=model, tokenizer=tokenizer)

    predictions = {}
    for head, labels in LABELS.items():
        descriptions = [NLI_LABEL_TEXT[head][label] for label in labels]
        by_description = {d: labels[i] for i, d in enumerate(descriptions)}
        results = classifier(texts, descriptions, hypothesis_template=template)
        results = results if isinstance(results, list) else [results]
        predictions[head] = [by_description[r["labels"][0]] for r in results]
        predictions[f"{head}_confidence"] = [r["scores"][0] for r in results]
    return predictions


def report_tokenizer_fertility(model_name: str) -> None:
    """Tokens per word on Tagalog. High means the model barely saw the language,
    which separates "the method failed" from "this model never learned Tagalog"."""
    samples = [
        "may malaking butas sa kalsada malapit sa barangay hall",
        "wala kaming tubig tatlong araw na po",
        "sobrang ingay ng kapitbahay namin tuwing gabi",
    ]
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    total_tokens = sum(len(tokenizer.tokenize(s)) for s in samples)
    total_words = sum(len(s.split()) for s in samples)
    print(f"  tokenizer fertility on Tagalog: {total_tokens / total_words:.2f} tokens/word")
    print("  under about 1.5 is healthy, over 2.5 means the language is barely covered")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=["embed", "nli"], default="embed")
    parser.add_argument("--data", type=Path, default=DATA)
    # val by default. The label descriptions below are effectively a prompt, so
    # iterating them while watching test accuracy would fit the held-out split.
    parser.add_argument("--split", default="val", choices=["val", "test"])
    # The NLI model was not trained on Tagalog, so an English template may
    # transfer better than a Tagalog one. Cheap to test, not worth guessing.
    parser.add_argument(
        "--template",
        default="Ang mensaheng ito ay tungkol sa {}.",
        help="NLI hypothesis template, must contain {}",
    )
    args = parser.parse_args()

    evaluation = load_csv(args.data / f"{args.split}.csv")
    texts = evaluation["text"].tolist()
    print(f"{args.method} over {len(texts)} rows from {args.split}.csv")

    model_name = EMBED_MODEL if args.method == "embed" else NLI_MODEL
    report_tokenizer_fertility(model_name)

    predictions = (
        run_embed(texts) if args.method == "embed" else run_nli(texts, args.template)
    )
    payload = {
        "model": model_name,
        "method": args.method,
        "trained": False,
        "split": args.split,
        "template": args.template if args.method == "nli" else None,
        "heads": {},
    }

    for head in LABELS:
        scores = score(head, evaluation[head], predictions[head])
        print_scores(f"zero-shot {args.method}", scores, evaluation[head], predictions[head])
        payload["heads"][head] = scores_to_dict(scores)

    write_results(f"zero_shot_{args.method}", payload)
    print("\nCompare against results/baseline.json. If this is close to or better")
    print("than the trained baseline, fine-tuning may not be needed. If it is far")
    print("below, that is the evidence for fine-tuning.")


if __name__ == "__main__":
    main()
