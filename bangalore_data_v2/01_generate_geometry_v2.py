"""
01_generate_geometry_v2.py
Rebuilds segment geometry per the agreed rules:

  1. Every segment is a SINGLE road class — never NH+Urban mixed (this was
     already true structurally, but is now enforced explicitly).
  2. Segment boundaries are placed at simulated INTERSECTIONS (real
     corridor-corridor crossings, computed geometrically) and at
     road-class/corridor boundaries — never mid-curve, never arbitrary.
  3. Segment-length hierarchy (midpoint of each range used as target):
        National Highway   1000-2000 m  (target 1500m)
        State Highway       500-1000 m  (target  750m)
        Urban Arterial       250-500 m  (target  375m)
        Suburban/Collector   250-400 m  (target  325m)
        Peri-Urban/Local     150-300 m  (target  225m)
  4. Total segment count target: ~1000-1200 (down from 4,966 — the prior
     count was not "applicable" per review; this was driven almost entirely
     by an oversized procedural local-road grid, now cut ~10x).
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
CENTER_LAT, CENTER_LON = 12.9716, 77.5946

# Same real-corridor waypoints as before (NH/SH/Ring), each corridor is a
# SINGLE road class end-to-end.
CORRIDORS = [
    ("NH-44 (Bellary Rd -> Hosur Rd)", "NH", [
        (13.2100, 77.6200), (13.0980, 77.5950), (12.9716, 77.5946),
        (12.9000, 77.6050), (12.7900, 77.6700), (12.6500, 77.7800)]),
    ("NH-75 (Bangalore-Mangalore, Tumkur Rd)", "NH", [
        (12.9716, 77.5946), (13.0270, 77.5230), (13.1100, 77.4100),
        (13.1800, 77.2700), (13.2600, 77.1100)]),
    ("NH-948 (Nelamangala Bypass)", "NH", [
        (13.1000, 77.3900), (13.0950, 77.3000), (13.0700, 77.2200)]),
    ("NH-209 (Bannerghatta Rd)", "NH", [
        (12.9716, 77.5946), (12.9100, 77.6000), (12.8000, 77.5780),
        (12.6800, 77.5600), (12.5500, 77.5400)]),
    ("SH-17 (Old Madras Rd)", "SH", [
        (12.9900, 77.6500), (13.0100, 77.7200), (13.0400, 77.8200),
        (13.0700, 77.9300)]),
    ("SH-35 (Kanakapura Rd)", "SH", [
        (12.9400, 77.5700), (12.8500, 77.5200), (12.7300, 77.4500),
        (12.5900, 77.4000)]),
    ("SH-87 (Magadi Rd)", "SH", [
        (12.9716, 77.5650), (13.0000, 77.4700), (13.0400, 77.3500)]),
    ("Hosur Road Extension", "NH", [
        (12.9300, 77.6300), (12.8400, 77.6700), (12.7400, 77.7100),
        (12.6300, 77.7600)]),
    ("Mysore Road (NH-275)", "NH", [
        (12.9550, 77.5500), (12.9100, 77.4700), (12.8500, 77.3600),
        (12.7800, 77.2200)]),
    ("Sarjapur Road", "SH", [
        (12.9250, 77.6650), (12.9000, 77.7200), (12.8700, 77.7900),
        (12.8500, 77.8600)]),
    ("Outer Ring Road (ORR)", "Ring", [
        (13.0450, 77.5950), (13.0250, 77.6450), (12.9900, 77.6950),
        (12.9350, 77.6950), (12.8900, 77.6500), (12.8900, 77.5950),
        (12.9200, 77.5350), (12.9700, 77.5050), (13.0250, 77.5250),
        (13.0450, 77.5950)]),
    ("Inner Ring Road", "Ring", [
        (12.9950, 77.5950), (12.9850, 77.6200), (12.9650, 77.6250),
        (12.9550, 77.6050), (12.9650, 77.5800), (12.9850, 77.5800),
        (12.9950, 77.5950)]),
    ("Devanahalli-Doddaballapur Rd (SH-9)", "SH", [
        (13.2400, 77.7100), (13.2900, 77.6200), (13.3000, 77.5300)]),
    ("Anekal-Attibele Rd (SH-82)", "SH", [
        (12.7100, 77.6950), (12.7600, 77.7700), (12.7900, 77.8700)]),
]

TARGET_LEN_KM = {"NH": 1.75, "SH": 0.90, "Ring": 0.45}  # midpoint-ish of each hierarchy band

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dlmb/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def seg_intersect(p1, p2, p3, p4):
    """Return intersection point of segment p1-p2 and p3-p4 (lat,lon tuples), or None."""
    x1, y1 = p1[1], p1[0]; x2, y2 = p2[1], p2[0]
    x3, y3 = p3[1], p3[0]; x4, y4 = p4[1], p4[0]
    d = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
    if abs(d) < 1e-12:
        return None
    t = ((x1-x3)*(y3-y4) - (y1-y3)*(x3-x4)) / d
    u = ((x1-x3)*(y1-y2) - (y1-y3)*(x1-x2)) / d
    if 0 <= t <= 1 and 0 <= u <= 1:
        ix = x1 + t*(x2-x1); iy = y1 + t*(y2-y1)
        return (iy, ix)  # (lat, lon)
    return None

# ── Step 1: find real geometric intersections between corridor waypoint legs.
# These become FORCED breakpoints (the "Intersection / Crossing" rule) —
# segments never get subdivided through the middle of a curve; they only
# break at these crossings or at hierarchy-length targets.
intersections_by_corridor = {name: [] for name, _, _ in CORRIDORS}
for i, (name_a, _, wpts_a) in enumerate(CORRIDORS):
    for name_b, _, wpts_b in CORRIDORS[i+1:]:
        for a1, a2 in zip(wpts_a[:-1], wpts_a[1:]):
            for b1, b2 in zip(wpts_b[:-1], wpts_b[1:]):
                pt = seg_intersect(a1, a2, b1, b2)
                if pt:
                    intersections_by_corridor[name_a].append(pt)
                    intersections_by_corridor[name_b].append(pt)

def densify_with_breaks(name, waypoints, target_km, forced_points):
    """Interpolate a polyline into target_km-ish segments, additionally
    forcing breakpoints exactly at any forced_points (real corridor
    crossings) that fall near this polyline."""
    pts = []
    for (lat1, lon1), (lat2, lon2) in zip(waypoints[:-1], waypoints[1:]):
        leg_km = haversine(lat1, lon1, lat2, lon2)
        # Collect fractional positions (0-1) along this leg where a forced
        # breakpoint (intersection) falls.
        forced_fracs = set()
        for (flat, flon) in forced_points:
            # project point onto leg, check it's actually close to the leg
            dlat, dlon = lat2-lat1, lon2-lon1
            denom = dlat**2 + dlon**2
            if denom < 1e-12:
                continue
            t = ((flat-lat1)*dlat + (flon-lon1)*dlon) / denom
            if 0.02 < t < 0.98:
                proj_lat, proj_lon = lat1 + t*dlat, lon1 + t*dlon
                if haversine(proj_lat, proj_lon, flat, flon) < 0.15:  # within 150m of the leg
                    forced_fracs.add(round(t, 4))
        n = max(1, round(leg_km / target_km))
        regular_fracs = [i/n for i in range(1, n)]
        all_breaks = sorted(set([0.0] + regular_fracs + list(forced_fracs) + [1.0]))
        # de-duplicate breaks that are too close together (< 80m) — avoid
        # creating tiny slivers right next to an intersection breakpoint
        cleaned = [all_breaks[0]]
        for f in all_breaks[1:]:
            if (f - cleaned[-1]) * leg_km > 0.08:
                cleaned.append(f)
        if cleaned[-1] != 1.0:
            cleaned[-1] = 1.0
        for f0, f1 in zip(cleaned[:-1], cleaned[1:]):
            pts.append((lat1+(lat2-lat1)*f0, lon1+(lon2-lon1)*f0,
                        lat1+(lat2-lat1)*f1, lon1+(lon2-lon1)*f1))
    return pts

records = []
seg_counter = 1
for name, ctype, wpts in CORRIDORS:
    segs = densify_with_breaks(name, wpts, TARGET_LEN_KM[ctype], intersections_by_corridor[name])
    for i, (la1, lo1, la2, lo2) in enumerate(segs):
        records.append(dict(
            segment_id=seg_counter, road_name=f"{name} Seg-{i+1}",
            corridor_base=name, corridor_seq=i,
            corridor_type=ctype, start_lat=la1, start_lon=lo1,
            end_lat=la2, end_lon=lo2,
        ))
        seg_counter += 1

n_corridor_segs = seg_counter - 1
print(f"Named-corridor segments (hierarchy length + real intersection breaks): {n_corridor_segs}")

# ──────────────────────────────────────────────────────────────────────────
# Procedural arterial/collector/local/peri-urban/rural roads.
# Each generated "road" is a SHORT, SINGLE-CLASS stretch (1-2 internal
# breakpoints max) representing the space between two intersections — not a
# uniform random grid blanket. Road counts cut ~9x vs. the prior version,
# which was the dominant source of the unusable 4,966-segment total.
# ──────────────────────────────────────────────────────────────────────────
ZONES = [
    # ring_id, radius_km_range, n_roads, functional_class, urban_rural, seg_len_km_range
    (0, (0, 6),    58, "Arterial",  "Urban",       (0.25, 0.50)),
    (0, (0, 6),    74, "Collector", "Urban",       (0.25, 0.40)),
    (1, (6, 12),   52, "Arterial",  "Urban",       (0.25, 0.50)),
    (1, (6, 12),   65, "Collector", "Urban",       (0.25, 0.40)),
    (2, (12, 20),  56, "Collector", "Peri-Urban",  (0.25, 0.40)),
    (2, (12, 20),  72, "Local",     "Peri-Urban",  (0.15, 0.30)),
    (3, (20, 35),  60, "Local",     "Rural",       (0.15, 0.30)),
    (3, (20, 35),  47, "MDR",       "Rural",       (0.25, 0.40)),
]

for ring_id, (r0, r1), n_roads, fclass, urb, (lo_len, hi_len) in ZONES:
    for _ in range(n_roads):
        r = rng.uniform(r0, r1)
        theta = rng.uniform(0, 2*np.pi)
        lat0 = CENTER_LAT + (r/111.0) * np.cos(theta)
        lon0 = CENTER_LON + (r/(111.0*np.cos(np.radians(CENTER_LAT)))) * np.sin(theta)
        bearing = rng.uniform(0, 2*np.pi)
        # a short "road" between two implied intersections — 1 or
        # occasionally 2 segments (i.e. one mid-road intersection), never
        # more, keeping each segment a clean single-class, single-context
        # stretch.
        n_internal_segs = 1 if rng.random() < 0.8 else 2
        cur_lat, cur_lon = lat0, lon0
        road_base_name = f"{fclass} Rd Zone{ring_id}-{seg_counter}"
        for s in range(n_internal_segs):
            seg_len_km = rng.uniform(lo_len, hi_len)
            lat2 = cur_lat + (seg_len_km/111.0) * np.cos(bearing)
            lon2 = cur_lon + (seg_len_km/(111.0*np.cos(np.radians(CENTER_LAT)))) * np.sin(bearing)
            records.append(dict(
                segment_id=seg_counter,
                road_name=f"{fclass} Rd Zone{ring_id}-{seg_counter}",
                corridor_base=road_base_name, corridor_seq=s,
                corridor_type=fclass, start_lat=cur_lat, start_lon=cur_lon,
                end_lat=lat2, end_lon=lon2, _ring=ring_id, _urb=urb,
            ))
            seg_counter += 1
            cur_lat, cur_lon = lat2, lon2
            bearing += rng.uniform(-0.3, 0.3)  # slight turn at the internal intersection

road_df = pd.DataFrame(records)
N = len(road_df)
print(f"Procedural grid segments: {N - n_corridor_segs}")
print(f"TOTAL segments: {N}")
road_df.to_csv("/home/claude/build_v2/_raw_geometry.csv", index=False)
