/* analyticsTab.js — TAB 7: Advanced Analytics Dashboard. */
const AnalyticsTab = (function () {
  function renderBox(rows) {
    const types = [...new Set(rows.map((r) => r.road_type))];
    const traces = types.map((t) => {
      const subset = rows.filter((r) => r.road_type === t);
      return {
        type: "box",
        name: t,
        y: subset.map((r) => r.road_risk_score),
        text: subset.map((r) => `Segment #${r.segment_id}`),
        marker: { color: ROAD_TYPE_PALETTE[t] || "#60a5fa" },
      };
    });
    plot("chart-adv-box", traces, { title: { text: "Risk Score by Road Type", font: { size: 12 } }, margin: { t: 30, b: 30, l: 40, r: 10 } });
  }

  function renderScatter1(rows) {
    const traces = RISK_ORDER.map((cat) => {
      const subset = rows.filter((r) => r.ai_risk_label === cat);
      return {
        type: "scatter", mode: "markers", name: cat,
        x: subset.map((r) => r.infrastructure_score), y: subset.map((r) => r.final_safe_speed),
        text: subset.map((r) => `Segment #${r.segment_id}`),
        marker: { color: RISK_PALETTE[cat], size: subset.map((r) => 5 + r.road_risk_score / 14) },
        hovertemplate: "%{text}<br>Infra: %{x}<br>Safe Speed: %{y}<extra></extra>",
      };
    });
    plot("chart-adv-scatter1", traces, {
      title: { text: "Infrastructure vs Safe Speed", font: { size: 12 } },
      margin: { t: 30, b: 30, l: 40, r: 10 }, showlegend: true, legend: { font: { size: 8 }, bgcolor: "rgba(0,0,0,0)" },
    });
  }

  function renderScatter2(rows) {
    const traces = HOTSPOT_ORDER.map((cat) => {
      const subset = rows.filter((r) => r.hotspot_category === cat);
      return {
        type: "scatter", mode: "markers", name: cat,
        x: subset.map((r) => r.exposure_score), y: subset.map((r) => r.crash_risk_score),
        text: subset.map((r) => `Segment #${r.segment_id}`),
        marker: { color: HOTSPOT_PALETTE[cat], size: subset.map((r) => 5 + r.hotspot_score / 14) },
        hovertemplate: "%{text}<br>Exposure: %{x}<br>Crash Risk: %{y}<extra></extra>",
      };
    });
    plot("chart-adv-scatter2", traces, {
      title: { text: "Exposure vs Crash Risk", font: { size: 12 } },
      margin: { t: 30, b: 30, l: 40, r: 10 }, showlegend: true, legend: { font: { size: 8 }, bgcolor: "rgba(0,0,0,0)" },
    });
  }



  function renderTopSafe(rows) {
    const sorted = rows.slice().reverse();
    plot(
      "chart-adv-topsafe",
      [
        {
          type: "bar", orientation: "h",
          x: sorted.map((r) => r.infrastructure_score), y: sorted.map((r) => `Segment #${r.segment_id}`),
          marker: { color: sorted.map((r) => r.final_safe_speed), colorscale: "Greens", showscale: true, colorbar: { title: { text: "Safe Speed", font: { size: 8 } }, tickfont: { size: 7 } } },
          hovertext: sorted.map((r) => `Risk: ${r.road_risk_score} | Safe Speed: ${r.final_safe_speed} km/h`),
        },
      ],
      { title: { text: "Safest 10 Segments (Infrastructure Score)", font: { size: 12 } }, margin: { t: 30, b: 20, l: 130, r: 10 }, xaxis: { tickfont: { size: 8 } }, yaxis: { tickfont: { size: 8 } } }
    );
  }

  function renderSummaryTable(rows) {
    const cols = [
      ["road_type", "Road Type"], ["Segments", "Segments"], ["Avg_Risk", "Avg Risk"], ["Avg_Safe_Speed", "Avg Safe Speed"],
      ["Avg_Infrastructure", "Avg Infra"], ["Avg_Exposure", "Avg Exposure"], ["Avg_Hotspot", "Avg Hotspot"], ["Fatal_Crashes", "Fatal Crashes"],
    ];
    document.getElementById("adv-summary-table").innerHTML = `<div class="data-table-wrap"><table class="data-table">
      <thead><tr>${cols.map((c) => `<th>${c[1]}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr>${cols.map((c) => `<td>${escapeHtml(r[c[0]])}</td>`).join("")}</tr>`).join("")}</tbody>
    </table></div>`;
  }

  async function refresh() {
    let data;
    try {
      data = await apiGet("/analytics/advanced", { date: AppState.date, time: AppState.time });
    } catch (e) {
      console.error(e);
      return;
    }
    renderBox(data.box);
    renderScatter1(data.scatter1);
    renderScatter2(data.scatter2);
    renderTopSafe(data.top_safe);
    renderSummaryTable(data.summary);
  }

  return { refresh };
})();
