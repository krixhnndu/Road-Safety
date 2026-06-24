"""
prediction.py
Core business logic, 1:1 ported from the original Streamlit app
(road-main/unified_platform.py). This module owns:

  - loading the master segment dataset + model metrics + the two ML models
  - all score/derivation formulas (hotspot score, recommended speed,
    speed-safety score, temporal exposure, school-zone override, etc.)
  - crash/hazard sync against the segment dataset for a given
    assessment date + time
  - the Explainable-AI factor builder used by the map detail panel and
    the XAI tab

Nothing here is UI-specific; routes.py calls into this module and
serializes the results to JSON.
"""
import os
from datetime import datetime, date as date_cls

import numpy as np
import pandas as pd

from . import model_loader, db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASETS_DIR = os.path.join(BASE_DIR, "datasets")

# ─── Constants (ported verbatim from unified_platform.py) ────────────────────
RISK_PALETTE = {
    'Aligned':               '#22c55e',
    'Moderate Misalignment': '#eab308',
    'High Misalignment':     '#f97316',
    'Critical Misalignment': '#ef4444',
}
HOTSPOT_PALETTE = {
    'Safe':           '#22c55e',
    'Moderate Risk':  '#eab308',
    'High Risk':      '#f97316',
    'Severe Hotspot': '#ef4444',
}
RISK_ORDER = ['Aligned', 'Moderate Misalignment', 'High Misalignment', 'Critical Misalignment']
HOTSPOT_ORDER = ['Safe', 'Moderate Risk', 'High Risk', 'Severe Hotspot']
BG = '#0d1b2e'

# crash_risk_score deliberately excluded — the classifier predicts whether the
# POSTED SPEED LIMIT is misaligned with road function/operating speed/VRU
# exposure (a leading indicator), not whether crashes have already happened
# (a lagging, behavior-confounded signal).
FEATURES = ['road_function_score', 'infrastructure_score', 'exposure_score',
            'human_tolerance_limit', 'operating_speed_score']

CRASH_EXPIRY_MINOR_DAYS = 60
CRASH_EXPIRY_OTHER_DAYS = 80
MINOR_WEIGHT = 10
MAJOR_WEIGHT = 25
FATAL_WEIGHT = 45
MIN_SEGMENT_LENGTH_KM = 0.25

# ─── Module-level state (loaded once at app startup) ──────────────────────────
_SOURCE_DF = None
_METRICS_DF = None
_FEATURE_IMPORTANCE_DF = None
_RF_MODEL = None
_GB_MODEL = None


def _normalize_posted_speed(df: "pd.DataFrame") -> "pd.DataFrame":
    """Round posted_speed_limit to nearest multiple of 10 and enforce
    per-road-type maximum caps.

    Constraints:
      National Highway : allowed multiples of 10 in [30..90]
      State Highway    : allowed multiples of 10 in [30..70]
      Urban Road       : allowed multiples of 10 in [20..60]

    Only posted_speed_limit is modified — all other speed columns are
    untouched.
    """
    _MAX_POSTED = {
        "National Highway": 90,
        "State Highway":    70,
        "Urban Road":       60,
    }
    _MIN_POSTED = {
        "National Highway": 30,
        "State Highway":    30,
        "Urban Road":       20,
    }

    df = df.copy()
    raw = pd.to_numeric(df["posted_speed_limit"], errors="coerce")

    # Round to nearest 10
    rounded = (raw / 10).round() * 10

    # Apply per-road-type min/max caps
    road_type = df["road_type"]
    max_cap = road_type.map(_MAX_POSTED).fillna(90)
    min_cap = road_type.map(_MIN_POSTED).fillna(20)
    clamped = rounded.clip(lower=min_cap, upper=max_cap)

    df["posted_speed_limit"] = clamped.astype(int)
    return df


def init():
    """Load the master dataset, model metrics, and the two trained models.
    Call once at app startup."""
    global _SOURCE_DF, _METRICS_DF, _FEATURE_IMPORTANCE_DF, _RF_MODEL, _GB_MODEL
    _SOURCE_DF = pd.read_csv(os.path.join(DATASETS_DIR, "unified_platform_data.csv"))
    _SOURCE_DF = _normalize_posted_speed(_SOURCE_DF)
    _METRICS_DF = pd.read_csv(os.path.join(DATASETS_DIR, "model_metrics.csv"))
    fi_path = os.path.join(DATASETS_DIR, "feature_importance.csv")
    _FEATURE_IMPORTANCE_DF = pd.read_csv(fi_path) if os.path.exists(fi_path) else None
    _RF_MODEL, _GB_MODEL = model_loader.load_models()
    db.init_db()
    db.purge_expired_hazards()


