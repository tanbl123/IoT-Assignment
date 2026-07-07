# Backend — Fall Detection ML

The laptop/ML side of the Smart Elderly Fall Detection System: trains a Random
Forest on the UP-Fall dataset, confirms falls, and serves a results dashboard.

`data/dataset.csv` (the 7-feature training file) is committed, so you can run
**everything below without downloading the multi-GB raw images**.

## Quick start (for teammates)

Prerequisite: **Python 3.10+** (`python --version`).

```bash
# 1. Get the code
git clone https://github.com/tanbl123/IoT-Assignment.git
cd IoT-Assignment/backend-python

# 2. Create an isolated environment (recommended, so it won't clash with other projects)
python -m venv fall-detection-env

#    Windows PowerShell: if you get "running scripts is disabled on this system",
#    run this once (safe — it only affects this terminal), then activate:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
fall-detection-env\Scripts\Activate.ps1      # Windows PowerShell
# source fall-detection-env/bin/activate     # macOS / Linux

# 3. Install the libraries
python -m pip install -r requirements.txt
```

> **PowerShell won't activate the venv?** The error "running scripts is disabled
> on this system" is a Windows default, not a bug. Either run the
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` line above first,
> or skip activation and call the venv's Python directly:
> `fall-detection-env\Scripts\python.exe -m pip install -r requirements.txt`
> then `fall-detection-env\Scripts\python.exe train_model.py`.

Then run whichever part you want:

### A. Train the model
```bash
python train_model.py            # trains the Random Forest from data/dataset.csv
                                 # -> saves fall_rf.joblib + prints the metrics
```

### B. Fall-detection demo (no hardware needed)
```bash
python live_inference.py --demo  # streams sample data: confirms a real fall,
                                 # dismisses a false alarm  (Stage-2 of the funnel)
```
*(Without `--demo` it reads a real ESP32 over serial; with no ESP32 it falls back to the demo.)*

### C. Results — website or charts
```bash
python app.py                    # live website at http://127.0.0.1:5000
#   (change the dataset? visit http://127.0.0.1:5000/refresh to recompute)

# ...or generate offline files instead:
python evaluate_and_plot.py      # writes results-dashboard.html + figures/*.png
```

## What each file does

| File | Role |
|------|------|
| `train_model.py` | Trains the Random Forest from `data/dataset.csv`; honest leakage-free + subject-independent metrics |
| `live_inference.py` | Stage-2 fall confirm loop; `--demo` runs with no hardware |
| `evaluate_and_plot.py` | Computes metrics + charts + dashboard **live from the dataset** |
| `app.py` | Serves the results as a local website (Flask) |
| `feature_extraction.py` | The 7 image + motion features (see `FEATURES.md`) |
| `firebase_client.py` | Uploads confirmed falls to Firebase (offline-safe) |
| `build_dataset_upfall.py` | (Re)builds `dataset.csv` from raw UP-Fall downloads — **needs the multi-GB images; not required to run A–C** |

## Reference docs
- `FEATURES.md` — the 7 features and why each matters
- `RESULTS.md` — the evaluation numbers (90.6% recall / 75.6% precision, 17 subjects)
- `data/DATASET_GUIDE.md` — how the dataset was built / how to rebuild it

## Notes
- Generated files (`figures/`, `results-dashboard.html`, `fall_rf.joblib`) are
  git-ignored — they regenerate from `data/dataset.csv`, so they never go stale.
- The results website (`app.py`) is **separate** from the live detection
  (`live_inference.py`) — run it only when you want to show the metrics.
