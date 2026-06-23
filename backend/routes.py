"""
routes.py
All HTTP API endpoints for the Road Safety platform, organized by the
original Streamlit tab each one replaces. The frontend (static/js/*) calls
these via fetch() and renders the results with Leaflet + Plotly.js.
"""

import os
import io
import json
from datetime import datetime, date as date_cls

import pandas as pd
from flask import Blueprint, jsonify, request, Response, send_from_directory

from . import prediction as pred
from . import db
from . import weather as wx
from . import traffic as tx

api = Blueprint("api", __name__, url_prefix="/api")


# ─── Shared helpers ──────────────────────────────────────────────────────────
def _parse_date(s):
    if not s:
        return datetime.now().date()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return datetime.now().date()


def _parse_time(s):
    if s:
        return s
    now = datetime.now()
    return f"{now.hour:02d}:{'00' if now.minute < 30 else '30'}"


def _date_time_from_request():
    return _parse_date(request.args.get("date")), _parse_time(request.args.get("time"))


def _filters_from_request():
    return dict(
        road_type=request.args.get("road_type", "All"),
        risk_cat=request.args.get("risk", "All"),
        hotspot_cat=request.args.get("hotspot", "All"),
        speed_min=request.args.get("speed_min", type=int),
        speed_max=request.args.get("speed_max", type=int),
    )


def records(df, cols=None):
    """NaN-safe DataFrame -> list[dict] (NaN becomes null, numpy scalars
    become native JSON types) via pandas' own JSON encoder."""
    d = df[cols] if cols else df
    return json.loads(d.to_json(orient="records"))


def _label(row):
    return f"{row.get('human_segment_id', '')} — {row.get('road_name', '')}"


# Columns sent for map rendering / popups (joined client-side with the
# geometry-only GeoJSON by segment_id).
MAP_COLUMNS = [
    'segment_id', 'human_segment_id', 'road_name', 'road_type',
    'posted_speed_limit', 'final_safe_speed', 'ai_recommended_speed',
    'human_tolerance_limit', 'ai_risk_label', 'ai_risk_probability',
    'road_risk_score', 'hotspot_score', 'hotspot_category',
    'infrastructure_score', 'exposure_score', 'crash_risk_score',
    'blackspot_flag', 'fatal_crashes', 'top_ai_factors',
]

TABLE_COLUMNS = [
    'human_segment_id', 'segment_id', 'road_name', 'road_type',
    'posted_speed_limit', 'speed_p85', 'final_safe_speed',
    'misalignment_score', 'misalignment_category', 'exposure_tier',
    'congestion_index', 'congestion_category',
    'ai_risk_label', 'ai_risk_probability',
    'road_risk_score', 'hotspot_score', 'hotspot_category',
    'infrastructure_score', 'exposure_score', 'ptw_share_pct',
    'crash_risk_score', 'road_function_score',
    'fatal_crashes', 'crash_count', 'blackspot_flag', 'top_ai_factors',
]


# ─── Sidebar options (filters, legend, active model) ──────────────────────
@api.route("/sidebar-options")
def sidebar_options():
    df = pred._SOURCE_DF
    time_opts = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
    best = pred.get_best_model_row()
    # Problem 5: only three road categories
    road_types = ["All", "National Highway", "State Highway", "Urban Road"]
    return jsonify(dict(
        road_types=road_types,
        risk_cats=["All"] + pred.RISK_ORDER,
        hotspot_cats=["All"] + pred.HOTSPOT_ORDER,
        speed_min=int(df["posted_speed_limit"].min()),
        speed_max=int(df["posted_speed_limit"].max()),
        time_opts=time_opts,
        default_time=_parse_time(None),
        risk_palette=pred.RISK_PALETTE,
        hotspot_palette=pred.HOTSPOT_PALETTE,
        hazard_type_opts=["Construction", "Accident", "Road Blockage", "Festival",
                           "Procession", "Political Rally", "Religious Gathering",
                           "VIP Movement", "School Event", "Market Event", "Other"],
        active_model=dict(name=best["model"], accuracy=float(best["accuracy"]), f1=float(best["f1"])),
        total_segments=int(len(df)),
    ))


