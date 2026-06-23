/* xaiTab.js — TAB 4: Explainable AI. */
const XaiTab = (function () {
  let currentSegmentId = null;
  let _segSS = null;   // SearchableSelect for xai-segment-select

  function renderProbChart(probabilities) {
    plot(
      "chart-xai-prob",
      [
        {
          type: "bar",
          orientation: "h",
          x: probabilities.values,
          y: probabilities.labels,
          marker: { color: probabilities.colors },
          text: probabilities.values.map((v) => `${(v * 100).toFixed(1)}%`),
          textposition: "outside",
          textfont: { color: "#e2e8f0", size: 10 },
        },
      ],
      {
        title: { text: "Risk Probabilities", font: { color: "#e2e8f0", size: 13 } },
        xaxis: { range: [0, 1.15], tickformat: ".0%" },
        margin: { t: 40, b: 10, l: 130, r: 50 },
      }
    );
  }

  function renderFeatureRadar(radar, color) {
    Plotly.newPlot(
      "chart-xai-radar",
      [
        {
          type: "scatterpolar",
          r: [...radar.values, radar.values[0]],
          theta: [...radar.labels, radar.labels[0]],
          fill: "toself",
          line: { color, width: 2 },
          fillcolor: color,
          opacity: 0.25,
        },
      ],
      {
        polar: { bgcolor: PLOT_BG, radialaxis: { visible: true, range: [0, 100], color: "#64748b", tickfont: { size: 8 } }, angularaxis: { color: "#94a3b8", tickfont: { size: 9 } } },
        paper_bgcolor: PAPER_BG,
        title: { text: "Feature Score Profile", font: { color: "#e2e8f0", size: 13 } },
        margin: { t: 40, b: 10 },
        showlegend: false,
      },
      { displayModeBar: false, responsive: true }
    );
  }

  function renderExplanationBox(d) {
    const tags = d.factors.map((f) => `<div class="factor-pill f-${f.severity}">${escapeHtml(f.label)}</div>`).join("");
    const topFactors = d.top_factors.map((f) => `<div class="xai-item">▸ ${escapeHtml(f)}</div>`).join("");
    document.getElementById("xai-explanation-box").innerHTML = `
      <div class="xai-box" style="margin-top:16px;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap;">
          <span style="font-size:2rem;font-weight:900;color:${d.color}">${d.recommended_speed} km/h</span>
          <span style="background:${d.color}22;color:${d.color};padding:3px 14px;border-radius:20px;font-size:.78rem;font-weight:700">${escapeHtml(d.label)}</span>
          <span style="color:#64748b;font-size:.76rem">AI Confidence: ${d.confidence.toFixed(1)}%</span>
        </div>
        <div class="xai-title">🤖 Top Contributing Factors</div>
        ${topFactors}
        ${tags}
        <div class="vz-box" style="margin-top:12px;">
          <b>Vision Zero Constraint:</b><br>
          min(AI Speed = ${d.ai_speed} km/h, Human Tolerance = ${d.tolerance} km/h) → <b>${d.recommended_speed} km/h</b>
        </div>
      </div>`;
  }

  async function loadSegment(id) {
    let d;
    try {
      d = await apiGet(`/xai/${id}`, { date: AppState.date, time: AppState.time });
    } catch (e) {
      console.error(e);
      return;
    }
    document.getElementById("img-shap-summary").src = d.shap_image;
    renderProbChart(d.probabilities);
    renderFeatureRadar(d.feature_radar, d.color);
    renderExplanationBox(d);
  }

  async function populateSelect() {
    const opts = await apiGet("/segments/options", baseParams({ scope: "filtered" }));

    function segLabel(o) {
      return `${o.road_type || ""} | Segment #${o.segment_id} | ${o.road_name || o.label}`;
    }
    function segSearch(o) {
      return [String(o.segment_id), o.human_segment_id || "", o.road_name || "", o.road_type || "", o.label || ""].join(" ");
    }

    if (!_segSS) {
      const el = document.getElementById("xai-segment-select");
      _segSS = new SearchableSelect(el, { placeholder: "Search segment by name or ID…" });
      _segSS.onChange((val) => {
        currentSegmentId = Number(val);
        loadSegment(currentSegmentId);
      });
    }

    const prevValue = _segSS.getValue();
    _segSS.setOptions(opts, "segment_id", segLabel, segSearch);
    if (opts.length === 0) return;

    const stillValid = opts.some((o) => String(o.segment_id) === prevValue);
    if (stillValid) {
      _segSS.setValue(prevValue);
    }
    currentSegmentId = Number(_segSS.getValue());
    await loadSegment(currentSegmentId);
  }

  let wired = false;
  async function refresh() {
    if (!wired) { wired = true; }   // wiring now handled by _segSS.onChange
    await populateSelect();
  }

  return { refresh };
})();
