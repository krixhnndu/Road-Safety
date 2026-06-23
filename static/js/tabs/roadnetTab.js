/* roadnetTab.js — TAB 9: Road Network Visualization (Detection 9)
   Loads stats from /api/road-network/stats and populates the KPI strip
   above the iframe embed of bengaluru_road_map.html. */
const RoadNetTab = (function () {

  let loaded = false;

  function formatNum(n) {
    return typeof n === 'number' ? n.toLocaleString() : n;
  }

  function statCard(label, value, color) {
    return `<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;
              padding:12px 18px;min-width:130px;text-align:center;">
      <div style="font-size:.75rem;color:var(--text-muted);margin-bottom:4px">${escapeHtml(label)}</div>
      <div style="font-size:1.4rem;font-weight:700;color:${color || 'var(--accent)'}">${escapeHtml(String(value))}</div>
    </div>`;
  }

  async function loadStats() {
    if (loaded) return;
    loaded = true;
    try {
      const data = await apiGet('/road-network/stats');
      const wrap = document.getElementById('roadnet-stats');
      if (!wrap) return;
      const nh = data.road_classes['National Highway'] || 0;
      const sh = data.road_classes['State Highway'] || 0;
      const urb = data.road_classes['Urban Road'] || 0;
      wrap.innerHTML =
        statCard('Total Segments', formatNum(data.total_segments), '#60a5fa') +
        statCard('Total Length', formatNum(data.total_length_km) + ' km', '#a78bfa') +
        statCard('National Highways', formatNum(nh), '#ef4444') +
        statCard('State Highways', formatNum(sh), '#f97316') +
        statCard('Urban Roads', formatNum(urb), '#3b82f6') +
        statCard('Source', data.source, '#94a3b8');
    } catch (e) {
      console.warn('Road network stats failed:', e);
    }
  }

  function init() {
    // Load stats when the Road Network tab is first activated
    document.querySelectorAll('.tab-btn[data-tab="roadnet"]').forEach(btn => {
      btn.addEventListener('click', loadStats);
    });
  }

  return { init };
})();
