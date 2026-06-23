"""
run.py
Entry point. From the project root:

    pip install -r requirements.txt
    python run.py

Then open http://localhost:5001

On the very first run (or if datasets/traffic_temporal_data.csv is missing),
the dataset is generated automatically before Flask starts.
This takes ~30-60 seconds and only happens once.
"""

# ── Dataset bootstrap (must come before any backend imports) ─────────────────
from dataset_bootstrap import ensure_dataset
ensure_dataset()
# ─────────────────────────────────────────────────────────────────────────────

from backend.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
