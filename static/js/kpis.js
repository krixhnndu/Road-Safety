/* kpis.js — top KPI row (ported from the `kpis = [...]` list in unified_platform.py). */
const KpiModule = (function () {
  async function refresh() {
    let k;
    try {
      k = await apiGet("/kpis", baseParams());
    } catch (e) {
      console.error(e);
      return;
    }
    const items = [
      [k.segments, "Segments", "sky"],
      [k.minor_crashes, "Minor Crashes", "green"],
      [k.major_crashes, "Major Crashes", "yellow"],
      [k.fatal_crashes, "Fatal Crashes", "red"],
      [k.total_crashes, "Total Crashes", "orange"],
      [k.severe_hotspots, "Severe Hotspots", "red"],
      [k.high_misalignment, "High Misalignment Roads", "orange"],
      [k.congested_now, "Congested Now", "yellow"],
      [`${k.avg_safe_speed} km/h`, "Avg Safe Speed", "blue"],
    ];
    document.getElementById("kpi-row").innerHTML = items
      .map(
        ([val, label, cls]) =>
          `<div class="kpi"><div class="kpi-v ${cls}">${escapeHtml(val)}</div><div class="kpi-l">${escapeHtml(label)}</div></div>`
      )
      .join("");
  }
  return { refresh };
})();
