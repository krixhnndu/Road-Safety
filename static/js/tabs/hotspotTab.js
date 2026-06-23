/* hotspotTab.js — TAB 2: Hotspot Detection & Analysis. */
const HotspotTab = (function () {
  function renderCards(cards) {
    const colors = { Safe: "#22c55e", "Moderate Risk": "#eab308", "High Risk": "#f97316", "Severe Hotspot": "#ef4444" };
    document.getElementById("hotspot-cards").innerHTML = HOTSPOT_ORDER
      .map((cat) => `<div class="kpi"><div class="kpi-v" style="color:${colors[cat]}">${cards[cat] || 0}</div><div class="kpi-l">${escapeHtml(cat)}</div></div>`)
      .join("");
  }

  function renderTop20(rows) {
    const sorted = rows.slice().reverse();
    plot(
      "chart-hotspot-top20",
      [
        {
          type: "bar",
          orientation: "h",
          x: sorted.map((r) => r.hotspot_score),
          y: sorted.map((r) => truncate(r.road_name, 22)),
          marker: { color: sorted.map((r) => HOTSPOT_PALETTE[r.hotspot_category] || "#f97316") },
          customdata: sorted.map((r) => [r.crash_count, r.fatal_crashes, r.road_risk_score]),
          hovertemplate: "%{y}<br>Hotspot: %{x}<br>Crashes: %{customdata[0]} (Fatal %{customdata[1]})<br>Risk: %{customdata[2]}<extra></extra>",
        },
      ],
      { margin: { t: 6, b: 20, l: 150, r: 10 }, xaxis: { range: [0, 100], tickfont: { size: 8 } }, yaxis: { tickfont: { size: 8 } } }
    );
    renderColorLegend("chart-hotspot-top20-legend", HOTSPOT_PALETTE, HOTSPOT_ORDER);
  }

  function renderScatter(rows) {
    const traces = HOTSPOT_ORDER.map((cat) => {
      const subset = rows.filter((r) => r.hotspot_category === cat);
      return {
        type: "scatter",
        mode: "markers",
        name: cat,
        x: subset.map((r) => r.crash_risk_score),
        y: subset.map((r) => r.hotspot_score),
        text: subset.map((r) => r.road_name),
        marker: { color: HOTSPOT_PALETTE[cat], size: subset.map((r) => 6 + r.road_risk_score / 12) },
        hovertemplate: "%{text}<br>Crash Risk: %{x}<br>Hotspot: %{y}<extra></extra>",
      };
    });
    plot("chart-hotspot-scatter", traces, {
      margin: { t: 6, b: 40, l: 46, r: 10 },
      showlegend: true,
      legend: { font: { size: 9 }, bgcolor: "rgba(0,0,0,0)" },
      xaxis: { title: { text: "Crash Risk Score", font: { size: 10 } } },
      yaxis: { title: { text: "Hotspot Score", font: { size: 10 } } },
    });
  }

  function renderSevereTable(rows) {
    const cols = [
      ["human_segment_id", "Segment"], ["road_name", "Road"], ["road_type", "Type"],
      ["hotspot_score", "Hotspot"], ["road_risk_score", "Risk"], ["crash_risk_score", "Crash Risk"],
      ["fatal_crashes", "Fatal"], ["crash_count", "Crashes"], ["final_safe_speed", "Safe Speed"], ["posted_speed_limit", "Posted"],
    ];
    const el = document.getElementById("hotspot-severe-table");
    if (!rows.length) {
      el.innerHTML = `<div class="loading-row">No severe hotspots under current conditions.</div>`;
      return;
    }
    el.innerHTML = `<div class="data-table-wrap"><table class="data-table">
      <thead><tr>${cols.map((c) => `<th>${c[1]}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr>${cols.map((c) => `<td>${escapeHtml(r[c[0]])}</td>`).join("")}</tr>`).join("")}</tbody>
    </table></div>`;
  }

  async function refresh() {
    let data;
    try {
      data = await apiGet("/analytics/hotspot", { date: AppState.date, time: AppState.time });
    } catch (e) {
      console.error(e);
      return;
    }
    renderCards(data.cards);
    renderTop20(data.top20);
    renderScatter(data.scatter);
    renderSevereTable(data.severe_table);
  }

  return { refresh };
})();