# ─── KPI row ────────────────────────────────────────────────────────────────
@api.route("/kpis")
def kpis():
    sel_date, sel_time = _date_time_from_request()
    filt = _filters_from_request()
    df, crashes, hazards, active_crashes = pred.compute_state(sel_date, sel_time)
    df_f = pred.apply_filters(df, **filt)

    n_minor = sum(1 for c in active_crashes if c['severity'] == 'Minor')
    n_major = sum(1 for c in active_crashes if c['severity'] == 'Major')
    n_fatal = sum(1 for c in active_crashes if c['severity'] == 'Fatal')
    n_total = len(active_crashes)
    n_hotspot = int((df['hotspot_category'] == 'Severe Hotspot').sum())
    n_high = int((df_f['ai_risk_label'] == 'High Misalignment').sum())
    n_crit = int((df_f['ai_risk_label'] == 'Critical Misalignment').sum())
    n_congested = int(df_f['congestion_category'].isin(['Moderate', 'Severe']).sum()) if 'congestion_category' in df_f.columns else 0
    avg_spd = int(df_f['final_safe_speed'].mean()) if len(df_f) else 0
    avg_exp = int(df_f['temporal_exposure'].mean()) if len(df_f) else 0
    avg_risk = int(df_f['road_risk_score'].mean()) if len(df_f) else 0

    return jsonify(dict(
        segments=len(df_f), minor_crashes=n_minor, major_crashes=n_major,
        fatal_crashes=n_fatal, total_crashes=n_total, severe_hotspots=n_hotspot,
        high_misalignment=n_high, critical_misalignment=n_crit, congested_now=n_congested,
        avg_safe_speed=avg_spd, avg_exposure=avg_exp, avg_risk_score=avg_risk,
    ))


# ─── TAB 1 — Interactive Map ────────────────────────────────────────────────
@api.route("/segments/options")
def segment_options():
    """Lightweight segment list for searchable dropdown widgets.
    Returns segment_id, label, road_name, road_type, human_segment_id for
    client-side multi-field search (segment ID / road name / road type).
    scope=all  → full network (Crash/Hazard forms)
    scope=filtered → applies sidebar filters (Map / XAI segment pickers).
    """
    sel_date, sel_time = _date_time_from_request()
    scope = request.args.get("scope", "all")
    df, *_ = pred.compute_state(sel_date, sel_time)
    if scope == "filtered":
        df = pred.apply_filters(df, **_filters_from_request())
    df = df.sort_values('hotspot_score', ascending=False)
    return jsonify([
        dict(
            segment_id=int(r['segment_id']),
            label=_label(r),
            road_name=str(r.get('road_name', '') or ''),
            road_type=str(r.get('road_type', '') or ''),
            human_segment_id=str(r.get('human_segment_id', '') or ''),
        )
        for _, r in df.iterrows()
    ])


@api.route("/segments/map")
def segments_map():
    sel_date, sel_time = _date_time_from_request()
    filt = _filters_from_request()

    df, crashes, hazards, active_crashes = pred.compute_state(sel_date, sel_time)
    df_f = pred.apply_filters(df, **filt)
    total_filtered = len(df_f)
    # Problem 3: no render cap — always return the full filtered set
    df_render = df_f

    active_hazard_segs = pred.get_active_hazard_segs(hazards, sel_date, sel_time)

    # Quick-analytics strip under the map — computed from the FULL filtered
    # set (df_f), not just the render-capped subset, mirroring the original
    # Streamlit charts which always read from df_f.
    risk_counts = df_f['ai_risk_label'].value_counts()
    risk_dist = [dict(label=c, count=int(risk_counts.get(c, 0))) for c in pred.RISK_ORDER]

    hotspot_counts = df_f['hotspot_category'].value_counts()
    hotspot_dist = [dict(label=c, count=int(hotspot_counts.get(c, 0))) for c in pred.HOTSPOT_ORDER]

    speed_dist = df_f['final_safe_speed'].tolist() if len(df_f) else []

    top10 = df_f.nlargest(10, "road_risk_score")[["road_name", "road_risk_score", "ai_risk_label"]]
    top10_risk = records(top10)

    bounds = None
    if len(df_f):
        bounds = [
            [float(min(df_f['start_lat'].min(), df_f['end_lat'].min())),
             float(min(df_f['start_lon'].min(), df_f['end_lon'].min()))],
            [float(max(df_f['start_lat'].max(), df_f['end_lat'].max())),
             float(max(df_f['start_lon'].max(), df_f['end_lon'].max()))],
        ]

    # Attach weather icon/condition to each segment for map rendering
    all_wx = wx.get_all_weather()
    seg_records = records(df_render, MAP_COLUMNS)
    for s in seg_records:
        sid = int(s['segment_id'])
        w = all_wx.get(sid, {})
        s['weather_icon'] = w.get('icon', '☀')
        s['weather_condition'] = w.get('condition', 'Clear / Sunny')
        s['weather_color'] = w.get('color', '#fbbf24')
        s['rainfall_mmhr'] = w.get('rainfall_mmhr', 0.0)

    return jsonify(dict(
        segments=seg_records,
        total_filtered=total_filtered,
        rendered=len(df_render),
        capped=False,
        render_cap=total_filtered,
        active_hazard_segments=sorted(active_hazard_segs),
        bounds=bounds,
        quick_charts=dict(risk_dist=risk_dist, hotspot_dist=hotspot_dist,
                           speed_dist=speed_dist, top10_risk=top10_risk),
    ))


