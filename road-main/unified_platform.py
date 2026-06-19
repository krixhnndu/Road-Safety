"""
AI for Safer Roads — Speed Limit Misalignment & Safety Management Platform
Bangalore Road Network (NH/SH/Arterial/Collector/Local, 4,966 segments)
Reframed per the ADB AI4SaferRoads Innovation Challenge: assesses whether
POSTED SPEED LIMITS are misaligned with road function, operating speed,
and VRU exposure — not whether drivers are speeding.
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
import joblib
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import random

try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_OK = True
except ImportError:
    FOLIUM_OK = False

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Road Safety Platform · Bangalore",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Base */
html,body,[data-testid="stAppViewContainer"]{background:#080e1a !important;}
.block-container{padding:0.8rem 1.8rem 2rem;}

/* Topbar */
.topbar{
  display:flex;align-items:center;gap:12px;
  background:linear-gradient(90deg,#0d1b2e,#0a1628);
  border:1px solid #1a2d45;border-radius:12px;
  padding:12px 20px;margin-bottom:16px;
}
.topbar-brand{
  font-family:'IBM Plex Mono',monospace;font-size:1.1rem;
  font-weight:700;color:#e2e8f0;letter-spacing:.04em;
  display:flex;align-items:center;gap:8px;
}
.topbar-dot{width:10px;height:10px;border-radius:50%;
  background:#22c55e;box-shadow:0 0 8px #22c55e;}
.topbar-tag{
  background:#1a2d45;color:#60a5fa;
  font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  padding:3px 10px;border-radius:20px;border:1px solid #2d4a6e;
}
.topbar-city{
  background:#1a1f35;color:#a78bfa;
  font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  padding:3px 10px;border-radius:20px;border:1px solid #3b3080;
}
.topbar-right{margin-left:auto;display:flex;align-items:center;gap:10px;}
.live-badge{
  background:#052e16;color:#22c55e;
  font-size:.68rem;font-weight:700;letter-spacing:.1em;
  padding:3px 9px;border-radius:20px;border:1px solid #166534;
}
.topbar-time{
  font-family:'IBM Plex Mono',monospace;font-size:.82rem;color:#94a3b8;
}

/* KPI Cards */
.kpi-row{display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;}
.kpi{
  flex:1;min-width:110px;
  background:linear-gradient(135deg,#0d1b2e,#0a1628);
  border-radius:12px;padding:14px 16px;
  border:1px solid #1a2d45;text-align:center;
}
.kpi-v{font-size:1.8rem;font-weight:800;line-height:1;}
.kpi-l{font-size:.66rem;color:#64748b;text-transform:uppercase;
       letter-spacing:.08em;margin-top:5px;}
.blue{color:#60a5fa;} .green{color:#22c55e;}
.orange{color:#f97316;} .red{color:#ef4444;}
.purple{color:#a78bfa;} .yellow{color:#fbbf24;} .teal{color:#2dd4bf;}
.pink{color:#f472b6;} .sky{color:#38bdf8;}

/* Tabs */
.stTabs [data-baseweb="tab-list"]{
  background:#0d1b2e;border-radius:10px;padding:4px;
  border:1px solid #1a2d45;
}
.stTabs [data-baseweb="tab"]{
  color:#64748b;font-size:.82rem;font-weight:600;
  border-radius:8px;padding:6px 16px;
}
.stTabs [aria-selected="true"]{
  background:#1a2d45 !important;color:#e2e8f0 !important;
}

/* Panels */
.panel{
  background:#0d1b2e;border-radius:12px;padding:16px;
  border:1px solid #1a2d45;margin-bottom:12px;
}
.panel h4{color:#e2e8f0;font-size:.85rem;margin:0 0 12px;
  text-transform:uppercase;letter-spacing:.06em;}
.panel-divider{border:none;border-top:1px solid #1a2d45;margin:10px 0;}

/* Segment detail */
.seg-header{
  background:linear-gradient(135deg,#0d1b2e,#0a2040);
  border-radius:12px;padding:16px;border:1px solid #1e3a5f;
  margin-bottom:12px;
}
.seg-id{font-family:'IBM Plex Mono',monospace;font-size:1.3rem;
  font-weight:700;color:#60a5fa;letter-spacing:.05em;}
.seg-name{font-size:.85rem;color:#94a3b8;margin-top:3px;}
.seg-type{
  display:inline-block;font-size:.65rem;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;
  padding:2px 8px;border-radius:4px;margin-top:6px;
}

/* Speed card */
.speed-card{
  background:#05122a;border:1px solid #1e3a5f;
  border-radius:12px;padding:16px;text-align:center;margin-bottom:10px;
}
.speed-main{font-size:3rem;font-weight:900;color:#60a5fa;line-height:1;}
.speed-unit{font-size:.9rem;color:#64748b;}
.speed-range{font-size:.78rem;color:#94a3b8;margin-top:4px;}
.speed-posted{font-size:.75rem;color:#64748b;margin-top:2px;}

/* Score bars */
.sbar{margin:5px 0;}
.sbar-lbl{display:flex;justify-content:space-between;
  font-size:.74rem;color:#64748b;margin-bottom:2px;}
.sbar-track{background:#0a1628;border-radius:3px;height:6px;overflow:hidden;}
.sbar-fill{height:100%;border-radius:3px;}

/* Risk/factor pills */
.factor-pill{
  display:inline-block;font-size:.68rem;font-weight:700;
  letter-spacing:.05em;text-transform:uppercase;
  padding:3px 9px;border-radius:3px;margin:3px 3px 3px 0;
}
.f-high{background:rgba(239,68,68,.15);color:#f87171;}
.f-med {background:rgba(251,191,36,.12);color:#fbbf24;}
.f-low {background:rgba(96,165,250,.12);color:#60a5fa;}

/* Blackspot banner */
.bs-banner{
  background:rgba(239,68,68,.1);border:1px solid #991b1b;
  border-radius:8px;padding:8px 12px;margin-bottom:10px;
  display:flex;align-items:center;gap:8px;
  font-size:.75rem;font-weight:700;color:#f87171;
  text-transform:uppercase;letter-spacing:.08em;
}
.bs-dot{width:8px;height:8px;border-radius:50%;
  background:#ef4444;box-shadow:0 0 6px #ef4444;flex-shrink:0;}

/* Hazard items */
.hazard-item{
  background:#0d1b2e;border:1px solid #1a2d45;
  border-radius:8px;padding:10px 12px;margin-bottom:6px;
}
.hazard-type{font-size:.72rem;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;color:#fbbf24;}
.hazard-meta{font-size:.7rem;color:#64748b;margin-top:2px;}

/* Chart card */
.chart-card{
  background:#0d1b2e;border-radius:12px;padding:14px;
  border:1px solid #1a2d45;margin-bottom:12px;
}
.chart-title{color:#94a3b8;font-size:.75rem;text-transform:uppercase;
  letter-spacing:.08em;margin-bottom:10px;}

/* Sidebar */
[data-testid="stSidebar"]{background:#05090f !important;}
[data-testid="stSidebar"] label{color:#64748b !important;font-size:.76rem !important;}
[data-testid="stSidebar"] .stSelectbox>div>div{
  background:#0d1b2e !important;border-color:#1a2d45 !important;color:#e2e8f0 !important;
}
[data-testid="stSidebar"] p{color:#94a3b8 !important;}

/* Metric */
[data-testid="metric-container"]{
  background:#0d1b2e !important;border-radius:10px !important;
  border:1px solid #1a2d45 !important;padding:10px !important;
}
[data-testid="metric-container"] label{color:#64748b !important;font-size:.7rem !important;}

/* XAI box */
.xai-box{
  background:#05122a;border:1px solid #1e3a5f;
  border-radius:12px;padding:16px;margin-top:10px;
}
.xai-title{color:#a78bfa;font-size:.78rem;font-weight:700;
  text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px;}
.xai-item{color:#c8d0e7;font-size:.78rem;padding:4px 0;
  border-bottom:1px solid #0d1b2e;}
.xai-item:last-child{border:none;}

/* Congestion note */
.congestion-note{
  background:rgba(251,191,36,.08);border:1px solid #92400e;
  border-radius:8px;padding:8px 12px;margin-bottom:10px;
  font-size:.76rem;color:#fbbf24;
}

/* Vision Zero */
.vz-box{
  background:#05122a;border:1px solid #1e3a5f;
  border-radius:8px;padding:10px 14px;margin-top:8px;
  font-size:.74rem;color:#94a3b8;
}
.vz-box b{color:#60a5fa;}

/* Info row */
.irow{display:flex;justify-content:space-between;padding:5px 0;
  border-bottom:1px solid #0a1628;font-size:.78rem;}
.irow:last-child{border:none;}
.irow-l{color:#64748b;}
.irow-v{color:#e2e8f0;font-weight:600;}

/* Probability bars */
.prob-wrap{margin:5px 0;}
.prob-lbl{display:flex;justify-content:space-between;
  font-size:.72rem;color:#64748b;margin-bottom:2px;}
.prob-track{background:#0a1628;border-radius:3px;height:7px;overflow:hidden;}
.prob-fill{height:100%;border-radius:3px;}

::-webkit-scrollbar{width:3px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:#1a2d45;border-radius:2px;}
</style>
""", unsafe_allow_html=True)

# ─── Color Constants ───────────────────────────────────────────────────────────
RISK_PALETTE = {
    'Aligned':                '#22c55e',
    'Moderate Misalignment':  '#eab308',
    'High Misalignment':      '#f97316',
    'Critical Misalignment':  '#ef4444',
}
HOTSPOT_PALETTE = {
    'Safe':          '#22c55e',
    'Moderate Risk': '#eab308',
    'High Risk':     '#f97316',
    'Severe Hotspot':'#ef4444',
}
RISK_ORDER    = ['Aligned','Moderate Misalignment','High Misalignment','Critical Misalignment']
HOTSPOT_ORDER = ['Safe','Moderate Risk','High Risk','Severe Hotspot']
BG = '#0d1b2e'

# ─── Loaders ──────────────────────────────────────────────────────────────────
CRASH_COLS  = ['crash_id','segment_id','severity','date','time','description']
HAZARD_COLS = ['hazard_id','segment_id','hazard_type','start_time','end_time',
               'date','temp_speed','description']

