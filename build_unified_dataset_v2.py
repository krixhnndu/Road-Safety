"""
build_unified_dataset_v2.py
Second revision, applying the segmentation/exposure/congestion review:

  1. Segment count reduced to ~1,112 (from 4,966) via a proper length
     hierarchy + real intersection-based breakpoints — see
     bangalore_data_v2/01_generate_geometry_v2.py.
  2. Every segment is single-road-class (NH+Urban mixing structurally
     impossible — enforced and verified).
  3. human_tolerance_limit now comes from VISION ZERO EXPOSURE TIERS
     (Significant Pedestrian Interaction / Side Impact Potential /
     Separated Traffic) instead of a rigid "POI within radius -> 30 km/h"
     rule.
  4. New Traffic Congestion Module: Congestion Index from expected vs.
     current vs. variance, with smoothing/tapering into the PREVIOUS
     segment along the same corridor (not just the congested segment).
  5. Fixed a latent start_km/end_km bug — the old groupby("road_name") was
     a no-op since road_name was unique per segment; now grouped by the
     correct corridor_base/corridor_seq.

Plus everything from the first revision (misalignment-first scoring,
crash_risk_score as validation-only, standardized road taxonomy, etc.)
"""
import numpy as np
import pandas as pd
import json

rng = np.random.default_rng(123)
SRC = "/home/claude/build/bangalore_data_v2"
OUT = "/home/claude/build/road-main"

road = pd.read_csv(f"{SRC}/road_network.csv")
gps = pd.read_csv(f"{SRC}/gps_probe_data.csv")
mapillary = pd.read_csv(f"{SRC}/mapillary_imagery.csv")
exposure = pd.read_csv(f"{SRC}/exposure_landuse.csv")
scores = pd.read_csv(f"{SRC}/scores_master.csv")
poi = pd.read_csv(f"{SRC}/poi_infrastructure.csv")
crash_db = pd.read_csv(f"{SRC}/crash_database.csv")
hazard_db = pd.read_csv(f"{SRC}/hazard_database.csv")

poi_wide = poi.pivot_table(index="segment_id", columns="poi_category",
                            values="count", aggfunc="sum").reset_index()

df = (road
      .merge(gps, on="segment_id")
      .merge(mapillary, on="segment_id")
      .merge(exposure, on="segment_id")
      .merge(scores.drop(columns=["road_name", "start_km_helper", "functional_class",
                                   "urban_rural_flag", "posted_speed_limit",
                                   "operating_speed_mean", "speed_p85", "ptw_share"]), on="segment_id")
      .merge(poi_wide, on="segment_id"))

# ── crash aggregation (validation-only layer) ──────────────────────────────
crash_count = crash_db.groupby("segment_id").size().rename("crash_count")
fatal_count = crash_db[crash_db.severity == "Fatal"].groupby("segment_id").size().rename("fatal_crashes")
df = df.merge(crash_count, on="segment_id", how="left").merge(fatal_count, on="segment_id", how="left")
df["crash_count"] = df["crash_count"].fillna(0).astype(int)
df["fatal_crashes"] = df["fatal_crashes"].fillna(0).astype(int)
df["blackspot_flag"] = np.where((df["crash_risk_score"] >= 50) | (df["fatal_crashes"] > 0), "Yes", "No")

# ── standardized field renames matching the platform's working schema ─────
df["road_type"] = df["functional_class"]  # Highway / Arterial / Collector / Local
df["schools_count"] = df.get("schools_colleges", pd.Series(0, index=df.index)).fillna(0).astype(int)
df["lighting_quality"] = np.where(df["lighting_presence"], "Good", "Poor")
df["roadside_hazards"] = df["roadside_hazard_level"]
df["ptw_share_pct"] = (df["ptw_share"] * 100).round(1)

# compliance kept ONLY as a display/diagnostic field — no longer feeds hotspot_score
df["speed_compliance_rate"] = (1 - np.clip((df["speed_p85"] - df["posted_speed_limit"]) /
                                            df["posted_speed_limit"], 0, None)).clip(0, 1).round(2)
df["speed_violation_score"] = (100 - df["speed_compliance_rate"] * 100).round(1)  # display-only now

# ── start/end km per road (cumulative along the actual corridor, using
# corridor_base/corridor_seq — grouping by road_name alone was a latent
# no-op bug, since road_name is unique per individual segment) ────────────
df = df.sort_values(["corridor_base", "corridor_seq"]).reset_index(drop=True)
df["start_km"] = df.groupby("corridor_base")["segment_length_km"].cumsum() - df["segment_length_km"]
df["end_km"] = df["start_km"] + df["segment_length_km"]

