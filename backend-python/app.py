"""
Results website (Flask) for the Smart Elderly Fall Detection System.

Serves the ML evaluation dashboard as a live local website. Metrics are computed
from data/dataset.csv when the server starts, so the page always reflects the
CURRENT dataset — change the data, restart (or hit /refresh), and it updates.

    python app.py
    -> open http://127.0.0.1:5000   in your browser

This is SEPARATE from live_inference.py (the real-time accelerometer / gyroscope /
ESP32-CAM detection). Run this only when you want to show the metrics — it does
not touch, and is not needed by, the live sensor pipeline.
"""

from __future__ import annotations
from flask import Flask, redirect
from evaluate_and_plot import compute_metrics, render_dashboard

app = Flask(__name__)
_cache = {"data": None}


def get_data(refresh=False):
    if refresh or _cache["data"] is None:
        _cache["data"] = compute_metrics()
    return _cache["data"]


@app.route("/")
def index():
    return render_dashboard(get_data())


@app.route("/refresh")
def refresh():
    """Recompute from the current data/dataset.csv, then show the dashboard."""
    get_data(refresh=True)
    return redirect("/")


if __name__ == "__main__":
    print("Computing metrics from data/dataset.csv ...")
    get_data()  # warm the cache so the first page load is instant
    print("Dashboard ready → http://127.0.0.1:5000   (Ctrl+C to stop)")
    print("Changed the dataset? Visit http://127.0.0.1:5000/refresh to recompute.")
    app.run(host="127.0.0.1", port=5000, debug=False)
