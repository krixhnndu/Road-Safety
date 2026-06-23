# Bengaluru AI Road Safety Platform

Flask-based road safety analytics platform with Detection 9 road network integration.

## Quick Start

```bash
pip install -r requirements.txt
python run.py
```

Open **http://localhost:5001**

> **First run only:** If `datasets/traffic_temporal_data.csv` is missing (it is excluded from the
> repository because it is 190 MB), `run.py` will **automatically generate it** from the road
> network data already in the repo. This takes ~30–60 seconds and only happens once.
> After that, every subsequent `python run.py` starts instantly.

**No manual downloads, no extra commands. Just `python run.py`.**

---

## Why the dataset is not in the repository

`datasets/traffic_temporal_data.csv` is a **fully synthetic** 190 MB file generated from
`road_network/bengaluru_road_segments.csv`. GitHub's 100 MB file limit makes it impossible
to store there directly, and Git LFS does not work for ZIP downloads. The solution is to
regenerate the dataset automatically on first run — which takes the same amount of time as
a slow network download but works completely offline and never fails.

---

## Project structure

```
.
├── run.py                          # Entry point — also triggers dataset bootstrap
├── dataset_bootstrap.py           # Auto-generates traffic_temporal_data.csv if missing
├── requirements.txt
├── backend/
│   ├── app.py                     # Flask application factory
│   ├── routes.py                  # /api/* endpoints
│   ├── prediction.py              # ML risk scoring
│   ├── traffic.py                 # Traffic temporal module (loads the CSV)
│   ├── weather.py                 # Weather simulation
│   └── traffic_generator.py      # Original standalone generator (kept for reference)
├── datasets/
│   ├── unified_platform_data.csv  # Main road segment dataset (in repo)
│   ├── traffic_temporal_data.csv  # AUTO-GENERATED on first run (not in repo)
│   └── *.csv / *.db               # Other seed datasets
├── road_network/                  # OSMnx-derived road geometry (Detection 9)
├── models/                        # Trained ML model files
├── static/                        # CSS, JS, GeoJSON, images
└── templates/index.html           # SPA shell
```

---

## What changed from the original webapp

### Road Network (Detection 9 Integration)
- `static/geojson/road_network.geojson` — **Replaced** with real OSMnx-derived geometry (2,842 segments)
- `datasets/unified_platform_data.csv` — **Replaced** with 2,842-row dataset using real road names and classes
- `road_network/` — **New folder** with Detection 9 source files
- `static/road_network_visualization.html` — **New** embedded Detection 9 Leaflet map

### Backend changes
- `backend/app.py` — Added `/road_network/<filename>` route
- `backend/routes.py` — Added `/api/road-network/stats`; increased render cap to 2,000 segments

### Frontend changes
- **🛣️ Road Network** tab (Tab 9) added with iframe + KPI strip + download buttons
- `Urban` road type added to map legend, sidebar filter, and chart palette

## Road network segment ID mapping

| Detection 9 class | `road_type` in dataset | Color |
|---|---|---|
| National Highway | Highway | 🟡 yellow |
| State Highway | Arterial | 🟠 orange |
| Urban Road | Urban | 🔵 blue |