# ── IDs ─────────────────────────────────────────────────────────────────
df["human_segment_id"] = [f"SEG-{i:05d}" for i in df["segment_id"]]
df["internal_id"] = [f"SEG_{i:09d}" for i in df["segment_id"]]

# ═══════════════════════════════════════════════════════════════════════
# ML MODEL: predicts MISALIGNMENT category. crash_risk_score intentionally
# EXCLUDED from features — it is a lagging/behavioral signal, not a
# determinant of whether the posted limit itself is appropriate.
# ═══════════════════════════════════════════════════════════════════════
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import joblib

FEATURES = ["road_function_score", "infrastructure_score", "exposure_score",
            "human_tolerance_limit", "operating_speed_score"]
LABELS = ["Aligned", "Moderate Misalignment", "High Misalignment", "Critical Misalignment"]
label_map = {l: i for i, l in enumerate(LABELS)}
df["misalignment_category"] = pd.Categorical(df["misalignment_category"], categories=LABELS)
y = df["misalignment_category"].map(label_map).astype(int)
X = df[FEATURES]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

rf = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42, class_weight="balanced")
rf.fit(X_train, y_train)
gb = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.08, random_state=42)
gb.fit(X_train, y_train)

metrics_rows = []
for name, model in [("Random Forest", rf), ("Gradient Boosting", gb)]:
    pred = model.predict(X_test)
    cv = cross_val_score(model, X, y, cv=5).mean()
    metrics_rows.append(dict(
        model=name,
        accuracy=accuracy_score(y_test, pred),
        precision=precision_score(y_test, pred, average="weighted", zero_division=0),
        recall=recall_score(y_test, pred, average="weighted", zero_division=0),
        f1=f1_score(y_test, pred, average="weighted", zero_division=0),
        cv_acc=cv,
    ))
metrics_df = pd.DataFrame(metrics_rows)
metrics_df.to_csv(f"{OUT}/model_metrics.csv", index=False)
print(metrics_df)

joblib.dump(rf, f"{OUT}/random_forest_model.pkl")
joblib.dump(gb, f"{OUT}/gradient_boosting_model.pkl")  # honestly named (old file was mislabeled "xgboost")

feat_imp = pd.DataFrame({
    "feature": FEATURES,
    "rf_importance": rf.feature_importances_,
    "gb_importance": gb.feature_importances_,
}).sort_values("gb_importance", ascending=False)
feat_imp.to_csv(f"{OUT}/feature_importance.csv", index=False)
print(feat_imp)

# Apply best model (GB, by F1) across the FULL dataset for live display
best = gb if metrics_df.set_index("model").loc["Gradient Boosting", "f1"] >= metrics_df.set_index("model").loc["Random Forest", "f1"] else rf
proba = best.predict_proba(X)
pred_classes = best.predict(X)
df["ai_risk_label"] = [LABELS[c] for c in pred_classes]
df["ai_risk_probability"] = [proba[i][pred_classes[i]] for i in range(len(df))]
df["prob_low_risk"] = proba[:, 0]       # "Aligned"
df["prob_medium_risk"] = proba[:, 1]    # "Moderate Misalignment"
df["prob_high_risk"] = proba[:, 2]      # "High Misalignment"
df["prob_critical_risk"] = proba[:, 3]  # "Critical Misalignment"

# road_risk_score: weighted expectation over class probs, severity-anchored
ANCHORS = [10, 40, 75, 100]
df["road_risk_score"] = (
    df["prob_low_risk"]*ANCHORS[0] + df["prob_medium_risk"]*ANCHORS[1] +
    df["prob_high_risk"]*ANCHORS[2] + df["prob_critical_risk"]*ANCHORS[3]
).round().astype(int)

# ═══════════════════════════════════════════════════════════════════════
# RECOMMENDED SPEED — now genuinely linked to misalignment, not opaque.
# ai_recommended_speed = the lower of: 85th-percentile observed operating
# speed (what the road is actually carrying) and human_tolerance_limit
# (Safe System threshold for the road's function/VRU mix).
# ═══════════════════════════════════════════════════════════════════════
df["ai_recommended_speed"] = np.minimum(df["speed_p85"], df["human_tolerance_limit"]).round().astype(int)
df["recommended_safe_speed"] = df["ai_recommended_speed"]
df["original_safe_speed"] = df["recommended_safe_speed"]

# ═══════════════════════════════════════════════════════════════════════
# TRAFFIC CONGESTION MODULE — propagation/smoothing.
# A congested segment gets its recommended speed pulled down toward its
# actually-observed operating speed (no point "recommending" a speed traffic
# already can't reach). The PREVIOUS segment along the same corridor then
# gets a smaller, smoothing reduction — tapering speed down in advance of
# the congestion point rather than presenting drivers with a cliff-edge drop.
# Example from the brief: Segment A expected=60, current=20 -> congested;
# recommended(A) drops toward 20; the previous segment's recommendation
# eases down (e.g. toward 40) rather than staying at its original value,
# but never below its own misalignment-based floor.
# ═══════════════════════════════════════════════════════════════════════
df = df.sort_values(["corridor_base", "corridor_seq"]).reset_index(drop=True)

