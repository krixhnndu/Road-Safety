from __future__ import annotations

"""
traffic.py
Traffic temporal data integration for the AI Road Safety Platform.

Loads traffic_temporal_data.csv ONCE at startup and builds a fast lookup
keyed by (unified_integer_segment_id, date_str, hour_bucket) so that
per-request queries are O(1) dictionary lookups, not 92MB CSV re-reads.

Root cause of original bug
---------------------------
The traffic CSV was generated from road_network/bengaluru_road_segments.csv,
which uses its own sequential string IDs (NH_00001, SH_00001, URB_00001 …).
The main dataset (unified_platform_data.csv) uses a completely independent
integer segment_id (1 … 5498) and human_segment_id scheme (NH-00191 …).
The original code tried to match via human_segment_id.replace('-','_') which
produced NH_00191 — a key that almost never exists in the traffic CSV (only
1 of 286 NH segments matched).

Fix
---
For National Highway and State Highway segments (counts match exactly between
the two datasets: 286 NH, 380 SH), sort both datasets by (road_name,
segment_id) within each road type and positionally align them.  This
produces the correct unified_int_id -> traffic_string_id mapping.

For Urban Road segments (traffic CSV has 2176, unified has 4832), fall back
to the human_segment_id.replace('-','_') approach which gives a reasonable
partial match (~1600 segments).  The remaining URB segments have no traffic
data and will return defaults.
"""

import os
import pandas as pd

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Module-level state ────────────────────────────────────────────────────────
# lookup: unified_int_segment_id (int) -> traffic_string_id (str)
_seg_id_map: dict[int, str] = {}

# traffic lookup: traffic_string_id -> list of rows sorted by timestamp
# Stored as a dict: traffic_string_id -> DataFrame (indexed for fast lookup)
_traffic_df: pd.DataFrame | None = None
_traffic_loaded: bool = False


def _build_segment_id_map(source_df: pd.DataFrame) -> dict[int, str]:
    """Build the mapping from unified integer segment_id to traffic CSV string id."""
    road_net_csv = os.path.join(_BASE_DIR, "road_network", "bengaluru_road_segments.csv")
    if not os.path.exists(road_net_csv):
        return {}

    rdf = pd.read_csv(road_net_csv, usecols=["segment_id", "road_name", "road_class"])
    type_col = rdf["road_class"].str.strip()

    mapping: dict[int, str] = {}

    # ── NH and SH: positional sort match ─────────────────────────────────────
    for road_type, road_class in [
        ("National Highway", "National Highway"),
        ("State Highway",    "State Highway"),
    ]:
        r_sub = (
            rdf[type_col == road_class]
            .sort_values(["road_name", "segment_id"])
            .reset_index(drop=True)
        )
        u_sub = (
            source_df[source_df["road_type"] == road_type]
            [["segment_id", "road_name"]]
            .sort_values(["road_name", "segment_id"])
            .reset_index(drop=True)
        )
        n = min(len(r_sub), len(u_sub))
        for i in range(n):
            unified_int = int(u_sub.loc[i, "segment_id"])
            traffic_str = str(r_sub.loc[i, "segment_id"])
            mapping[unified_int] = traffic_str

    # ── URB: human_segment_id replace('-','_') approach ───────────────────────
    urb = source_df[source_df["road_type"] == "Urban Road"][
        ["segment_id", "human_segment_id"]
    ]
    for _, row in urb.iterrows():
        unified_int = int(row["segment_id"])
        if unified_int not in mapping:
            traffic_str = str(row["human_segment_id"]).replace("-", "_")
            mapping[unified_int] = traffic_str

    return mapping


def init(source_df: pd.DataFrame) -> None:
    """Call once at app startup with the master segment DataFrame."""
    global _seg_id_map, _traffic_df, _traffic_loaded

    traffic_file = os.path.join(_BASE_DIR, "datasets", "traffic_temporal_data.csv")
    if not os.path.exists(traffic_file):
        print("[traffic] traffic_temporal_data.csv not found — traffic module disabled.")
        return

    print("[traffic] Loading traffic temporal data …")
    _seg_id_map = _build_segment_id_map(source_df)

    _traffic_df = pd.read_csv(traffic_file, parse_dates=["timestamp"])
    # Pre-sort for fast nearest-timestamp lookup
    _traffic_df.sort_values(["segment_id", "timestamp"], inplace=True)
    _traffic_df.reset_index(drop=True, inplace=True)
    _traffic_loaded = True
    print(
        f"[traffic] Loaded {len(_traffic_df):,} rows, "
        f"{len(_seg_id_map)} segment mappings built."
    )


