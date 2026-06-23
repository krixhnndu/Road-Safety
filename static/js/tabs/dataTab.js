/* dataTab.js — TAB 8: Unified Predictions Dataset. */
const DataTab = (function () {
  let wired = false;

  const COLS = [
    ["human_segment_id", "Segment"], ["road_name", "Road"], ["road_type", "Type"],
    ["posted_speed_limit", "Posted"], ["speed_p85", "85th %ile"], ["final_safe_speed", "Safe Speed"],
    ["misalignment_score", "Misalign. Score"], ["misalignment_category", "Misalign. Category"], ["exposure_tier", "Exposure Tier"],
    ["congestion_index", "Congestion Idx"], ["congestion_category", "Congestion"],
    ["ai_risk_label", "Risk Label"], ["ai_risk_probability", "Risk Prob."],
    ["road_risk_score", "Risk Score"], ["hotspot_score", "Hotspot Score"], ["hotspot_category", "Hotspot"],
    ["infrastructure_score", "Infra"], ["exposure_score", "Exposure"], ["ptw_share_pct", "PTW %"],
    ["crash_risk_score", "Crash Risk"], ["road_function_score", "Road Function"],
    ["fatal_crashes", "Fatal"], ["crash_count", "Crashes"], ["blackspot_flag", "Blackspot"], ["top_ai_factors", "Top Factors"],
  ];

  function renderTable(rows, total) {
    const el = document.getElementById("data-table-wrap");
    if (!rows.length) {
      el.innerHTML = `<div class="loading-row">No segments match the current filters.</div>`;
      return;
    }
    el.innerHTML = `<div class="section-sub">${total.toLocaleString()} segments match current filters · sorted by Risk Score</div>
      <div class="data-table-wrap"><table class="data-table">
      <thead><tr>${COLS.map((c) => `<th>${c[1]}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr>${COLS.map((c) => `<td>${escapeHtml(r[c[0]])}</td>`).join("")}</tr>`).join("")}</tbody>
    </table></div>`;
  }

  function wire() {
    document.getElementById("export-filtered-btn").addEventListener("click", () => triggerDownload("/export/filtered", baseParams()));
    document.getElementById("export-full-btn").addEventListener("click", () => triggerDownload("/export/full", { date: AppState.date, time: AppState.time }));
  }

  async function refresh() {
    if (!wired) { wire(); wired = true; }
    let data;
    try {
      data = await apiGet("/segments/table", baseParams());
    } catch (e) {
      console.error(e);
      return;
    }
    renderTable(data.rows, data.total);
  }

  return { refresh };
})();