@api.route("/segments/<int:segment_id>")
def segment_detail(segment_id):
    sel_date, sel_time = _date_time_from_request()
    df, crashes, hazards, active_crashes = pred.compute_state(sel_date, sel_time)
    match = df[df['segment_id'] == segment_id]
    if match.empty:
        return jsonify(error="segment not found"), 404
    r = match.iloc[0]

    # ── Traffic temporal data lookup (pre-loaded at startup, O(1) lookup) ──
    traffic_info = tx.get_traffic(
        unified_segment_id=segment_id,
        sel_date=sel_date,
        sel_time=sel_time,
        base_safe_speed=int(r.get('final_safe_speed', r.get('recommended_safe_speed', 0))),
    )
    sel_hour = int(sel_time.split(':')[0])

    has_hazard = segment_id in pred.get_active_hazard_segs(hazards, sel_date, sel_time)
    hz_temp_spd = pred.get_hazard_temp_speed(hazards, segment_id, sel_date, sel_time, df) if has_hazard else None

    ai_spd = int(r.get('ai_recommended_speed', r.get('final_safe_speed', r['recommended_safe_speed'])))
    base_spd = hz_temp_spd if hz_temp_spd else int(r.get('final_safe_speed', r['recommended_safe_speed']))
    tol = int(r.get('human_tolerance_limit', 70))

    # Compute weather FIRST so we can subtract the reduction from rec_spd
    weather_info = wx.apply_weather_speed(base_spd, segment_id, r['road_type'])

    # Apply weather reduction — skip when a hazard override is in effect
    if hz_temp_spd:
        rec_spd = hz_temp_spd  # hazard takes absolute priority
    else:
        road_type_str = r['road_type']
        wx_reduction = weather_info.get('speed_reduction', 0)
        min_spd = pred.ROAD_TYPE_MIN.get(road_type_str, 20)
        rec_spd = max(base_spd - wx_reduction, min_spd)

    seg_crashes = [c for c in active_crashes if int(c['segment_id']) == segment_id]
    n_minor = sum(1 for c in seg_crashes if c['severity'] == 'Minor')
    n_major = sum(1 for c in seg_crashes if c['severity'] == 'Major')
    n_fatal = sum(1 for c in seg_crashes if c['severity'] == 'Fatal')

    factors = pred.build_factors(r, sel_hour, traffic_info=traffic_info)
    temp_exp = pred.temporal_exposure(r, sel_hour)

    payload = dict(
        segment_id=int(r['segment_id']),
        human_segment_id=r['human_segment_id'],
        road_name=r['road_name'],
        road_type=r['road_type'],
        is_blackspot=str(r.get('blackspot_flag', '')) == 'Yes',
        has_active_hazard=has_hazard,
        hazard_temp_speed=hz_temp_spd,
        speed=dict(ai_speed=ai_spd, recommended_speed=rec_spd, posted_speed=int(r['posted_speed_limit']),
                   tolerance=tol, is_hazard_override=bool(hz_temp_spd)),
        scores=dict(
            road_risk_score=float(r['road_risk_score']),
            ai_risk_probability=float(r['ai_risk_probability']) * 100,
            hotspot_score=float(r['hotspot_score']),
            exposure_now=float(temp_exp),
            infrastructure_score=float(r['infrastructure_score']),
            crash_risk_score=float(r['crash_risk_score']),
            road_function_score=float(r['road_function_score']),
            speed_safety_score=float(r.get('speed_safety_score', 50)),
            congestion_index=float(r.get('congestion_index', 0) or 0) * 100,
        ),
        congestion_category=r.get('congestion_category') if pd.notna(r.get('congestion_category')) else 'None',
        congestion_smoothed=bool(r.get('congestion_smoothed', False)) if pd.notna(r.get('congestion_smoothed')) else False,
        operating_speed_mean=float(r.get('operating_speed_mean', 0) or 0),
        info=dict(
            start_km=float(r['start_km']), end_km=float(r['end_km']),
            risk_category=r['ai_risk_label'], hotspot_category=r['hotspot_category'],
            exposure_tier=r.get('exposure_tier') if pd.notna(r.get('exposure_tier')) else '—',
            schools_count=int(r.get('schools_count', 0) or 0),
            minor_crashes=n_minor, major_crashes=n_major, fatal_crashes=n_fatal,
            time=sel_time,
        ),
        probabilities=[
            dict(label='Aligned', value=float(r.get('prob_low_risk', 0)), color=pred.RISK_PALETTE['Aligned']),
            dict(label='Moderate Misalignment', value=float(r.get('prob_medium_risk', 0)), color=pred.RISK_PALETTE['Moderate Misalignment']),
            dict(label='High Misalignment', value=float(r.get('prob_high_risk', 0)), color=pred.RISK_PALETTE['High Misalignment']),
            dict(label='Critical Misalignment', value=float(r.get('prob_critical_risk', 0)), color=pred.RISK_PALETTE['Critical Misalignment']),
        ],
        factors=[dict(label=l, severity=c) for l, c in factors],
        risk_color=pred.RISK_PALETTE.get(r['ai_risk_label'], '#eab308'),
        hotspot_color=pred.HOTSPOT_PALETTE.get(r['hotspot_category'], '#f97316'),
        weather=weather_info,
        traffic=traffic_info,
    )
    return jsonify(payload)


