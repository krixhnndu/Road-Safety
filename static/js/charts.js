/* charts.js — shared Plotly.js primitives. Each tab module builds its own
   traces and calls plot(); this file only owns the dark-theme defaults and
   the color palettes (ported from RISK_PALETTE / HOTSPOT_PALETTE in the
   original unified_platform.py). */

const RISK_PALETTE = {
  "Aligned": "#22c55e",
  "Moderate Misalignment": "#eab308",
  "High Misalignment": "#f97316",
  "Critical Misalignment": "#ef4444",
};
const HOTSPOT_PALETTE = {
  "Safe": "#22c55e",
  "Moderate Risk": "#eab308",
  "High Risk": "#f97316",
  "Severe Hotspot": "#ef4444",
};
// Problem 5: Only three road categories — National Highway, State Highway, Urban Road
const ROAD_TYPE_PALETTE = {
  "National Highway": "#ef4444",   // red  — most prominent
  "State Highway":    "#f97316",   // orange
  "Urban Road":       "#60a5fa",   // blue
};
const ROAD_TYPE_ORDER = ["National Highway", "State Highway", "Urban Road"];

const RISK_ORDER = ["Aligned", "Moderate Misalignment", "High Misalignment", "Critical Misalignment"];
const HOTSPOT_ORDER = ["Safe", "Moderate Risk", "High Risk", "Severe Hotspot"];

const PAPER_BG = "#080e1a";
const PLOT_BG  = "#0d1b2e";

function scoreColor(v, invert) {
  v = Number(v);
  if (invert) {
    if (v >= 75) return "#ef4444";
    if (v >= 45) return "#f97316";
    if (v >= 25) return "#eab308";
    return "#22c55e";
  }
  if (v >= 75) return "#22c55e";
  if (v >= 50) return "#eab308";
  if (v >= 25) return "#f97316";
  return "#ef4444";
}

function baseLayout(over) {
  return Object.assign(
    {
      paper_bgcolor: PAPER_BG,
      plot_bgcolor:  PLOT_BG,
      font: { color: "#94a3b8", size: 11 },
      margin: { t: 30, b: 36, l: 46, r: 16 },
      xaxis: { color: "#64748b", gridcolor: "#13233a", zerolinecolor: "#13233a" },
      yaxis: { color: "#64748b", gridcolor: "#13233a", zerolinecolor: "#13233a" },
      showlegend: false,
    },
    over || {}
  );
}

function plot(divId, data, layoutOver, configOver) {
  const el = document.getElementById(divId);
  if (!el) return;
  Plotly.newPlot(
    el,
    data,
    baseLayout(layoutOver),
    Object.assign({ displayModeBar: false, responsive: true }, configOver || {})
  );
}

/** Tiny HTML color-key legend, used where bar ordering matters and a native
    Plotly legend (with its own implicit reordering) would be awkward. */
function renderColorLegend(containerId, palette, order) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const keys = order || Object.keys(palette);
  el.innerHTML = keys
    .map(
      (k) => `<span style="display:inline-flex;align-items:center;gap:5px;margin:0 12px 4px 0;font-size:.68rem;color:#94a3b8;">
        <span style="width:10px;height:10px;border-radius:2px;background:${palette[k]};display:inline-block;"></span>${escapeHtml(k)}
      </span>`
    )
    .join("");
}

function truncate(s, n) {
  s = s || "";
  return s.length > n ? s.slice(0, n) + "…" : s;
}
