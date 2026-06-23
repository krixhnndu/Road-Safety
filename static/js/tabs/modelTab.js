/* modelTab.js — TAB 3: ML Model Evaluation. */
const ModelTab = (function () {
  function renderCards(models) {
    document.getElementById("model-cards").innerHTML = models
      .map((row) => {
        const rows = [
          ["Accuracy", row.accuracy], ["Precision", row.precision], ["Recall", row.recall],
          ["F1 Score", row.f1], ["CV Accuracy", row.cv_acc != null ? row.cv_acc : row.accuracy],
        ];
        return `<div class="panel"><h4>${row.is_best ? "✅ " : ""}${escapeHtml(row.model)}</h4>
          ${rows.map(([l, v]) => `<div class="irow"><span class="irow-l">${l}</span><span class="irow-v" style="color:${row.is_best && l === "F1 Score" ? "#22c55e" : "var(--text)"}">${(v * 100).toFixed(2)}%</span></div>`).join("")}
        </div>`;
      })
      .join("");
  }

  function renderRadar(radar) {
    const colors = ["#60a5fa", "#f97316"];
    const traces = radar.series.map((s, i) => ({
      type: "scatterpolar",
      r: [...s.values, s.values[0]],
      theta: [...radar.categories, radar.categories[0]],
      fill: "toself",
      name: s.name,
      line: { color: colors[i % colors.length], width: 2 },
      fillcolor: colors[i % colors.length],
      opacity: 0.55,
    }));
    plot(
      "chart-model-radar",
      traces,
      {
        polar: { bgcolor: PLOT_BG, radialaxis: { visible: true, range: [0, 1], color: AXIS_COLOR, tickfont: { size: 8 } }, angularaxis: { color: FONT_COLOR } },
        showlegend: true,
        legend: { font: { color: FONT_COLOR, size: 10 }, bgcolor: "rgba(0,0,0,0)" },
        title: { text: "Model Performance Comparison", font: { color: FONT_COLOR, size: 14 } },
        margin: { t: 50, b: 20 },
      }
    );
  }

  async function refresh() {
    let data;
    try {
      data = await apiGet("/metrics");
    } catch (e) {
      console.error(e);
      return;
    }
    renderCards(data.models);
    renderRadar(data.radar);
    document.getElementById("img-feature-importance").src = data.images.feature_importance;
    document.getElementById("img-model-evaluation").src = data.images.model_evaluation;
  }

  return { refresh };
})();
