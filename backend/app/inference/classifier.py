"""The classifier the API calls.

Loads the quantized ONNX models exported by `ml/scripts/export_onnx.py`. Nothing
here imports torch or transformers: onnxruntime plus a tokenizer is all inference
needs, and that is most of why this fits a small instance.

Two models, one per head, because they were fine-tuned separately. Both load once
per worker, which is why the README runs a single worker. onnxruntime releases the
GIL and inference already goes through a threadpool, so one worker still serves
concurrent requests, and a second one would double the model memory for very
little throughput.

**If no model directory is present, `classify` returns `UNCLASSIFIED` with zero
confidence.** Zero is below any threshold, so every request goes to the review
queue and a human labels it. That is the fallback the system is designed around,
not a placeholder, and it is also what happens if a model fails to load in
production.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.core.config import get_settings
from app.models.enums import Urgency

log = logging.getLogger(__name__)
settings = get_settings()

# Slug order must match the exported model's label order, which comes from
# ml/scripts/common.py. The model directory carries its own config.json with
# id2label, so that is what gets read rather than a copy kept here.
CATEGORY_HEAD = "category"
URGENCY_HEAD = "urgency"


@dataclass(frozen=True)
class Prediction:
    category_slug: str | None
    category_confidence: float
    urgency: Urgency | None
    urgency_confidence: float
    model_version: str | None


UNCLASSIFIED = Prediction(
    category_slug=None,
    category_confidence=0.0,
    urgency=None,
    urgency_confidence=0.0,
    model_version=None,
)


class _Head:
    """One ONNX model plus its tokenizer and label list."""

    def __init__(self, directory: Path):
        from onnxruntime import InferenceSession
        from tokenizers import Tokenizer

        config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
        self.labels = [config["id2label"][str(i)] for i in range(len(config["id2label"]))]

        quantized = directory / "model_quantized.onnx"
        model_file = quantized if quantized.exists() else directory / "model.onnx"
        self.session = InferenceSession(str(model_file), providers=["CPUExecutionProvider"])
        self.inputs = {i.name for i in self.session.get_inputs()}

        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=128)

        # Per head, not shared. The two models are fine-tuned separately and can
        # be retrained separately, so one string for both would claim a single
        # vintage for two artifacts of different ages. Delta c exists so Chapter
        # 4 can compare across versions, and a blurred version defeats it.
        version_file = directory / "VERSION"
        self.version = (
            version_file.read_text(encoding="utf-8").strip()
            if version_file.exists()
            else "unversioned"
        )

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


_heads: dict[str, _Head] = {}
_model_version: str | None = None


def load() -> None:
    """Called once at startup from the lifespan handler, never per request.

    A missing or broken model is not fatal. The API still accepts requests and
    routes them to a human, which is worse than classifying but much better than
    refusing to start.
    """
    global _model_version
    _heads.clear()
    _model_version = None

    root = Path(settings.model_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root

    for head in (CATEGORY_HEAD, URGENCY_HEAD):
        directory = root / f"{head}-onnx"
        if not directory.exists():
            log.warning("no %s model at %s, requests will go to manual review", head, directory)
            _heads.clear()
            return
        try:
            _heads[head] = _Head(directory)
        except Exception:
            log.exception("could not load the %s model, requests will go to manual review", head)
            _heads.clear()
            return

    _model_version = ", ".join(
        f"{head}={_heads[head].version}" for head in (CATEGORY_HEAD, URGENCY_HEAD)
    )
    log.info("classifier ready, %s", _model_version)


def is_loaded() -> bool:
    return len(_heads) == 2


def classify(text: str) -> Prediction:
    """Plain `def`, not `async def`. Inference is CPU work and would block the
    event loop for every other request. Callers hand this to a threadpool."""
    if not is_loaded():
        return UNCLASSIFIED

    category_slug, category_confidence = _heads[CATEGORY_HEAD].predict(text)
    urgency_slug, urgency_confidence = _heads[URGENCY_HEAD].predict(text)

    # Same treatment as an unknown category slug: warn and send it to a human.
    # Happens when the taxonomy changes and only one head gets retrained.
    try:
        urgency = Urgency(urgency_slug)
    except ValueError:
        log.warning("model returned unknown urgency %s, sending to review", urgency_slug)
        return UNCLASSIFIED

    return Prediction(
        category_slug=category_slug,
        category_confidence=category_confidence,
        urgency=urgency,
        urgency_confidence=urgency_confidence,
        model_version=_model_version,
    )
