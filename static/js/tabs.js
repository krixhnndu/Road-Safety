/* tabs.js — tab nav + lazy refresh orchestration. Each tab is only
   fetched the first time it's opened; a global filter/date/time change
   invalidates every tab so it re-fetches next time it's shown (and
   immediately refreshes whichever tab is currently visible). */
const TabsModule = (function () {
  const loadedTabs = new Set();

  function modules() {
    return {
      map: MapModule, hotspot: HotspotTab,
      crash: CrashTab, hazard: HazardTab, analytics: AnalyticsTab, data: DataTab,
      weather: WeatherTab, xai: XaiTab
    };
  }

  function activate(tabName) {
    AppState.activeTab = tabName;
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tabName));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === "panel-" + tabName));
    const mod = modules()[tabName];
    if (mod && !loadedTabs.has(tabName)) {
      loadedTabs.add(tabName);
      if (mod && typeof mod.refresh === 'function') {
        mod.refresh();
      }
    }
  }

  function markLoaded(tabName) {
    loadedTabs.add(tabName);
  }

  function invalidateAll() {
    loadedTabs.clear();
    loadedTabs.add(AppState.activeTab);
  }

  function refreshActive() {
    const mod = modules()[AppState.activeTab];
    if (mod && typeof mod.refresh === 'function') {
      mod.refresh();
    }
  }

  function init() {
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => activate(btn.dataset.tab));
    });
    document.addEventListener("app:globalChanged", () => {
      invalidateAll();
      KpiModule.refresh();
      refreshActive();
    });
  }

  return { init, activate, markLoaded };
})();