@api.route("/segments/<int:segment_id>/crashes", methods=["POST"])
def quick_log_crash(segment_id):
    body = request.get_json(force=True) or {}
    sel_date, sel_time = _date_time_from_request()
    severity = body.get("severity", "Minor")
    crash_id = db.add_crash(segment_id, severity, str(sel_date), sel_time,
                             f"{severity} crash logged at {sel_time}")
    return jsonify(success=True, crash_id=crash_id)


# ─── TAB 2 — Hotspot Analysis ───────────────────────────────────────────────
@api.route("/analytics/hotspot")
def analytics_hotspot():
    sel_date, sel_time = _date_time_from_request()
    df, *_ = pred.compute_state(sel_date, sel_time)

    cards = {cat: int((df['hotspot_category'] == cat).sum()) for cat in pred.HOTSPOT_ORDER}

    top20 = df.nlargest(20, "hotspot_score")[
        ["road_name", "hotspot_score", "hotspot_category", "crash_risk_score",
         "road_risk_score", "fatal_crashes", "crash_count"]]

    scatter = df[["road_name", "crash_risk_score", "hotspot_score", "hotspot_category",
                  "road_risk_score", "fatal_crashes", "crash_count", "exposure_score"]]

    severe = df[df['hotspot_category'] == 'Severe Hotspot'][
        ['human_segment_id', 'road_name', 'road_type', 'hotspot_score',
         'road_risk_score', 'crash_risk_score', 'fatal_crashes',
         'crash_count', 'final_safe_speed', 'posted_speed_limit']
    ].sort_values('hotspot_score', ascending=False)

    return jsonify(dict(
        cards=cards,
        top20=records(top20),
        scatter=records(scatter),
        severe_table=records(severe),
    ))