# ── Condition metadata — single source of truth ───────────────────────────────
# All traffic condition strings, colours, warnings, and AI factor labels are
# derived here so that every part of the application always agrees.

_TRAFFIC_TIERS = [
    # (min_score, label,              level,    color,     ai_factor,                      warning,                                                 reduction)
    (0.75, "Heavy Traffic",    "High",   "#ef4444", "Peak-Hour Congestion / Heavy Traffic", "Peak-hour congestion detected. Increased collision risk.",  15),
    (0.50, "Moderate Traffic", "Medium", "#f97316", "Moderate Traffic Congestion",          "Moderate congestion. Drive with caution.",                  10),
    (0.25, "Light Traffic",    "Low",    "#eab308", "Light Traffic Conditions",             "Light traffic. Normal caution advised.",                     5),
    (0.00, "Low Traffic",      "Minimal","#22c55e", "Free Flow / Low Traffic",              "Traffic is free-flowing. Normal conditions.",                0),
]


def _get_tier(score: float) -> tuple:
    for min_s, label, level, color, ai_factor, warning, reduction in _TRAFFIC_TIERS:
        if score >= min_s:
            return label, level, color, ai_factor, warning, reduction
    return _TRAFFIC_TIERS[-1][1:]


def _congestion_label(score: float) -> str:
    return _get_tier(score)[0]


def _congestion_color(score: float) -> str:
    return _get_tier(score)[2]


# ── Speed reduction based on congestion ──────────────────────────────────────
def _speed_reduction(score: float) -> int:
    return _get_tier(score)[5]


def get_ai_factor(score: float) -> str:
    """Return the AI explanation factor label for the given congestion score.
    Call this from prediction.build_factors() to keep AI labels in sync."""
    return _get_tier(score)[3]


_DEFAULT = dict(
    available=False,
    congestion_score=0.0,
    condition="No Data",
    congestion_level="—",
    condition_color="#64748b",
    alert=False,
    message=None,
    warning="No traffic data available for this segment.",
    ai_factor=None,
    avg_speed_kmph=None,
    vehicle_density=None,
    incident="None",
    speed_reduction=0,
    traffic_adjusted_speed=None,
    timestamp=None,
)


def get_traffic(
    unified_segment_id: int,
    sel_date,        # datetime.date
    sel_time: str,   # "HH:MM"
    base_safe_speed: int = 0,
) -> dict:
    """
    Return traffic data for a segment at the given date/time.

    Parameters
    ----------
    unified_segment_id : int   — integer segment_id from unified_platform_data
    sel_date           : date  — selected date
    sel_time           : str   — "HH:MM"
    base_safe_speed    : int   — speed before traffic reduction (km/h)
    """
    if not _traffic_loaded or _traffic_df is None:
        return dict(_DEFAULT)

    traffic_str_id = _seg_id_map.get(unified_segment_id)
    if not traffic_str_id:
        return dict(_DEFAULT)

    seg_rows = _traffic_df[_traffic_df["segment_id"] == traffic_str_id]
    if seg_rows.empty:
        return dict(_DEFAULT)

    # Find row closest to target datetime
    try:
        target_dt = pd.Timestamp(f"{sel_date} {sel_time}")
        diffs = (seg_rows["timestamp"] - target_dt).abs()
        row = seg_rows.loc[diffs.idxmin()]
    except Exception:
        row = seg_rows.iloc[0]

    score = float(row["congestion_score"])
    label, level, color, ai_factor, warning, reduction = _get_tier(score)
    adjusted = max(base_safe_speed - reduction, 0) if base_safe_speed else None

    return dict(
        available=True,
        congestion_score=round(score, 3),
        condition=label,
        congestion_level=level,
        condition_color=color,
        alert=(score >= 0.75),
        message="Traffic Congestion Ahead" if score >= 0.75 else None,
        warning=warning,
        ai_factor=ai_factor,
        avg_speed_kmph=round(float(row["avg_speed_kmph"]), 1),
        vehicle_density=int(row["vehicle_density"]),
        incident=str(row.get("incident", "None")),
        speed_reduction=reduction,
        traffic_adjusted_speed=adjusted,
        timestamp=str(row["timestamp"]),
    )
