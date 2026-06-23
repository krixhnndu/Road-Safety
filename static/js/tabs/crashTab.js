/* crashTab.js — TAB 5: Crash Management System. */
const CrashTab = (function () {
  let wired = false;
  let _segSS = null;   // SearchableSelect for crash-segment

  function renderKpis(k) {
    const items = [[k.minor, "Minor Crashes", "#22c55e"], [k.major, "Major Crashes", "#f97316"], [k.fatal, "Fatal Crashes", "#ef4444"], [k.total, "Total Crashes", "#60a5fa"]];
    document.getElementById("crash-kpis").innerHTML = items
      .map(([v, l, c]) => `<div class="kpi"><div class="kpi-v" style="color:${c}">${v}</div><div class="kpi-l">${escapeHtml(l)}</div></div>`)
      .join("");
  }

  function renderLogTable(rows) {
    const cols = [["crash_id", "ID"], ["human_segment_id", "Segment"], ["road_name", "Road"], ["severity", "Severity"], ["date", "Date"], ["time", "Time"], ["description", "Description"]];
    const el = document.getElementById("crash-log-table");
    if (!rows.length) {
      el.innerHTML = `<div class="loading-row">No crashes logged for the selected conditions.</div>`;
      return;
    }
    el.innerHTML = `<div class="data-table-wrap" style="max-height:460px;"><table class="data-table">
      <thead><tr>${cols.map((c) => `<th>${c[1]}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr>${cols.map((c) => `<td>${escapeHtml(r[c[0]])}</td>`).join("")}</tr>`).join("")}</tbody>
    </table></div>`;
  }

  function renderCharts(charts) {
    const sevColors = { Minor: "#22c55e", Major: "#f97316", Fatal: "#ef4444" };
    plot(
      "chart-crash-pie",
      [{ type: "pie", labels: charts.severity_pie.map((d) => d.severity), values: charts.severity_pie.map((d) => d.count), marker: { colors: charts.severity_pie.map((d) => sevColors[d.severity]) }, hole: 0.45, textfont: { size: 9 } }],
      { margin: { t: 10, b: 0, l: 0, r: 0 }, showlegend: true, legend: { font: { size: 9 }, bgcolor: "rgba(0,0,0,0)" } }
    );

    const severities = ["Minor", "Major", "Fatal"];
    const traces = severities.map((sev) => {
      const rows = charts.monthly.filter((m) => m.severity === sev);
      return { type: "bar", name: sev, x: rows.map((r) => r.month), y: rows.map((r) => r.count), marker: { color: sevColors[sev] } };
    });
    plot("chart-crash-monthly", traces, { title: { text: "Monthly Crash Trend", font: { size: 12 } }, margin: { t: 30, b: 30, l: 30, r: 10 }, barmode: "stack" });
  }

  async function populateSegmentSelect() {
    const opts = await apiGet("/segments/options", { scope: "all" });

    function segLabel(o) {
      return `${o.road_type || ""} | Segment #${o.segment_id} | ${o.road_name || o.label}`;
    }
    function segSearch(o) {
      return [String(o.segment_id), o.human_segment_id || "", o.road_name || "", o.road_type || "", o.label || ""].join(" ");
    }

    if (!_segSS) {
      const el = document.getElementById("crash-segment");
      _segSS = new SearchableSelect(el, { placeholder: "Search segment by name or ID…" });
    }
    _segSS.setOptions(opts, "segment_id", segLabel, segSearch);
  }

  async function loadData() {
    const [list, charts] = await Promise.all([
      apiGet("/crashes", { date: AppState.date, time: AppState.time, severity: AppState.crashSeverityFilter }),
      apiGet("/crashes/charts", { date: AppState.date, time: AppState.time }),
    ]);
    renderKpis(list.kpis);
    renderLogTable(list.recent);
    renderCharts(charts);
  }

  function wire() {
    document.getElementById("crash-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      // Read value from SearchableSelect if available, else native select
      const segment_id = Number(_segSS ? _segSS.getValue() : document.getElementById("crash-segment").value);
      const severity = document.getElementById("crash-severity").value;
      const date = document.getElementById("crash-date").value;
      const time = document.getElementById("crash-time").value;
      const description = document.getElementById("crash-desc").value;
      try {
        await apiPost("/crashes", { segment_id, severity, date, time, description });
        showToast(`✅ ${severity} crash logged`);
        document.getElementById("crash-desc").value = "";
        document.dispatchEvent(new CustomEvent("app:globalChanged"));
      } catch (err) {
        showToast(err.message, true);
      }
    });

    document.getElementById("crash-export-btn").addEventListener("click", () => triggerDownload("/crashes/export"));

    document.getElementById("crash-date").value = AppState.date;
    const timeSel = document.getElementById("crash-time");
    timeSel.innerHTML = AppState.sidebarOptions.time_opts.map((t) => `<option>${t}</option>`).join("");
    timeSel.value = AppState.time;
  }

  async function refresh() {
    if (!wired) { wire(); wired = true; }
    await populateSegmentSelect();
    await loadData();
  }

  return { refresh };
})();