@st.cache_data
def load_all():
    df = pd.read_csv("unified_platform_data.csv")

    # Crash DB — guaranteed schema even if file is missing or empty
    try:
        crash_db = pd.read_csv("crash_database.csv")
        crash_db.columns = [c.lower().strip() for c in crash_db.columns]  # normalise capitalisation
        for col in CRASH_COLS:
            if col not in crash_db.columns:
                crash_db[col] = None
        crash_db = crash_db[CRASH_COLS]
    except Exception:
        crash_db = pd.DataFrame(columns=CRASH_COLS)

    # Hazard DB — guaranteed schema even if file is missing or empty
    try:
        hazard_db = pd.read_csv("hazard_database.csv")
        hazard_db.columns = [c.lower().strip() for c in hazard_db.columns]  # normalise capitalisation
        for col in HAZARD_COLS:
            if col not in hazard_db.columns:
                hazard_db[col] = None
        hazard_db = hazard_db[HAZARD_COLS]
    except Exception:
        hazard_db = pd.DataFrame(columns=HAZARD_COLS)

    metrics = pd.read_csv("model_metrics.csv")
    with open("ai_road_segments_unified.geojson") as f:
        gj = json.load(f)
    return df, crash_db, hazard_db, metrics, gj

@st.cache_resource
def load_models():
    try:
        # Runtime unpickle namespace alias hook for scikit-learn version mismatch in gb
        import sys
        import sklearn._loss
        import sklearn._loss.loss as l
        sys.modules['sklearn._loss'].CyHalfMultinomialLoss = l.CyHalfMultinomialLoss
        sys.modules['_loss'] = sys.modules['sklearn._loss']
        def reconstruct(cls, checksum, state):
            return l.CyHalfMultinomialLoss(n_classes=4)
        sys.modules['sklearn._loss'].__pyx_unpickle_CyHalfMultinomialLoss = reconstruct
        sys.modules['_loss'].__pyx_unpickle_CyHalfMultinomialLoss = reconstruct
    except Exception:
        pass

    try:
        rf = joblib.load("random_forest_model.pkl")
        gb = joblib.load("gradient_boosting_model.pkl")
        return rf, gb
    except Exception:
        return None, None

df, crash_db, hazard_db, metrics_df, geojson = load_all()
rf_model, gb_model = load_models()

# ─── Sidebar Date & Time Controls (defined early for calculations) ────────────
with st.sidebar:
    st.markdown("### ⚙️ Platform Controls")
    sel_date  = st.date_input("Assessment Date", value=date.today())
    time_opts = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0,30)]
    now_slot  = f"{datetime.now().hour:02d}:{'00' if datetime.now().minute < 30 else '30'}"
    sel_time  = st.selectbox("Time Slot", time_opts,
                              index=time_opts.index(now_slot) if now_slot in time_opts else 0)
    sel_hour  = int(sel_time.split(':')[0])

# ─── Helper utilities for crash/hazard calculations and persistence ───────────
def apply_school_zone_speed(row, base_speed, hour, weekday):
    schools_count = int(row.get('schools_count', 0)) if pd.notna(row.get('schools_count')) else 0
    is_sunday = (weekday == 6)
    if schools_count > 0 and not is_sunday:
        if 8 <= hour <= 16:
            final_speed = base_speed * 0.6
            return int(round(max(20.0, final_speed)))
    return base_speed

def save_crashes():
    st.session_state.crashes.to_csv("crash_database.csv", index=False)

def save_hazards():
    st.session_state.hazards.to_csv("hazard_database.csv", index=False)

def save_predictions():
    df.to_csv("unified_platform_data.csv", index=False)

def is_time_in_range(start, end, now_t):
    if start <= end:
        return start <= now_t <= end
    else: # Overnight range
        return now_t >= start or now_t <= end

def sync_segment_crashes(active_crashes_df):
    # Recalculate crash stats — VALIDATION-ONLY layer. Crash history no longer
    # feeds the ML risk-classification model (that model predicts whether the
    # *posted speed limit* is misaligned with road function/operating speed/
    # VRU exposure — a leading indicator — not whether crashes have already
    # happened, which is a lagging, behavior-confounded signal).
    df['crash_count'] = 0
    df['fatal_crashes'] = 0
    df['crash_risk_score'] = 0

    if not active_crashes_df.empty:
        
        minor_counts = active_crashes_df[
        active_crashes_df['severity'] == 'Minor'
        ].groupby('segment_id').size()

        major_counts = active_crashes_df[
            active_crashes_df['severity'] == 'Major'
        ].groupby('segment_id').size()

        fatal_counts = active_crashes_df[
            active_crashes_df['severity'] == 'Fatal'
        ].groupby('segment_id').size()

        df['minor_crashes'] = df['segment_id'].map(minor_counts).fillna(0).astype(int)
        df['major_crashes'] = df['segment_id'].map(major_counts).fillna(0).astype(int)
        df['fatal_crashes'] = df['segment_id'].map(fatal_counts).fillna(0).astype(int)

        df['crash_risk_score'] = (
            df['minor_crashes'] * 5
            + df['major_crashes'] * 20
            + df['fatal_crashes'] * 40
        ).clip(upper=100)
        df['blackspot_flag'] = ((df['crash_risk_score'] >= 50) | (df['fatal_crashes'] > 0)).map({True: 'Yes', False: 'No'})

    # Recalculate ML predictions (misalignment classifier), road_risk_score,
    # hotspot_score, and hotspot_category
    model = gb_model if (gb_model is not None) else rf_model
    if model is not None:
        try:
            X = df[FEATURES]   # crash_risk_score intentionally excluded — see note above
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

            # road_risk_score: severity-anchored expectation over class probabilities
            df['road_risk_score'] = (
                df['prob_low_risk'] * 10 +
                df['prob_medium_risk'] * 40 +
                df['prob_high_risk'] * 75 +
                df['prob_critical_risk'] * 100
            ).round().astype(int)

            # hotspot_score reframed: MISALIGNMENT is now the dominant weight
            # (50%); exposure 25%; crash history kept ONLY as a smaller,
            # secondary VALIDATION weight (15%); infrastructure deficit 10%.
            # The old 20% "speed_violation_score" (driver-behavior / compliance)
            # weight has been REMOVED — the challenge framing is explicit that
            # this is not about measuring whether drivers are speeding.
            df['hotspot_score'] = (
                0.40 * df['misalignment_score'] +
                0.25 * df['exposure_score'] +
                0.25 * df['crash_risk_score'] +
                0.10 * (100 - df['infrastructure_score'])
            ).round(1)

            # Map hotspot_score to hotspot_category
            def get_hotspot_cat(score):
                if score >= 75: return 'Severe Hotspot'
                if score >= 50: return 'High Risk'
                if score >= 25: return 'Moderate Risk'
                return 'Safe'
            df['hotspot_category'] = df['hotspot_score'].apply(get_hotspot_cat)

            # recommended_safe_speed now genuinely tied to the misalignment
            # logic: lower of observed 85th-percentile operating speed and
            # the Safe System human_tolerance_limit for this road's function/
            # VRU mix (fixes the old disconnect between speed output and risk
            # scoring).
            df['ai_recommended_speed'] = np.minimum(df['speed_p85'], df['human_tolerance_limit']).round().astype(int)
            if 'original_safe_speed' not in df.columns:
                df['original_safe_speed'] = df['ai_recommended_speed']
            
            df['recommended_safe_speed'] = (
                df['ai_recommended_speed']
                - (df['crash_risk_score'] / 5)
            ).clip(lower=20).round().astype(int)

            df['speed_safety_score'] = (100 - (df['misalignment_score']*0.6 +
                                                df['crash_risk_score']*0.2 +
                                                (100 - df['infrastructure_score'])*0.2)).clip(0, 100).round(1)

        except Exception as e:
            pass

def fill_missing_hazard_speeds():
    if not st.session_state.hazards.empty:
        updated = False
        for idx, row in st.session_state.hazards.iterrows():
            if pd.isna(row.get('temp_speed')) or row.get('temp_speed') == '' or row.get('temp_speed') is None:
                try:
                    seg_id = int(row['segment_id'])
                    r_type = df[df['segment_id'] == seg_id]['road_type'].iloc[0]
                except Exception:
                    r_type = ""
                default_spd = 60 if r_type == "Highway" else 40 if r_type == "Arterial" else 30
                st.session_state.hazards.at[idx, 'temp_speed'] = default_spd
                updated = True
        if updated:
            save_hazards()

def apply_dynamic_hazard_speeds():
    # Keep original recommended_safe_speed
    if 'original_safe_speed' not in df.columns:
        df['original_safe_speed'] = df['recommended_safe_speed'].copy()
    
    df['recommended_safe_speed'] = (
        df['ai_recommended_speed']
        - (df['crash_risk_score'] / 5)
    ).clip(lower=20).round().astype(int)
    
    for _, hz in st.session_state.hazards.iterrows():
        try:
            hz_date = pd.to_datetime(hz['date']).date()
            if hz_date != sel_date:
                continue
            start = datetime.strptime(str(hz['start_time']), "%H:%M").time()
            end   = datetime.strptime(str(hz['end_time']),   "%H:%M").time()
            now_t = datetime.strptime(sel_time,              "%H:%M").time()
            
            if is_time_in_range(start, end, now_t):
                sid = int(hz['segment_id'])
                spd = hz.get('temp_speed')
                if pd.isna(spd) or not spd:
                    try:
                        r_type = df[df['segment_id'] == sid]['road_type'].iloc[0]
                    except Exception:
                        r_type = ""
                    spd = 60 if r_type == "Highway" else 40 if r_type == "Arterial" else 30
                df.loc[df['segment_id'] == sid, 'recommended_safe_speed'] = int(spd)
        except Exception:
            continue

FEATURES = ['road_function_score','infrastructure_score','exposure_score',
            'human_tolerance_limit','operating_speed_score']
# NOTE: crash_risk_score deliberately excluded — see sync_segment_crashes()

# ── Crash auto-expiry helper (dynamically filters crashes for the selected date) ─
def get_active_crashes(crashes_df, assessment_date):
    if crashes_df.empty:
        return crashes_df.copy()
    def _active(row):
        try:
            crash_date = pd.to_datetime(row['date']).date()
            days_since = (assessment_date - crash_date).days
            if days_since < 0:
                return False
            limit = 60 if row['severity'] == 'Minor' else 80
            return days_since <= limit
        except Exception:
            return False
    mask = crashes_df.apply(_active, axis=1)
    return crashes_df[mask].reset_index(drop=True)

# ── Hazard auto-expiry helper (removes past hazards from database on startup) ─
def apply_hazard_expiry(hazards_df):
    if hazards_df.empty:
        return hazards_df.copy()
    today = date.today()
    now_time = datetime.now().time()
    def _expired(row):
        try:
            hz_date = pd.to_datetime(row['date']).date()
            if hz_date < today:
                return True
            if hz_date == today:
                end_time = datetime.strptime(str(row['end_time']), "%H:%M").time()
                return end_time < now_time
            return False
        except Exception:
            return False
    mask = hazards_df.apply(_expired, axis=1)
    return hazards_df[~mask].reset_index(drop=True)

# ── Session state for dynamic crash/hazard management ─────────────────────────
# Always validate schema — reset from disk if columns are missing (handles stale session state)
def _valid_df(df_ss, required_cols):
    """Return True if df has all required columns and at least 0 rows."""
    return isinstance(df_ss, pd.DataFrame) and all(c in df_ss.columns for c in required_cols)