def get_metrics_df():
    return _METRICS_DF.copy()


def get_feature_importance_df():
    return _FEATURE_IMPORTANCE_DF.copy() if _FEATURE_IMPORTANCE_DF is not None else None


def get_best_model_row():
    return _METRICS_DF.sort_values('f1', ascending=False).iloc[0]


def get_active_model():
    return _GB_MODEL if _GB_MODEL is not None else _RF_MODEL


def get_active_model_name():
    if _GB_MODEL is not None:
        return "Gradient Boosting"
    if _RF_MODEL is not None:
        return "Random Forest"
    return "None"


# ─── Generic scoring helpers (ported) ─────────────────────────────────────────
def score_color(v, invert=False):
    v = float(v)
    if invert:
        if v >= 75: return '#ef4444'
        if v >= 45: return '#f97316'
        if v >= 25: return '#eab308'
        return '#22c55e'
    else:
        if v >= 75: return '#22c55e'
        if v >= 50: return '#eab308'
        if v >= 25: return '#f97316'
        return '#ef4444'


def temporal_exposure(row, hour):
    base = float(row.get('exposure_score', 50))
    schools = int(row.get('schools_count', 0) or 0)
    school_m = 1.5 if (8 <= hour <= 16 and schools > 0) else 0.8
    peak_m = 1.4 if (7 <= hour <= 9 or 17 <= hour <= 20) else 1.0
    night_m = 0.4 if (hour >= 23 or hour <= 5) else 1.0
    urb = str(row.get('urban_rural_flag', ''))
    market_m = 1.3 if (urb == 'Urban' and (9 <= hour <= 20)) else 1.0
    return min(100, base * school_m * peak_m * night_m * market_m)


def build_factors(row, hour=None, traffic_info=None):
    """Build explainability factors. traffic_info (from traffic.get_traffic())
    is used to source the traffic label so AI Explanation always matches the
    Traffic Conditions panel.  Falls back to hour-based heuristic when absent.
    """
    factors = []
    exp = float(row.get('exposure_score', 0) or 0)
    crash = float(row.get('crash_risk_score', 0) or 0)
    inf = float(row.get('infrastructure_score', 100) or 100)
    func = float(row.get('road_function_score', 0) or 0)
    ped = float(row.get('pedestrian_exposure_score', 0) or 0)
    sc = int(row.get('schools_count', 0) or 0)
    blk = str(row.get('blackspot_flag', ''))
    fc = int(row.get('fatal_crashes', 0) or 0)

    if ped > 40 or exp > 60: factors.append(('High Pedestrian Exposure', 'high'))
    if sc > 0: factors.append(('School Zone Active', 'high'))
    if crash > 70: factors.append(('High Crash History', 'high'))
    if fc > 0: factors.append(('Fatal Crashes Recorded', 'high'))
    if blk == 'Yes': factors.append(('Accident Blackspot', 'high'))
    if inf < 40: factors.append(('Poor Infrastructure Safety', 'high'))
    if inf < 30: factors.append(('Missing Sidewalks / Crosswalks', 'high'))
    if func > 70: factors.append(('High Road Function Complexity', 'med'))
    if exp > 40: factors.append(('High Activity Zone Nearby', 'med'))

    # Traffic factor: use dataset-derived label to stay in sync with Traffic panel
    if traffic_info and traffic_info.get('available') and traffic_info.get('ai_factor'):
        score = traffic_info.get('congestion_score', 0)
        severity = 'high' if score >= 0.75 else 'med' if score >= 0.25 else 'low'
        factors.append((traffic_info['ai_factor'], severity))
    elif hour is not None and (7 <= hour <= 9 or 17 <= hour <= 20):
        factors.append(('Peak Hour Traffic', 'med'))  # fallback when no traffic data

    if hour is not None and (8 <= hour <= 16 and sc > 0):
        factors.append(('School Hours — Children Present', 'high'))
    return factors if factors else [('Meets General Safety Standards', 'low')]
def apply_school_zone_speed(row, base_speed, hour, weekday):
    schools_count = int(row.get('schools_count', 0) or 0)
    is_sunday = (weekday == 6)
    if schools_count > 0 and not is_sunday:
        if 8 <= hour <= 16:
            final_speed = base_speed * 0.6
            return int(round(max(20.0, final_speed)))
    return int(base_speed)


def is_time_in_range(start, end, now_t):
    if start <= end:
        return start <= now_t <= end
    return now_t >= start or now_t <= end  # overnight range


