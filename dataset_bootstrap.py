"""
dataset_bootstrap.py
--------------------
Called by run.py before Flask starts.
Checks if datasets/traffic_temporal_data.csv exists; if not, generates it
automatically from road_network/bengaluru_road_segments_full.csv
(6,066 segments × 480 timestamps = 2,911,680 rows — identical to the
original dataset).

This file is the single entry-point for dataset readiness. run.py does:

    from dataset_bootstrap import ensure_dataset
    ensure_dataset()
"""

import os
import sys
import time

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE        = os.path.dirname(os.path.abspath(__file__))
_DATASET_PATH = os.path.join(_HERE, "datasets", "traffic_temporal_data.csv")
_ROADS_PATH   = os.path.join(_HERE, "road_network", "bengaluru_road_segments_full.csv")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def ensure_dataset() -> None:
    """
    Main entry point called by run.py.
    - Dataset exists  → prints confirmation, returns immediately.
    - Dataset missing → generates 2,911,680 rows (~60 s), then returns.
    """
    if os.path.exists(_DATASET_PATH):
        size_mb = os.path.getsize(_DATASET_PATH) / 1_048_576
        print(f"[bootstrap] ✓ Dataset found ({size_mb:.1f} MB) — skipping generation.")
        return

    print("[bootstrap] Dataset not found — generating now (one-time setup).")
    print("[bootstrap] This takes ~60–90 s and only runs once.")
    _generate()


# ---------------------------------------------------------------------------
# Generation logic (mirrors traffic_generator.py exactly)
# ---------------------------------------------------------------------------
def _get_base_congestion(row: pd.Series) -> float:
    score = 0.20
    road_class = str(row.get("road_class", "")).lower()
    if "primary" in road_class:
        score += 0.25
    elif "secondary" in road_class:
        score += 0.18
    elif "residential" in road_class:
        score += 0.08

    if str(row.get("highway", "nan")).lower() not in ("nan", "none", ""):
        score += 0.15

    length = float(row.get("length_m", 0))
    if length > 2000:
        score += 0.12
    elif length > 1000:
        score += 0.07

    connections = str(row.get("connected_segment_ids", ""))
    n_conn = len([c for c in connections.split(",") if c.strip()])
    if n_conn > 4:
        score += 0.15
    elif n_conn > 2:
        score += 0.08

    return min(score, 1.0)


def _time_factor(hour: int) -> float:
    if 7 <= hour <= 10:          return 1.6   # morning rush
    if 17 <= hour <= 20:         return 1.8   # evening rush
    if 11 <= hour <= 15:         return 1.1   # daytime
    if hour >= 22 or hour <= 5:  return 0.35  # night
    return 0.8


def _weekend_factor(day: int) -> float:
    return 0.80 if day in (5, 6) else 1.0


def _incident_factor():
    x = np.random.rand()
    if x < 0.02: return "Accident",     1.50
    if x < 0.04: return "Construction", 1.30
    return "None", 1.0


def _generate() -> None:
    if not os.path.exists(_ROADS_PATH):
        print(f"[bootstrap] ERROR: Road segments file not found at {_ROADS_PATH}")
        sys.exit(1)

    roads = pd.read_csv(_ROADS_PATH)
    n_roads = len(roads)

    # 60 days × 8 timestamps/day (every 3 h) = 480 per segment
    start_date = pd.Timestamp.today().floor("D")
    timestamps = pd.date_range(start=start_date, periods=60 * 8, freq="3h")
    n_ts  = len(timestamps)
    total = n_roads * n_ts

    print(f"[bootstrap] {n_roads:,} segments × {n_ts} timestamps = {total:,} rows")
    print()

    rows = []
    t0 = time.time()

    for i, (_, road) in enumerate(roads.iterrows()):
        base = _get_base_congestion(road)
        for ts in timestamps:
            tm = _time_factor(ts.hour)
            wk = _weekend_factor(ts.weekday())
            incident, im = _incident_factor()

            congestion  = base * tm * wk * im
            congestion += np.random.uniform(-0.05, 0.05)
            congestion  = max(0.05, min(1.0, congestion))

            rows.append([
                road["segment_id"],
                road["road_name"],
                ts,
                incident,
                round(congestion, 3),
                round(80 * (1 - congestion), 2),
                int(congestion * np.random.randint(100, 500)),
            ])

        # Progress bar every 100 roads
        if (i + 1) % 100 == 0 or (i + 1) == n_roads:
            pct     = (i + 1) / n_roads
            done    = int(pct * 40)
            bar     = "█" * done + "░" * (40 - done)
            elapsed = time.time() - t0
            eta     = (elapsed / (i + 1)) * (n_roads - i - 1)
            print(
                f"\r  [{bar}] {pct*100:5.1f}%  "
                f"{i+1:>5}/{n_roads}  ETA {eta:4.0f}s",
                end="", flush=True,
            )

    print()
    print(f"[bootstrap] Done in {time.time()-t0:.1f}s — saving …")

    df = pd.DataFrame(rows, columns=[
        "segment_id", "road_name", "timestamp",
        "incident", "congestion_score", "avg_speed_kmph", "vehicle_density",
    ])

    os.makedirs(os.path.dirname(_DATASET_PATH), exist_ok=True)
    df.to_csv(_DATASET_PATH, index=False)

    size_mb = os.path.getsize(_DATASET_PATH) / 1_048_576
    print(f"[bootstrap] ✓ {len(df):,} rows saved → datasets/traffic_temporal_data.csv  ({size_mb:.1f} MB)")
    print()
