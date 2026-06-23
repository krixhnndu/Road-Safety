# Migration Plan — Streamlit → Flask + HTML/CSS/JS/Leaflet

This document maps every file in the original Streamlit app
(`Road-Safety-main/road-main/`) to its disposition in the new web app, per
Step 9 of the migration brief.

## File-by-file disposition

| Original file | Disposition | Notes |
|---|---|---|
| `unified_platform.py` | **Converted** | Split across `backend/prediction.py` (scores/formulas), `backend/routes.py` (API endpoints, one section per tab), `backend/model_loader.py` (model loading), and the entire `static/js/` + `templates/index.html` tree (UI). See table below for the tab-by-tab breakdown. |
| `unified_platform_data.csv` | **Retained** | Copied to `datasets/unified_platform_data.csv`, loaded once at startup by `prediction.init()`. Unchanged schema. |
| `ai_road_segments_unified.geojson` | **Converted** | Stripped down to geometry + `segment_id` only and copied to `static/geojson/road_network.geojson`. All the score/label properties that used to live on each GeoJSON feature now come from `/api/segments/map` and are joined client-side by `segment_id` — this is what makes the road network swappable (Step 8): drop in a new geometry-only GeoJSON with the same `segment_id` keys and nothing else has to change. |
| `random_forest_model.pkl` / `gradient_boosting_model.pkl` | **Retained** | Copied to `models/`. Loaded by `backend/model_loader.py` with the same sklearn-version compatibility shim used in the original app. |
| `model_metrics.csv` | **Retained** | Copied to `datasets/`. Served via `GET /api/metrics`. |
| `feature_importance.csv` | **Retained** | Copied to `datasets/`. Currently loaded but not surfaced separately — the feature-importance **image** (below) is what the original UI actually displayed. |
| `feature_importance.png`, `model_evaluation.png`, `shap_summary.png` | **Retained** | Copied to `static/images/`. Served as plain static files and referenced directly by the ML Model Evaluation and Explainable AI tabs (`<img>` tags) — no backend processing needed since these are pre-rendered exports. |
| `crash_database.csv` | **Converted** | Seeded once into the new SQLite table `crashes` (`datasets/app.db`) on first run. New crashes are written to SQLite (durable across restarts) instead of a CSV rewritten on every change. |
| `hazard_database.csv` | **Converted** | Same treatment as crashes, into the `hazards` SQLite table. |
| `check_crashes.py` | **Removed** | This was a one-off debugging script (prints crash CSV shape/head to the console). Not part of the running app; superseded by `GET /api/crashes` for inspecting crash data. |
| `requirements_unified.txt` | **Converted** | Replaced by `requirements.txt` (Flask instead of Streamlit/folium/streamlit-folium/plotly — the frontend now talks to Leaflet.js + Plotly.js directly via CDN, so those Python packages are no longer needed server-side). |

## Tab-by-tab breakdown (where each piece of `unified_platform.py` went)

| Streamlit tab | Backend (`routes.py` section) | Frontend |
|---|---|---|
| Interactive Map | `/api/segments/map`, `/api/segments/<id>`, `/api/segments/<id>/crashes`, `/api/segments/options` | `static/js/map.js` + the `#panel-map` section of `templates/index.html` |
| Hotspot Analysis | `/api/analytics/hotspot` | `static/js/tabs/hotspotTab.js` |
| ML Model Evaluation | `/api/metrics` | `static/js/tabs/modelTab.js` |
| Explainable AI | `/api/xai/<id>` | `static/js/tabs/xaiTab.js` |
| Crash Management | `/api/crashes` (GET/POST), `/api/crashes/charts`, `/api/crashes/export` | `static/js/tabs/crashTab.js` |
| Hazard Management | `/api/hazards` (GET/POST/DELETE), `/api/hazards/default-speed` | `static/js/tabs/hazardTab.js` |
| Advanced Analytics | `/api/analytics/advanced` | `static/js/tabs/analyticsTab.js` |
| Data Table | `/api/segments/table`, `/api/export/filtered`, `/api/export/full` | `static/js/tabs/dataTab.js` |
| Sidebar (filters / controls / legend / active model) | `/api/sidebar-options`, `/api/kpis` | `static/js/sidebar.js`, `static/js/kpis.js` |

## Streamlit -> HTML/JS component mapping

| Streamlit | Web equivalent |
|---|---|
| `st.sidebar` | `<aside class="sidebar">` in `templates/index.html` |
| `st.selectbox` | `<select>` populated by JS from `/api/sidebar-options` or `/api/segments/options` |
| `st.slider` | `<input type="range">` (line width, render cap) |
| `st.date_input` | `<input type="date">` |
| `st.button` / `st.form_submit_button` | `<button>` / `<form>` with a `submit` listener calling `apiPost()` |
| `st.metric` | `.kpi` cards (`kpis.js`, tab-specific card renderers) |
| `st.dataframe` | `<table class="data-table">` rendered from JSON rows |
| `st.plotly_chart` | Plotly.js, loaded from cdnjs, called directly in each tab's JS module |
| `folium` map + `streamlit_folium.st_folium` | Leaflet.js map in `static/js/map.js`, tiles from CartoDB/OSM/Esri |
| `st.tabs` | `.tab-nav` buttons + `.tab-panel` sections, switched by `static/js/tabs.js` |
| `st.session_state` (crash/hazard DBs) | SQLite (`backend/db.py`) |
| `st.download_button` (CSV exports) | `triggerDownload()` -> `GET /api/export/...` / `/api/crashes/export` (Flask `Response` with `Content-Disposition: attachment`) |

## Standalone `/api/predict` endpoint

Step 5 of the brief specifies an exact contract:

```
POST /api/predict
{"infrastructure_score": 70, "exposure_score": 50, "crash_risk_score": 40, "operating_speed": 60}
-> {"recommended_safe_speed": 45}
```

This input shape (`infrastructure_score` / `exposure_score` / `crash_risk_score` /
`operating_speed`) does **not** match the five features the actual trained
classifier expects (`road_function_score`, `infrastructure_score`,
`exposure_score`, `human_tolerance_limit`, `operating_speed_score` — see
`FEATURES` in `backend/prediction.py`), so it cannot be a direct call into
the Gradient Boosting / Random Forest model. `predict_quick()` implements it
as a transparent, documented Vision-Zero-style formula instead. The real
per-segment ML pipeline that powers the dashboard is exposed through
`/api/segments/map`, `/api/segments/<id>`, and `/api/xai/<id>`. If you'd
rather have `/api/predict` accept the actual 5 model features (and run the
real classifier), that's a small change to `predict()` in `routes.py` and
`prediction.py`.

## Known minor deviations from the original (for transparency)

- **Posted-speed filter** is now two plain number inputs (min/max) instead of
  a single dual-handle slider — `st.slider((min,max))` has no native HTML
  equivalent without a JS slider library; this can be upgraded later with a
  small noUiSlider/rangeslider component if desired.
- **Map render cap**: Leaflet (SVG/Canvas in the browser) can't smoothly
  render 1,112+ polylines with rich popups the way `folium` could hand off
  to a server-rendered map. The map now renders the highest-priority
  segments (by hotspot score) up to a user-adjustable cap (default 1,500;
  slider goes to 5,000) and shows a banner when capped. **The Data Table tab
  and both CSV downloads are never capped** — they always reflect every
  segment matching the filters.
- **Crash/Hazard dropdowns** are sorted by hotspot score (highest priority
  first) rather than CSV row order, to make the busiest segments easier to
  find when logging a crash or hazard. Pure UX nicety, doesn't change any
  scoring logic.