# ─── TAB 3 — ML Model Evaluation ────────────────────────────────────────────
@api.route("/metrics")
def metrics():
    metrics_df = pred.get_metrics_df()
    best_f1 = metrics_df['f1'].max()
    models = records(metrics_df)
    for m in models:
        m['is_best'] = bool(m['f1'] == best_f1)

    categories = ['Accuracy', 'Precision', 'Recall', 'F1']
    radar = [
        dict(name=row['model'],
             values=[row['accuracy'], row['precision'], row['recall'], row['f1']])
        for row in metrics_df.to_dict('records')
    ]
    return jsonify(dict(
        models=models,
        radar=dict(categories=categories, series=radar),
        images=dict(
            feature_importance="/static/images/feature_importance.png",
            model_evaluation="/static/images/model_evaluation.png",
        ),
    ))


# ─── TAB 4 — Explainable AI ─────────────────────────────────────────────────
@api.route("/xai/<int:segment_id>")
def xai_segment(segment_id):
    sel_date, sel_time = _date_time_from_request()
    df, crashes, hazards, active_crashes = pred.compute_state(sel_date, sel_time)
    match = df[df['segment_id'] == segment_id]
    if match.empty:
        return jsonify(error="segment not found"), 404
    r = match.iloc[0]
    sel_hour = int(sel_time.split(':')[0])

    label = r['ai_risk_label']
    color = pred.RISK_PALETTE.get(label, '#eab308')

    probs = dict(
        Aligned=float(r.get('prob_low_risk', 0)),
        **{'Moderate Misalignment': float(r.get('prob_medium_risk', 0))},
        **{'High Misalignment': float(r.get('prob_high_risk', 0))},
        **{'Critical Misalignment': float(r.get('prob_critical_risk', 0))},
    )

    feat_labels = ['Road Function', 'Infrastructure', 'Exposure', 'Human Tolerance', 'Op. Speed']
    feat_values = [float(r.get(f, 0)) for f in pred.FEATURES]

    # Fetch traffic info so AI factors match the Traffic Conditions panel
    _xai_traffic = tx.get_traffic(
        unified_segment_id=int(r['segment_id']),
        sel_date=sel_date, sel_time=sel_time,
        base_safe_speed=int(r.get('final_safe_speed', r.get('recommended_safe_speed', 0))),
    )
    factors = pred.build_factors(r, sel_hour, traffic_info=_xai_traffic)
    ai_spd = int(r.get('ai_recommended_speed', r.get('final_safe_speed', r['recommended_safe_speed'])))
    has_hazard = segment_id in pred.get_active_hazard_segs(hazards, sel_date, sel_time)
    hz_temp_spd = pred.get_hazard_temp_speed(hazards, segment_id, sel_date, sel_time, df) if has_hazard else None
    base_spd_xai = hz_temp_spd if hz_temp_spd else int(r.get('final_safe_speed', r['recommended_safe_speed']))
    if hz_temp_spd:
        rec_spd = hz_temp_spd
    else:
        _wx_xai = wx.apply_weather_speed(base_spd_xai, int(r['segment_id']), r['road_type'])
        _min_xai = pred.ROAD_TYPE_MIN.get(r['road_type'], 20)
        rec_spd = max(base_spd_xai - _wx_xai.get('speed_reduction', 0), _min_xai)
    tol = int(r.get('human_tolerance_limit', 70))

    top_factors_str = str(r.get('top_ai_factors', '') or '')
    top_factors_list = [f.strip() for f in top_factors_str.split('|') if f.strip()]

    return jsonify(dict(
        label=label, color=color, confidence=float(r['ai_risk_probability']) * 100,
        probabilities=dict(labels=list(probs.keys()), values=list(probs.values()),
                            colors=[pred.RISK_PALETTE[k] for k in probs]),
        feature_radar=dict(labels=feat_labels, values=feat_values),
        top_factors=top_factors_list,
        factors=[dict(label=l, severity=c) for l, c in factors],
        ai_speed=ai_spd, recommended_speed=rec_spd, tolerance=tol,
        shap_image="/static/images/shap_summary.png",
    ))