if 'crashes' not in st.session_state or not _valid_df(st.session_state.crashes, CRASH_COLS):
    st.session_state.crashes = crash_db.copy()
if 'hazards' not in st.session_state or not _valid_df(st.session_state.hazards, HAZARD_COLS):
    st.session_state.hazards = hazard_db.copy()

# Belt-and-suspenders: add any still-missing columns without wiping data
for _col in CRASH_COLS:
    if _col not in st.session_state.crashes.columns:
        st.session_state.crashes[_col] = None
for _col in HAZARD_COLS:
    if _col not in st.session_state.hazards.columns:
        st.session_state.hazards[_col] = None

# Fill missing hazard speeds with defaults, expire past ones, and save to disk
fill_missing_hazard_speeds()
st.session_state.hazards = apply_hazard_expiry(st.session_state.hazards)
save_hazards()

if 'next_crash_id' not in st.session_state:
    _max_cid = st.session_state.crashes['crash_id'].dropna()
    st.session_state.next_crash_id = (int(_max_cid.max()) + 1) if len(_max_cid) else 1
if 'next_hazard_id' not in st.session_state:
    _max_hid = st.session_state.hazards['hazard_id'].dropna()
    st.session_state.next_hazard_id = (int(_max_hid.max()) + 1) if len(_max_hid) else 1

active_crashes = get_active_crashes(st.session_state.crashes, sel_date)
sync_segment_crashes(active_crashes)

# ── Active hazard helper: only hazards whose date matches AND time is in window ─
def get_active_hazard_segs(hazards_df, check_date, check_time_str):
    """Return set of segment_ids with a currently active hazard."""
    active = set()
    for _, hz in hazards_df.iterrows():
        try:
            hz_date = pd.to_datetime(hz['date']).date()
            if hz_date != check_date:
                continue
            start = datetime.strptime(str(hz['start_time']), "%H:%M").time()
            end   = datetime.strptime(str(hz['end_time']),   "%H:%M").time()
            now_t = datetime.strptime(check_time_str,         "%H:%M").time()
            if is_time_in_range(start, end, now_t):
                active.add(int(hz['segment_id']))
        except Exception:
            continue
    return active

# ── Hazard temp_speed lookup for a segment ────────────────────────────────────
def get_hazard_temp_speed(hazards_df, segment_id, check_date, check_time_str):
    """Return temp_speed (int) if an active hazard has one, else None."""
    for _, hz in hazards_df.iterrows():
        try:
            if int(hz['segment_id']) != segment_id:
                continue
            hz_date = pd.to_datetime(hz['date']).date()
            if hz_date != check_date:
                continue
            start = datetime.strptime(str(hz['start_time']), "%H:%M").time()
            end   = datetime.strptime(str(hz['end_time']),   "%H:%M").time()
            now_t = datetime.strptime(check_time_str,         "%H:%M").time()
            if is_time_in_range(start, end, now_t):
                spd = hz.get('temp_speed')
                if pd.notna(spd) and spd:
                    return int(spd)
                else:
                    # Fallback to road-type default
                    try:
                        r_type = df[df['segment_id'] == segment_id]['road_type'].iloc[0]
                    except Exception:
                        r_type = ""
                    return 60 if r_type == "Highway" else 40 if r_type == "Arterial" else 30
        except Exception:
            continue
    return None

# (CSV Persistence helpers moved to top)


def score_color(v, invert=False):
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
    base     = float(row.get('exposure_score', 50))
    schools  = int(row.get('schools_count', 0))
    rt       = str(row.get('road_type', ''))
    school_m = 1.5 if (8 <= hour <= 16 and schools > 0) else 0.8
    peak_m   = 1.4 if (7 <= hour <= 9 or 17 <= hour <= 20) else 1.0
    night_m  = 0.4 if (hour >= 23 or hour <= 5) else 1.0
    urb      = str(row.get('urban_rural_flag', ''))
    market_m = 1.3 if (urb == 'Urban' and (9 <= hour <= 20)) else 1.0
    return min(100, base * school_m * peak_m * night_m * market_m)

def build_factors(row, hour=None):
    factors = []
    exp  = float(row.get('exposure_score', 0))
    crash= float(row.get('crash_risk_score', 0))
    inf  = float(row.get('infrastructure_score', 100))
    func = float(row.get('road_function_score', 0))
    ped  = float(row.get('pedestrian_exposure_score', 0))
    sc   = int(row.get('schools_count', 0))
    blk  = str(row.get('blackspot_flag', ''))
    fc   = int(row.get('fatal_crashes', 0))
    if ped > 40 or exp > 60: factors.append(('High Pedestrian Exposure', 'high'))
    if sc > 0:               factors.append(('School Zone Active', 'high'))
    if crash > 70:           factors.append(('High Crash History', 'high'))
    if fc > 0:               factors.append(('Fatal Crashes Recorded', 'high'))
    if blk == 'Yes':         factors.append(('Accident Blackspot', 'high'))
    if inf < 40:             factors.append(('Poor Infrastructure Safety', 'high'))
    if inf < 30:             factors.append(('Missing Sidewalks / Crosswalks', 'high'))
    if func > 70:            factors.append(('High Road Function Complexity', 'med'))
    if exp > 40:             factors.append(('High Activity Zone Nearby', 'med'))
    if hour and (7 <= hour <= 9 or 17 <= hour <= 20):
        factors.append(('Peak Hour Traffic', 'med'))
    if hour and (8 <= hour <= 16 and sc > 0):
        factors.append(('School Hours — Children Present', 'high'))
    return factors if factors else [('Meets General Safety Standards', 'low')]

def sbar(label, val, color, max_val=100):
    pct = min(100, max(0, float(val) / max_val * 100))
    return (f'<div class="sbar"><div class="sbar-lbl"><span>{label}</span>'
            f'<span style="color:{color}">{float(val):.0f}</span></div>'
            f'<div class="sbar-track"><div class="sbar-fill" '
            f'style="width:{pct:.1f}%;background:{color}"></div></div></div>')

def irow(label, val, color='#e2e8f0'):
    return (f'<div class="irow"><span class="irow-l">{label}</span>'
            f'<span class="irow-v" style="color:{color}">{val}</span></div>')

def prob_bar(label, val, color):
    pct = min(100, max(0, float(val) * 100))
    return (f'<div class="prob-wrap"><div class="prob-lbl"><span>{label}</span>'
            f'<span style="color:{color}">{pct:.1f}%</span></div>'
            f'<div class="prob-track"><div class="prob-fill" '
            f'style="width:{pct:.1f}%;background:{color}"></div></div></div>')

# ─── Topbar ───────────────────────────────────────────────────────────────────
now_str = datetime.now().strftime("%H:%M:%S")
best_model = metrics_df.sort_values('f1', ascending=False).iloc[0]