# ─── Crash sync ────────────────────────────────────────────────────────────
def get_active_crashes(crash_records, assessment_date):
    """Filter crash records to only those still 'active' (not yet expired)
    as of assessment_date. Minor crashes expire after 60 days, Major/Fatal
    after 80 days."""
    active = []
    for c in crash_records:
        try:
            crash_date = datetime.strptime(str(c['date']), "%Y-%m-%d").date()
        except Exception:
            continue
        days_since = (assessment_date - crash_date).days
        if days_since < 0:
            continue
        limit = CRASH_EXPIRY_MINOR_DAYS if c['severity'] == 'Minor' else CRASH_EXPIRY_OTHER_DAYS
        if days_since <= limit:
            active.append(c)
    return active


def sync_segment_crashes(df, active_crashes, model):
    """Recompute crash_count/fatal_crashes/crash_risk_score/blackspot_flag
    from the active crash list, then re-run the ML classifier (misalignment
    label + probabilities), road_risk_score, hotspot_score/category, and
    the AI-recommended / final recommended safe speed. Mirrors
    sync_segment_crashes() in the original app."""
    df = df.copy()
    df['minor_crashes'] = 0
    df['major_crashes'] = 0
    df['fatal_crashes'] = 0
    df['crash_count'] = 0
    df['crash_risk_score'] = 0.0

    # Defensive handling: Fill missing/invalid segment lengths with 250m, clip to minimum 250m
    df['segment_length_km'] = df['length_m'].fillna(250.0).clip(lower=250.0) / 1000.0
    df['effective_length_km'] = df['segment_length_km'].clip(lower=MIN_SEGMENT_LENGTH_KM)
    df['severity_density'] = 0.0

    if active_crashes:
        cdf = pd.DataFrame(active_crashes)
        minor_counts = cdf[cdf['severity'] == 'Minor'].groupby('segment_id').size()
        major_counts = cdf[cdf['severity'] == 'Major'].groupby('segment_id').size()
        fatal_counts = cdf[cdf['severity'] == 'Fatal'].groupby('segment_id').size()

        df['minor_crashes'] = df['segment_id'].map(minor_counts).fillna(0).astype(int)
        df['major_crashes'] = df['segment_id'].map(major_counts).fillna(0).astype(int)
        df['fatal_crashes'] = df['segment_id'].map(fatal_counts).fillna(0).astype(int)
        df['crash_count'] = df['minor_crashes'] + df['major_crashes'] + df['fatal_crashes']

        df['crash_risk_score'] = (
            (df['minor_crashes'] * MINOR_WEIGHT + df['major_crashes'] * MAJOR_WEIGHT + df['fatal_crashes'] * FATAL_WEIGHT)
            / df['effective_length_km']
        ).clip(0, 100)

        df['severity_density'] = (
            df['minor_crashes'] * MINOR_WEIGHT +
            df['major_crashes'] * MAJOR_WEIGHT +
            df['fatal_crashes'] * FATAL_WEIGHT
        ) / df['effective_length_km']
        
    else:
        df['blackspot_flag'] = 'No'

    if model is not None:
        try:
            X = df[FEATURES]
            pred_classes = model.predict(X)
            pred_probs = model.predict_proba(X)

            labels = ['Aligned', 'Moderate Misalignment', 'High Misalignment', 'Critical Misalignment']
            df['ai_risk_label'] = [labels[c] for c in pred_classes]
            df['risk_category'] = df['ai_risk_label']
            df['ai_risk_probability'] = [pred_probs[i][pred_classes[i]] for i in range(len(df))]

            df['prob_low_risk'] = pred_probs[:, 0]
            df['prob_medium_risk'] = pred_probs[:, 1]
            df['prob_high_risk'] = pred_probs[:, 2]
            df['prob_critical_risk'] = pred_probs[:, 3]

            danger_mass = df['prob_high_risk'] + df['prob_critical_risk']
            severity_tilt = 1 + (df['prob_critical_risk'] / (danger_mass + 1e-6))
            ml_base = ((danger_mass * 100) * severity_tilt).clip(0, 100)
            df['road_risk_score'] = (
                ml_base * 0.7 + df['crash_risk_score'] * 0.3
            ).clip(0, 100).round().astype(int)

            df['segment_risk_score'] = (
                df['road_risk_score'] * 0.6 +
                df['crash_risk_score'] * 0.4
            ).clip(0, 100).round().astype(int)

            df['blackspot_flag'] = np.where(
                df['segment_risk_score'] >= 80,
                "Yes",
                "No"
            )


            df['ai_recommended_speed'] = np.minimum(df['speed_p85'], df['human_tolerance_limit']).round().astype(int)
            if 'original_safe_speed' not in df.columns:
                df['original_safe_speed'] = df['ai_recommended_speed']

            PENALTY_SCALE = {
                "National Highway": 3,
                "State Highway": 4,
                "Urban Road": 6
            }
            penalty_series = df['road_type'].map(PENALTY_SCALE).fillna(5)
            df['recommended_safe_speed'] = (
                df['ai_recommended_speed'] - (df['crash_risk_score'] / penalty_series)
            ).clip(lower=20).round().astype(int)

            df['speed_safety_score'] = (100 - (
                df['road_risk_score'] * 0.40 +
                df['crash_risk_score'] * 0.30 +
                (100 - df['infrastructure_score']) * 0.30
            )).clip(0, 100).round(1)
        except Exception as e:
            print(f"[prediction] model scoring failed: {e}")

    # hotspot_score / hotspot_category: always recomputed unconditionally
    # so that new crashes immediately update the Severe Hotspot KPI.
    # crash_risk_score is already freshly set above from active_crashes.
    df['hotspot_score'] = (
        0.40 * df['misalignment_score'] +
        0.25 * df['exposure_score'] +
        0.25 * df['severity_density'].clip(0, 100) +
        0.10 * (100 - df['infrastructure_score'])
    ).clip(0, 100).round(1)

    def _hotspot_cat(score):
        if score >= 75: return 'Severe Hotspot'
        if score >= 50: return 'High Risk'
        if score >= 25: return 'Moderate Risk'
        return 'Safe'
    df['hotspot_category'] = df['hotspot_score'].apply(_hotspot_cat)        

    return df


