# ml

Text classification for citizen service requests. Two independent heads over the
same input: **category** (multi-class) and **urgency** (low / medium / high).

This directory is deliberately decoupled from the API. Everything runs as scripts
against a CSV and writes metrics to `results/`. Nothing here imports from
`backend/`, and `backend/` does not import from here. It loads only the exported
ONNX model.

## Layout

```
data/       labeled dataset + train/val/test splits (committed; fixed seed)
scripts/    baseline, training, evaluation, quantization/export
results/    metrics, confusion matrices, run logs (committed, because they are results)
```

Model weights and checkpoints are gitignored. Datasets, splits, and results are not.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Dataset format

```csv
text,category,urgency,source
"may malaking butas sa kalsada malapit sa barangay hall delikado na",road_infrastructure,high,synthetic
```

`source` is `real` or `synthetic`, so performance can be reported per subset.
Splits are stratified 70/15/15 with a fixed seed and committed as files, so every
run is reproducible.