st.markdown(f"""
<div class="topbar">
  <div class="topbar-brand">
    <div class="topbar-dot"></div>
    AI Road Safety Platform
  </div>
  <div class="topbar-tag">Safe Speed Assessment</div>
  <div class="topbar-city">🏙️ Bangalore, Karnataka</div>
  <div class="topbar-right">
    <span class="topbar-time">{now_str}</span>
    <span class="live-badge">● LIVE</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    st.markdown("### 🔍 Filters")
    road_types = ["All"] + sorted(df["road_type"].unique())
    sel_rt     = st.selectbox("Road Type", road_types)

    risk_cats  = ["All"] + RISK_ORDER
    sel_risk   = st.selectbox("AI Risk Category", risk_cats)

    hotspot_cats = ["All"] + HOTSPOT_ORDER
    sel_hotspot  = st.selectbox("Hotspot Category", hotspot_cats)

    crash_sev = ["All", "Fatal", "Major", "Minor"]
    sel_crash_sev = st.selectbox("Crash Severity Filter", crash_sev)

    speed_min, speed_max = int(df["posted_speed_limit"].min()), int(df["posted_speed_limit"].max())
    sel_speed = st.slider("Posted Speed (km/h)", speed_min, speed_max, (speed_min, speed_max))

    st.markdown("---")
    st.markdown("### 🗺️ Map Options")
    map_mode  = st.selectbox("Map View", ["Risk Score","Hotspot Score","Road Type","Speed Limit"])
    tile_opt  = st.selectbox("Base Map", ["Dark","Street","Satellite"])
    line_w    = st.slider("Line Width", 2, 8, 4)
    st.session_state['map_render_cap'] = st.slider(
        "Max segments rendered on map", 200, 5000, 1500, step=100,
        help="Caps how many segments are drawn on the map for browser performance "
             "(the network has ~5,000 segments total). Highest-priority segments "
             "by hotspot score are always shown first. The Data Table tab and CSV "
             "downloads always include every segment regardless of this setting.")

    st.markdown("---")
    st.markdown("### 🤖 Active Model")
    st.markdown(
        f'<div style="background:#0d1b2e;border-radius:8px;padding:10px;border:1px solid #1a2d45">'
        f'<div style="color:#a78bfa;font-weight:700;font-size:.85rem">{best_model["model"]}</div>'
        f'<div style="color:#64748b;font-size:.72rem;margin-top:4px">'
        f'Accuracy: <span style="color:#22c55e">{best_model["accuracy"]:.1%}</span> &nbsp;|&nbsp; '
        f'F1: <span style="color:#60a5fa">{best_model["f1"]:.1%}</span></div></div>',
        unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📌 Legend")
    for lbl, clr in RISK_PALETTE.items():
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
            f'<div style="width:20px;height:4px;background:{clr};border-radius:2px"></div>'
            f'<span style="color:#94a3b8;font-size:.76rem">{lbl}</span></div>',
            unsafe_allow_html=True)

# ─── Apply Filters ─────────────────────────────────────────────────────────────
apply_dynamic_hazard_speeds()
df['final_safe_speed'] = df.apply(
    lambda r: apply_school_zone_speed(r, r['recommended_safe_speed'], sel_hour, sel_date.weekday()),
    axis=1
)
df_f = df.copy()
if sel_rt      != "All": df_f = df_f[df_f["road_type"]       == sel_rt]
if sel_risk    != "All": df_f = df_f[df_f["ai_risk_label"]   == sel_risk]
if sel_hotspot != "All": df_f = df_f[df_f["hotspot_category"]== sel_hotspot]
df_f = df_f[(df_f["posted_speed_limit"] >= sel_speed[0]) & (df_f["posted_speed_limit"] <= sel_speed[1])]
filt_ids = set(df_f["segment_id"].tolist())

# Recompute temporal exposure for current hour
df_f = df_f.copy()
df_f['temporal_exposure'] = df_f.apply(lambda r: temporal_exposure(r, sel_hour), axis=1)

# ─── KPI Row ──────────────────────────────────────────────────────────────────
crashes_st = active_crashes
n_minor = n_major = n_fatal = 0
n_total = 0
if isinstance(crashes_st, pd.DataFrame):
    # If the column exists, compute counts; otherwise fallback to zero
    if 'severity' in crashes_st.columns:
        try:
            n_minor  = int((crashes_st['severity'] == 'Minor').sum())
            n_major  = int((crashes_st['severity'] == 'Major').sum())
            n_fatal  = int((crashes_st['severity'] == 'Fatal').sum())
        except Exception:
            n_minor = n_major = n_fatal = 0
    n_total = len(crashes_st)
n_hotspot= int((df['hotspot_category']=='Severe Hotspot').sum())
n_high   = int((df_f['ai_risk_label']=='High Misalignment').sum())
n_crit   = int((df_f['ai_risk_label']=='Critical Misalignment').sum())
n_congested = int(df_f['congestion_category'].isin(['Moderate','Severe']).sum()) if 'congestion_category' in df_f.columns else 0
avg_spd  = int(df_f['final_safe_speed'].mean()) if len(df_f) and 'final_safe_speed' in df_f.columns else (int(df_f['recommended_safe_speed'].mean()) if len(df_f) else 0)
avg_exp  = int(df_f['temporal_exposure'].mean()) if len(df_f) else 0
avg_risk = int(df_f['road_risk_score'].mean()) if len(df_f) else 0

cols = st.columns(11)
kpis = [
    (len(df_f),  "Segments",       "sky"),
    (n_minor,    "Minor Crashes",  "green"),
    (n_major,    "Major Crashes",  "yellow"),
    (n_fatal,    "Fatal Crashes",  "red"),
    (n_total,    "Total Crashes",  "orange"),
    (n_hotspot,  "Severe Hotspots","red"),
    (n_high,     "High Misalignment Roads","orange"),
    (n_congested,"Congested Now",  "yellow"),
    (f"{avg_spd} km/h","Avg Safe Speed","blue"),
    (avg_exp,    "Avg Exposure",   "purple"),
    (avg_risk,   "Avg Risk Score", "pink"),
]
for col, (val, lbl, cls) in zip(cols, kpis):
    col.markdown(
        f'<div class="kpi"><div class="kpi-v {cls}">{val}</div>'
        f'<div class="kpi-l">{lbl}</div></div>',
        unsafe_allow_html=True)

# ─── TABS ─────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "🗺️ Interactive Map",
    "🔴 Hotspot Analysis",
    "📊 ML Model Evaluation",
    "🤖 Explainable AI",
    "🚨 Crash Management",
    "⚠️ Hazard Management",
    "📈 Advanced Analytics",
    "📂 Data Table",
])
tab_map, tab_hot, tab_model, tab_xai, tab_crash, tab_hazard, tab_analytics, tab_data = tabs

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — INTERACTIVE MAP
# ══════════════════════════════════════════════════════════════════════════════
with tab_map:
    if not FOLIUM_OK:
        st.warning("Install `folium` and `streamlit-folium` to enable the interactive map.")
        st.code("pip install folium streamlit-folium")
        st.stop()

    map_col, detail_col = st.columns([3, 1.15])

    tile_urls = {
        "Dark":      "CartoDB dark_matter",
        "Street":    "OpenStreetMap",
        "Satellite": "Esri.WorldImagery",
    }

    with map_col:
        m = folium.Map(location=[12.97, 77.59], zoom_start=11,
                       tiles=tile_urls.get(tile_opt,"CartoDB dark_matter"),
                       attr="© OpenStreetMap", prefer_canvas=True)

        # Active hazard set — only hazards matching selected date AND time window
        active_hazard_segs = get_active_hazard_segs(
            st.session_state.hazards, sel_date, sel_time)

        # Auto-fit the view to the full filtered network extent (computed
        # before the render cap below, so the view always reflects the
        # full filtered set even if only a subset is drawn).
        if not df_f.empty:
            lats = pd.concat([df_f['start_lat'], df_f['end_lat']])
            lons = pd.concat([df_f['start_lon'], df_f['end_lon']])
            m.fit_bounds([[lats.min(), lons.min()], [lats.max(), lons.max()]])

        # PERFORMANCE: the network now has ~5,000 segments. Leaflet (the
        # browser map library) becomes very slow/unresponsive with that many
        # individual PolyLine layers + full HTML popups — this is the real
        # cause of "few segments shown" (most are loaded but the browser
        # struggles to render/paint them). Two fixes:
        #   1. O(1) dict lookup instead of a per-feature dataframe scan
        #      (was up to ~25M row comparisons building the map).
        #   2. A render cap, prioritized by hotspot_score descending, so the
        #      most important segments are always the ones actually drawn.
        row_lookup = df.set_index('segment_id').to_dict('index')

        MAX_RENDER = st.session_state.get('map_render_cap', 1500)
        render_ids = filt_ids
        if len(filt_ids) > MAX_RENDER:
            priority_ids = (df_f.sort_values('hotspot_score', ascending=False)
                             ['segment_id'].head(MAX_RENDER).tolist())
            render_ids = set(priority_ids)
            st.warning(
                f"Showing the {MAX_RENDER:,} highest-priority segments (by hotspot score) "
                f"out of {len(filt_ids):,} matching your filters — full browser rendering of "
                f"all segments at once is impractical. Narrow the filters (Road Type / Risk / "
                f"Hotspot / Speed range) to see a different subset, or raise the cap in the "
                f"sidebar 'Map Options'.")

        for feat in geojson["features"]:
            sid = int(feat["properties"]["segment_id"])
            if sid not in render_ids:
                continue
            p   = feat["properties"]
            row = row_lookup.get(sid)
            if row is not None:
                p.update(row)

            rc  = p.get("ai_risk_label","Moderate Misalignment")
            hsc = p.get("hotspot_category","Moderate Risk")

            if map_mode == "Risk Score":
                color = RISK_PALETTE.get(rc, '#eab308')
            elif map_mode == "Hotspot Score":
                color = HOTSPOT_PALETTE.get(hsc, '#f97316')
            elif map_mode == "Road Type":
                type_colors = {
                    'Highway':   '#facc15',
                    'Arterial':  '#fb923c',
                    'Collector': '#60a5fa',
                    'Local':     '#34d399',
                }
                color = type_colors.get(p.get('road_type',''), '#94a3b8')
            else:  # Speed Limit
                spd = int(p.get('posted_speed_limit',60))
                if spd >= 100: color = '#facc15'
                elif spd >= 60: color = '#fb923c'
                elif spd >= 40: color = '#60a5fa'
                else: color = '#34d399'

            # Hazard override — add glow
            has_hazard = sid in active_hazard_segs
            weight = line_w + (2 if rc in ['Critical Misalignment','Severe Hotspot'] else 0)

            hz_temp_spd_map = get_hazard_temp_speed(st.session_state.hazards, sid, sel_date, sel_time)
            if has_hazard and hz_temp_spd_map:
                hazard_banner = f'<div style="margin-top:8px;padding:6px 8px;background:#4c0519;border-radius:5px;font-size:.7rem;color:#f87171;font-weight:700">⚠️ ACTIVE HAZARD — TEMP SPEED: {hz_temp_spd_map} km/h</div>'
                speed_calc_note = f"Temporary speed limit override due to active hazard: {hz_temp_spd_map} km/h"
            else:
                hazard_banner = ''
                speed_calc_note = f"Vision Zero: min(AI={p.get('ai_recommended_speed',p.get('final_safe_speed', p['recommended_safe_speed']))} km/h, Tolerance={p.get('human_tolerance_limit',70):.0f} km/h) → {p.get('final_safe_speed', p['recommended_safe_speed'])} km/h"

            popup_html = f"""
            <div style="font-family:system-ui;min-width:260px;background:#0d1b2e;
                 color:#e2e8f0;padding:14px;border-radius:10px;border:1px solid #1a2d45">
              <div style="font-size:1.1rem;font-weight:700;color:#60a5fa">
                {p.get('human_segment_id','—')} &nbsp;<span style="font-size:.75rem;color:#94a3b8">#{sid}</span>
              </div>
              <div style="font-size:.82rem;color:#94a3b8;margin-top:2px">{p['road_name']}</div>
              <div style="font-size:.7rem;color:#64748b">{p['road_type']}</div>
              <hr style="border-color:#1a2d45;margin:8px 0">
              <table style="width:100%;font-size:.78rem;border-collapse:collapse">
                <tr><td style="color:#64748b;padding:2px 0">Posted Limit</td>
                    <td style="color:#fbbf24;font-weight:700">{p['posted_speed_limit']} km/h</td></tr>
                <tr><td style="color:#64748b">AI Safe Speed</td>
                    <td style="color:#22c55e;font-weight:700">{p.get('final_safe_speed', p['recommended_safe_speed'])} km/h</td></tr>
                <tr><td style="color:#64748b">Risk Category</td>
                    <td style="color:{color};font-weight:700">{rc}</td></tr>
                <tr><td style="color:#64748b">Risk Probability</td>
                    <td style="color:{color}">{p['ai_risk_probability']*100:.1f}%</td></tr>
                <tr><td style="color:#64748b">Risk Score</td>
                    <td><b>{p['road_risk_score']}/100</b></td></tr>
                <tr><td style="color:#64748b">Hotspot Score</td>
                    <td style="color:{HOTSPOT_PALETTE.get(hsc,'#f97316')}">{p.get('hotspot_score',0):.0f} — {hsc}</td></tr>
                <tr><td style="color:#64748b">Infrastructure</td>
                    <td>{p['infrastructure_score']:.0f}/100</td></tr>
                <tr><td style="color:#64748b">Exposure</td>
                    <td>{p['exposure_score']:.0f}/100</td></tr>
                <tr><td style="color:#64748b">Crash Risk</td>
                    <td>{p['crash_risk_score']:.0f}/100</td></tr>
                <tr><td style="color:#64748b">Blackspot</td>
                    <td style="color:{'#f87171' if p.get('blackspot_flag')=='Yes' else '#64748b'}">{p.get('blackspot_flag','—')}</td></tr>
                <tr><td style="color:#64748b">Fatal Crashes</td>
                    <td style="color:{'#ef4444' if int(p.get('fatal_crashes',0))>0 else '#e2e8f0'}">{p.get('fatal_crashes',0)}</td></tr>
              </table>
              {hazard_banner}
              <div style="margin-top:8px;padding:6px 8px;background:#030a1a;border-radius:6px;font-size:.7rem;color:#a78bfa">
                🤖 {p.get('top_ai_factors','—')}
              </div>
              <div style="margin-top:6px;font-size:.67rem;color:#1a2d45">
                {speed_calc_note}
              </div>
            </div>"""

            tooltip = (f"{p.get('human_segment_id','')}: {p['road_name']} | "
                       f"Safe: {p.get('final_safe_speed', p['recommended_safe_speed'])} km/h | "
                       f"Risk: {p['road_risk_score']:.0f}")

            if has_hazard:
                folium.PolyLine(
                    [[c[1],c[0]] for c in feat['geometry']['coordinates']],
                    color='#fbbf24', weight=weight+3, opacity=0.3
                ).add_to(m)

            folium.PolyLine(
                [[c[1],c[0]] for c in feat['geometry']['coordinates']],
                color=color, weight=weight, opacity=0.88,
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=folium.Tooltip(tooltip, sticky=True),
            ).add_to(m)

        # Map legend
        legend_items = (RISK_PALETTE if map_mode=="Risk Score" else
                        HOTSPOT_PALETTE if map_mode=="Hotspot Score" else
                        {'Highway':'#facc15','Arterial':'#fb923c',
                         'Collector':'#60a5fa','Local':'#34d399'} if map_mode=="Road Type" else
                        {'100 km/h':'#facc15','60 km/h':'#fb923c','40 km/h':'#60a5fa','<40 km/h':'#34d399'})
        legend_html = (
            '<div style="position:fixed;bottom:26px;right:10px;z-index:1000;'
            'background:#0d1b2e;border:1px solid #1a2d45;border-radius:10px;'
            'padding:12px 16px;font-family:system-ui;box-shadow:0 4px 20px rgba(0,0,0,.6)">'
            f'<div style="color:#e2e8f0;font-size:.78rem;font-weight:700;margin-bottom:8px">{map_mode}</div>'
            + "".join(
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:5px">'
                f'<div style="width:22px;height:4px;background:{c};border-radius:2px"></div>'
                f'<span style="color:#94a3b8;font-size:.72rem">{l}</span></div>'
                for l, c in legend_items.items()
            ) + '</div>')
        m.get_root().html.add_child(folium.Element(legend_html))

        map_data = st_folium(m, height=560, width="100%",
                              returned_objects=["last_object_clicked_tooltip"],
                              key="main_map")

        # Quick analytics under map
        st.markdown("---")
        qc1, qc2, qc3, qc4 = st.columns(4)
        for col_w, (title, fig_fn) in zip([qc1,qc2,qc3,qc4],[
            ("Risk Distribution", lambda: px.bar(
                df_f["ai_risk_label"].value_counts().reindex(RISK_ORDER).fillna(0).reset_index()
                   .rename(columns={"ai_risk_label":"Risk","count":"Count"}),
                x="Risk", y="Count", color="Risk",
                color_discrete_map=RISK_PALETTE, template="plotly_dark")),
            ("Hotspot Distribution", lambda: px.pie(
                df_f["hotspot_category"].value_counts().reset_index()
                   .rename(columns={"hotspot_category":"Category","count":"Count"}),
                names="Category", values="Count",
                color="Category", color_discrete_map=HOTSPOT_PALETTE,
                template="plotly_dark")),
            ("Safe Speed Distribution", lambda: px.histogram(
                df_f, x="final_safe_speed" if "final_safe_speed" in df_f.columns else "recommended_safe_speed", nbins=12,
                color_discrete_sequence=["#a78bfa"], template="plotly_dark")),
            ("Top 10 Risk Segments", lambda: px.bar(
                df_f.nlargest(10,"road_risk_score")[["road_name","road_risk_score","ai_risk_label"]]
                   .assign(short=lambda x: x["road_name"].str[:16]+"…"),
                x="road_risk_score", y="short", orientation="h",
                color="ai_risk_label", color_discrete_map=RISK_PALETTE,
                template="plotly_dark")),
        ]):
            with col_w:
                st.markdown(f'<div class="chart-title">{title}</div>', unsafe_allow_html=True)
                fig = fig_fn()
                fig.update_layout(height=220, margin=dict(t=10,b=0,l=0,r=0),
                                   paper_bgcolor=BG, plot_bgcolor=BG, showlegend=False,
                                   xaxis=dict(color='#64748b',tickfont=dict(size=7)),
                                   yaxis=dict(color='#64748b',tickfont=dict(size=7),autorange="reversed"))
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})

    # ── Detail Panel ──────────────────────────────────────────────────────────
    with detail_col:
        st.markdown("#### 📋 Segment Detail")
        clicked_tt = (map_data or {}).get("last_object_clicked_tooltip","")
        seg_opts   = df_f.apply(
            lambda r: f"{r['human_segment_id']} — {r['road_name']}", axis=1).tolist()

        # Try to auto-select from map click
        default_idx = 0
        if clicked_tt and " | " in clicked_tt:
            clicked_name = clicked_tt.split(":")[1].split("|")[0].strip() if ":" in clicked_tt else ""
            for i, opt in enumerate(seg_opts):
                if clicked_name and clicked_name[:10] in opt:
                    default_idx = i
                    break

        if not seg_opts:
            st.warning("No segments match filters.")
        else:
            sel_seg_label = st.selectbox("Segment", seg_opts,
                                          index=default_idx, label_visibility="collapsed")
            sel_seg_id = df_f[
                df_f.apply(lambda r: f"{r['human_segment_id']} — {r['road_name']}"==sel_seg_label, axis=1)
            ]['segment_id'].iloc[0]
            r = df_f[df_f['segment_id']==sel_seg_id].iloc[0]

            rc     = r['ai_risk_label']
            rc_col = RISK_PALETTE.get(rc,'#eab308')
            hc     = r['hotspot_category']
            hc_col = HOTSPOT_PALETTE.get(hc,'#f97316')
            is_bs  = str(r.get('blackspot_flag','')) == 'Yes'
            temp_exp = temporal_exposure(r, sel_hour)
            has_hz = int(r['segment_id']) in get_active_hazard_segs(
                st.session_state.hazards, sel_date, sel_time)

            # Segment header
            type_badge_colors = {
                'Highway':   ('rgba(250,204,21,.15)','#facc15'),
                'Arterial':  ('rgba(251,146,60,.15)', '#fb923c'),
                'Collector': ('rgba(96,165,250,.15)', '#60a5fa'),
                'Local':     ('rgba(52,211,153,.15)', '#34d399'),
            }
            tbg, tcol = type_badge_colors.get(r['road_type'],('rgba(148,163,184,.15)','#94a3b8'))

            st.markdown(f"""
            <div class="seg-header">
              <div class="seg-id">{r['human_segment_id']}</div>
              <div class="seg-name">{r['road_name']}</div>
              <span class="seg-type" style="background:{tbg};color:{tcol}">{r['road_type']}</span>
            </div>""", unsafe_allow_html=True)

            if is_bs:
                st.markdown(
                    '<div class="bs-banner"><div class="bs-dot"></div>ACCIDENT BLACKSPOT</div>',
                    unsafe_allow_html=True)
            if has_hz:
                hz_temp_spd = get_hazard_temp_speed(
                    st.session_state.hazards, int(r['segment_id']), sel_date, sel_time)
                if hz_temp_spd and hz_temp_spd > 0:
                    st.markdown(
                        f'<div class="congestion-note">⚠️ Active hazard — temporary speed limit: <b>{hz_temp_spd} km/h</b></div>',
                        unsafe_allow_html=True)
            else:
                hz_temp_spd = None

            # Speed card — temp_speed overrides recommended_safe_speed when active
            ai_spd  = int(r.get('ai_recommended_speed', r.get('final_safe_speed', r['recommended_safe_speed'])))
            rec_spd = hz_temp_spd if hz_temp_spd else int(r.get('final_safe_speed', r['recommended_safe_speed']))
            posted  = int(r['posted_speed_limit'])
            tol     = int(r.get('human_tolerance_limit', 70))

            speed_title = "Recommended Safe Speed (Hazard Override)" if hz_temp_spd else "Recommended Safe Speed"
            card_style = "style='border: 2px solid #fbbf24; background: #18150a;'" if hz_temp_spd else ""

            st.markdown(f"""
            <div class="speed-card" {card_style}>
              <div style="font-size:.67rem;color:{'#fbbf24' if hz_temp_spd else '#64748b'};text-transform:uppercase;
                   letter-spacing:.08em;margin-bottom:4px">{speed_title}</div>
              <div class="speed-main" style="color:{'#fbbf24' if hz_temp_spd else '#60a5fa'}">{rec_spd}</div>
              <div class="speed-unit">km/h</div>
              <div class="speed-range">AI Engine: {ai_spd} km/h &nbsp;|&nbsp; VZ Tolerance: {tol} km/h</div>
              <div class="speed-posted">Posted: <span style="color:#fbbf24">{posted} km/h</span></div>
            </div>""", unsafe_allow_html=True)

            # Scores
            congestion_pct = float(r.get('congestion_index', 0)) * 100
            st.markdown(f"""
            <div class="panel">
              <h4>📊 Score Profile</h4>
              {sbar("Road Risk Score",      r['road_risk_score'],      score_color(r['road_risk_score'],True))}
              {sbar("AI Risk Probability",  r['ai_risk_probability']*100, rc_col)}
              {sbar("Hotspot Score",        r['hotspot_score'],        hc_col)}
              {sbar("Exposure (Now)",       temp_exp,                  score_color(temp_exp, True))}
              {sbar("Infrastructure",       r['infrastructure_score'], score_color(r['infrastructure_score']))}
              {sbar("Crash Risk",           r['crash_risk_score'],     score_color(r['crash_risk_score'],True))}
              {sbar("Road Function",        r['road_function_score'],  '#a78bfa')}
              {sbar("Speed Safety",         r.get('speed_safety_score', 50), score_color(r.get('speed_safety_score',50)))}
              {sbar("Congestion Index",     congestion_pct,             score_color(congestion_pct, True))}
            </div>""", unsafe_allow_html=True)
            if str(r.get('congestion_category','None')) in ('Moderate','Severe'):
                st.markdown(
                    f'<div class="congestion-note">🚦 {r["congestion_category"]} congestion detected — '
                    f'recommended speed adjusted to observed conditions '
                    f'({r["operating_speed_mean"]:.0f} km/h actual vs {r["posted_speed_limit"]} km/h posted).</div>',
                    unsafe_allow_html=True)
            elif bool(r.get('congestion_smoothed', False)):
                st.markdown(
                    '<div class="congestion-note">↘️ Speed tapered in advance of congestion on the next segment '
                    'along this corridor.</div>', unsafe_allow_html=True)

            # Segment info
            seg_crashes = active_crashes[
                active_crashes['segment_id']==int(r['segment_id'])]
            n_sc_minor = int((seg_crashes['severity']=='Minor').sum())
            n_sc_major = int((seg_crashes['severity']=='Major').sum())
            n_sc_fatal = int((seg_crashes['severity']=='Fatal').sum())

            st.markdown(f"""
            <div class="panel">
              <h4>📍 Segment Info</h4>
              {irow("Segment ID",     f"#{int(r['segment_id'])} ({r['human_segment_id']})")}
              {irow("Start KM",       f"{r['start_km']:.1f} km")}
              {irow("End KM",         f"{r['end_km']:.1f} km")}
              {irow("Risk Category",  rc, rc_col)}
              {irow("Hotspot",        hc, hc_col)}
              {irow("Exposure Tier",  str(r.get('exposure_tier','—')))}
              {irow("Schools Nearby", str(int(r.get('schools_count',0))))}
              {irow("Minor Crashes",  str(n_sc_minor), '#22c55e')}
              {irow("Major Crashes",  str(n_sc_major), '#f97316')}
              {irow("Fatal Crashes",  str(n_sc_fatal), '#ef4444')}
              {irow("Temporal Time",  sel_time)}
            </div>""", unsafe_allow_html=True)

            # Risk probabilities
            probs = [
                ('Aligned',                float(r.get('prob_low_risk',0)),    RISK_PALETTE['Aligned']),
                ('Moderate Misalignment',  float(r.get('prob_medium_risk',0)), RISK_PALETTE['Moderate Misalignment']),
                ('High Misalignment',      float(r.get('prob_high_risk',0)),   RISK_PALETTE['High Misalignment']),
                ('Critical Misalignment',  float(r.get('prob_critical_risk',0)),RISK_PALETTE['Critical Misalignment']),
            ]
            st.markdown(
                '<div class="panel"><h4>📉 Risk Probabilities</h4>' +
                "".join(prob_bar(l,v,c) for l,v,c in probs) +
                '</div>', unsafe_allow_html=True)

            # AI Explanation
            factors = build_factors(r, sel_hour)
            tags = "".join(
                f'<div class="factor-pill f-{cls}">{lbl}</div>'
                for lbl, cls in factors)
            st.markdown(f"""
            <div class="xai-box">
              <div class="xai-title">🤖 AI Explanation — {rec_spd} km/h</div>
              <div style="color:#94a3b8;font-size:.75rem;margin-bottom:10px">
                Safe speed set to <b style="color:#60a5fa">{rec_spd} km/h</b>
                based on conditions at <b>{sel_time}</b> on {sel_date}:
              </div>
              {tags}
              <div class="vz-box" style="margin-top:10px">
                <b>Vision Zero Constraint:</b><br>
                min(AI Speed = {ai_spd} km/h, Human Tolerance = {tol} km/h)
                → <b>{rec_spd} km/h</b>
              </div>
            </div>""", unsafe_allow_html=True)

            # Quick crash add
            st.markdown("---")
            st.markdown("**🚨 Log Crash on This Segment**")
            crash_type = st.selectbox("Severity", ["Minor","Major","Fatal"],
                                       key=f"quick_crash_{sel_seg_id}")
            if st.button("➕ Add Crash", key=f"add_crash_{sel_seg_id}"):
                new_crash = pd.DataFrame([{
                    'crash_id':    st.session_state.next_crash_id,
                    'segment_id':  int(r['segment_id']),
                    'severity':    crash_type,
                    'date':        str(sel_date),
                    'time':        sel_time,
                    'description': f'{crash_type} crash logged at {sel_time}',
                }])
                st.session_state.crashes = pd.concat(
                    [st.session_state.crashes, new_crash], ignore_index=True)
                st.session_state.next_crash_id += 1
                active_crashes_updated = get_active_crashes(st.session_state.crashes, sel_date)
                sync_segment_crashes(active_crashes_updated)
                save_crashes()
                save_predictions()
                st.success(f"✅ {crash_type} crash logged on {r['human_segment_id']}")
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — HOTSPOT ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
with tab_hot:
    st.markdown("## 🔴 Hotspot Detection & Analysis")
    st.markdown(
        '<p style="color:#64748b;font-size:.85rem;margin-top:-10px">'
        'Hotspot Score = 40% Crash Severity + 25% Traffic Volume + '
        '20% Speed Violations + 15% AI Risk Score</p>', unsafe_allow_html=True)

    hc1, hc2, hc3, hc4 = st.columns(4)
    for col_w, cat, col_c in zip(
        [hc1,hc2,hc3,hc4],
        ['Safe','Moderate Risk','High Risk','Severe Hotspot'],
        ['#22c55e','#eab308','#f97316','#ef4444'],
    ):
        n = int((df['hotspot_category']==cat).sum())
        col_w.markdown(
            f'<div class="kpi"><div class="kpi-v" style="color:{col_c}">{n}</div>'
            f'<div class="kpi-l">{cat}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    ha1, ha2 = st.columns(2)

    with ha1:
        top20 = df.nlargest(20,"hotspot_score")[
            ["road_name","hotspot_score","hotspot_category","crash_risk_score",
             "road_risk_score","fatal_crashes","crash_count"]].copy()
        top20["label"] = top20["road_name"].str[:22]
        fig = px.bar(top20, x="hotspot_score", y="label", orientation="h",
                     color="hotspot_category", color_discrete_map=HOTSPOT_PALETTE,
                     title="Top 20 Hotspot Segments", template="plotly_dark",
                     hover_data=["crash_count","fatal_crashes","road_risk_score"])
        fig.update_layout(height=480, paper_bgcolor=BG, plot_bgcolor=BG,
                           margin=dict(t=40,b=10,l=0,r=10), showlegend=True,
                           legend=dict(font=dict(size=9),bgcolor='rgba(0,0,0,0)'),
                           yaxis=dict(autorange="reversed",tickfont=dict(size=8)),
                           xaxis=dict(range=[0,100],color='#64748b'))
        st.plotly_chart(fig, use_container_width=True)

    with ha2:
        fig2 = px.scatter(df, x="crash_risk_score", y="hotspot_score",
                          color="hotspot_category", size="road_risk_score",
                          color_discrete_map=HOTSPOT_PALETTE,
                          hover_name="road_name",
                          hover_data=["fatal_crashes","crash_count","exposure_score"],
                          title="Crash Risk vs Hotspot Score", template="plotly_dark")
        fig2.update_layout(height=480, paper_bgcolor=BG, plot_bgcolor=BG,
                            margin=dict(t=40,b=10), showlegend=True,
                            legend=dict(font=dict(size=9),bgcolor='rgba(0,0,0,0)'))
        st.plotly_chart(fig2, use_container_width=True)

    # Hotspot table
    st.markdown("### 🗂️ Severe Hotspot Registry")
    severe = df[df['hotspot_category']=='Severe Hotspot'][
        ['human_segment_id','road_name','road_type','hotspot_score',
         'road_risk_score','crash_risk_score','fatal_crashes',
         'crash_count','final_safe_speed' if 'final_safe_speed' in df.columns else 'recommended_safe_speed','posted_speed_limit']
    ].sort_values('hotspot_score', ascending=False)
    st.dataframe(severe, use_container_width=True, height=280)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — ML MODEL EVALUATION
# ══════════════════════════════════════════════════════════════════════════════
with tab_model:
    st.markdown("## 🤖 ML Model Evaluation")

    m1, m2 = st.columns(2)
    for col_w, row in zip([m1,m2], metrics_df.to_dict('records')):
        with col_w:
            best_flag = row['f1'] == metrics_df['f1'].max()
            st.markdown(
                f'<div class="panel"><h4>{"✅ " if best_flag else ""}{row["model"]}</h4>'
                + "".join(irow(l,f"{v:.2%}",
                               '#22c55e' if best_flag and l=='F1 Score' else '#e2e8f0')
                          for l, v in [
                    ("Accuracy",   row['accuracy']),
                    ("Precision",  row['precision']),
                    ("Recall",     row['recall']),
                    ("F1 Score",   row['f1']),
                    ("CV Accuracy",row.get('cv_acc', row['accuracy'])),
                ]) + '</div>', unsafe_allow_html=True)

    # Radar
    fig_radar = go.Figure()
    for i, row in enumerate(metrics_df.to_dict('records')):
        cats = ['Accuracy','Precision','Recall','F1']
        vals = [row['accuracy'],row['precision'],row['recall'],row['f1']]
        fig_radar.add_trace(go.Scatterpolar(
            r=vals+[vals[0]], theta=cats+[cats[0]],
            fill='toself', name=row['model'],
            line=dict(color=['#60a5fa','#f97316'][i], width=2),
            fillcolor=['#60a5fa','#f97316'][i], opacity=0.2))
    fig_radar.update_layout(
        polar=dict(bgcolor=BG,
                   radialaxis=dict(visible=True,range=[0,1],color='#64748b',tickfont=dict(size=8)),
                   angularaxis=dict(color='#94a3b8')),
        paper_bgcolor='#080e1a', showlegend=True,
        legend=dict(font=dict(color='#e2e8f0',size=10),bgcolor='rgba(0,0,0,0)'),
        title=dict(text='Model Performance Comparison', font=dict(color='#e2e8f0',size=14)),
        height=380, margin=dict(t=50,b=20))
    st.plotly_chart(fig_radar, use_container_width=True)

    # Feature importance / confusion matrix images
    ic1, ic2 = st.columns(2)
    with ic1:
        st.markdown("### 📈 Feature Importance")
        try: st.image("feature_importance.png", use_column_width=True)
        except: st.info("Run ML pipeline to generate feature_importance.png")
    with ic2:
        st.markdown("### 🧮 Model Evaluation")
        try: st.image("model_evaluation.png", use_column_width=True)
        except: st.info("Run ML pipeline to generate model_evaluation.png")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — EXPLAINABLE AI
# ══════════════════════════════════════════════════════════════════════════════
with tab_xai:
    st.markdown("## 🔍 Explainable AI — Feature Importance Analysis")
    st.caption("Gini/impurity-based feature importance from the trained Random Forest & "
               "Gradient Boosting models (not SHAP — `shap` is not part of this environment's "
               "dependency set; swap in true SHAP values if available in your deployment).")

    try: st.image("shap_summary.png", use_column_width=True)
    except: st.info("Run ML pipeline to generate shap_summary.png")

    st.markdown("---")
    st.markdown("### 🔎 Per-Segment Explanation Explorer")

    xai_seg_opts = df_f["road_name"].tolist()
    xai_sel = st.selectbox("Select Road Segment", xai_seg_opts)
    r_x = df_f[df_f["road_name"]==xai_sel].iloc[0]
    label_x = r_x["ai_risk_label"]
    color_x = RISK_PALETTE.get(label_x,'#eab308')

    xc1, xc2 = st.columns(2)

    with xc1:
        probs_x = {
            'Aligned':                float(r_x.get('prob_low_risk',0)),
            'Moderate Misalignment':  float(r_x.get('prob_medium_risk',0)),
            'High Misalignment':      float(r_x.get('prob_high_risk',0)),
            'Critical Misalignment':  float(r_x.get('prob_critical_risk',0)),
        }
        fig_p = go.Figure(go.Bar(
            x=list(probs_x.values()), y=list(probs_x.keys()), orientation='h',
            marker_color=[RISK_PALETTE[k] for k in probs_x],
            text=[f"{v*100:.1f}%" for v in probs_x.values()],
            textposition='outside', textfont=dict(color='#e2e8f0', size=10)))
        fig_p.update_layout(
            title=dict(text='Risk Probabilities', font=dict(color='#e2e8f0',size=13)),
            xaxis=dict(range=[0,1.15],tickformat='.0%',color='#64748b'),
            yaxis=dict(color='#94a3b8'),
            plot_bgcolor=BG, paper_bgcolor='#080e1a',
            height=260, margin=dict(t=40,b=10,l=10,r=60), showlegend=False)
        st.plotly_chart(fig_p, use_container_width=True)

    with xc2:
        feat_lbls = ['Road Function','Infrastructure','Exposure',
                     'Human Tolerance','Op. Speed']
        feat_vals = [float(r_x.get(f,0)) for f in FEATURES]
        fig_sp = go.Figure(go.Scatterpolar(
            r=feat_vals+[feat_vals[0]], theta=feat_lbls+[feat_lbls[0]],
            fill='toself', line=dict(color=color_x,width=2),
            fillcolor=color_x, opacity=0.25))
        fig_sp.update_layout(
            polar=dict(bgcolor=BG,
                       radialaxis=dict(visible=True,range=[0,100],color='#64748b',tickfont=dict(size=8)),
                       angularaxis=dict(color='#94a3b8',tickfont=dict(size=9))),
            paper_bgcolor='#080e1a',
            title=dict(text='Feature Score Profile',font=dict(color='#e2e8f0',size=13)),
            height=260, margin=dict(t=40,b=10), showlegend=False)
        st.plotly_chart(fig_sp, use_container_width=True)

    factors_x = build_factors(r_x, sel_hour)
    tags_x = "".join(f'<div class="factor-pill f-{c}">{l}</div>' for l,c in factors_x)
    ai_spd_x = int(r_x.get('ai_recommended_speed', r_x.get('final_safe_speed', r_x['recommended_safe_speed'])))
    hz_temp_spd_x = get_hazard_temp_speed(st.session_state.hazards, int(r_x['segment_id']), sel_date, sel_time)
    rec_spd_x = hz_temp_spd_x if hz_temp_spd_x else int(r_x.get('final_safe_speed', r_x['recommended_safe_speed']))
    tol_x = int(r_x.get('human_tolerance_limit',70))

    st.markdown(f"""
    <div class="xai-box" style="margin-top:16px">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
        <span style="font-size:2rem;font-weight:900;color:{color_x}">{rec_spd_x} km/h</span>
        <span style="background:{color_x}22;color:{color_x};padding:3px 14px;
               border-radius:20px;font-size:.78rem;font-weight:700">{label_x}</span>
        <span style="color:#64748b;font-size:.76rem">
          AI Confidence: {r_x['ai_risk_probability']*100:.1f}%</span>
      </div>
      <div class="xai-title">🤖 Top Contributing Factors</div>
      {"".join(f'<div class="xai-item">▸ {f.strip()}</div>'
               for f in str(r_x.get('top_ai_factors','')).split(' | ') if f.strip())}
      {tags_x}
      <div class="vz-box" style="margin-top:12px">
        <b>Vision Zero Constraint:</b><br>
        min(AI Speed = {ai_spd_x} km/h, Human Tolerance = {tol_x} km/h)
        → <b>{rec_spd_x} km/h</b>
      </div>
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — CRASH MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════
with tab_crash:
    st.markdown("## 🚨 Crash Management System")

    cr1, cr2, cr3, cr4 = st.columns(4)
    crashes_now = active_crashes
    for col_w, sev, clr in zip(
        [cr1,cr2,cr3,cr4],
        ['Minor','Major','Fatal','Total'],
        ['#22c55e','#f97316','#ef4444','#60a5fa'],
    ):
        n = int((crashes_now['severity']==sev).sum()) if sev != 'Total' else len(crashes_now)
        col_w.markdown(
            f'<div class="kpi"><div class="kpi-v" style="color:{clr}">{n}</div>'
            f'<div class="kpi-l">{sev} Crashes</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    cl1, cl2 = st.columns([1.4, 1])

    with cl1:
        st.markdown("### ➕ Log New Crash")
        with st.form("crash_form"):
            crash_seg_opts = df[['human_segment_id','road_name']].apply(
                lambda r: f"{r['human_segment_id']} — {r['road_name']}", axis=1).tolist()
            crash_seg_sel = st.selectbox("Segment", crash_seg_opts)
            crash_sev_sel = st.selectbox("Severity", ["Minor","Major","Fatal"])
            crash_date    = st.date_input("Date", value=date.today())
            crash_time    = st.selectbox("Time", time_opts,
                                          index=time_opts.index(now_slot) if now_slot in time_opts else 0)
            crash_desc    = st.text_area("Description", height=60, placeholder="Brief crash description…")
            submitted     = st.form_submit_button("🚨 Log Crash")
            if submitted:
                seg_name_c = crash_seg_sel.split(" — ")[1]
                sid_c = int(df[df['road_name']==seg_name_c]['segment_id'].iloc[0])
                new_c = pd.DataFrame([{
                    'crash_id':    st.session_state.next_crash_id,
                    'segment_id':  sid_c,
                    'severity':    crash_sev_sel,
                    'date':        str(crash_date),
                    'time':        crash_time,
                    'description': crash_desc or f"{crash_sev_sel} crash",
                }])
                st.session_state.crashes = pd.concat(
                    [st.session_state.crashes, new_c], ignore_index=True)
                st.session_state.next_crash_id += 1
                active_crashes_updated = get_active_crashes(st.session_state.crashes, sel_date)
                sync_segment_crashes(active_crashes_updated)
                save_crashes()
                save_predictions()
                st.success(f"✅ {crash_sev_sel} crash logged on {crash_seg_sel}")
                st.rerun()

        # Charts
        st.markdown("### 📊 Crash Analytics")
        cca1, cca2 = st.columns(2)
        with cca1:
            sev_counts = crashes_now['severity'].value_counts().reset_index()
            sev_counts.columns = ['Severity','Count']
            sev_colors = {'Minor':'#22c55e','Major':'#f97316','Fatal':'#ef4444'}
            fig_sv = px.pie(sev_counts, names='Severity', values='Count',
                             color='Severity', color_discrete_map=sev_colors,
                             template="plotly_dark", hole=0.45)
            fig_sv.update_layout(height=220, paper_bgcolor=BG,
                                   margin=dict(t=10,b=0,l=0,r=0),
                                   legend=dict(font=dict(size=9),bgcolor='rgba(0,0,0,0)'))
            st.plotly_chart(fig_sv, use_container_width=True)
        with cca2:
            month_c = crashes_now.copy()
            month_c['month'] = pd.to_datetime(month_c['date'], errors='coerce').dt.month
            mc = month_c.groupby(['month','severity']).size().reset_index(name='count')
            fig_mc = px.bar(mc, x='month', y='count', color='severity',
                             color_discrete_map=sev_colors,
                             template="plotly_dark", title="Monthly Crash Trend")
            fig_mc.update_layout(height=220, paper_bgcolor=BG, plot_bgcolor=BG,
                                  margin=dict(t=30,b=0,l=0,r=0), showlegend=False,
                                  xaxis=dict(color='#64748b'),yaxis=dict(color='#64748b'))
            st.plotly_chart(fig_mc, use_container_width=True)

    with cl2:
        st.markdown("### 📋 Recent Crash Log")
        if sel_crash_sev != "All":
            display_crashes = crashes_now[crashes_now['severity']==sel_crash_sev].copy()
        else:
            display_crashes = crashes_now.copy()

        # Merge road names
        display_crashes = display_crashes.merge(
            df[['segment_id','road_name','human_segment_id']].drop_duplicates(),
            on='segment_id', how='left')
        display_crashes = display_crashes.sort_values('crash_id', ascending=False)
        st.dataframe(
            display_crashes[['crash_id','human_segment_id','road_name','severity','date','time','description']].head(50),
            use_container_width=True, height=460)

        all_crashes = st.session_state.crashes.merge(
            df[['segment_id','road_name','human_segment_id']].drop_duplicates(),
            on='segment_id', how='left').sort_values('crash_id', ascending=False)
        csv_c = all_crashes[['crash_id','human_segment_id','road_name','severity','date','time','description']].to_csv(index=False)
        st.download_button("⬇️ Export Crash Log", csv_c, "crash_log.csv", "text/csv")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — HAZARD MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════
with tab_hazard:
    st.markdown("## ⚠️ Authority Hazard Management System")

    hz1, hz2 = st.columns([1, 1.5])

    with hz1:
        st.markdown("### ➕ Add Temporary Hazard")
        # Remove st.form to enable dynamic updates on selection change
        hz_type_opts = ["Construction","Accident","Road Blockage","Festival",
                        "Procession","Political Rally","Religious Gathering",
                        "VIP Movement","School Event","Market Event","Other"]
        hz_type  = st.selectbox("Hazard Type", hz_type_opts)
        hz_segs  = df.apply(
            lambda r: f"{r['human_segment_id']} — {r['road_name']}", axis=1).tolist()
        hz_seg   = st.selectbox("Affected Segment", hz_segs)
        hz_date  = st.date_input("Date", value=date.today(), key="hz_date")
        hz_start = st.selectbox("Start Time", time_opts, key="hz_start")
        hz_end   = st.selectbox("End Time", time_opts,
                                 index=min(len(time_opts)-1,
                                           time_opts.index(hz_start)+4
                                           if hz_start in time_opts else 8),
                                 key="hz_end")
        # Determine road type for the selected segment to set default temp speed
        try:
            _seg_road_name = hz_seg.split(" — ")[1]
            _seg_road_type = df[df['road_name'] == _seg_road_name]['road_type'].iloc[0]
        except Exception:
            _seg_road_type = ""
        _default_speed = 60 if _seg_road_type == "Highway" else 40 if _seg_road_type == "Arterial" else 30
        
        # Dynamic key forces widget recreation on segment change, updating the default value instantly
        hz_speed = st.number_input(
            f"Temporary Speed Limit (km/h) — default for {_seg_road_type or 'this road'}: {_default_speed} km/h",
            min_value=5, max_value=100, value=_default_speed, step=5,
            key=f"hz_speed_val_{hz_seg}")
            
        hz_desc  = st.text_area("Description", height=60)
        hz_submit= st.button("⚠️ Add Hazard")
        if hz_submit:
            seg_name_h = hz_seg.split(" — ")[1]
            sid_h = int(df[df['road_name']==seg_name_h]['segment_id'].iloc[0])
            new_h = pd.DataFrame([{
                'hazard_id':   st.session_state.next_hazard_id,
                'segment_id':  sid_h,
                'hazard_type': hz_type,
                'start_time':  hz_start,
                'end_time':    hz_end,
                'date':        str(hz_date),
                'temp_speed':  hz_speed,
                'description': hz_desc or hz_type,
            }])
            st.session_state.hazards = pd.concat(
                [st.session_state.hazards, new_h], ignore_index=True)
            st.session_state.next_hazard_id += 1
            save_hazards()
            st.success(f"✅ Hazard added on {hz_seg} with temp speed {hz_speed} km/h")
            st.rerun()

    with hz2:
        # Compute currently active hazards for the selected date/time
        def is_hazard_active(hz_row, check_date, check_time_str):
            try:
                hz_date = pd.to_datetime(hz_row['date']).date()
                if hz_date != check_date:
                    return False
                start = datetime.strptime(str(hz_row['start_time']), "%H:%M").time()
                end   = datetime.strptime(str(hz_row['end_time']),   "%H:%M").time()
                now_t = datetime.strptime(check_time_str,         "%H:%M").time()
                return is_time_in_range(start, end, now_t)
            except Exception:
                return False

        hazards_now = st.session_state.hazards.merge(
            df[['segment_id','road_name','human_segment_id']].drop_duplicates(),
            on='segment_id', how='left')
        hazards_now['_is_active'] = hazards_now.apply(
            lambda row: is_hazard_active(row, sel_date, sel_time), axis=1)

        active_hz   = hazards_now[hazards_now['_is_active']]
        inactive_hz = hazards_now[~hazards_now['_is_active']]

        st.markdown(f"### 🗂️ Active Hazards ({sel_date} · {sel_time})")
        if len(active_hz) == 0:
            st.info("No hazards active for the selected date and time.")
        else:
            for _, hz in active_hz.iterrows():
                temp_spd_str = f"Temp Speed: {int(hz['temp_speed'])} km/h" \
                               if pd.notna(hz.get('temp_speed')) and hz.get('temp_speed') else ""
                st.markdown(f"""
                <div class="hazard-item" style="border-color:#92400e">
                  <div style="display:flex;justify-content:space-between;align-items:center">
                    <div>
                      <div class="hazard-type">🟡 {hz['hazard_type']}</div>
                      <div class="hazard-meta">{hz.get('human_segment_id','—')} · {hz.get('road_name','—')}</div>
                      <div class="hazard-meta">{hz.get('date','—')} · {hz.get('start_time','—')} – {hz.get('end_time','—')}</div>
                      {f'<div class="hazard-meta" style="color:#60a5fa">{temp_spd_str}</div>' if temp_spd_str else ''}
                    </div>
                  </div>
                </div>""", unsafe_allow_html=True)
                if st.button(f"🗑️ Remove", key=f"rmhz_{hz['hazard_id']}"):
                    st.session_state.hazards = st.session_state.hazards[
                        st.session_state.hazards['hazard_id'] != hz['hazard_id']]
                    save_hazards()
                    st.rerun()

        if len(inactive_hz) > 0:
            with st.expander(f"📁 All Scheduled / Past Hazards ({len(inactive_hz)})"):
                for _, hz in inactive_hz.iterrows():
                    temp_spd_str = f"Temp Speed: {int(hz['temp_speed'])} km/h" \
                                   if pd.notna(hz.get('temp_speed')) and hz.get('temp_speed') else ""
                    st.markdown(f"""
                    <div class="hazard-item" style="opacity:0.6">
                      <div class="hazard-type">⬜ {hz['hazard_type']}</div>
                      <div class="hazard-meta">{hz.get('human_segment_id','—')} · {hz.get('road_name','—')}</div>
                      <div class="hazard-meta">{hz.get('date','—')} · {hz.get('start_time','—')} – {hz.get('end_time','—')}</div>
                      {f'<div class="hazard-meta" style="color:#60a5fa">{temp_spd_str}</div>' if temp_spd_str else ''}
                    </div>""", unsafe_allow_html=True)
                    if st.button(f"🗑️ Remove", key=f"rmhz_i_{hz['hazard_id']}"):
                        st.session_state.hazards = st.session_state.hazards[
                            st.session_state.hazards['hazard_id'] != hz['hazard_id']]
                        save_hazards()
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — ADVANCED ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════
with tab_analytics:
    st.markdown("## 📈 Advanced Analytics Dashboard")

    # Row 1
    aa1, aa2, aa3 = st.columns(3)

    with aa1:
        fig = px.box(df, x="road_type", y="road_risk_score",
                     color="road_type", template="plotly_dark",
                     title="Risk Score by Road Type")
        fig.update_layout(height=300, paper_bgcolor=BG, plot_bgcolor=BG,
                           margin=dict(t=40,b=40,l=10,r=10), showlegend=False,
                           xaxis=dict(tickfont=dict(size=8),color='#64748b'),
                           yaxis=dict(color='#64748b'))
        st.plotly_chart(fig, use_container_width=True)

    with aa2:
        fig2 = px.scatter(df, x="infrastructure_score", y="final_safe_speed" if "final_safe_speed" in df.columns else "recommended_safe_speed",
                          color="ai_risk_label", color_discrete_map=RISK_PALETTE,
                          size="road_risk_score", hover_name="road_name",
                          title="Infrastructure vs Safe Speed", template="plotly_dark")
        fig2.update_layout(height=300, paper_bgcolor=BG, plot_bgcolor=BG,
                            margin=dict(t=40,b=10,l=10,r=10),
                            legend=dict(font=dict(size=8),bgcolor='rgba(0,0,0,0)'),
                            xaxis=dict(color='#64748b'), yaxis=dict(color='#64748b'))
        st.plotly_chart(fig2, use_container_width=True)

    with aa3:
        fig3 = px.scatter(df, x="exposure_score", y="crash_risk_score",
                          color="hotspot_category", color_discrete_map=HOTSPOT_PALETTE,
                          hover_name="road_name", size="hotspot_score",
                          title="Exposure vs Crash Risk", template="plotly_dark")
        fig3.update_layout(height=300, paper_bgcolor=BG, plot_bgcolor=BG,
                            margin=dict(t=40,b=10,l=10,r=10),
                            legend=dict(font=dict(size=8),bgcolor='rgba(0,0,0,0)'),
                            xaxis=dict(color='#64748b'), yaxis=dict(color='#64748b'))
        st.plotly_chart(fig3, use_container_width=True)

    # Row 2
    aa4, aa5 = st.columns(2)

    with aa4:
        # Temporal exposure heatmap
        hours = list(range(24))
        road_types_u = df['road_type'].unique()[:6]
        heat_data = []
        for rt in road_types_u:
            rt_df = df[df['road_type']==rt]
            row_vals = []
            for h in hours:
                avg = rt_df.apply(lambda r: temporal_exposure(r,h), axis=1).mean()
                row_vals.append(round(avg,1))
            heat_data.append(row_vals)

        fig_heat = go.Figure(go.Heatmap(
            z=heat_data, x=[f"{h:02d}:00" for h in hours],
            y=list(road_types_u),
            colorscale='YlOrRd', showscale=True,
            colorbar=dict(tickfont=dict(color='#94a3b8',size=8))))
        fig_heat.update_layout(
            title=dict(text='Temporal Exposure by Road Type & Hour',
                        font=dict(color='#e2e8f0',size=13)),
            paper_bgcolor='#080e1a', plot_bgcolor=BG,
            height=300, margin=dict(t=40,b=40,l=10,r=10),
            xaxis=dict(color='#64748b',tickfont=dict(size=7)),
            yaxis=dict(color='#94a3b8',tickfont=dict(size=8)))
        st.plotly_chart(fig_heat, use_container_width=True)

    with aa5:
        # Top 10 safest
        safe_cols = ['road_name','road_type','final_safe_speed' if 'final_safe_speed' in df.columns else 'recommended_safe_speed',
                     'road_risk_score','infrastructure_score','exposure_score']
        top_safe = df.nsmallest(10,'road_risk_score')[safe_cols].copy()
        top_safe['label'] = top_safe['road_name'].str[:22]
        fig_safe = px.bar(top_safe[::-1], x='infrastructure_score', y='label',
                          orientation='h', color='final_safe_speed' if 'final_safe_speed' in top_safe.columns else 'recommended_safe_speed',
                          color_continuous_scale='Greens',
                          title="Top 10 Safest Roads (by Infrastructure)",
                          template="plotly_dark")
        fig_safe.update_layout(height=300, paper_bgcolor=BG, plot_bgcolor=BG,
                                margin=dict(t=40,b=10,l=10,r=10),
                                yaxis=dict(autorange="reversed",tickfont=dict(size=8),color='#94a3b8'),
                                xaxis=dict(color='#64748b'))
        st.plotly_chart(fig_safe, use_container_width=True)

    # Summary stats table
    st.markdown("### 📊 Road Type Summary Statistics")
    summary = df.groupby('road_type').agg(
        Segments=('segment_id','count'),
        Avg_Risk=('road_risk_score','mean'),
        Avg_Safe_Speed=('final_safe_speed' if 'final_safe_speed' in df.columns else 'recommended_safe_speed','mean'),
        Avg_Infrastructure=('infrastructure_score','mean'),
        Avg_Exposure=('exposure_score','mean'),
        Avg_Hotspot=('hotspot_score','mean'),
        Fatal_Crashes=('fatal_crashes','sum'),
    ).round(1).reset_index()
    st.dataframe(summary, use_container_width=True, height=240)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 8 — DATA TABLE
# ══════════════════════════════════════════════════════════════════════════════
with tab_data:
    st.markdown("## 📂 Unified Predictions Dataset")

    show_cols = ['human_segment_id','segment_id','road_name','road_type',
                 'posted_speed_limit','speed_p85','final_safe_speed' if 'final_safe_speed' in df_f.columns else 'recommended_safe_speed',
                 'misalignment_score','misalignment_category','exposure_tier',
                 'congestion_index','congestion_category',
                 'ai_risk_label','ai_risk_probability',
                 'road_risk_score','hotspot_score','hotspot_category',
                 'infrastructure_score','exposure_score','ptw_share_pct',
                 'crash_risk_score','road_function_score',
                 'fatal_crashes','crash_count','blackspot_flag',
                 'top_ai_factors']
    disp = df_f[[c for c in show_cols if c in df_f.columns]].sort_values(
        'road_risk_score', ascending=False).copy()
    disp['ai_risk_probability'] = (disp['ai_risk_probability']*100).round(1).astype(str)+"%"

    st.dataframe(disp, use_container_width=True, height=420)

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button("⬇️ Download Filtered Data",
                            df_f.to_csv(index=False),
                            "filtered_predictions.csv","text/csv")
    with col_dl2:
        st.download_button("⬇️ Download Full Dataset",
                            df.to_csv(index=False),
                            "full_predictions.csv","text/csv")

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;color:#1a2d45;font-size:.7rem;
     padding:16px 0 6px;border-top:1px solid #0d1b2e;margin-top:20px">
  AI for Safer Roads · Speed Limit Misalignment Platform ·
  Bangalore Road Network (4,966 segments, NH→Local→Peri-Urban/Rural) ·
  Random Forest + Gradient Boosting · Safe System / Vision Zero Constraints
</div>""", unsafe_allow_html=True)