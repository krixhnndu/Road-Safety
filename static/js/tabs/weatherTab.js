/* weatherTab.js — Weather Intelligence tab.
   Simulated IoT weather sensors: no external APIs used.
   Refreshes every 30 minutes matching the backend simulation cycle. */

const WeatherTab = (function () {
  const CONDITION_ORDER = [
    "Clear / Sunny",
    "Light Rain",
    "Moderate Rain",
    "Heavy Rainfall",
    "Extreme Rainfall / Storm",
  ];
  const CONDITION_ICONS = {
    "Clear / Sunny":            "☀",
    "Light Rain":               "🌦",
    "Moderate Rain":            "🌧",
    "Heavy Rainfall":           "⛈",
    "Extreme Rainfall / Storm": "⚠",
  };
  const CONDITION_COLORS = {
    "Clear / Sunny":            "#fbbf24",
    "Light Rain":               "#60a5fa",
    "Moderate Rain":            "#3b82f6",
    "Heavy Rainfall":           "#f97316",
    "Extreme Rainfall / Storm": "#ef4444",
  };

  let _refreshTimer = null;

  // ── helpers ──────────────────────────────────────────────────────────────
  function condColor(c) { return CONDITION_COLORS[c] || "#94a3b8"; }
  function condIcon(c)  { return CONDITION_ICONS[c]  || "☀"; }

  function esc(s) {
    if (s == null) return "";
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }

  function setHtml(id, html) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  }

  // ── Render summary KPI cards ──────────────────────────────────────────
  function renderSummary(s) {
    const iconColor = condColor(s.dominant_condition);
    setHtml("wx-kpis", `
      <div class="wx-kpi-grid">
        <div class="wx-kpi-card" style="border-color:${iconColor}40;">
        <div class="wx-kpi-label">Dominant Condition</div>
        <div class="wx-kpi-value">${esc(s.dominant_condition)}</div>
        </div>
        <div class="wx-kpi-card">
          <div class="wx-kpi-icon"></div>
          <div class="wx-kpi-label">Avg Rainfall</div>
          <div class="wx-kpi-value" style="color:#60a5fa">${s.avg_rainfall_mmhr.toFixed(2)} mm/hr</div>
        </div>
        <div class="wx-kpi-card" style="border-color:#f9731640;">
          <div class="wx-kpi-icon"></div>
          <div class="wx-kpi-label">Heavy Rainfall Segments</div>
          <div class="wx-kpi-value" style="color:#f97316">${s.heavy_count}</div>
        </div>
        <div class="wx-kpi-card" style="border-color:#ef444440;">
          <div class="wx-kpi-icon"></div>
          <div class="wx-kpi-label">Extreme Rainfall Segments</div>
          <div class="wx-kpi-value" style="color:#ef4444">${s.extreme_count}</div>
        </div>
        <div class="wx-kpi-card">
          <div class="wx-kpi-icon"></div>
          <div class="wx-kpi-label">Total Segments Monitored</div>
          <div class="wx-kpi-value" style="color:#a78bfa">${s.total_segments}</div>
        </div>
        <div class="wx-kpi-card">
          <div class="wx-kpi-icon"></div>
          <div class="wx-kpi-label">Last Sensor Cycle</div>
          <div class="wx-kpi-value" style="color:#94a3b8">${esc(s.last_updated)}</div>
        </div>
      </div>
    `);
  }

  // ── Plotly distribution chart ─────────────────────────────────────────
  function renderDistributionChart(dist) {
    const labels = dist.map(d => `${condIcon(d.condition)} ${d.condition}`);
    const counts = dist.map(d => d.count);
    const colors = dist.map(d => condColor(d.condition));

    Plotly.newPlot("wx-dist-chart", [{
      type: "bar",
      x: labels,
      y: counts,
      marker: { color: colors, opacity: 0.85 },
      text: dist.map(d => `${d.pct}%`),
      textposition: "outside",
    }], {
      paper_bgcolor: "transparent",
      plot_bgcolor: "#0d1b2e",
      font: { color: "#e2e8f0", size: 11 },
      title: { text: "Weather Distribution Across Road Segments", font: { color: "#e2e8f0", size: 13 } },
      xaxis: { gridcolor: "#1e3a5f", tickfont: { size: 10 } },
      yaxis: { gridcolor: "#1e3a5f", title: "Segment Count" },
      margin: { t: 40, l: 50, r: 20, b: 60 },
    }, { responsive: true, displayModeBar: false });
  }

  // ── Pie chart for severity distribution ───────────────────────────────
  function renderSeverityPie(dist) {
    const labels = dist.map(d => `${condIcon(d.condition)} ${d.condition}`);
    const values = dist.map(d => d.count);
    const colors = dist.map(d => condColor(d.condition));

    Plotly.newPlot("wx-severity-pie", [{
      type: "pie",
      labels,
      values,
      marker: { colors },
      textinfo: "label+percent",
      textfont: { size: 10, color: "#e2e8f0" },
      hole: 0.35,
    }], {
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { color: "#e2e8f0", size: 11 },
      title: { text: "Rainfall Severity Distribution", font: { color: "#e2e8f0", size: 13 } },
      showlegend: false,
      margin: { t: 40, l: 10, r: 10, b: 10 },
    }, { responsive: true, displayModeBar: false });
  }

  // ── Segment weather table ─────────────────────────────────────────────
  function renderSegmentTable(rows) {
    // Sort by rainfall descending
    rows = [...rows].sort((a, b) => b.rainfall_mmhr - a.rainfall_mmhr);
    // Show top 100 to keep table manageable
    const display = rows.slice(0, 100);
    const html = `
      <div style="overflow-x:auto;">
        <table class="data-table" style="font-size:.78rem;">
          <thead>
            <tr>
              <th>Segment</th>
              <th>Road Name</th>
              <th>Type</th>
              <th>Weather</th>
              <th>Rainfall (mm/hr)</th>
              <th>Speed Reduction</th>
              <th>Base Speed</th>
              <th>Weather-Adjusted Speed</th>
            </tr>
          </thead>
          <tbody>
            ${display.map(r => `
              <tr>
                <td>${esc(r.human_segment_id)}</td>
                <td>${esc(r.road_name)}</td>
                <td>${esc(r.road_type)}</td>
                <td style="color:${r.weather_color}">
                  ${esc(r.weather_icon)} ${esc(r.weather_condition)}
                </td>
                <td style="text-align:right">${r.rainfall_mmhr.toFixed(2)}</td>
                <td style="text-align:right;color:${r.speed_reduction > 0 ? '#f97316' : '#22c55e'}">
                  ${r.speed_reduction > 0 ? '-' : ''}${r.speed_reduction} km/h
                </td>
                <td style="text-align:right">${r.base_safe_speed} km/h</td>
                <td style="text-align:right;color:#60a5fa;font-weight:700">${r.weather_adjusted_speed} km/h</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
        ${rows.length > 100 ? `<div style="color:#64748b;font-size:.75rem;padding:8px;">Showing top 100 of ${rows.length} segments by rainfall intensity.</div>` : ''}
      </div>`;
    setHtml("wx-segment-table", html);
  }

  // ── Weather trend (simulated rolling window using current distribution) ─
  function renderTrendChart(dist) {
    // Simulate a 24h trend using the current distribution as baseline
    const hours = Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, '0')}:00`);
    const total = dist.reduce((s, d) => s + d.count, 0) || 1;

    // Build stacked traces per condition
    const traces = dist.map(d => {
      // Apply a sinusoidal modulation to simulate morning fog / afternoon storms
      const base = d.count / total;
      const values = hours.map((_, h) => {
        let mod = 1.0;
        if (d.condition === "Heavy Rainfall" || d.condition === "Extreme Rainfall / Storm") {
          mod = 0.5 + 0.5 * Math.sin((h - 14) * Math.PI / 12);
          mod = Math.max(0, mod);
        } else if (d.condition === "Clear / Sunny") {
          mod = 0.6 + 0.4 * Math.cos((h - 6) * Math.PI / 12);
          mod = Math.max(0, mod);
        }
        return Math.round(base * total * mod);
      });
      return {
        x: hours,
        y: values,
        type: "scatter",
        mode: "lines",
        name: `${condIcon(d.condition)} ${d.condition}`,
        line: { color: condColor(d.condition), width: 2 },
        fill: "tonexty",
        stackgroup: "one",
      };
    });

    Plotly.newPlot("wx-trend-chart", traces, {
      paper_bgcolor: "transparent",
      plot_bgcolor: "#0d1b2e",
      font: { color: "#e2e8f0", size: 11 },
      title: { text: "Simulated 24-Hour Weather Trend (Segment Count by Condition)", font: { color: "#e2e8f0", size: 13 } },
      xaxis: { gridcolor: "#1e3a5f", title: "Hour of Day" },
      yaxis: { gridcolor: "#1e3a5f", title: "Segments" },
      legend: { bgcolor: "transparent", font: { size: 10 }, orientation: "h", y: -0.25 },
      margin: { t: 40, l: 50, r: 20, b: 80 },
    }, { responsive: true, displayModeBar: false });
  }

  // ── Severity statistics card ───────────────────────────────────────────
  function renderSeverityStats(dist) {
    const total = dist.reduce((s, d) => s + d.count, 0) || 1;
    const html = `
      <div class="wx-severity-stats">
        ${dist.map(d => {
          const pct = (d.count / total * 100).toFixed(1);
          const barW = Math.min(100, d.count / total * 100).toFixed(1);
          return `
            <div class="wx-sev-row">
              <div class="wx-sev-label">
                <span style="font-size:1.1rem">${condIcon(d.condition)}</span>
                <span style="color:${condColor(d.condition)}">${esc(d.condition)}</span>
              </div>
              <div class="wx-sev-bar-wrap">
                <div class="wx-sev-bar" style="width:${barW}%;background:${condColor(d.condition)};opacity:0.8;"></div>
              </div>
              <div class="wx-sev-count" style="color:${condColor(d.condition)}">${d.count} <span style="color:#64748b;font-size:.75rem;">(${pct}%)</span></div>
            </div>`;
        }).join('')}
      </div>`;
    setHtml("wx-severity-stats", html);
  }

  // ── Main refresh ───────────────────────────────────────────────────────
  async function refresh() {
    setHtml("wx-kpis", `<div class="loading-row">⏳ Loading weather data…</div>`);

    try {
      const [summary, segments] = await Promise.all([
        apiGet("/weather/summary"),
        apiGet("/weather/segments"),
      ]);

      renderSummary(summary);
      renderDistributionChart(summary.distribution || []);
      renderSeverityPie(summary.distribution || []);
      renderTrendChart(summary.distribution || []);
      renderSeverityStats(summary.distribution || []);
      renderSegmentTable(segments || []);
    } catch (e) {
      setHtml("wx-kpis", `<div class="loading-row" style="color:#ef4444">Weather data unavailable: ${e.message}</div>`);
    }
  }

  function init() {
    // Auto-refresh every 30 min matching sensor cycle
    if (_refreshTimer) clearInterval(_refreshTimer);
    _refreshTimer = setInterval(() => {
      if (AppState.activeTab === "weather") refresh();
    }, 30 * 60 * 1000);
  }

  return { refresh, init };
})();
