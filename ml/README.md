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

The barangay declined to share its records on
privacy grounds, so every entry is authored by the proponents and `source` reads
`synthetic` throughout. That is stated in Chapter 3 as a limitation.

Splits are stratified 70/15/15 with a fixed seed and committed as files, so every
run is reproducible.

## Running it

Python 3.12. The baseline needs only scikit-learn, pandas, numpy and matplotlib;
the rest of `requirements.txt` is for fine-tuning and export.

```bash
python scripts/make_splits.py data/requests.csv   # writes train/val/test.csv
python scripts/baseline.py                        # TF-IDF + linear SVM
python scripts/threshold_sweep.py                 # picks the threshold, on val
```

`scripts/common.py` holds the label sets and the metrics. The transformer run
imports the same `score()` so both models are measured identically. Diverge here
and the comparison in Chapter 4 stops being a comparison.

### `tests/smoke_sample.csv`

42 rows, written to prove the scripts run. **Not the dataset.** Far too small to
train anything, and no number produced from it means anything. It exists so the
harness can be exercised before the real file lands, and so a broken script fails
today rather than the week the data arrives. Delete it once `requests.csv` is in.