congested_mask = df["congestion_category"].isin(["Moderate", "Severe"])
congestion_adjusted_speed = np.maximum(
    df["operating_speed_mean"].round().astype(int),
    (df["human_tolerance_limit"] * 0.5).round().astype(int)  # never recommend below half the safety floor
)
df.loc[congested_mask, "recommended_safe_speed"] = congestion_adjusted_speed[congested_mask]

# smoothing into the previous segment of the same corridor
df["_prev_seg_idx"] = df.groupby("corridor_base").cumcount()
shifted_congested = congested_mask.shift(-1).fillna(False)
same_corridor_as_next = df["corridor_base"] == df["corridor_base"].shift(-1)
taper_mask = shifted_congested & same_corridor_as_next & (~congested_mask)
next_seg_speed = df["recommended_safe_speed"].shift(-1)
taper_target = ((df["recommended_safe_speed"] + next_seg_speed) / 2).round().astype("Int64")
# never taper below the segment's own misalignment-derived floor (don't
# create a NEW misalignment by smoothing too aggressively)
taper_floor = (df["human_tolerance_limit"] * 0.7).round().astype(int)
df.loc[taper_mask, "recommended_safe_speed"] = np.maximum(
    taper_target[taper_mask].astype(int), taper_floor[taper_mask])

df["congestion_smoothed"] = taper_mask
df = df.drop(columns=["_prev_seg_idx"])

# ═══════════════════════════════════════════════════════════════════════
# HOTSPOT SCORE — reframed: misalignment is now the dominant weight;
# crash history is a smaller, secondary VALIDATION weight; the old
# speed_violation_score (driver-behavior) weight is REMOVED entirely.
#   old: 0.40 crash + 0.25 exposure + 0.20 violation(driver behavior) + 0.15 road_risk
#   new: 0.50 misalignment + 0.25 exposure + 0.15 crash(validation) + 0.10 infra-deficit
# ═══════════════════════════════════════════════════════════════════════
df["hotspot_score"] = (
    0.50 * df["misalignment_score"] +
    0.25 * df["exposure_score"] +
    0.15 * df["crash_risk_score"] +
    0.10 * (100 - df["infrastructure_score"])
).round(1)

def hotspot_cat(v):
    if v >= 75: return "Severe Hotspot"
    if v >= 50: return "High Risk"
    if v >= 25: return "Moderate Risk"
    return "Safe"
df["hotspot_category"] = df["hotspot_score"].apply(hotspot_cat)

# speed_safety_score recomputed consistently (was already in scores_master,
# kept here so it's derived from the SAME final misalignment/crash values)
df["speed_safety_score"] = (100 - (df["misalignment_score"]*0.6 +
                                    df["crash_risk_score"]*0.2 +
                                    (100 - df["infrastructure_score"])*0.2)).clip(0, 100).round(1)

# ── top_ai_factors: short human-readable summary (mirrors build_factors() logic) ──
def top_factors(row):
    tags = []
    if row["misalignment_score"] >= 50: tags.append("Speed Limit Misaligned")
    if row["exposure_tier"] == "Significant Pedestrian Interaction": tags.append("High Pedestrian Interaction")
    if row.get("congestion_category") in ("Moderate", "Severe"): tags.append("Active Congestion")
    if row.get("congestion_smoothed"): tags.append("Approach to Congestion (Tapered)")
    if row["crash_risk_score"] > 50: tags.append("Crash History")
    if row["infrastructure_score"] < 35: tags.append("Poor Infrastructure")
    if row["human_tolerance_limit"] < row["posted_speed_limit"]: tags.append("Above Human Tolerance Limit")
    if not tags: tags = ["Meets Safe System Standards"]
    return " | ".join(tags[:3])
df["top_ai_factors"] = df.apply(top_factors, axis=1)

