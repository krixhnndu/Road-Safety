/* map.js — TAB 1: Interactive Map + Segment Detail panel.
 *
 * Architecture (per spec):
 *   - Display layer: the FULL classified road network (all 5498 features from
 *     bengaluru_roads_classified / road_network.geojson). NO render cap — every
 *     road is drawn as a continuous geometry exactly as exported by Detection 9.
 *   - Analytics layer: scoring data from /api/segments/map, joined by segment_id.
 *   - Interaction: clicking a polyline selects that segment and loads its detail
 *     panel. Segmentation is only used for analysis, never for display splitting.
 *
 * Road type palette (Problem 5 — three categories only):
 *   National Highway  → #ef4444  (red)
 *   State Highway     → #f97316  (orange)
 *   Urban Road        → #60a5fa  (blue)
 *
 * Basemaps (Problem 7): Dark, Street, Satellite — all restored.
 */
const MapModule = (function () {
  let leafletMap = null;
  let tileLayer = null;
  let roadLayer = null;     // L.geoJSON layer — the full network display layer
  let geometryById = {};       // segment_id → coordinates (for legacy join path)
  let featureById = {};       // segment_id → GeoJSON feature (full geometry)
  let cachedSegments = [];      // analytics data from /api/segments/map
  let activeHazardSet = new Set();
  let currentMode = "Road Type"; // default colour mode on load
  let _segmentSS = null;        // SearchableSelect instance for segment-select
  let selectedSegmentId = null; // Currently selected segment ID
  let layerById = {};           // Map of segment_id to Leaflet layer

  // ── Basemap definitions (Problem 7: all three restored) ────────────────────
  const TILE_DEFS = {
    Street: {
      url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      subdomains: "abc",
      attribution: "© OpenStreetMap contributors",
    },
    Satellite: {
      url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      attribution: "Tiles © Esri — Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community",
    },
  };

  function setTileLayer(name) {
    const def = TILE_DEFS[name] || TILE_DEFS.Street;
    if (tileLayer) leafletMap.removeLayer(tileLayer);
    tileLayer = L.tileLayer(def.url, {
      subdomains: def.subdomains || "",
      attribution: def.attribution,
      maxZoom: 19,
    });
    tileLayer.addTo(leafletMap);
  }

  // ── Road type helpers ───────────────────────────────────────────────────────
  function roadTypeColor(roadType) {
    return ROAD_TYPE_PALETTE[roadType] || "#94a3b8";
  }

  function roadTypeWeight(roadType) {
    if (roadType === "National Highway") return 4;
    if (roadType === "State Highway") return 3;
    return 2;
  }

  // ── Colour for a segment in the current mode ────────────────────────────────
  function colorForSegment(p, mode) {
    if (!p) return roadTypeColor("Urban Road"); // fallback before analytics loads
    if (mode === "Risk Score") return RISK_PALETTE[p.ai_risk_label] || "#eab308";
    if (mode === "Hotspot Score") return HOTSPOT_PALETTE[p.hotspot_category] || "#f97316";
    if (mode === "Road Type") return roadTypeColor(p.road_type);
    // Speed mode
    const spd = p.posted_speed_limit || 0;
    if (spd >= 80) return "#ef4444";
    if (spd >= 60) return "#f97316";
    if (spd >= 40) return "#60a5fa";
    return "#34d399";
  }

  // ── Popup HTML ──────────────────────────────────────────────────────────────
  function buildPopupHtml(p, hasHazard) {
    if (!p) {
      return `<div style="font-family:system-ui;background:#0d1b2e;color:#e2e8f0;
              padding:10px;border-radius:8px;min-width:200px;">
        <div style="color:#60a5fa;font-weight:700">${escapeHtml(p && p.human_segment_id || "Road")}</div>
        <div style="color:#64748b;font-size:.8rem">Analytics loading…</div>
      </div>`;
    }
    const rc = p.ai_risk_label;
    const hsc = p.hotspot_category;
    const color = RISK_PALETTE[rc] || "#eab308";
    const tcColor = ROAD_TYPE_PALETTE[p.road_type] || "#94a3b8";
    const hazardBanner = hasHazard
      ? `<div style="margin-top:8px;padding:6px 8px;background:#4c0519;border-radius:5px;
           font-size:.7rem;color:#f87171;font-weight:700">⚠️ ACTIVE HAZARD</div>`
      : "";
    return `
    <div style="font-family:system-ui;min-width:240px;background:#0d1b2e;color:#e2e8f0;
                padding:14px;border-radius:10px;border:1px solid #1a2d45">
      <div style="font-size:1.05rem;font-weight:700;color:#60a5fa">
        ${escapeHtml(p.human_segment_id)}
        <span style="font-size:.7rem;color:#94a3b8">#${p.segment_id}</span>
      </div>
      <div style="font-size:.8rem;color:#94a3b8;margin-top:2px">${escapeHtml(p.road_name)}</div>
      <div style="font-size:.68rem;font-weight:700;color:${tcColor}">${escapeHtml(p.road_type)}</div>
      <hr style="border-color:#1a2d45;margin:8px 0">
      <table style="width:100%;font-size:.76rem;border-collapse:collapse">
        <tr><td style="color:#64748b;padding:2px 0">Posted Limit</td>
            <td style="color:#fbbf24;font-weight:700">${p.posted_speed_limit} km/h</td></tr>
        <tr><td style="color:#64748b">AI Safe Speed</td>
            <td style="color:#22c55e;font-weight:700">${p.final_safe_speed} km/h</td></tr>
        <tr><td style="color:#64748b">Risk Category</td>
            <td style="color:${color};font-weight:700">${escapeHtml(rc)}</td></tr>
        <tr><td style="color:#64748b">Risk Probability</td>
            <td style="color:${color}">${(p.ai_risk_probability * 100).toFixed(1)}%</td></tr>
        <tr><td style="color:#64748b">Risk Score</td>
            <td><b>${p.road_risk_score}/100</b></td></tr>
        <tr><td style="color:#64748b">Hotspot</td>
            <td style="color:${HOTSPOT_PALETTE[hsc] || '#f97316'}">${p.hotspot_score} — ${escapeHtml(hsc)}</td></tr>
        <tr><td style="color:#64748b">Infrastructure</td>
            <td>${p.infrastructure_score}/100</td></tr>
        <tr><td style="color:#64748b">Exposure</td>
            <td>${p.exposure_score}/100</td></tr>
        <tr><td style="color:#64748b">Crash Risk</td>
            <td>${p.crash_risk_score}/100</td></tr>
        <tr><td style="color:#64748b">Fatal Crashes</td>
            <td style="color:${p.fatal_crashes > 0 ? '#ef4444' : '#e2e8f0'}">${p.fatal_crashes}</td></tr>
        ${p.weather_icon ? `<tr><td style="color:#64748b">Weather</td>
            <td style="color:${p.weather_color || '#fbbf24'};font-weight:700">${escapeHtml(p.weather_icon)} ${escapeHtml(p.weather_condition)}</td></tr>
        <tr><td style="color:#64748b">Rainfall</td>
            <td style="color:#60a5fa">${typeof p.rainfall_mmhr === 'number' ? p.rainfall_mmhr.toFixed(2) : '0.00'} mm/hr</td></tr>` : ''}
      </table>
      ${hazardBanner}
      <div style="margin-top:8px;padding:6px 8px;background:#030a1a;border-radius:6px;
                  font-size:.7rem;color:#a78bfa">
        🤖 ${escapeHtml(p.top_ai_factors || "—")}
      </div>
    </div>`;
  }

  function buildTooltip(roadName, roadType, segId) {
    return `${escapeHtml(roadName)} <span style="color:${roadTypeColor(roadType)}">[${escapeHtml(roadType)}]</span> #${segId}`;
  }

  // ── Legend overlay ──────────────────────────────────────────────────────────
  function renderMapLegendOverlay(mode) {
    let palette, order;
    if (mode === "Risk Score") { palette = RISK_PALETTE; order = RISK_ORDER; }
    else if (mode === "Hotspot Score") { palette = HOTSPOT_PALETTE; order = HOTSPOT_ORDER; }
    else if (mode === "Road Type") { palette = ROAD_TYPE_PALETTE; order = ROAD_TYPE_ORDER; }
    else {
      palette = {
        "≥80 km/h": "#ef4444", "60 km/h": "#f97316",
        "40 km/h": "#60a5fa", "<40 km/h": "#34d399"
      };
      order = Object.keys(palette);
    }

    let el = document.getElementById("map-legend-overlay");
    if (!el) {
      el = document.createElement("div");
      el.id = "map-legend-overlay";
      el.className = "map-legend";
      document.getElementById("leaflet-map").appendChild(el);
    }
    el.innerHTML =
      `<div class="legend-title">${escapeHtml(mode)}</div>` +
      order.map((k) =>
        `<div class="legend-row">
           <div class="legend-swatch" style="background:${palette[k]}"></div>
           <span class="legend-label">${escapeHtml(k)}</span>
         </div>`
      ).join("");
  }

  // ── Build a lookup of analytics data by segment_id ─────────────────────────
  function buildAnalyticsLookup(segments) {
    const lu = {};
    segments.forEach((s) => { lu[s.segment_id] = s; });
    return lu;
  }

  // ── Load and render the FULL road network GeoJSON ─────────────────────────
  // Problem 1-4: All 5498 features, exact geometry, no cap, no fragmentation.
  async function loadAndRenderNetwork(analyticsData) {
    const mode = AppState.mapOptions.mode;
    const width = AppState.mapOptions.lineWidth;

    // Load GeoJSON (cached in memory after first load)
    let gj;
    if (MapModule._geojsonCache) {
      gj = MapModule._geojsonCache;
    } else {
      const res = await fetch("/static/geojson/road_network.geojson");
      gj = await res.json();
      MapModule._geojsonCache = gj;
      // Build feature lookup
      gj.features.forEach((f) => {
        const id = f.properties.segment_id;
        featureById[id] = f;
        // Also store coordinates for legacy compatibility
        const g = f.geometry;
        if (g.type === "LineString") {
          geometryById[id] = g.coordinates;
        } else if (g.type === "MultiLineString") {
          geometryById[id] = g.coordinates.flat();
        }
      });
    }

    const analyticsLookup = analyticsData ? buildAnalyticsLookup(analyticsData) : {};

    // Remove old layer
    if (roadLayer) { leafletMap.removeLayer(roadLayer); roadLayer = null; }
    layerById = {}; // Clear layer lookup

    // Create new GeoJSON layer — all features, exact geometry
    roadLayer = L.geoJSON(gj, {
      style: (feature) => {
        const id = feature.properties.segment_id;
        const seg = analyticsLookup[id];
        const roadType = (seg && seg.road_type) || feature.properties.road_class;
        const color = seg ? colorForSegment(seg, mode) : roadTypeColor(roadType);
        const baseWeight = roadTypeWeight(roadType);
        const extraWeight = (seg && seg.ai_risk_label === "Critical Misalignment") ? 2 : 0;
        const isHazard = activeHazardSet.has(id);
        const isSelected = (id === selectedSegmentId);
        return {
          color: isSelected ? "#00ffff" : (isHazard ? "#fbbf24" : color),
          weight: (width + baseWeight + extraWeight) + (isSelected ? 5 : 0),
          opacity: isSelected ? 1.0 : 0.88,
          lineCap: "round",
          lineJoin: "round",
        };
      },
      onEachFeature: (feature, layer) => {
        const id = feature.properties.segment_id;
        layerById[id] = layer; // Save layer to lookup
        
        const seg = analyticsLookup[id];
        const roadName = (seg && seg.road_name) || feature.properties.road_name || "Unnamed";
        const roadType = (seg && seg.road_type) || feature.properties.road_class || "Urban Road";
        const hasHazard = activeHazardSet.has(id);

        layer.bindTooltip(buildTooltip(roadName, roadType, id), { sticky: true });
        layer.bindPopup(buildPopupHtml(seg, hasHazard), { maxWidth: 300 });
        layer.on("click", async () => {
          // Open loading popup immediately
          layer.setPopupContent(buildPopupHtml(null, hasHazard));
          layer.openPopup();

          // Load sidebar analytics
          selectSegment(id, false);

          // Update popup with latest analytics data
          try {
            const d = await apiGet(`/segments/${id}`, {
              date: AppState.date,
              time: AppState.time
            });

            // Convert detail response to popup-compatible format
            const popupData = {
              segment_id: d.segment_id,
              human_segment_id: d.human_segment_id,
              road_name: d.road_name,
              road_type: d.road_type,
              posted_speed_limit: d.speed.posted_speed,
              final_safe_speed: d.speed.recommended_speed,
              ai_risk_label: d.info.risk_category,
              ai_risk_probability: d.scores.ai_risk_probability / 100,
              road_risk_score: d.scores.road_risk_score,
              hotspot_score: d.scores.hotspot_score,
              hotspot_category: d.info.hotspot_category,
              infrastructure_score: d.scores.infrastructure_score,
              exposure_score: d.scores.exposure_now,
              crash_risk_score: d.scores.crash_risk_score,
              fatal_crashes: d.info.fatal_crashes,
              top_ai_factors: d.factors.map(f => f.label).join(", "),
              weather_icon: d.weather ? d.weather.weather_icon : null,
              weather_condition: d.weather ? d.weather.weather_condition : null,
              weather_color: d.weather ? d.weather.weather_color : null,
              rainfall_mmhr: d.weather ? d.weather.rainfall_mmhr : 0,
            };

            layer.setPopupContent(
              buildPopupHtml(popupData, d.has_active_hazard)
            );
          } catch (err) {
            console.error(err);
            layer.setPopupContent(`
            <div style="padding:10px;color:#ef4444">
                Failed to load analytics
            </div>
        `);
          }
        });
      },
      // Use canvas renderer for performance with 5000+ features
      renderer: L.canvas(),
    });

    roadLayer.addTo(leafletMap);
    renderMapLegendOverlay(mode);
  }

  // ── Re-style existing layer (avoids re-parsing GeoJSON on mode change) ─────
  function restyleNetwork(analyticsData) {
    if (!roadLayer) return;
    const mode = AppState.mapOptions.mode;
    const width = AppState.mapOptions.lineWidth;
    const analyticsLookup = buildAnalyticsLookup(analyticsData || cachedSegments);

    // Determine whether any filter is active so we know whether to hide
    // segments absent from the filtered analytics result set.
    const f = AppState.filters;
    const filtersActive = (
      (f.road_type && f.road_type !== "All") ||
      (f.risk      && f.risk      !== "All") ||
      (f.hotspot   && f.hotspot   !== "All") ||
      (f.speed_min !== null && f.speed_min !== "") ||
      (f.speed_max !== null && f.speed_max !== "")
    );

    roadLayer.eachLayer((layer) => {
      const id = layer.feature.properties.segment_id;
      const seg = analyticsLookup[id];

      // If filters are active and this segment is not in the filtered result,
      // hide it by zeroing opacity and weight.
      if (filtersActive && !seg) {
        layer.setStyle({ opacity: 0, weight: 0, fillOpacity: 0 });
        return;
      }

      // Segment passes filter (or no filter active) — apply normal style.
      const roadType = (seg && seg.road_type) || layer.feature.properties.road_class;
      const color = seg ? colorForSegment(seg, mode) : roadTypeColor(roadType);
      const baseWeight = roadTypeWeight(roadType);
      const extraWeight = (seg && seg.ai_risk_label === "Critical Misalignment") ? 2 : 0;
      const isHazard = activeHazardSet.has(id);
      const isSelected = (id === selectedSegmentId);
      layer.setStyle({
        color: isSelected ? "#00ffff" : (isHazard ? "#fbbf24" : color),
        weight: (width + baseWeight + extraWeight) + (isSelected ? 5 : 0),
        opacity: isSelected ? 1.0 : 0.88,
      });
    });

    renderMapLegendOverlay(mode);
  }

  // ── Quick-analytics charts (same as before) ─────────────────────────────────
  function renderQuickCharts(qc) {
    plot(
      "chart-risk-dist",
      [{
        type: "bar",
        x: qc.risk_dist.map((d) => d.label),
        y: qc.risk_dist.map((d) => d.count),
        marker: { color: qc.risk_dist.map((d) => RISK_PALETTE[d.label]) }
      }],
      { margin: { t: 6, b: 56, l: 30, r: 6 }, xaxis: { tickfont: { size: 7 } }, yaxis: { tickfont: { size: 7 } } }
    );
    plot(
      "chart-hotspot-dist",
      [{
        type: "pie",
        labels: qc.hotspot_dist.map((d) => d.label),
        values: qc.hotspot_dist.map((d) => d.count),
        marker: { colors: qc.hotspot_dist.map((d) => HOTSPOT_PALETTE[d.label]) },
        textinfo: "none", hole: 0.4
      }],
      {
        margin: { t: 6, b: 6, l: 6, r: 6 }, showlegend: true,
        legend: { font: { size: 7 }, bgcolor: "rgba(0,0,0,0)", orientation: "h", y: -0.1 }
      }
    );
    plot(
      "chart-speed-dist",
      [{ type: "histogram", x: qc.speed_dist, nbinsx: 12, marker: { color: "#a78bfa" } }],
      {
        margin: { t: 15, b: 40, l: 45, r: 15 },
        xaxis: { title: { text: "speed", font: { size: 9 } }, tickfont: { size: 7 } },
        yaxis: { title: { text: "segments", font: { size: 9 } }, tickfont: { size: 7 } }
      }
    );
  }

  // ── Segment detail panel ────────────────────────────────────────────────────
  function sbarHtml(label, val, color, maxVal) {
    maxVal = maxVal || 100;
    const pct = Math.min(100, Math.max(0, (Number(val) / maxVal) * 100));
    return `<div class="sbar">
      <div class="sbar-lbl">
        <span>${escapeHtml(label)}</span>
        <span style="color:${color}">${Number(val).toFixed(0)}</span>
      </div>
      <div class="sbar-track">
        <div class="sbar-fill" style="width:${pct.toFixed(1)}%;background:${color}"></div>
      </div>
    </div>`;
  }
  function irowHtml(label, val, color) {
    color = color || "#e2e8f0";
    return `<div class="irow">
      <span class="irow-l">${escapeHtml(label)}</span>
      <span class="irow-v" style="color:${color}">${escapeHtml(String(val))}</span>
    </div>`;
  }
  function probBarHtml(label, val, color) {
    const pct = Math.min(100, Math.max(0, Number(val) * 100));
    return `<div class="prob-wrap">
      <div class="prob-lbl">
        <span>${escapeHtml(label)}</span>
        <span style="color:${color}">${pct.toFixed(1)}%</span>
      </div>
      <div class="prob-track">
        <div class="prob-fill" style="width:${pct.toFixed(1)}%;background:${color}"></div>
      </div>
    </div>`;
  }

  function renderDetailPanel(d) {
    const s = d.scores;
    const hazardBanner = d.has_active_hazard
      ? `<div class="congestion-note">⚠️ Active hazard — temporary speed limit: <b>${d.hazard_temp_speed} km/h</b></div>`
      : "";
    const bsBanner = d.is_blackspot
      ? `<div class="bs-banner"><div class="bs-dot"></div>ACCIDENT BLACKSPOT</div>`
      : "";
    // ── Traffic detail block — reference-image style ────────────────────
    const trafficInfo = d.traffic;
    const _tScore = trafficInfo ? (trafficInfo.congestion_score * 100).toFixed(0) : 0;
    const _tColor = trafficInfo ? trafficInfo.condition_color : '#64748b';

    // Alert banner (near top of panel, only when congestion >= Heavy)
    const trafficBanner = (trafficInfo && trafficInfo.alert)
      ? `<div class="traffic-banner">
          <div class="traffic-dot"></div>
          ${escapeHtml(trafficInfo.message || 'TRAFFIC CONGESTION AHEAD')}
          <br><small style="opacity:.85">Congestion Score: ${_tScore}%</small>
        </div>`
      : "";

    // Full traffic card (always rendered after weather panel)
    const trafficDetailHtml = (trafficInfo && trafficInfo.available)
      ? `<div class="traffic-detail-card">
          <div class="traffic-detail-header" style="color:${_tColor}">
             TRAFFIC CONDITIONS
          </div>
          <div class="traffic-condition-row">
            <span class="traffic-condition-dot" style="background:${_tColor}"></span>
            <span class="traffic-condition-label" style="color:${_tColor}">
              ${escapeHtml(trafficInfo.condition)}
            </span>
          </div>
          ${irowHtml('Congestion Level', trafficInfo.congestion_level || '—', _tColor)}
          ${irowHtml('Congestion Score', _tScore + '%', _tColor)}
          ${trafficInfo.avg_speed_kmph != null ? irowHtml('Avg Traffic Speed', trafficInfo.avg_speed_kmph + ' km/h', '#60a5fa') : ''}
          ${trafficInfo.vehicle_density != null ? irowHtml('Vehicle Density', trafficInfo.vehicle_density + ' veh/km', '#a78bfa') : ''}
          ${trafficInfo.incident && trafficInfo.incident !== 'None' ? irowHtml('Incident', trafficInfo.incident, '#f87171') : ''}
          <div class="traffic-warning-box" style="border-color:${_tColor}40;">
            <div class="traffic-warning-title" style="color:${_tColor}">⚠ Traffic Warning</div>
            <div class="traffic-warning-msg">${escapeHtml(trafficInfo.warning || '—')}</div>
          </div>
          <div style="font-size:.66rem;color:#475569;margin-top:8px;text-align:right;">📅 ${escapeHtml(trafficInfo.timestamp || '—')}</div>
        </div>`
      : `<div class="traffic-detail-card" style="opacity:.45;">
          <div class="traffic-detail-header">🚦 TRAFFIC CONDITIONS</div>
          <div style="color:#64748b;font-size:.78rem;padding:6px 0;">No traffic data for this segment.</div>
         </div>`;
    const tcColor = ROAD_TYPE_PALETTE[d.road_type] || "#94a3b8";
    const congestionNote =
      ["Moderate", "Severe"].includes(d.congestion_category)
        ? `<div class="congestion-note"> ${escapeHtml(d.congestion_category)} congestion — adjusted to actual flow (${d.operating_speed_mean.toFixed(0)} km/h vs ${d.speed.posted_speed} km/h posted).</div>`
        : d.congestion_smoothed
          ? `<div class="congestion-note">↘ Speed tapered for downstream congestion.</div>`
          : "";

    const factorsHtml = d.factors.map((f) =>
      `<div class="factor-pill f-${f.severity}">${escapeHtml(f.label)}</div>`
    ).join("");
    const cardStyle = d.speed.is_hazard_override ? "style='border:2px solid #fbbf24;background:#18150a;'" : "";
    const speedColor = d.speed.is_hazard_override ? "#fbbf24" : "#60a5fa";

    document.getElementById("segment-detail-panel").innerHTML = `
      <div class="seg-header">
        <div class="seg-id">${escapeHtml(d.human_segment_id)}</div>
        <div class="seg-name">${escapeHtml(d.road_name)}</div>
        <span class="seg-type" style="background:${tcColor}22;color:${tcColor}">${escapeHtml(d.road_type)}</span>
      </div>
      ${bsBanner}${hazardBanner}${trafficBanner}
      <div class="speed-card" ${cardStyle}>
        <div class="speed-title" style="color:${d.speed.is_hazard_override ? '#fbbf24' : '#64748b'}">
          Recommended Safe Speed${d.speed.is_hazard_override ? ' (Hazard Override)' : ''}
        </div>
        <div class="speed-main" style="color:${speedColor}">${d.speed.recommended_speed}</div>
        <div class="speed-unit">km/h</div>
        <div class="speed-range">AI Engine: ${d.speed.ai_speed} km/h &nbsp;|&nbsp; VZ Tolerance: ${d.speed.tolerance} km/h</div>
        <div class="speed-posted">Posted: <span style="color:#fbbf24">${d.speed.posted_speed} km/h</span></div>
        ${d.weather && d.weather.speed_reduction > 0 ? `
        <div class="wx-impact-box">
          <div class="wx-impact-title">🌦 Weather Impact</div>
          ${irowHtml('Base Safe Speed', (d.weather.base_speed ?? d.speed.ai_speed) + ' km/h', '#94a3b8')}
          ${irowHtml('Weather', escapeHtml(d.weather.weather_icon) + ' ' + escapeHtml(d.weather.weather_condition), d.weather.weather_color)}
          ${irowHtml('Weather Reduction', '-' + d.weather.speed_reduction + ' km/h', '#f97316')}
        </div>` : ""}
      </div>
      <div class="panel">
        <h4> Score Profile</h4>
        ${sbarHtml("Road Risk Score", s.road_risk_score, scoreColor(s.road_risk_score, true))}
        ${sbarHtml("AI Risk Probability", s.ai_risk_probability, RISK_PALETTE[d.ai_risk_label] || "#eab308")}
        ${sbarHtml("Hotspot Score", s.hotspot_score, scoreColor(s.hotspot_score, true))}
        ${sbarHtml("Exposure (Now)", s.exposure_now, scoreColor(s.exposure_now, true))}
        ${sbarHtml("Infrastructure", s.infrastructure_score, scoreColor(s.infrastructure_score))}
        ${sbarHtml("Crash Risk", s.crash_risk_score, scoreColor(s.crash_risk_score, true))}
        ${sbarHtml("Road Function", s.road_function_score, "#a78bfa")}
        ${sbarHtml("Speed Safety", s.speed_safety_score, scoreColor(s.speed_safety_score))}
        ${sbarHtml("Congestion Index", s.congestion_index, scoreColor(s.congestion_index, true))}
      </div>
      ${congestionNote}
      <div class="panel">
        <h4> Segment Info</h4>
        ${irowHtml("Segment ID", `#${d.segment_id} (${d.human_segment_id})`)}
        ${irowHtml("Road Type", d.road_type, tcColor)}
        ${irowHtml("Start KM", `${d.info.start_km.toFixed(1)} km`)}
        ${irowHtml("End KM", `${d.info.end_km.toFixed(1)} km`)}
        ${irowHtml("Risk Category", d.info.risk_category, RISK_PALETTE[d.info.risk_category])}
        ${irowHtml("Hotspot", d.info.hotspot_category, HOTSPOT_PALETTE[d.info.hotspot_category])}
        ${irowHtml("Exposure Tier", d.info.exposure_tier)}
        ${irowHtml("Schools Nearby", d.info.schools_count)}
        ${irowHtml("Minor Crashes", d.info.minor_crashes, "#22c55e")}
        ${irowHtml("Major Crashes", d.info.major_crashes, "#f97316")}
        ${irowHtml("Fatal Crashes", d.info.fatal_crashes, "#ef4444")}
        ${irowHtml("Temporal Time", d.info.time)}
      </div>
      <div class="panel">
        <h4> Risk Probabilities</h4>
        ${d.probabilities.map((p) => probBarHtml(p.label, p.value, p.color)).join("")}
      </div>
      <div class="xai-box">
        <div class="xai-title"> AI Explanation — ${d.speed.recommended_speed} km/h</div>
        <div style="color:#94a3b8;font-size:.75rem;margin-bottom:10px;">
          Safe speed set to <b style="color:#60a5fa">${d.speed.recommended_speed} km/h</b>
          based on conditions at <b>${escapeHtml(d.info.time)}</b>:
        </div>
        ${factorsHtml}
        <div class="vz-box" style="margin-top:10px;">
          <b>Vision Zero Constraint:</b><br>
          min(AI Speed = ${d.speed.ai_speed} km/h, Human Tolerance = ${d.speed.tolerance} km/h)
          → <b>${d.speed.recommended_speed} km/h</b>
        </div>
      </div>
      ${d.weather ? `
      <div class="wx-detail-panel">
        <h4>🌦 Weather Intelligence</h4>
        ${irowHtml("Current Condition", `${escapeHtml(d.weather.weather_icon)} ${escapeHtml(d.weather.weather_condition)}`, d.weather.weather_color)}
        ${irowHtml("Rainfall Intensity", `${d.weather.rainfall_mmhr.toFixed(2)} mm/hr`, "#60a5fa")}
        ${irowHtml("Speed Reduction", d.weather.speed_reduction > 0 ? `-${d.weather.speed_reduction} km/h` : "None", d.weather.speed_reduction > 0 ? "#f97316" : "#22c55e")}
      </div>` : ""}
      ${trafficDetailHtml}
      <hr style="border:none;border-top:1px solid var(--border);margin:14px 0;">
      <div class="form-card">
        <div style="font-weight:700;font-size:.85rem;margin-bottom:8px;">🚨 Log Crash on This Segment</div>
        <div class="field">
          <select id="quick-crash-severity">
            <option>Minor</option><option>Major</option><option>Fatal</option>
          </select>
        </div>
        <button class="btn btn-primary btn-block" id="quick-crash-add-btn">➕ Add Crash</button>
      </div>`;

    document.getElementById("quick-crash-add-btn").onclick = async () => {
      const severity = document.getElementById("quick-crash-severity").value;
      try {
        await apiPost(`/segments/${d.segment_id}/crashes`, { severity });
        showToast(`✅ ${severity} crash logged on ${d.human_segment_id}`);
        document.dispatchEvent(new CustomEvent("app:globalChanged"));
      } catch (e) {
        showToast(e.message, true);
      }
    };
  }

  async function loadSegmentDetail(id) {
    try {
      const d = await apiGet(`/segments/${id}`, { date: AppState.date, time: AppState.time });
      renderDetailPanel(d);
    } catch (e) {
      console.error("loadSegmentDetail error:", e);
    }
  }

  function selectSegment(id, panTo = false) {
    const prevSelectedId = selectedSegmentId;

    // Update the searchable dropdown if it exists, else fall back to native select
    if (_segmentSS) {
      if (_segmentSS.getValue() !== String(id)) {
        _segmentSS.setValue(String(id));
      }
    } else {
      const sel = document.getElementById("segment-select");
      if (sel && [...sel.options].some((o) => o.value === String(id))) {
        if (sel.value !== String(id)) sel.value = String(id);
      }
    }

    if (prevSelectedId === id) {
      loadSegmentDetail(id);
      return;
    }

    selectedSegmentId = id;

    // 1. Reset style of the previously selected segment
    if (prevSelectedId && layerById[prevSelectedId]) {
      const prevLayer = layerById[prevSelectedId];
      roadLayer.resetStyle(prevLayer);
    }

    // 2. Style the newly selected segment
    if (id && layerById[id]) {
      const layer = layerById[id];
      const mode = AppState.mapOptions.mode;
      const width = AppState.mapOptions.lineWidth;
      const analyticsLookup = buildAnalyticsLookup(cachedSegments);
      const seg = analyticsLookup[id];
      const feature = layer.feature;
      const roadType = (seg && seg.road_type) || feature.properties.road_class;
      const color = seg ? colorForSegment(seg, mode) : roadTypeColor(roadType);
      const baseWeight = roadTypeWeight(roadType);
      const extraWeight = (seg && seg.ai_risk_label === "Critical Misalignment") ? 2 : 0;
      const isHazard = activeHazardSet.has(id);

      layer.setStyle({
        color: "#00ffff", // Neon cyan highlight
        weight: width + baseWeight + extraWeight + 5,
        opacity: 1.0,
      });

      if (typeof layer.bringToFront === "function") {
        layer.bringToFront();
      }

      // 3. Zoom/pan to the segment and fire click to open popup
      if (panTo) {
        if (typeof layer.getBounds === "function") {
          leafletMap.fitBounds(layer.getBounds(), { maxZoom: 16, animate: true });
        } else if (typeof layer.getLatLng === "function") {
          leafletMap.setView(layer.getLatLng(), 16, { animate: true });
        }
        layer.fire("click");
      }
    }

    loadSegmentDetail(id);
  }

  async function populateSegmentSelect() {
    const opts = await apiGet("/segments/options", baseParams({ scope: "filtered" }));

    if (!opts.length) {
      document.getElementById("segment-detail-panel").innerHTML =
        `<div class="loading-row">No segments match filters.</div>`;
      return;
    }

    // Label shown in the dropdown: "RoadType | Segment #ID | RoadName"
    // searchText includes segment_id, human_segment_id, road_name so all are searchable
    function segLabel(o) {
      return `${o.road_type || ""} | Segment #${o.segment_id} | ${o.road_name || o.label}`;
    }
    function segSearch(o) {
      // concatenate everything the user might type
      return [
        String(o.segment_id),
        o.human_segment_id || "",
        o.road_name || "",
        o.road_type || "",
        o.label || "",
      ].join(" ");
    }

    if (_segmentSS) {
      const prevValue = _segmentSS.getValue();
      _segmentSS.setOptions(opts, "segment_id", segLabel, segSearch);
      if (prevValue && opts.some((o) => String(o.segment_id) === prevValue)) {
        _segmentSS.setValue(prevValue);
      }
    }

    const currentId = _segmentSS ? _segmentSS.getValue() : String(opts[0].segment_id);
    if (currentId) {
      selectSegment(Number(currentId), false);
    }
  }

  // ── Top-level refresh ──────────────────────────────────────────────────────
  async function refresh() {
    // Fetch analytics (no render cap — fetch all)
    const params = baseParams({ render_cap: 99999 });
    let data;
    try {
      data = await apiGet("/segments/map", params);
    } catch (e) {
      console.error("segments/map fetch failed:", e);
      return;
    }

    cachedSegments = data.segments;
    activeHazardSet = new Set(data.active_hazard_segments);

    // If GeoJSON already loaded, just restyle; otherwise load + render full network
    if (roadLayer) {
      restyleNetwork(cachedSegments);
    } else {
      await loadAndRenderNetwork(cachedSegments);
    }

    // Fit bounds from data
    if (data.bounds) leafletMap.fitBounds(data.bounds);

    // Clear the render-cap warning — we always render everything
    const capWarn = document.getElementById("map-cap-warning");
    if (capWarn) capWarn.innerHTML = "";

    renderQuickCharts(data.quick_charts);
    await populateSegmentSelect();
  }

  // ── Initialization ─────────────────────────────────────────────────────────
  async function init() {
    leafletMap = L.map("leaflet-map", { preferCanvas: true }).setView([12.97, 77.59], 11);
    setTileLayer(AppState.mapOptions.tile);

    // Load the full road network immediately (Problem 4: show complete network first)
    await loadAndRenderNetwork(null);

    // Initialise searchable dropdown for segment selection
    const segSelectEl = document.getElementById("segment-select");
    _segmentSS = new SearchableSelect(segSelectEl, {
      placeholder: "Search by segment ID, road name or type…",
    });
    // When user picks a segment via the searchable dropdown, load its detail and zoom to it
    _segmentSS.onChange((val) => {
      if (val) {
        selectSegment(Number(val), true);
      }
    });

    // Style/tile change events
    document.addEventListener("app:mapStyleChanged", () => {
      setTileLayer(AppState.mapOptions.tile);
      restyleNetwork(cachedSegments);
    });

    // Full refresh (filters changed, date/time changed, etc.)
    await refresh();
  }

  return { init, refresh };
})();