# ─── Hazard overrides ──────────────────────────────────────────────────────
def get_active_hazard_segs(hazards, sel_date, sel_time):
    active = set()
    for hz in hazards:
        try:
            hz_date = datetime.strptime(str(hz['date']), "%Y-%m-%d").date()
            if hz_date != sel_date:
                continue
            start = datetime.strptime(str(hz['start_time']), "%H:%M").time()
            end = datetime.strptime(str(hz['end_time']), "%H:%M").time()
            now_t = datetime.strptime(sel_time, "%H:%M").time()
            if is_time_in_range(start, end, now_t):
                active.add(int(hz['segment_id']))
        except Exception:
            continue
    return active


def get_hazard_temp_speed(hazards, segment_id, sel_date, sel_time, df):
    for hz in hazards:
        try:
            if int(hz['segment_id']) != segment_id:
                continue
            hz_date = datetime.strptime(str(hz['date']), "%Y-%m-%d").date()
            if hz_date != sel_date:
                continue
            start = datetime.strptime(str(hz['start_time']), "%H:%M").time()
            end = datetime.strptime(str(hz['end_time']), "%H:%M").time()
            now_t = datetime.strptime(sel_time, "%H:%M").time()
            if is_time_in_range(start, end, now_t):
                spd = hz.get('temp_speed')
                if spd:
                    return int(float(spd))
                r_type = df.loc[df['segment_id'] == segment_id, 'road_type']
                r_type = r_type.iloc[0] if len(r_type) else ""
                return default_hazard_speed(r_type)
        except Exception:
            continue
    return None


def default_hazard_speed(road_type):
    if road_type == "National Highway": return 60
    if road_type == "State Highway":    return 50
    return 30  # Urban Road


def apply_dynamic_hazard_speeds(df, hazards, sel_date, sel_time):
    df = df.copy()
    if 'original_safe_speed' not in df.columns:
        df['original_safe_speed'] = df['recommended_safe_speed'].copy()

    df['recommended_safe_speed'] = (
        df['ai_recommended_speed'] - (df['crash_risk_score'] / 5)
    ).clip(lower=20).round().astype(int)

    for hz in hazards:
        try:
            hz_date = datetime.strptime(str(hz['date']), "%Y-%m-%d").date()
            if hz_date != sel_date:
                continue
            start = datetime.strptime(str(hz['start_time']), "%H:%M").time()
            end = datetime.strptime(str(hz['end_time']), "%H:%M").time()
            now_t = datetime.strptime(sel_time, "%H:%M").time()
            if is_time_in_range(start, end, now_t):
                sid = int(hz['segment_id'])
                spd = hz.get('temp_speed')
                if not spd:
                    r_type = df.loc[df['segment_id'] == sid, 'road_type']
                    r_type = r_type.iloc[0] if len(r_type) else ""
                    spd = default_hazard_speed(r_type)
                df.loc[df['segment_id'] == sid, 'recommended_safe_speed'] = int(float(spd))
        except Exception:
            continue
    return df


