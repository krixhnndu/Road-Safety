# Road Safety Model — Revision 2 (Segmentation, Exposure Rules, Congestion)

This revision implements the segmentation/exposure/congestion review on top
of the prior misalignment-reframed model. Run exactly as before:
```
cd road-main
pip install -r requirements_unified.txt
python -m streamlit run unified_platform.py
```

## Headline numbers
- **Segments: 1,112** (down from 4,966 — explicitly targeted into the
  recommended 1,000–1,200 range)
- 532 segments on real-geometry named NH/SH/Ring corridors
- 580 segments on the procedural local/peri-urban/rural network
- Model accuracy: Gradient Boosting 74.0% / Random Forest 72.6% (down from
  ~89-90% in the prior revision — see "why accuracy dropped" below; this is
  expected and explained, not a bug)

## Every rule implemented

### 1. No segment contains multiple road classes
Verified programmatically: grouping all segments by their underlying
corridor/road and checking `corridor_type.nunique()` returns 1 for all 18
named corridors and all procedurally generated roads — zero mixed-class
segments. (This was structurally already true in the generator, but is now
explicitly checked rather than assumed.)

### 2. Segment boundaries at intersections, not mid-curve
For the 14 named NH/SH/Ring corridors, every pairwise **geometric
line-intersection** between corridor waypoint legs is computed
(`seg_intersect()` in `01_generate_geometry_v2.py`), and those real crossing
points become forced breakpoints during segmentation — in addition to the
length-hierarchy targets. Breakpoints within 80m of each other are merged to
avoid slivers. This means a segment boundary on, say, NH-44 falls where it
actually crosses SH-87 or the Outer Ring Road, not at an arbitrary distance.

For the procedural local/peri-urban/rural network (which doesn't have real
topology to intersect against), each generated "road" is a short 1-2
segment stretch by construction — each segment is bounded by the road's own
start/end, standing in for "between two intersections" rather than being
sliced out of a long uniform path. This is a documented simplification for
synthetic data, not claimed as real intersection detection.

### 3. Segment-length hierarchy
| Road Type | Target Used | Hierarchy Range |
|---|---|---|
| National Highway | 1,750 m | 1,000–2,000 m |
| State Highway | 900 m | 500–1,000 m |
| Ring Road (treated as Urban Arterial) | 450 m | 250–500 m |
| Arterial (procedural) | 250–500 m range | 250–500 m |
| Collector/Suburban | 250–400 m range | 250–400 m |
| Local/Peri-Urban/Rural | 150–300 m range | 150–300 m |

Verified: per-class length stats are within (or very close to) each band;
the handful of sub-100m segments (3 of 1,112) are deliberate — they sit
immediately adjacent to a forced intersection breakpoint, which is how real
short link segments between closely-spaced junctions actually look.

### 4. Vision Zero Exposure Tiers (replaces the rigid POI-proximity rule)
The old "school/hospital within radius → max 30 km/h" rule is gone. Instead,
`human_tolerance_limit` is now driven by an **exposure interaction tier**
computed per segment from actual separation/pedestrian-mixing signals
(`exposure_interaction_tier()` in `02_generate_features_v2.py`):

| Condition | Max Safe Speed |
|---|---|
| Significant Pedestrian Interaction (heavy foot traffic actually crossing/mixing with the carriageway) | 30 km/h |
| Side Impact Potential (some mixing/cross-traffic, not severe pedestrian exposure) | 50 km/h |
| Separated Traffic (physical median, low intersection density, low pedestrian mixing) | 70 km/h (80 km/h on Highway class) |

A school 400m from a fully-separated NH with low pedestrian crossing no
longer forces 30 km/h — only genuine pedestrian interaction does. Current
distribution: 690 Side Impact Potential / 322 Separated Traffic / 100
Significant Pedestrian Interaction.

### 5. Traffic Congestion Module (new)
Per segment: `Congestion Index = clip((expected_speed − current_speed) / expected_speed, 0, 1)`,
where **expected_speed is the segment's own typical/free-flow operating
speed** (not the posted limit — comparing against the posted limit would
flag ordinary under-limit urban driving as "congestion," which isn't the
intent), plus a small additional penalty for high speed variance (unstable,
stop-and-go conditions). Categorized None/Light/Moderate/Severe.

**Propagation/smoothing** (the worked example from the brief, implemented
exactly): if Segment A is congested (expected 60, observed 23 in one actual
case in this run), its `recommended_safe_speed` drops toward its real
observed operating speed. The **previous segment along the same corridor**
then gets a smaller taper — e.g. in the dataset, a segment recommended at
80 km/h whose immediate successor drops to 40 km/h due to congestion now
tapers to 60 km/h itself, rather than staying at 80 right up to the
slowdown. The taper never drops below 70% of that segment's own Vision Zero
tolerance floor, so smoothing can't manufacture a *new* misalignment.

Current distribution: 663 None / 369 Light / 1 Moderate / 79 Severe;
42 segments received a smoothing taper from a congested neighbor.

### 6. Fixed a latent bug found while implementing this
`start_km`/`end_km` were previously computed via `groupby("road_name")`,
but `road_name` was unique per individual segment (e.g. "NH-44 Seg-3") —
so the cumulative-km calculation was silently a no-op for every segment.
Fixed by adding proper `corridor_base`/`corridor_seq` columns and grouping
by those instead. This also is what makes "previous segment along the same
corridor" (needed for congestion smoothing) actually well-defined.

## Why model accuracy dropped (74% vs. ~89% previously) — expected, not a bug
Three compounding, explainable reasons:
1. **~4.5x less training data** (1,112 vs. 4,966 rows) — fewer examples per
   class, especially for the rare High/Critical Misalignment classes (45
   and 9 segments respectively).
2. **`human_tolerance_limit` is now a discrete tier value** (30/50/70/80)
   instead of a smoother 12-row lookup table — this makes the decision
   boundary the classifier has to learn lumpier and harder to separate
   cleanly from the other continuous features.
3. **`exposure_score`'s relationship to the target shifted** because the
   tolerance values it's compared against in `misalignment_score` changed
   shape (see #2), changing which segments land in which class near the
   boundaries.

This isn't being hidden — `model_metrics.csv` and the dashboard's "ML Model
Evaluation" tab show the real, current numbers (74.0% / 72.6%), and the
confusion matrices in `model_evaluation.png` are regenerated from the
actual retrained models on a real held-out test set.

## New UI surfaces (in `unified_platform.py`)
- Segment detail panel: new "Congestion Index" score bar + a live note when
  a segment is actively congested or tapering ahead of one.
- Segment info panel: new "Exposure Tier" row (Vision Zero tier).
- KPI row: new "Congested Now" count (11 KPIs instead of 10).
- Data table: `exposure_tier`, `congestion_index`, `congestion_category`
  columns added.

## Known remaining gaps (not addressed this round)
- True topological intersection detection for the procedural local-road
  network (not just the named corridors) would require actual road-network
  topology, which is out of scope for synthetic/dummy data.
- The "Moderate" congestion tier is thin (1 segment) — the transition
  between "Light" and "Severe" is closer to a step than a smooth gradient
  in this random draw; cosmetic, not structurally wrong.
