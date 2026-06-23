/* hazardTab.js — TAB 6: Authority Hazard Management System. */
const HazardTab = (function () {
  let wired = false;
  let _segSS = null;   // SearchableSelect for hazard-segment

  function hazardItemHtml(hz, isActive) {
    return `<div class="hazard-item ${isActive ? "" : "inactive"}">
      <div class="hazard-type">${escapeHtml(hz.hazard_type)}</div>
      <div style="font-size:.78rem;color:var(--text-dim);margin-top:2px;">${escapeHtml(hz.human_segment_id)} — ${escapeHtml(hz.road_name)}</div>
      <div class="hazard-meta">${escapeHtml(hz.date)} · ${escapeHtml(hz.start_time)}–${escapeHtml(hz.end_time)} · Temp limit: ${hz.temp_speed} km/h</div>
      ${hz.description ? `<div class="hazard-meta">${escapeHtml(hz.description)}</div>` : ""}
      <button class="hazard-remove" data-id="${hz.hazard_id}">Remove</button>
    </div>`;
  }

  function renderLists(active, inactive) {
    document.getElementById("hazard-active-title").textContent = `Active Hazards (${active.length})`;
    document.getElementById("hazard-active-list").innerHTML = active.length
      ? active.map((hz) => hazardItemHtml(hz, true)).join("")
      : `<div class="loading-row">No active hazards right now.</div>`;

    document.getElementById("hazard-inactive-summary").textContent = `All Scheduled / Past Hazards (${inactive.length})`;
    document.getElementById("hazard-inactive-list").innerHTML = inactive.length
      ? inactive.map((hz) => hazardItemHtml(hz, false)).join("")
      : `<div class="loading-row">Nothing scheduled.</div>`;

    document.querySelectorAll(".hazard-remove").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await apiDelete(`/hazards/${btn.dataset.id}`);
          showToast("Hazard removed");
          document.dispatchEvent(new CustomEvent("app:globalChanged"));
        } catch (e) {
          showToast(e.message, true);
        }
      });
    });
  }

  function fillTimeSelect(id, def) {
    const el = document.getElementById(id);
    el.innerHTML = AppState.sidebarOptions.time_opts.map((t) => `<option>${t}</option>`).join("");
    el.value = def;
  }

  async function refreshDefaultSpeed() {
    const val = _segSS ? _segSS.getValue() : document.getElementById("hazard-segment").value;
    if (!val) return;
    const detail = await apiGet("/segments/" + val, { date: AppState.date, time: AppState.time }).catch(() => null);
    const roadType = detail ? detail.road_type : "";
    const r = await apiGet("/hazards/default-speed", { road_type: roadType });
    document.getElementById("hazard-speed").value = r.default_speed;
    document.getElementById("hazard-speed-label").textContent = `Temporary Speed Limit (km/h) — default for ${roadType || "this road"}`;
  }

  async function populateForm() {
    const opts = await apiGet("/segments/options", { scope: "all" });

    function segLabel(o) {
      return `${o.road_type || ""} | Segment #${o.segment_id} | ${o.road_name || o.label}`;
    }
    function segSearch(o) {
      return [String(o.segment_id), o.human_segment_id || "", o.road_name || "", o.road_type || "", o.label || ""].join(" ");
    }

    if (!_segSS) {
      const el = document.getElementById("hazard-segment");
      _segSS = new SearchableSelect(el, { placeholder: "Search segment by name or ID…" });
      // Fire speed default refresh when user changes segment
      _segSS.onChange(() => refreshDefaultSpeed());
    }
    _segSS.setOptions(opts, "segment_id", segLabel, segSearch);

    fillTimeSelect("hazard-start", "08:00");
    fillTimeSelect("hazard-end",   "10:00");

    document.getElementById("hazard-type").innerHTML = AppState.sidebarOptions.hazard_type_opts.map((h) => `<option>${escapeHtml(h)}</option>`).join("");
    document.getElementById("hazard-date").value = AppState.date;
    await refreshDefaultSpeed();
  }

  function wire() {
    document.getElementById("hazard-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = {
        segment_id: Number(_segSS ? _segSS.getValue() : document.getElementById("hazard-segment").value),
        hazard_type: document.getElementById("hazard-type").value,
        date: document.getElementById("hazard-date").value,
        start_time: document.getElementById("hazard-start").value,
        end_time: document.getElementById("hazard-end").value,
        temp_speed: Number(document.getElementById("hazard-speed").value),
        description: document.getElementById("hazard-desc").value,
      };
      try {
        await apiPost("/hazards", body);
        showToast(`${body.hazard_type} hazard added`);
        document.getElementById("hazard-desc").value = "";
        document.dispatchEvent(new CustomEvent("app:globalChanged"));
      } catch (err) {
        showToast(err.message, true);
      }
    });
  }

  async function refresh() {
    if (!wired) { wire(); wired = true; }
    await populateForm();
    const data = await apiGet("/hazards", { date: AppState.date, time: AppState.time });
    renderLists(data.active, data.inactive);
  }

  return { refresh };
})();
