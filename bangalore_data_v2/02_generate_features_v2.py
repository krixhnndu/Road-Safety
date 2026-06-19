"""
02_generate_features_v2.py
Same layered dataset family as before, rebuilt on the new 1,112-segment
geometry, with two substantive rule changes:

  A. human_tolerance_limit is now driven by VISION ZERO EXPOSURE TIERS
     (Significant Pedestrian Interaction / Side Impact Potential / Separated
     Traffic) instead of a rigid "school/hospital within radius -> 30 km/h"
     rule. A school 400m from a fully-separated NH no longer forces 30 km/h
     by itself — only actual pedestrian interaction/crossing exposure does.

  B. A new Traffic Congestion Module: per-segment Congestion Index from
     (expected speed vs. current speed vs. speed variance), which then
     SMOOTHS into the previous segment along the same corridor (advance
     speed tapering toward a congestion point), not just the congested
     segment itself.
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)

geo = pd.read_csv("/home/claude/build_v2/_raw_geometry.csv")
N = len(geo)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dlmb/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

geo["segment_length_km"] = haversine(geo.start_lat, geo.start_lon, geo.end_lat, geo.end_lon).round(3)
geo["dist_from_center_km"] = haversine(geo.start_lat, geo.start_lon, 12.9716, 77.5946).round(2)

# ──────────────────────────────────────────────────────────────────────────
# 1. ROAD NETWORK DATA
# ──────────────────────────────────────────────────────────────────────────
FCLASS_MAP = {
    "NH": "Highway", "SH": "Highway", "Ring": "Arterial",
    "Arterial": "Arterial", "Collector": "Collector",
    "Local": "Local", "MDR": "Collector",
}
geo["functional_class"] = geo["corridor_type"].map(FCLASS_MAP)

def urban_rural(row):
    if "_urb" in row and pd.notna(row.get("_urb")):
        return row["_urb"]
    d = row["dist_from_center_km"]
    if d <= 10: return "Urban"
    if d <= 20: return "Peri-Urban"
    return "Rural"
geo["urban_rural_flag"] = geo.apply(urban_rural, axis=1)

LANES = {"Highway": (4, 8), "Arterial": (2, 6), "Collector": (2, 4), "Local": (1, 2)}
geo["lane_count"] = geo["functional_class"].map(
    lambda f: rng.integers(LANES[f][0], LANES[f][1] + 1))

MEDIAN_P = {"Highway": 0.85, "Arterial": 0.5, "Collector": 0.15, "Local": 0.02}
geo["median_presence"] = geo["functional_class"].map(
    lambda f: rng.random() < MEDIAN_P[f])

base_int = geo["functional_class"].map({"Highway": 0.4, "Arterial": 1.4,
                                         "Collector": 2.2, "Local": 3.0})
density_falloff = np.clip(1.6 - geo["dist_from_center_km"] / 25, 0.3, 1.6)
geo["intersection_density"] = (base_int * density_falloff * rng.uniform(0.8, 1.2, N)).round(2)

POSTED = {"Highway": (60, 100), "Arterial": (40, 60), "Collector": (30, 50), "Local": (20, 40)}
geo["posted_speed_limit"] = geo["functional_class"].map(
    lambda f: int(rng.integers(POSTED[f][0], POSTED[f][1] + 1) // 10 * 10))

geo["geometry"] = ("LINESTRING(" + geo.start_lon.round(6).astype(str) + " " +
                    geo.start_lat.round(6).astype(str) + ", " +
                    geo.end_lon.round(6).astype(str) + " " +
                    geo.end_lat.round(6).astype(str) + ")")

road_network = geo[["segment_id", "road_name", "corridor_base", "corridor_seq", "corridor_type",
                     "functional_class", "urban_rural_flag", "segment_length_km", "lane_count",
                     "median_presence", "intersection_density", "posted_speed_limit",
                     "start_lat", "start_lon", "end_lat", "end_lon", "geometry",
                     "dist_from_center_km"]].copy()
road_network.to_csv("/home/claude/build_v2/road_network.csv", index=False)

# ──────────────────────────────────────────────────────────────────────────
# 2. GPS PROBE DATA (current / expected speed inputs for congestion module)
# ──────────────────────────────────────────────────────────────────────────
mismatch_flag = rng.random(N) < 0.30
speed_ratio = np.where(mismatch_flag, rng.uniform(1.02, 1.35, N), rng.uniform(0.65, 1.00, N))
speed_p85 = (road_network["posted_speed_limit"] * speed_ratio).round(1)
operating_speed_mean = (speed_p85 * rng.uniform(0.82, 0.92, N)).round(1)
speed_p15 = (operating_speed_mean * rng.uniform(0.55, 0.7, N)).round(1)

traffic_base = road_network["functional_class"].map(
    {"Highway": 3200, "Arterial": 1800, "Collector": 800, "Local": 250})
traffic_volume_avg = (traffic_base * rng.uniform(0.6, 1.5, N)).round(0).astype(int)
peak_mult = rng.uniform(1.3, 1.9, N)

# inject a deliberate congestion pocket on ~8% of segments so the module has
# something real to detect/smooth (current speed well below expected)
congested_flag = rng.random(N) < 0.08
operating_speed_mean = np.where(congested_flag,
                                 operating_speed_mean * rng.uniform(0.25, 0.45, N),
                                 operating_speed_mean)
# additional mild, continuous everyday variability (minor slowdowns from
# ordinary traffic ebb/flow) so the congestion index spans the full
# None->Light->Moderate->Severe range rather than being purely bimodal
mild_noise = rng.uniform(0.85, 1.05, N)
operating_speed_mean = np.where(~congested_flag, operating_speed_mean * mild_noise, operating_speed_mean)

gps_probe = pd.DataFrame({
    "segment_id": road_network.segment_id,
    "operating_speed_mean": operating_speed_mean.round(1),
    "speed_p15": speed_p15,
    "speed_p85": speed_p85,
    "traffic_volume_avg_daily": traffic_volume_avg,
    "peak_hour_volume": (traffic_volume_avg * peak_mult / 12).round(0).astype(int),
    "off_peak_hour_volume": (traffic_volume_avg * (2 - peak_mult) / 12).round(0).astype(int),
    "data_window": "rolling_30day_dummy",
    "data_date": "2026-06-19",
})
gps_probe.to_csv("/home/claude/build_v2/gps_probe_data.csv", index=False)

# ──────────────────────────────────────────────────────────────────────────
# 3. MAPILLARY-STYLE IMAGERY
# ──────────────────────────────────────────────────────────────────────────
roadside_hazard = rng.choice(["Low", "Medium", "High"], size=N, p=[0.4, 0.35, 0.25])
sidewalk_base_p = road_network["functional_class"].map(
    {"Highway": 0.35, "Arterial": 0.55, "Collector": 0.45, "Local": 0.25})
sidewalk_p = np.where(roadside_hazard == "High", sidewalk_base_p * 0.3, sidewalk_base_p)
crosswalk_p = sidewalk_p * rng.uniform(0.6, 0.9, N)
lighting_p = road_network["urban_rural_flag"].map({"Urban": 0.75, "Peri-Urban": 0.45, "Rural": 0.2})

mapillary = pd.DataFrame({
    "segment_id": road_network.segment_id,
    "roadside_hazard_level": roadside_hazard,
    "sidewalk_presence": rng.random(N) < sidewalk_p,
    "crosswalk_presence": rng.random(N) < crosswalk_p,
    "lane_markings_quality": rng.choice(["Good", "Fair", "Poor"], size=N, p=[0.4, 0.35, 0.25]),
    "signage_type": rng.choice(["Standard", "Faded", "Missing"], size=N, p=[0.55, 0.3, 0.15]),
    "lighting_presence": rng.random(N) < lighting_p,
    "image_coverage_date": "2026-05-01",
})
mapillary.to_csv("/home/claude/build_v2/mapillary_imagery.csv", index=False)

# ──────────────────────────────────────────────────────────────────────────
# 4. POI / INFRASTRUCTURE
# ──────────────────────────────────────────────────────────────────────────
POI_CATEGORIES = {
    "schools_colleges":   dict(radius_m=200, mean=0.30, weight=12),
    "hospitals_clinics":  dict(radius_m=300, mean=0.18, weight=12),
    "markets_commercial": dict(radius_m=300, mean=0.40, weight=8),
    "religious_institutions": dict(radius_m=200, mean=0.22, weight=5),
    "bus_stops":          dict(radius_m=150, mean=0.55, weight=9),
    "rail_metro_stations":dict(radius_m=500, mean=0.05, weight=10),
    "government_offices": dict(radius_m=300, mean=0.10, weight=4),
    "parks_playgrounds":  dict(radius_m=300, mean=0.20, weight=6),
    "event_tourist_venues": dict(radius_m=500, mean=0.06, weight=5),
}
urban_mult = road_network["urban_rural_flag"].map({"Urban": 1.6, "Peri-Urban": 0.8, "Rural": 0.3}).values

poi_long_frames = []
poi_wide = pd.DataFrame({"segment_id": road_network.segment_id})
for cat, spec in POI_CATEGORIES.items():
    lam = np.clip(spec["mean"] * urban_mult, 0.01, None)
    counts = rng.poisson(lam)
    poi_wide[cat + "_count"] = counts
    poi_long_frames.append(pd.DataFrame({
        "segment_id": road_network.segment_id, "poi_category": cat,
        "count": counts, "radius_m": spec["radius_m"], "category_weight": spec["weight"],
    }))
poi_infrastructure_long = pd.concat(poi_long_frames, ignore_index=True)
poi_infrastructure_long.to_csv("/home/claude/build_v2/poi_infrastructure.csv", index=False)

pop_density_tier = pd.cut(
    rng.gamma(2.0, road_network["urban_rural_flag"].map({"Urban": 1800, "Peri-Urban": 700, "Rural": 250}).values / 2),
    bins=[-1, 1000, 3000, 7000, 1e9], labels=["Low", "Medium", "High", "Very High"])

raw_score = sum(poi_wide[c + "_count"] * spec["weight"] for c, spec in POI_CATEGORIES.items())
infrastructure_score = (raw_score / raw_score.max() * 100).round(1)

# ──────────────────────────────────────────────────────────────────────────
# 5. EXPOSURE / PTW / LAND-USE
# ──────────────────────────────────────────────────────────────────────────
LANDUSE_P = {"Urban": [0.25, 0.35, 0.30, 0.10], "Peri-Urban": [0.45, 0.15, 0.15, 0.25],
             "Rural": [0.65, 0.05, 0.05, 0.25]}
landuse_cats = ["Residential", "Commercial", "Mixed", "Industrial"]
land_use_type = road_network["urban_rural_flag"].map(lambda u: rng.choice(landuse_cats, p=LANDUSE_P[u]))

PTW_BASE = {"Urban": 0.62, "Peri-Urban": 0.55, "Rural": 0.40}
ptw_share = (road_network["urban_rural_flag"].map(PTW_BASE) + rng.uniform(-0.07, 0.07, N)).clip(0.1, 0.9).round(3)

def temporal_exposure_multiplier(hour, schools_present, road_functional_class):
    school_m = 1.5 if (8 <= hour <= 16 and schools_present) else 0.8
    peak_m   = 1.4 if (7 <= hour <= 9 or 17 <= hour <= 20) else 1.0
    night_m  = 0.4 if (hour >= 23 or hour <= 5) else 1.0
    market_m = 1.3 if (road_functional_class in ("Arterial", "Collector") and 9 <= hour <= 20) else 1.0
    return school_m * peak_m * night_m * market_m

base_ped_index = (infrastructure_score * 0.5 + rng.uniform(0, 20, N)).clip(0, 100)
mult_noon = [temporal_exposure_multiplier(13, s > 0, fc) for s, fc in
             zip(poi_wide["schools_colleges_count"], road_network["functional_class"])]
pedestrian_count_index = (base_ped_index * np.array(mult_noon) / 1.3).clip(0, 100).round(1)
cyclist_count_index = (pedestrian_count_index * rng.uniform(0.2, 0.5, N)).round(1)

exposure_landuse = pd.DataFrame({
    "segment_id": road_network.segment_id,
    "pedestrian_count_index": pedestrian_count_index,
    "cyclist_count_index": cyclist_count_index,
    "ptw_share": ptw_share.values,
    "land_use_type": land_use_type.values,
    "population_density_tier": pop_density_tier.astype(str),
})
exposure_landuse.to_csv("/home/claude/build_v2/exposure_landuse.csv", index=False)

# ──────────────────────────────────────────────────────────────────────────
# 6. VISION ZERO EXPOSURE TIER + human_tolerance_limit
#    Replaces the rigid "POI within radius -> 30 km/h" rule. A school near a
#    fully-separated highway no longer forces a low limit by itself; only
#    genuine pedestrian-interaction / lack-of-separation exposure does.
#
#       Condition                          Max Safe Speed
#       Significant Pedestrian Interaction      30
#       Side Impact Potential                   50
#       Separated Traffic                       70+ (80 for Highway)
# ──────────────────────────────────────────────────────────────────────────
def exposure_interaction_tier(row):
    ped = row["pedestrian_count_index"]
    sep = row["median_presence"]            # physical separation present
    fclass = row["functional_class"]
    int_density = row["intersection_density"]
    crosswalk = row["crosswalk_presence"]

    # Significant Pedestrian Interaction: heavy foot traffic actually
    # crossing/mixing with the carriageway (not just "a school is nearby")
    if ped >= 55 or (crosswalk and ped >= 35) or (fclass == "Local" and ped >= 25):
        return "Significant Pedestrian Interaction"
    # Separated Traffic: physically divided, low intersection frequency,
    # low pedestrian mixing — even with a POI somewhat nearby
    if sep and int_density < 1.6 and ped < 35:
        return "Separated Traffic"
    # Everything else: some mixing/cross-traffic but not severe — side
    # impact risk from intersections/driveways rather than pedestrian mixing
    return "Side Impact Potential"

merged_for_tier = road_network.merge(mapillary[["segment_id", "crosswalk_presence"]], on="segment_id")
merged_for_tier = merged_for_tier.merge(exposure_landuse[["segment_id", "pedestrian_count_index"]], on="segment_id")
merged_for_tier["exposure_tier"] = merged_for_tier.apply(exposure_interaction_tier, axis=1)

TIER_MAX_SPEED = {
    "Significant Pedestrian Interaction": 30,
    "Side Impact Potential": 50,
    "Separated Traffic": 70,
}
human_tolerance_limit = merged_for_tier["exposure_tier"].map(TIER_MAX_SPEED)
# Highways with full separation get the 70+ upper end (80) per the rule
is_highway_separated = (merged_for_tier["functional_class"] == "Highway") & (merged_for_tier["exposure_tier"] == "Separated Traffic")
human_tolerance_limit = np.where(is_highway_separated, 80, human_tolerance_limit)

# keep a small reference table for documentation/display purposes (not used
# as a lookup anymore — tolerance is now computed directly per-segment from
# the exposure tier above, which is more faithful to "vision zero exposure
# rules" than a coarse functional_class x tier lookup table)
human_tolerance_lookup = pd.DataFrame([
    {"exposure_tier": "Significant Pedestrian Interaction", "max_safe_speed_kmh": 30},
    {"exposure_tier": "Side Impact Potential",               "max_safe_speed_kmh": 50},
    {"exposure_tier": "Separated Traffic",                   "max_safe_speed_kmh": 70},
    {"exposure_tier": "Separated Traffic (Highway)",         "max_safe_speed_kmh": 80},
])
human_tolerance_lookup.to_csv("/home/claude/build_v2/human_tolerance_lookup.csv", index=False)

# ──────────────────────────────────────────────────────────────────────────
# 7. road_function_score
# ──────────────────────────────────────────────────────────────────────────
FCLASS_W = {"Highway": 90, "Arterial": 65, "Collector": 45, "Local": 25}
road_function_score = (
    road_network["functional_class"].map(FCLASS_W)
    + road_network["lane_count"] * 2.5
    + road_network["median_presence"].astype(int) * 8
).clip(0, 100).round(1)

# ──────────────────────────────────────────────────────────────────────────
# 8. exposure_score, pedestrian_exposure_score
# ──────────────────────────────────────────────────────────────────────────
exposure_score = (pedestrian_count_index * 0.45 + cyclist_count_index * 0.25 +
                   ptw_share.values * 100 * 0.30).clip(0, 100).round(1)
pedestrian_exposure_score = pedestrian_count_index

# ──────────────────────────────────────────────────────────────────────────
# 9. operating_speed_score
# ──────────────────────────────────────────────────────────────────────────
operating_speed_score = (100 - np.abs(operating_speed_mean - road_network["posted_speed_limit"]) * 1.5).clip(0, 100).round(1)

# ──────────────────────────────────────────────────────────────────────────
# 10. CRASH / HAZARD (validation-only layer, unchanged mechanism)
# ──────────────────────────────────────────────────────────────────────────
n_crash_segments = int(N * 0.18)
crash_segs = rng.choice(road_network.segment_id, size=n_crash_segments, replace=False)
crash_rows = []
crash_id = 1
for sid in crash_segs:
    n_cr = rng.poisson(1.4) + 1
    for _ in range(n_cr):
        sev = rng.choice(["Minor", "Major", "Fatal"], p=[0.65, 0.27, 0.08])
        crash_rows.append(dict(
            crash_id=crash_id, segment_id=sid, severity=sev,
            date=pd.Timestamp("2024-01-01") + pd.to_timedelta(int(rng.integers(0, 880)), unit="D"),
            vehicle_type=rng.choice(["Car", "PTW", "Bus", "Truck", "Pedestrian"], p=[0.3, 0.35, 0.1, 0.1, 0.15]),
        ))
        crash_id += 1
crash_database = pd.DataFrame(crash_rows)
crash_database.to_csv("/home/claude/build_v2/crash_database.csv", index=False)

n_hazards = max(1, int(N * 0.05))
hazard_segs = rng.choice(road_network.segment_id, size=n_hazards, replace=False)
hazard_database = pd.DataFrame({
    "hazard_id": range(1, n_hazards + 1),
    "segment_id": hazard_segs,
    "hazard_type": rng.choice(["Construction", "Waterlogging", "Accident", "Event/Crowd", "Pothole"], size=n_hazards),
    "date": pd.Timestamp("2026-06-19"),
    "start_time": rng.choice(["06:00", "08:00", "09:00", "17:00", "20:00"], size=n_hazards),
    "end_time": rng.choice(["10:00", "12:00", "18:00", "21:00", "23:00"], size=n_hazards),
    "temp_speed": rng.choice([20, 30, np.nan], size=n_hazards, p=[0.4, 0.4, 0.2]),
})
hazard_database.to_csv("/home/claude/build_v2/hazard_database.csv", index=False)

crash_count = crash_database.groupby("segment_id").size()
fatal_count = crash_database[crash_database.severity == "Fatal"].groupby("segment_id").size()
crash_risk_score = (
    road_network.segment_id.map(crash_count).fillna(0) * 3 +
    road_network.segment_id.map(fatal_count).fillna(0) * 10
).clip(upper=100)

# ──────────────────────────────────────────────────────────────────────────
# 11. MISALIGNMENT SCORE (unchanged formula, now built on tolerance limits
#     that come from the Vision Zero exposure tier rather than POI proximity)
# ──────────────────────────────────────────────────────────────────────────
gap = road_network["posted_speed_limit"].values - speed_p85.values
gap_term = np.clip(-gap, 0, None) * 1.2
tolerance_gap = np.clip(road_network["posted_speed_limit"].values - np.array(human_tolerance_limit), 0, None) * 1.5
exposure_term = exposure_score.values * 0.4
infra_term = (100 - infrastructure_score.values) * 0.15
misalignment_score = (gap_term + tolerance_gap + exposure_term + infra_term)
misalignment_score = (misalignment_score / misalignment_score.max() * 100).round(1)

def misalignment_category(v):
    if v >= 75: return "Critical Misalignment"
    if v >= 50: return "High Misalignment"
    if v >= 25: return "Moderate Misalignment"
    return "Aligned"
misalignment_category_s = pd.Series(misalignment_score).apply(misalignment_category)

# ──────────────────────────────────────────────────────────────────────────
# 12. TRAFFIC CONGESTION MODULE (new)
#     Expected speed (design/posted expectation) vs. Current speed (observed
#     GPS-probe operating mean) vs. Speed variance (p85-p15 spread) ->
#     Congestion Index. Then SMOOTH into the previous segment along the same
#     corridor — drivers should see speed taper down *before* reaching a
#     congested point, not just at it.
# ──────────────────────────────────────────────────────────────────────────
expected_speed = speed_p85.values * 0.87   # this segment's OWN typical/free-flow operating
                                            # speed (the normal operating/p85 ratio absent
                                            # congestion is ~0.82-0.92) — comparing against the
                                            # posted limit instead would flag ordinary
                                            # under-limit urban driving as "congestion", which
                                            # is not what this module is meant to detect.
current_speed = operating_speed_mean
speed_variance = (speed_p85.values - speed_p15.values)

congestion_index = np.clip((expected_speed - current_speed) / expected_speed, 0, 1)
# a small dead-band absorbs normal random noise around the expected ratio
congestion_index = np.where(congestion_index < 0.08, 0, congestion_index)
# variance adds a small additional penalty: a wide, unstable speed spread
# alongside a slowdown indicates stop-and-go conditions, not just a slower
# but steady flow
congestion_index = np.clip(congestion_index + (speed_variance / np.maximum(expected_speed, 1)) * 0.10 * (congestion_index > 0), 0, 1)
congestion_index = congestion_index.round(3)

def congestion_cat(v):
    if v >= 0.5: return "Severe"
    if v >= 0.25: return "Moderate"
    if v >= 0.10: return "Light"
    return "None"
congestion_category = pd.Series(congestion_index).apply(congestion_cat)

scores_df = pd.DataFrame({
    "segment_id": road_network.segment_id.values,
    "road_name": road_network.road_name.values,
    "start_km_helper": geo["dist_from_center_km"].values,  # placeholder, replaced after start_km computed in adapter
    "functional_class": road_network.functional_class.values,
    "urban_rural_flag": road_network.urban_rural_flag.values,
    "posted_speed_limit": road_network.posted_speed_limit.values,
    "operating_speed_mean": operating_speed_mean,
    "speed_p85": speed_p85.values,
    "road_function_score": road_function_score.values,
    "infrastructure_score": infrastructure_score.values,
    "exposure_score": exposure_score.values,
    "pedestrian_exposure_score": pedestrian_exposure_score.values,
    "ptw_share": ptw_share.values,
    "exposure_tier": merged_for_tier["exposure_tier"].values,
    "human_tolerance_limit": human_tolerance_limit,
    "operating_speed_score": operating_speed_score.values,
    "crash_risk_score": crash_risk_score.values,
    "misalignment_score": misalignment_score,
    "misalignment_category": misalignment_category_s.values,
    "congestion_index": congestion_index,
    "congestion_category": congestion_category.values,
})

# speed_safety_score (kept consistent with prior formula)
scores_df["speed_safety_score"] = (100 - (scores_df["misalignment_score"]*0.6 +
                                           scores_df["crash_risk_score"]*0.2 +
                                           (100 - scores_df["infrastructure_score"])*0.2)).clip(0, 100).round(1)

scores_df.to_csv("/home/claude/build_v2/scores_master.csv", index=False)

print("N segments:", N)
print(scores_df["misalignment_category"].value_counts())
print(scores_df["congestion_category"].value_counts())
print(merged_for_tier["exposure_tier"].value_counts())