# ─── TAB 5 — Crash Management ───────────────────────────────────────────────
@api.route("/crashes")
def list_crashes():
    sel_date, sel_time = _date_time_from_request()
    severity = request.args.get("severity", "All")
    df, crashes, hazards, active_crashes = pred.compute_state(sel_date, sel_time)

    n_minor = sum(1 for c in active_crashes if c['severity'] == 'Minor')
    n_major = sum(1 for c in active_crashes if c['severity'] == 'Major')
    n_fatal = sum(1 for c in active_crashes if c['severity'] == 'Fatal')

    display = active_crashes if severity == "All" else [c for c in active_crashes if c['severity'] == severity]
    display = sorted(display, key=lambda c: c['crash_id'], reverse=True)[:50]

    name_lookup = df.set_index('segment_id')[['road_name', 'human_segment_id']].to_dict('index')
    for c in display:
        info = name_lookup.get(int(c['segment_id']), {})
        c['road_name'] = info.get('road_name', '—')
        c['human_segment_id'] = info.get('human_segment_id', '—')

    return jsonify(dict(
        kpis=dict(minor=n_minor, major=n_major, fatal=n_fatal, total=len(active_crashes)),
        recent=display,
    ))


@api.route("/crashes/charts")
def crash_charts():
    sel_date, sel_time = _date_time_from_request()
    df, crashes, hazards, active_crashes = pred.compute_state(sel_date, sel_time)

    sev_counts = {}
    for c in active_crashes:
        sev_counts[c['severity']] = sev_counts.get(c['severity'], 0) + 1

    monthly = {}
    for c in active_crashes:
        try:
            month = datetime.strptime(str(c['date']), "%Y-%m-%d").month
        except Exception:
            continue
        key = (month, c['severity'])
        monthly[key] = monthly.get(key, 0) + 1
    monthly_rows = [dict(month=k[0], severity=k[1], count=v) for k, v in monthly.items()]

    return jsonify(dict(
        severity_pie=[dict(severity=k, count=v) for k, v in sev_counts.items()],
        monthly=monthly_rows,
    ))


@api.route("/crashes", methods=["POST"])
def add_crash():
    body = request.get_json(force=True) or {}
    try:
        segment_id = int(body["segment_id"])
        severity = body["severity"]
        crash_date = body.get("date") or str(datetime.now().date())
        crash_time = body.get("time") or _parse_time(None)
        description = body.get("description") or f"{severity} crash"
    except (KeyError, ValueError):
        return jsonify(error="segment_id and severity are required"), 400

    crash_id = db.add_crash(segment_id, severity, crash_date, crash_time, description)
    return jsonify(success=True, crash_id=crash_id)


@api.route("/crashes/export")
def export_crashes():
    df, *_ = pred.compute_state(datetime.now().date(), _parse_time(None))
    crashes = db.get_all_crashes()
    name_lookup = df.set_index('segment_id')[['road_name', 'human_segment_id']].to_dict('index')
    for c in crashes:
        info = name_lookup.get(int(c['segment_id']), {})
        c['road_name'] = info.get('road_name', '—')
        c['human_segment_id'] = info.get('human_segment_id', '—')
    cdf = pd.DataFrame(crashes, columns=['crash_id', 'human_segment_id', 'road_name', 'severity', 'date', 'time', 'description'])
    csv_data = cdf.sort_values('crash_id', ascending=False).to_csv(index=False)
    return Response(csv_data, mimetype="text/csv",
                     headers={"Content-Disposition": "attachment;filename=crash_log.csv"})


# ─── TAB 6 — Hazard Management ─────────────────────────────────────────────
@api.route("/hazards")
def list_hazards():
    sel_date, sel_time = _date_time_from_request()
    df, crashes, hazards, active_crashes = pred.compute_state(sel_date, sel_time)
    name_lookup = df.set_index('segment_id')[['road_name', 'human_segment_id']].to_dict('index')

    active, inactive = [], []
    for hz in hazards:
        info = name_lookup.get(int(hz['segment_id']), {})
        hz = dict(hz)
        hz['road_name'] = info.get('road_name', '—')
        hz['human_segment_id'] = info.get('human_segment_id', '—')
        try:
            hz_date = datetime.strptime(str(hz['date']), "%Y-%m-%d").date()
            start = datetime.strptime(str(hz['start_time']), "%H:%M").time()
            end = datetime.strptime(str(hz['end_time']), "%H:%M").time()
            now_t = datetime.strptime(sel_time, "%H:%M").time()
            is_active = (hz_date == sel_date) and pred.is_time_in_range(start, end, now_t)
        except Exception:
            is_active = False
        (active if is_active else inactive).append(hz)

    return jsonify(dict(active=active, inactive=inactive))


