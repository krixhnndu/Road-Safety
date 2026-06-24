"""
weather.py
Simulated Roadside IoT Weather Sensing Unit for the AI Road Safety Platform.
Generates rainfall intensity measurements per road segment every 30 minutes,
using weighted probabilities to mimic real-world ITS weather station data.
No external APIs are used — purely internal simulation.
"""
import random
import time
import threading
from datetime import datetime

# ─── Weather condition thresholds (mm/hr) ─────────────────────────────────
WEATHER_CONDITIONS = [
    (0,    0,    "Clear / Sunny",           "☀",  "#fbbf24", 0),
    (0.1,  2.5,  "Light Rain",              "🌦", "#60a5fa", 3),
    (2.5,  10,   "Moderate Rain",           "🌧", "#3b82f6", 5),
    (10,   50,   "Heavy Rainfall",          "⛈", "#f97316", 10),
    (50,   999,  "Extreme Rainfall / Storm","⚠",  "#ef4444", 15),
]

# Weighted buckets: (label, weight, rainfall_range)
_WEATHER_BUCKETS = [
    ("Clear / Sunny",            0.40, (0,    0)),
    ("Light Rain",               0.25, (0.1,  2.5)),
    ("Moderate Rain",            0.20, (2.5,  10)),
    ("Heavy Rainfall",           0.10, (10,   50)),
    ("Extreme Rainfall / Storm", 0.05, (50,   60)),
]

# ─── Minimum speeds after all adjustments ─────────────────────────────────
ROAD_TYPE_MIN_SPEED = {
    "National Highway": 30,
    "State Highway":    30,
    "Urban Road":       20,
}

# ─── Module state ─────────────────────────────────────────────────────────
_weather_data = {}        # segment_id -> {rainfall_mmhr, condition, icon, color, speed_reduction, last_updated}
_lock = threading.Lock()
_refresh_interval_seconds = 1800   # 30 minutes


def _classify_rainfall(mmhr: float) -> dict:
    """Return condition metadata for a given rainfall value."""
    for lo, hi, label, icon, color, reduction in WEATHER_CONDITIONS:
        if mmhr <= 0.0 and lo == 0:
            return dict(condition=label, icon=icon, color=color, speed_reduction=reduction)
        if lo <= mmhr < hi:
            return dict(condition=label, icon=icon, color=color, speed_reduction=reduction)
    # fallback: extreme
    _, _, label, icon, color, reduction = WEATHER_CONDITIONS[-1]
    return dict(condition=label, icon=icon, color=color, speed_reduction=reduction)


def _sample_rainfall() -> float:
    """Sample a rainfall value using weighted probabilities."""
    r = random.random()
    cumulative = 0.0
    for _, weight, (lo, hi) in _WEATHER_BUCKETS:
        cumulative += weight
        if r < cumulative:
            if lo == 0 and hi == 0:
                return 0.0
            return round(random.uniform(lo, hi), 2)
    return 0.0


def _generate_for_segments(segment_ids):
    """Generate (or regenerate) weather readings for all given segment IDs."""
    now_str = datetime.now().strftime("%H:%M")
    new_data = {}
    for sid in segment_ids:
        mmhr = _sample_rainfall()
        meta = _classify_rainfall(mmhr)
        new_data[sid] = dict(
            segment_id=sid,
            rainfall_mmhr=mmhr,
            **meta,
            last_updated=now_str,
        )
    with _lock:
        _weather_data.update(new_data)


def _refresh_loop(segment_ids):
    while True:
        _generate_for_segments(segment_ids)
        time.sleep(_refresh_interval_seconds)


def init(segment_ids):
    """Call once at startup with the list of all segment IDs."""
    _generate_for_segments(segment_ids)
    t = threading.Thread(target=_refresh_loop, args=(segment_ids,), daemon=True)
    t.start()


def get_weather(segment_id: int) -> dict:
    """Return the current weather reading for a segment."""
    with _lock:
        return _weather_data.get(int(segment_id), {
            "segment_id": segment_id,
            "rainfall_mmhr": 0.0,
            "condition": "Clear / Sunny",
            "icon": "☀",
            "color": "#fbbf24",
            "speed_reduction": 0,
            "last_updated": "--:--",
        })


def get_all_weather() -> dict:
    """Return a copy of all weather readings keyed by segment_id."""
    with _lock:
        return dict(_weather_data)


def apply_weather_speed(base_speed: int, segment_id: int, road_type: str) -> dict:
    """
    Apply weather-based speed reduction to an existing safe speed.
    Returns dict with weather_condition, rainfall_mmhr, icon, color,
    speed_reduction, weather_adjusted_speed.
    Enforces road-type minimum speeds after reduction.
    """
    w = get_weather(segment_id)
    reduction = w.get("speed_reduction", 0)
    adjusted = max(base_speed - reduction, 0)
    min_speed = ROAD_TYPE_MIN_SPEED.get(road_type, 20)
    final = max(adjusted, min_speed)
    return dict(
        weather_condition=w.get("condition", "Clear / Sunny"),
        rainfall_mmhr=w.get("rainfall_mmhr", 0.0),
        weather_icon=w.get("icon", "☀"),
        weather_color=w.get("color", "#fbbf24"),
        speed_reduction=reduction,
        base_speed=base_speed,
        weather_adjusted_speed=final,
        min_speed_enforced=(final == min_speed and adjusted < min_speed),
    )


def get_summary_stats() -> dict:
    """Compute fleet-wide weather summary for the Weather Intelligence tab."""
    with _lock:
        rows = list(_weather_data.values())
    if not rows:
        return {}

    total = len(rows)
    dist = {}
    total_rainfall = 0.0
    heavy_count = 0
    extreme_count = 0

    for r in rows:
        cond = r["condition"]
        dist[cond] = dist.get(cond, 0) + 1
        total_rainfall += r["rainfall_mmhr"]
        if cond == "Heavy Rainfall":
            heavy_count += 1
        elif cond == "Extreme Rainfall / Storm":
            extreme_count += 1

    # dominant condition
    dominant = max(dist, key=dist.get) if dist else "Clear / Sunny"
    dom_meta = _classify_rainfall(0.0 if dominant == "Clear / Sunny" else
                                   1.0 if dominant == "Light Rain" else
                                   5.0 if dominant == "Moderate Rain" else
                                   20.0 if dominant == "Heavy Rainfall" else 55.0)

    condition_order = [b[0] for b in _WEATHER_BUCKETS]
    dist_ordered = [{"condition": c, "count": dist.get(c, 0),
                     "pct": round(dist.get(c, 0) / total * 100, 1)}
                    for c in condition_order]

    return dict(
        total_segments=total,
        dominant_condition=dominant,
        dominant_icon=dom_meta["icon"],
        dominant_color=dom_meta["color"],
        avg_rainfall_mmhr=round(total_rainfall / total, 2),
        heavy_count=heavy_count,
        extreme_count=extreme_count,
        distribution=dist_ordered,
        last_updated=rows[0]["last_updated"] if rows else "--:--",
    )
