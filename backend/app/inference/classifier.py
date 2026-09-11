"""The seam the trained model drops into.

Nothing is trained yet, so `classify` returns no labels and zero confidence.
That is not a stub standing in for behaviour: zero is below any threshold, so
every request goes to the review queue and a human labels it, which is the
fallback the system is designed around anyway.

Swapping the real model in means filling `load` and `classify`. Nothing outside
this file changes.
"""

from dataclasses import dataclass

from app.models.enums import Urgency

# Set when a model is loaded. Stored per request so Chapter 4 can compare
# accuracy across retrained versions instead of one blurred number.
MODEL_VERSION: str | None = None

_model = None


@dataclass(frozen=True)
class Prediction:
    category_id: int | None
    category_confidence: float
    urgency: Urgency | None
    urgency_confidence: float
    model_version: str | None


UNCLASSIFIED = Prediction(
    category_id=None,
    category_confidence=0.0,
    urgency=None,
    urgency_confidence=0.0,
    model_version=MODEL_VERSION,
)


def load() -> None:
    """Called once at startup, never per request. A model takes seconds to load."""
    global _model
    _model = None


def is_loaded() -> bool:
    return _model is not None


def classify(text: str) -> Prediction:
    """Plain `def`, not `async def`. Inference is CPU work and would block the
    event loop for every other request. Callers hand this to a threadpool."""
    if _model is None:
        return UNCLASSIFIED
    raise NotImplementedError("no trained model yet")