@api.route("/hazards", methods=["POST"])
def add_hazard():
    body = request.get_json(force=True) or {}
    try:
        segment_id = int(body["segment_id"])
        hazard_type = body["hazard_type"]
        start_time = body["start_time"]
        end_time = body["end_time"]
        hz_date = body.get("date") or str(datetime.now().date())
        temp_speed = body.get("temp_speed")
        description = body.get("description") or hazard_type
    except (KeyError, ValueError):
        return jsonify(error="segment_id, hazard_type, start_time, end_time are required"), 400

    if not temp_speed:
        df = pred._SOURCE_DF
        row = df[df['segment_id'] == segment_id]
        road_type = row['road_type'].iloc[0] if len(row) else ""
        temp_speed = pred.default_hazard_speed(road_type)

    hazard_id = db.add_hazard(segment_id, hazard_type, start_time, end_time, hz_date,
                               float(temp_speed), description)
    return jsonify(success=True, hazard_id=hazard_id)


@api.route("/hazards/<int:hazard_id>", methods=["DELETE"])
def remove_hazard(hazard_id):
    db.delete_hazard(hazard_id)
    return jsonify(success=True)


@api.route("/hazards/default-speed")
def hazard_default_speed():
    road_type = request.args.get("road_type", "")
    return jsonify(default_speed=pred.default_hazard_speed(road_type))


# ─── TAB 7 — Advanced Analytics ─────────────────────────────────────────────
@api.route("/analytics/advanced")
def analytics_advanced():
    sel_date, sel_time = _date_time_from_request()
    df, *_ = pred.compute_state(sel_date, sel_time)

    box = df[["road_type", "road_risk_score", "segment_id"]]
    scatter1 = df[["infrastructure_score", "final_safe_speed", "ai_risk_label", "road_risk_score", "segment_id"]]
    scatter2 = df[["exposure_score", "crash_risk_score", "hotspot_category", "hotspot_score", "segment_id"]]

    hours = list(range(24))
    road_types_u = df['road_type'].unique()[:6]
    heat_z = []
    for rt in road_types_u:
        rt_df = df[df['road_type'] == rt]
        row_vals = [round(rt_df.apply(lambda r: pred.temporal_exposure(r, h), axis=1).mean(), 1) for h in hours]
        heat_z.append(row_vals)

    top_safe = df.nsmallest(10, 'road_risk_score')[
        ['segment_id', 'road_type', 'final_safe_speed', 'road_risk_score', 'infrastructure_score', 'exposure_score']]

    summary = df.groupby('road_type').agg(
        Segments=('segment_id', 'count'),
        Avg_Risk=('road_risk_score', 'mean'),
        Avg_Safe_Speed=('final_safe_speed', 'mean'),
        Avg_Infrastructure=('infrastructure_score', 'mean'),
        Avg_Exposure=('exposure_score', 'mean'),
        Avg_Hotspot=('hotspot_score', 'mean'),
        Fatal_Crashes=('fatal_crashes', 'sum'),
    ).round(1).reset_index()

    return jsonify(dict(
        box=records(box),
        scatter1=records(scatter1),
        scatter2=records(scatter2),
        heatmap=dict(x=[f"{h:02d}:00" for h in hours], y=list(road_types_u), z=heat_z),
        top_safe=records(top_safe),
        summary=records(summary),
    ))


# ─── TAB 8 — Data Table ─────────────────────────────────────────────────────
@api.route("/segments/table")
def segments_table():
    sel_date, sel_time = _date_time_from_request()
    filt = _filters_from_request()
    df, *_ = pred.compute_state(sel_date, sel_time)
    df_f = pred.apply_filters(df, **filt).sort_values('road_risk_score', ascending=False)
    cols = [c for c in TABLE_COLUMNS if c in df_f.columns]
    rows = records(df_f, cols)
    for row in rows:
        if row.get('ai_risk_probability') is not None:
            row['ai_risk_probability'] = f"{row['ai_risk_probability'] * 100:.1f}%"
    return jsonify(dict(rows=rows, total=len(rows)))


