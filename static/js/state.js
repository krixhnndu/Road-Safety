/* state.js — global, shared application state. */
function _today() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

const AppState = {
  date: _today(),
  time: null, // set from /api/sidebar-options default_time
  filters: { road_type: "All", risk: "All", hotspot: "All", speed_min: null, speed_max: null },
  crashSeverityFilter: "All",
  mapOptions: { mode: "Road Type", tile: "Street", lineWidth: 2, renderCap: 99999 },
  sidebarOptions: null,
  activeTab: "map",
};

/** Standard query params shared by almost every endpoint: date/time + filters. */
function baseParams(extra) {
  const p = { date: AppState.date, time: AppState.time };
  const f = AppState.filters;
  if (f.road_type && f.road_type !== "All") p.road_type = f.road_type;
  if (f.risk && f.risk !== "All") p.risk = f.risk;
  if (f.hotspot && f.hotspot !== "All") p.hotspot = f.hotspot;
  if (f.speed_min !== null && f.speed_min !== "") p.speed_min = f.speed_min;
  if (f.speed_max !== null && f.speed_max !== "") p.speed_max = f.speed_max;
  return Object.assign(p, extra || {});
}