# ── final column selection matching the platform's working schema ────────
KEEP = ["segment_id", "road_name", "road_type", "road_risk_score", "ai_risk_label",
        "ai_risk_label", "ai_risk_probability", "prob_low_risk", "prob_medium_risk",
        "prob_high_risk", "prob_critical_risk", "ai_recommended_speed",
        "recommended_safe_speed", "road_function_score", "infrastructure_score",
        "exposure_score", "human_tolerance_limit", "operating_speed_score",
        "crash_risk_score", "start_km", "end_km", "start_lat", "start_lon",
        "end_lat", "end_lon", "geometry", "posted_speed_limit",
        "pedestrian_exposure_score", "blackspot_flag", "crash_count", "fatal_crashes",
        "schools_count", "lighting_quality", "roadside_hazards", "intersection_density",
        "speed_compliance_rate", "speed_violation_score", "hotspot_score",
        "hotspot_category", "human_segment_id", "internal_id", "speed_safety_score",
        "original_safe_speed", "misalignment_score", "misalignment_category",
        "speed_p85", "ptw_share_pct", "exposure_tier", "urban_rural_flag",
        "lane_count", "median_presence", "land_use_type", "top_ai_factors",
        "corridor_base", "corridor_seq", "congestion_index", "congestion_category",
        "congestion_smoothed", "operating_speed_mean"]
KEEP = list(dict.fromkeys(KEEP))  # dedupe, preserve order
df["risk_category"] = df["ai_risk_label"]
KEEP.insert(3, "risk_category")
final = df[KEEP].copy()
final.to_csv(f"{OUT}/unified_platform_data.csv", index=False)
print("Final dataset:", final.shape)

# ── GeoJSON for the map layer ──────────────────────────────────────────
features = []
for _, r in final.iterrows():
    features.append({
        "type": "Feature",
        "properties": {"segment_id": int(r["segment_id"])},
        "geometry": {
            "type": "LineString",
            "coordinates": [[r["start_lon"], r["start_lat"]], [r["end_lon"], r["end_lat"]]],
        },
    })
with open(f"{OUT}/ai_road_segments_unified.geojson", "w") as f:
    json.dump({"type": "FeatureCollection", "features": features}, f)

# ── carry over crash / hazard DBs (segment_id space now matches) ─────────
crash_db.to_csv(f"{OUT}/crash_database.csv", index=False)
hazard_db.to_csv(f"{OUT}/hazard_database.csv", index=False)

print("Done. risk label distribution:")
print(final["ai_risk_label"].value_counts())
print("hotspot category distribution:")
print(final["hotspot_category"].value_counts())

# ═══════════════════════════════════════════════════════════════════════
# Regenerate dashboard image assets from the ACTUAL new model/data
# (old PNGs were for the previous 6-feature, crash-inclusive model and
# would otherwise be silently stale/misleading).
# ═══════════════════════════════════════════════════════════════════════
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix

plt.style.use("dark_background")

# 1. feature_importance.png
fig, ax = plt.subplots(figsize=(8.5, 4.2))
imp = feat_imp.sort_values("gb_importance")
ax.barh(imp["feature"], imp["gb_importance"], color="#60a5fa", label="Gradient Boosting")
ax.barh(imp["feature"], imp["rf_importance"], color="#f97316", alpha=0.5, label="Random Forest", height=0.4)
ax.set_xlabel("Gini Importance")
ax.set_title("Feature Importance — Misalignment Classifier\n(crash_risk_score intentionally excluded)", fontsize=11)
ax.legend()
fig.tight_layout()
fig.savefig(f"{OUT}/feature_importance.png", dpi=110, facecolor="#0a1628")
plt.close(fig)

# 2. model_evaluation.png — confusion matrices for both models
fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
for ax, (name, model) in zip(axes, [("Random Forest", rf), ("Gradient Boosting", gb)]):
    pred = model.predict(X_test)
    cm = confusion_matrix(y_test, pred, labels=[0, 1, 2, 3])
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(4)); ax.set_yticks(range(4))
    short = ["Aligned", "Moderate", "High", "Critical"]
    ax.set_xticklabels(short, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(short, fontsize=8)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
    ax.set_title(name, fontsize=10)
    for i in range(4):
        for j in range(4):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                     color="white" if cm[i, j] < cm.max()/2 else "black", fontsize=8)
fig.suptitle("Confusion Matrices — Misalignment Category (held-out 20% test set)")
fig.tight_layout()
fig.savefig(f"{OUT}/model_evaluation.png", dpi=110, facecolor="#0a1628")
plt.close(fig)

# 3. shap_summary.png — honestly a permutation-importance plot, NOT SHAP
from sklearn.inspection import permutation_importance
perm = permutation_importance(gb, X_test, y_test, n_repeats=10, random_state=42)
order = perm.importances_mean.argsort()
fig, ax = plt.subplots(figsize=(7, 4.2))
ax.boxplot(perm.importances[order].T, vert=False, tick_labels=np.array(FEATURES)[order])
ax.set_title("Permutation Importance (Gradient Boosting) — NOT SHAP values")
ax.set_xlabel("Decrease in accuracy when feature is shuffled")
fig.tight_layout()
fig.savefig(f"{OUT}/shap_summary.png", dpi=110, facecolor="#0a1628")
plt.close(fig)

print("Regenerated feature_importance.png, model_evaluation.png, shap_summary.png")
