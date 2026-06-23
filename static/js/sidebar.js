/* sidebar.js — Platform Controls / Filters / Map Options / Active Model / Legend. */
const SidebarModule = (function () {
  function emitGlobalChange() { document.dispatchEvent(new CustomEvent("app:globalChanged")); }
  function emitMapStyleChange() { document.dispatchEvent(new CustomEvent("app:mapStyleChanged")); }
  function emitCrashFilterChange() { document.dispatchEvent(new CustomEvent("app:crashFilterChanged")); }

  // ── SearchableSelect instances for sidebar dropdowns ───────────────────
  let _timeSS = null;
  let _roadTypeSS = null;
  let _riskSS = null;
  let _hotspotSS = null;
  let _crashSevSS = null;

  /** Plain string array → SearchableSelect */
  function makeSimpleSS(elId, opts, cfg) {
    const el = document.getElementById(elId);
    if (!el) return null;
    const ss = new SearchableSelect(el, cfg || {});
    ss.setOptions(opts, (s) => s, (s) => s);
    return ss;
  }

  function renderLegend() {
    const mode = AppState.mapOptions.mode;
    const opts = AppState.sidebarOptions;
    let palette, order;
    if (mode === "Risk Score") {
      palette = opts.risk_palette; order = RISK_ORDER;
    } else if (mode === "Hotspot Score") {
      palette = opts.hotspot_palette; order = HOTSPOT_ORDER;
    } else if (mode === "Road Type") {
      // Problem 5: exactly three categories
      palette = ROAD_TYPE_PALETTE; order = ROAD_TYPE_ORDER;
    } else {
      palette = {
        "≥80 km/h": "#ef4444", "60 km/h": "#f97316",
        "40 km/h": "#60a5fa", "<40 km/h": "#34d399"
      };
      order = Object.keys(palette);
    }

    const el = document.getElementById("sidebar-legend");
    el.innerHTML = order
      .map((k) =>
        `<div class="legend-row">
           <div class="legend-swatch" style="background:${palette[k]}"></div>
           <span class="legend-label">${escapeHtml(k)}</span>
         </div>`
      ).join("");
  }

  async function init() {
    const opts = await apiGet("/sidebar-options");
    AppState.sidebarOptions = opts;
    AppState.time = opts.default_time;
    AppState.filters.speed_min = opts.speed_min;
    AppState.filters.speed_max = opts.speed_max;

    document.getElementById("ctrl-date").value = AppState.date;

    // ── Time slot ── searchable
    _timeSS = makeSimpleSS("ctrl-time", opts.time_opts, { placeholder: "Select time slot…" });
    if (_timeSS) {
      _timeSS.setValue(opts.default_time);
      _timeSS.onChange((val) => { AppState.time = val; emitGlobalChange(); });
    }

    // ── Road Type filter ── searchable (small list but consistent UX)
    const roadTypeOptions = ["All", "National Highway", "State Highway", "Urban Road"];
    _roadTypeSS = makeSimpleSS("filter-road-type", roadTypeOptions, { placeholder: "Filter road type…" });
    if (_roadTypeSS) {
      _roadTypeSS.setValue("All");
      _roadTypeSS.onChange((val) => { AppState.filters.road_type = val; emitGlobalChange(); });
    }

    // ── Risk category filter ── searchable
    _riskSS = makeSimpleSS("filter-risk", opts.risk_cats, { placeholder: "Filter risk category…" });
    if (_riskSS) {
      _riskSS.setValue("All");
      _riskSS.onChange((val) => { AppState.filters.risk = val; emitGlobalChange(); });
    }

    // ── Hotspot category filter ── searchable
    _hotspotSS = makeSimpleSS("filter-hotspot", opts.hotspot_cats, { placeholder: "Filter hotspot…" });
    if (_hotspotSS) {
      _hotspotSS.setValue("All");
      _hotspotSS.onChange((val) => { AppState.filters.hotspot = val; emitGlobalChange(); });
    }

    // ── Crash severity filter ── searchable
    const crashSevOpts = ["All", "Fatal", "Major", "Minor"];
    _crashSevSS = makeSimpleSS("filter-crash-severity", crashSevOpts, { placeholder: "Filter severity…" });
    if (_crashSevSS) {
      _crashSevSS.setValue("All");
      _crashSevSS.onChange((val) => { AppState.crashSeverityFilter = val; emitCrashFilterChange(); });
    }

    document.getElementById("filter-speed-min").value = opts.speed_min;
    document.getElementById("filter-speed-max").value = opts.speed_max;
    document.getElementById("filter-speed-min").placeholder = opts.speed_min;
    document.getElementById("filter-speed-max").placeholder = opts.speed_max;

    renderLegend();

    // ── Platform controls ──
    document.getElementById("ctrl-date").addEventListener("change", (e) => {
      AppState.date = e.target.value || AppState.date;
      emitGlobalChange();
    });

    // ── Speed filters (plain number inputs — no searchable needed) ──
    document.getElementById("filter-speed-min").addEventListener("change", (e) => {
      AppState.filters.speed_min = e.target.value === "" ? opts.speed_min : Number(e.target.value);
      emitGlobalChange();
    });
    document.getElementById("filter-speed-max").addEventListener("change", (e) => {
      AppState.filters.speed_max = e.target.value === "" ? opts.speed_max : Number(e.target.value);
      emitGlobalChange();
    });

    // ── Map options (small static lists — keep as native selects but also wrap) ──
    document.getElementById("map-mode").addEventListener("change", (e) => {
      AppState.mapOptions.mode = e.target.value;
      renderLegend();
      emitMapStyleChange();
    });
    // Problem 7: Tile / basemap switcher
    document.getElementById("map-tile").addEventListener("change", (e) => {
      AppState.mapOptions.tile = e.target.value;
      emitMapStyleChange();
    });
    document.getElementById("map-line-width").addEventListener("input", (e) => {
      AppState.mapOptions.lineWidth = Number(e.target.value);
      document.getElementById("map-line-width-val").textContent = e.target.value;
      emitMapStyleChange();
    });
    // Render cap slider — now hidden/no-op since we always render all roads,
    // but keep listeners in case the element still exists in the HTML.
    const capEl = document.getElementById("map-render-cap");
    if (capEl) {
      capEl.addEventListener("change", () => { });
      capEl.addEventListener("input", () => { });
    }
  }

  return { init };
})();