# ─── Hard final-speed constraints ─────────────────────────────────────────
# Applied after ALL other modules (AI, weather, traffic, school-zone, Vision
# Zero) have run, but BEFORE returning results to the caller.
# Hazard-override segments (where a manual temp_speed was set through Hazard
# Management) are excluded — their speed is already the operator's explicit
# choice and must not be clamped.

ROAD_TYPE_MAX = {
    "Urban Road": 70,          # hard ceiling
    # NH and SH have no ceiling — existing logic is preserved
}
ROAD_TYPE_MIN = {
    "National Highway": 30,
    "State Highway":    25,
    "Urban Road":       20,
}


def apply_final_speed_constraints(df: "pd.DataFrame",
                                   hazard_segment_ids: set) -> "pd.DataFrame":
    """Enforce road-type min/max hard constraints on final_safe_speed.

    Segments in *hazard_segment_ids* have a manually set operator speed and
    are completely bypassed — the hazard override takes absolute priority.
    """
    for idx, row in df.iterrows():
        sid = int(row["segment_id"])
        if sid in hazard_segment_ids:
            continue          # hazard override — do not clamp

        rt  = row.get("road_type", "")
        spd = int(row["final_safe_speed"])

        # Maximum constraint (Urban Road only)
        if rt in ROAD_TYPE_MAX:
            spd = min(spd, ROAD_TYPE_MAX[rt])

        # Minimum constraint (all road types)
        if rt in ROAD_TYPE_MIN:
            spd = max(spd, ROAD_TYPE_MIN[rt])

        df.at[idx, "final_safe_speed"] = spd

    return df


# ─── Top-level state computation ──────────────────────────────────────────
def compute_state(sel_date, sel_time):
    """Returns (df, crashes, hazards, active_crashes) for the given
    assessment date (a date object) and time ('HH:MM' string) — the full,
    unfiltered network with all scores/overrides freshly applied."""
    crashes = db.get_all_crashes()
    hazards = db.get_all_hazards()
    active_crashes = get_active_crashes(crashes, sel_date)

    df = sync_segment_crashes(_SOURCE_DF, active_crashes, get_active_model())
    df = apply_dynamic_hazard_speeds(df, hazards, sel_date, sel_time)

    sel_hour = int(sel_time.split(':')[0])
    weekday = sel_date.weekday()
    df['final_safe_speed'] = df.apply(
        lambda r: apply_school_zone_speed(r, r['recommended_safe_speed'], sel_hour, weekday), axis=1)
    df['temporal_exposure'] = df.apply(lambda r: temporal_exposure(r, sel_hour), axis=1)

    # Step 6-8: Apply hard road-type min/max constraints (after all other modules).
    # Segments with an active manual hazard speed are excluded from clamping.
    active_hazard_sids = get_active_hazard_segs(hazards, sel_date, sel_time)
    df = apply_final_speed_constraints(df, active_hazard_sids)

    return df, crashes, hazards, active_crashes


def apply_filters(df, road_type=None, risk_cat=None, hotspot_cat=None,
                   speed_min=None, speed_max=None):
    df_f = df
    if road_type and road_type != 'All':
        df_f = df_f[df_f['road_type'] == road_type]
    if risk_cat and risk_cat != 'All':
        df_f = df_f[df_f['ai_risk_label'] == risk_cat]
    if hotspot_cat and hotspot_cat != 'All':
        df_f = df_f[df_f['hotspot_category'] == hotspot_cat]
    if speed_min is not None:
        df_f = df_f[df_f['posted_speed_limit'] >= speed_min]
    if speed_max is not None:
        df_f = df_f[df_f['posted_speed_limit'] <= speed_max]
    return df_f


# ─── Standalone /api/predict — simplified quick-estimate endpoint ─────────
# NOTE: this implements the exact request/response contract requested in
# the migration brief (infrastructure_score / exposure_score /
# crash_risk_score / operating_speed -> recommended_safe_speed). It is a
# transparent Vision-Zero-style formula, deliberately separate from the
# full 5-feature Gradient-Boosting/Random-Forest classifier that powers
# the per-segment dashboard (see /api/segments and FEATURES above) —
# that model was trained on road_function_score/human_tolerance_limit/
# operating_speed_score and cannot be queried with only these four inputs.
def predict_quick(infrastructure_score, exposure_score, crash_risk_score, operating_speed):
    tolerance = 80.0
    tolerance -= (100 - infrastructure_score) * 0.2
    tolerance -= exposure_score * 0.3
    tolerance -= crash_risk_score * 0.2
    tolerance = max(20.0, min(80.0, tolerance))
    recommended = min(float(operating_speed), tolerance)
    return int(round(recommended))