@api.route("/export/filtered")
def export_filtered():
    sel_date, sel_time = _date_time_from_request()
    filt = _filters_from_request()
    df, *_ = pred.compute_state(sel_date, sel_time)
    df_f = pred.apply_filters(df, **filt)
    csv_data = df_f.to_csv(index=False)
    return Response(csv_data, mimetype="text/csv",
                     headers={"Content-Disposition": "attachment;filename=filtered_predictions.csv"})


@api.route("/export/full")
def export_full():
    sel_date, sel_time = _date_time_from_request()
    df, *_ = pred.compute_state(sel_date, sel_time)
    csv_data = df.to_csv(index=False)
    return Response(csv_data, mimetype="text/csv",
                     headers={"Content-Disposition": "attachment;filename=full_predictions.csv"})


# ─── Standalone quick-predict API (Step 5 of the migration brief) ─────────
@api.route("/predict", methods=["POST"])
def predict():
    body = request.get_json(force=True) or {}
    try:
        infra = float(body["infrastructure_score"])
        exposure = float(body["exposure_score"])
        crash_risk = float(body["crash_risk_score"])
        op_speed = float(body["operating_speed"])
    except (KeyError, ValueError, TypeError):
        return jsonify(error="infrastructure_score, exposure_score, crash_risk_score, "
                              "operating_speed are required numeric fields"), 400

    recommended = pred.predict_quick(infra, exposure, crash_risk, op_speed)
    return jsonify(recommended_safe_speed=recommended)


# ─── Road Network (Detection 9) stats endpoint ───────────────────────────
@api.route("/road-network/stats")
def road_network_stats():
    """Returns summary stats about the Detection 9 road network layer."""
    import os, json
    road_net_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "road_network", "bengaluru_road_segments.geojson"
    )
    try:
        with open(road_net_path) as f:
            rn = json.load(f)
        feats = rn.get("features", [])
        road_classes = {}
        total_length = 0
        for feat in feats:
            rc = feat["properties"].get("road_class", "Unknown")
            road_classes[rc] = road_classes.get(rc, 0) + 1
            total_length += feat["properties"].get("length_m", 0)
        return jsonify(
            total_segments=len(feats),
            road_classes=road_classes,
            total_length_km=round(total_length / 1000, 1),
            source="OSMnx / OpenStreetMap",
            pipeline="Detection 9"
        )
    except Exception as e:
        return jsonify(error=str(e)), 500


# ─── Weather Intelligence API ─────────────────────────────────────────────

@api.route("/weather/summary")
def weather_summary():
    """Fleet-wide weather summary for the Weather Intelligence tab."""
    return jsonify(wx.get_summary_stats())


@api.route("/weather/segments")
def weather_segments():
    """Per-segment weather data with weather-adjusted speed."""
    sel_date, sel_time = _date_time_from_request()
    df, crashes, hazards, active_crashes = pred.compute_state(sel_date, sel_time)
    all_wx = wx.get_all_weather()
    result = []
    for _, r in df.iterrows():
        sid = int(r['segment_id'])
        base_speed = int(r.get('final_safe_speed', r.get('recommended_safe_speed', 30)))
        road_type = r['road_type']
        w = all_wx.get(sid, {})
        reduction = w.get('speed_reduction', 0)
        min_speed = wx.ROAD_TYPE_MIN_SPEED.get(road_type, 20)
        adjusted = max(base_speed - reduction, min_speed)
        result.append(dict(
            segment_id=sid,
            human_segment_id=r['human_segment_id'],
            road_name=r['road_name'],
            road_type=road_type,
            base_safe_speed=base_speed,
            rainfall_mmhr=w.get('rainfall_mmhr', 0.0),
            weather_condition=w.get('condition', 'Clear / Sunny'),
            weather_icon=w.get('icon', '☀'),
            weather_color=w.get('color', '#fbbf24'),
            speed_reduction=reduction,
            weather_adjusted_speed=adjusted,
            last_updated=w.get('last_updated', '--:--'),
        ))
    return jsonify(result)
