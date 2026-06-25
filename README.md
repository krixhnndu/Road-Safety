<div align="center">

# 🚦 Velora
### *Right Road. Right Time. Right Speed.*

**An AI-Powered Dynamic Safe Speed Recommendation System**

Submission for the **[ADB AI for Safer Roads Innovation Challenge](https://challenges.adb.org/en/challenges/ai4saferroads)**
*Asian Development Bank × World Bank · Asia-Pacific Road Safety Initiative*

**[▶ Watch Demo Video](https://drive.google.com/file/d/17b-jtB8lgm0XKolXuyotjMw2IpVf77t7/view?usp=drivesdk)**

---

| | |
|---|---|
| **Team** | Anand Krishna S · Aswin P A · Katherin K V · Krishnendu S Binu · Muhammed Nasmil · Shweta Nair |
|**Institution**| SCMS School of Engineering and Technology, Karukutty<br>Center of Excellence, SCMS Institute for Road Safety and Transportation (SiRST) |
| **Mentor** | Ms. Binu John, Assistant Professor, Department of Artificial Intelligence and Data Science |
| **Focus City** | Bengaluru, Karnataka, India |
| **Stack** | Python · Flask · Leaflet.js · scikit-learn · OSMnx · Pandas |
| **Python** | 3.8 or higher |

</div>

---

## What is Velora?

Velora is a full-stack AI road safety analytics platform built for Bengaluru's urban road network. It goes beyond static speed limit analysis — it dynamically computes a **safe recommended speed for every road segment in real time**, factoring in:

- Current time of day and day of week
- Live traffic congestion conditions
- Simulated roadside weather sensor data
- Active crash history (with time-based expiry)
- Reported hazard events
- School zone proximity
- Pedestrian and vulnerable road user exposure
- Road infrastructure quality

The platform is directly aligned with **Safe System principles** and **Vision Zero** — it asks not just *"what is the speed limit?"* but *"what speed is actually safe here, right now?"*

---

## Quick Start

```bash
git clone https://github.com/your-username/bengaluru-road-safety.git
cd bengaluru-road-safety

pip install -r requirements.txt
python run.py
```

Open **http://localhost:5001**

> **First run only:** `datasets/traffic_temporal_data.csv` (190 MB) is not stored in the repository due to GitHub's 100 MB file limit. When you run `python run.py` for the first time, it is **automatically generated** from the road network data already in the repo. This takes approximately 60–90 seconds and only happens once. Every subsequent run starts immediately.

**No manual downloads. No extra commands. Just `python run.py`.**

---

## Requirements

| Requirement | Version |
|---|---|
| Python | **3.8 or higher** |
| Flask | ≥ 3.0.0 |
| pandas | ≥ 2.0.0 |
| numpy | ≥ 1.24.0 |
| scikit-learn | ≥ 1.3.0 |
| joblib | ≥ 1.3.0 |

Install all dependencies with:
```bash
pip install -r requirements.txt
```

---

## How It Works

### Startup Flow

```
python run.py
     │
     ▼
dataset_bootstrap.py
     │
     ├── datasets/traffic_temporal_data.csv EXISTS?
     │        │
     │       YES ──► Skip generation (instant)
     │        │
     │        NO ──► Generate 2,911,680 rows from road network
     │                 (~60–90 s, runs only once)
     │
     ▼
Flask app starts
     │
     ├── prediction.init()   — loads ML models + master dataset
     ├── weather.init()      — starts IoT weather simulation thread
     └── traffic.init()      — loads temporal traffic CSV into memory
     │
     ▼
http://localhost:5001
```

### Safe Speed Computation Pipeline

For every road segment, at every date/time query, Velora runs a multi-stage pipeline:

```
Road Segment
     │
     ▼
[Stage 1] ML Risk Classification
     │   Gradient Boosting classifier (5 features)
     │   → Aligned / Moderate / High / Critical Misalignment
     │   → AI Risk Probability Score (0–100)
     │
     ▼
[Stage 2] Crash History Sync
     │   Active crashes only (Minor: 60-day expiry, Major/Fatal: 80-day expiry)
     │   → crash_risk_score (Minor×10 + Major×25 + Fatal×45) ÷ segment length, capped at 100)
     │
     ▼
[Stage 3] Hotspot Scoring
     │   25% misalignment + 30% exposure + 35% crash severity density + 10% infrastructure deficit
     │   → Safe / Moderate Risk / High Risk / Severe Hotspot
     │
     ▼
[Stage 4] AI Recommended Speed
     │   min(85th-percentile operating speed, human tolerance limit)
     │   − crash penalty (crash_risk_score ÷ 5)
     │
     ▼
[Stage 5] Weather Adjustment
     │   Simulated IoT rainfall sensor (refreshed every 30 min)
     │   Clear: 0 km/h reduction → Extreme Storm: −15 km/h
     │
     ▼
[Stage 6] Traffic Adjustment
     │   Temporal congestion score from 60-day traffic dataset
     │   Low: −0 → Heavy: −15 km/h
     │
     ▼
[Stage 7] School Zone Override
     │   If schools_count > 0, weekday, between 08:00–16:00
     │   → Speed × 0.6 (minimum 20 km/h)
     │
     ▼
[Stage 8] Hazard Event Override
     │   Operator-reported events (roadworks, flooding, accidents)
     │   → Manual temporary speed, bypasses all other stages
     │
     ▼
[Stage 9] Hard Road-Type Constraints
     │   Urban Road: max 70 km/h, min 20 km/h
     │   State Highway: min 25 km/h
     │   National Highway: min 30 km/h
     │
     ▼
  final_safe_speed  ← displayed on map and in detail panel
```

---

## Platform Modules

### 1. Interactive Map
The primary interface. Renders all 5,498 road segments on a Leaflet map with color-coded safe speed recommendations. Click any segment to open a detail panel showing the full speed derivation, AI risk classification, active weather and traffic conditions, and explainability factors.

### 2. Hotspot Analysis
Identifies and ranks road segments by composite hotspot score. Visualizes spatial clustering of risk across the network. Supports filtering by hotspot category (Safe → Severe Hotspot) and road type.

### 3. Blackspot Detection
Identifies accident-prone road segments using a composite risk assessment framework. Unlike traditional approaches that depend solely on crash history, the module combines crash records with infrastructure quality, exposure levels, pedestrian facilities, traffic conditions, and environmental factors to identify both existing and emerging blackspots. Segments exceeding the blackspot threshold are automatically flagged for priority intervention.

### 4. Crash Management
Log, view, and manage crash events on the road network. Crashes are time-aware — Minor crashes expire after 60 days, Major/Fatal after 80 days. Active crashes dynamically raise risk scores and lower safe speed recommendations across affected segments.

### 5. Hazard Management
Report temporary hazard events (roadworks, flooding, fallen trees, accidents) with a date, time window, and optional manual speed override. Active hazards are reflected instantly on the map and take absolute priority over all other speed adjustments.

### 6. Advanced Analytics
Charts and KPI dashboards covering:
- Speed misalignment distribution across the network
- Risk category breakdown by road type
- Hotspot frequency analysis
- ML model performance metrics (accuracy, precision, recall, F1)
- Feature importance visualization
- SHAP summary plot

### 7. Explainable AI (XAI)
For every road segment, the XAI module displays the contribution of each factor to the final safe speed recommendation, providing a transparent audit trail for road safety engineers and policy makers. Includes both per-segment explanations and a network-wide SHAP summary plot. Factors surfaced include infrastructure deficiencies, pedestrian exposure, school zone activity, crash history, and traffic conditions.

### 8. Weather Intelligence
Simulates a network of roadside IoT weather sensors using a risk-based adaptive sensing framework. Sensor placement is prioritized around severe hotspots, flood-prone corridors, major intersections, bridges, and locations with high vulnerable road user exposure. Each sensor refreshes every 30 minutes using weighted probability distributions to mimic real-world rainfall patterns, including monsoon probability weighting for Bengaluru. Weather conditions feed directly into the safe speed pipeline with automatic speed reductions.

The simulation models a deployment of Tipping Bucket Rain Gauges connected via ESP32 microcontrollers, transmitting over a GSM/MQTT pipeline into the `weather.py` ingestion module — a blueprint for real hardware integration.

### 9. Traffic Conditions
Displays real-time-style congestion levels derived from the 60-day temporal traffic dataset. Each segment is assigned a congestion score (0–1) based on time of day, day of week, road class, and random incident simulation. Traffic conditions are used both for map display and as an input to the AI Explanation panel.

### 10. Pedestrian Facility Assessment
The platform evaluates the availability and quality of pedestrian infrastructure such as sidewalks, pedestrian crossings, refuge islands, traffic calming measures, and accessibility facilities. Road segments with inadequate pedestrian facilities are assigned higher risk scores even where historical crash records are limited, enabling proactive identification of safety deficiencies before severe accidents occur.

### 11. Data Table
Full tabular view of all road segments with sortable columns. Export-ready for policy review and GIS integration.

### 12. Road Network
Embedded visualization of the OSMnx-derived Bengaluru road network with segment-level statistics, KPIs, and GeoJSON/CSV download links for GIS platforms.

---

## ML Models

Two trained classifiers are included. The **Gradient Boosting** model is used by default; the system falls back to Random Forest if GB is unavailable.

**Task:** Multi-class classification — predict whether a road segment's posted speed limit is *Aligned*, *Moderate Misalignment*, *High Misalignment*, or *Critical Misalignment* with Safe System principles.

**Features used:**

| Feature | Description |
|---|---|
| `road_function_score` | Complexity of road function (intersection density, road hierarchy) |
| `infrastructure_score` | Physical safety quality (sidewalks, lighting, crosswalks) |
| `exposure_score` | Vulnerability of road users (pedestrian volume, PTW share) |
| `human_tolerance_limit` | Biomechanical speed threshold for survivable crash |
| `operating_speed_score` | Observed 85th-percentile speed relative to limit |

Note: `crash_risk_score` is deliberately excluded from features — it is a lagging indicator confounded by reporting behavior. The classifier predicts *leading* risk, not observed crash outcomes.

**Model Validation:** Train-test split, K-Fold Cross Validation, and Confusion Matrix analysis were applied. Performance was evaluated using Accuracy, Precision, Recall, F1-Score, and ROC-AUC Score.

---

## Dataset

| File | Size | Description |
|---|---|---|
| `datasets/unified_platform_data.csv` | 2.7 MB | Master dataset — 5,498 road segments with all features, scores, and ML predictions |
| `datasets/traffic_temporal_data.csv` | ~190 MB | **Auto-generated on first run** — 2,911,680 rows of synthetic temporal traffic data (6,066 segments × 480 timestamps) |
| `datasets/crash_database_seed.csv` | 13 KB | Seed crash events for initial database population |
| `datasets/hazard_database_seed.csv` | <1 KB | Seed hazard events |
| `datasets/model_metrics.csv` | <1 KB | Classifier performance metrics |
| `datasets/feature_importance.csv` | <1 KB | Feature importance scores for XAI tab |
| `road_network/bengaluru_road_segments.csv` | ~0.5 MB | OSMnx-derived road segments (2,842 rows) with geometry and connectivity |
| `road_network/bengaluru_road_segments_full.csv` | ~2 MB | Extended road segment source for traffic generation (6,066 segments) |
| `road_network/bengaluru_road_segments.geojson` | GeoJSON | Leaflet-ready road geometry |
| `road_network/bengaluru_roads_classified.geojson` | GeoJSON | Road network with classification overlay |

The unified dataset was synthesized by integrating OpenStreetMap road network data, GPS probe-derived operating speed indicators, Mapillary-inspired street-level infrastructure references, traffic congestion patterns, crash records, hazard information, and weather parameters. Statistical relationships from transportation research literature were used to maintain realistic distributions across all variables.

### Road Network Coverage

| Class | Segments | Color |
|---|---|---|
| National Highway | 286 | Yellow |
| State Highway | 380 | Orange |
| Urban Road | 4,832 | Blue |
| **Total** | **5,498** | |

---

## Project Structure

```
bengaluru_road_safety_platform/
│
├── run.py                              # Entry point — triggers bootstrap then starts Flask
├── dataset_bootstrap.py               # Auto-generates traffic_temporal_data.csv if missing
├── requirements.txt
├── .gitignore                          # Excludes traffic_temporal_data.csv (190 MB)
├── README.md
│
├── backend/
│   ├── __init__.py
│   ├── app.py                          # Flask application factory
│   ├── routes.py                       # All /api/* endpoints
│   ├── prediction.py                   # ML risk scoring, safe speed pipeline
│   ├── traffic.py                      # Traffic temporal data module
│   ├── weather.py                      # Simulated IoT weather sensing
│   ├── model_loader.py                 # Loads .pkl model files
│   ├── db.py                           # SQLite crash/hazard database
│   └── traffic_generator.py           # Standalone traffic data generator (reference)
│
├── datasets/
│   ├── unified_platform_data.csv       # Master road segment dataset (5,498 rows)
│   ├── traffic_temporal_data.csv       # ← AUTO-GENERATED (not in repo)
│   ├── crash_database_seed.csv
│   ├── hazard_database_seed.csv
│   ├── model_metrics.csv
│   ├── feature_importance.csv
│   └── app.db                          # SQLite database (crashes + hazards)
│
├── models/
│   ├── gradient_boosting_model.pkl     # Primary classifier
│   └── random_forest_model.pkl        # Fallback classifier
│
├── road_network/
│   ├── bengaluru_road_segments.csv
│   ├── bengaluru_road_segments_full.csv
│   ├── bengaluru_road_segments.geojson
│   └── bengaluru_roads_classified.geojson
│
├── static/
│   ├── css/style.css
│   ├── geojson/road_network.geojson    # Leaflet map geometry
│   ├── images/                         # Model evaluation charts, SHAP plots
│   ├── road_network_visualization.html # Embedded OSM road network view
│   └── js/
│       ├── main.js                     # App bootstrap
│       ├── map.js                      # Leaflet map rendering
│       ├── sidebar.js                  # Controls and filters
│       ├── charts.js                   # Plotly chart builders
│       ├── kpis.js                     # KPI strip
│       ├── api.js                      # fetch() wrappers
│       ├── state.js                    # Global UI state
│       ├── tabs.js                     # Tab switching
│       └── tabs/
│           ├── analyticsTab.js
│           ├── crashTab.js
│           ├── dataTab.js
│           ├── hazardTab.js
│           ├── hotspotTab.js
│           ├── modelTab.js
│           ├── roadnetTab.js
│           ├── weatherTab.js
│           └── xaiTab.js
│
└── templates/
    └── index.html                      # Single-page application shell
```

---

## API Reference

The backend exposes a REST API consumed by the frontend. Key endpoints:

| Endpoint | Description |
|---|---|
| `GET /api/segments` | All road segments with computed scores for current date/time |
| `GET /api/segment/<id>` | Full detail for a single segment including XAI factors |
| `GET /api/kpis` | Network-level KPIs (total segments, risk distribution, avg speed) |
| `GET /api/hotspots` | Hotspot-ranked segment list |
| `GET /api/crashes` | Active crash events |
| `POST /api/crashes` | Log a new crash event |
| `GET /api/hazards` | Active hazard events |
| `POST /api/hazards` | Report a new hazard event |
| `GET /api/weather/<id>` | Current weather conditions for a segment |
| `GET /api/traffic/<id>` | Current traffic conditions for a segment |
| `GET /api/analytics` | Aggregated chart data |
| `GET /api/model-metrics` | ML model performance metrics |
| `GET /api/road-network/stats` | Road network coverage statistics |

All endpoints accept optional `?date=YYYY-MM-DD&time=HH:MM` query parameters to simulate any point in time.

---

## Competition Alignment

This platform directly addresses the ADB AI for Safer Roads challenge brief:

| Challenge Requirement | Velora Implementation |
|---|---|
| Assess whether speed limits follow Safe System principles | ML classifier produces Aligned/Misalignment labels per segment |
| Identify segments exposing VRUs to unacceptable risk | Exposure score, pedestrian score, school zone detection, pedestrian facility assessment |
| Map-based visualization | Interactive Leaflet map with color-coded safe speeds |
| Speed Safety Score | `speed_safety_score` field per segment (0–100) |
| Policy-ready outputs | Data Table tab with exportable CSV; Road Network download |
| Prioritize road interventions | Hotspot Analysis and Blackspot Detection with composite risk ranking |
| Dynamic / real-time capability | Date + time controls update every score in real time |
| Scalability | OSMnx pipeline generalizes to any city with OSM road network data, supporting deployment across ADB member countries |

---

## Vision Zero Principles Applied

- **No speed limit is safe if the road cannot support it** — infrastructure score directly penalizes inadequate physical safety features
- **Human tolerance limits are biological, not political** — `human_tolerance_limit` is derived from biomechanical survivability thresholds, not posted limits
- **Vulnerable road users have asymmetric risk** — pedestrian exposure, PTW share, and school proximity are weighted heavily in hotspot scoring
- **Crashes are preventable, not inevitable** — the system treats every Critical Misalignment segment as an intervention opportunity

---

## Individual Contributions

<table>
<tr>
<th>Member</th>
<th>Primary Contributions</th>
</tr>
<tr>
<td><b>Anand Krishna S</b></td>
<td>Safe speed recommendation engine · Multi-stage speed pipeline · Backend APIs &amp; system integration · Model evaluation</td>
</tr>
<tr>
<td><b>Aswin P A</b></td>
<td>ML framework (Gradient Boosting &amp; Random Forest) · Road network classification · XAI / SHAP analysis · Crash &amp; Hazard Management</td>
</tr>
<tr>
<td><b>Krishnendu S Binu</b></td>
<td>Road network segmentation · Leaflet GIS visualization · Segment connectivity mapping · Vision Zero literature review</td>
</tr>
<tr>
<td><b>Katherin K V</b></td>
<td>Traffic dataset generation (2.9M rows) · Congestion scoring · Unified dataset integration · Temporal traffic simulation</td>
</tr>
<tr>
<td><b>Muhammed Nasmil</b></td>
<td>Frontend SPA architecture · Dashboard &amp; UI components · Navigation, filters &amp; KPI displays · UI/UX design</td>
</tr>
<tr>
<td><b>Shweta Nair</b></td>
<td>Weather intelligence module · IoT sensing framework · Weather-based speed adjustment · Analytics dashboards &amp; hotspot charts</td>
</tr>
</table>

---

<div align="center">

**[Detailed Research Report](https://drive.google.com/file/d/17X8ZyuxsF6Pbr0NhrwOlyoTvZveHG_yU/view?usp=drivesdk)**

*Built with Vision Zero principles for the ADB AI for Safer Roads Innovation Challenge*
*Focused on Bengaluru, India · Scalable to any city with OSM road network data*

</div>
