/* main.js — application bootstrap. */
function updateClock() {
  const el = document.getElementById("topbar-clock");
  if (el) el.textContent = new Date().toLocaleTimeString();
}

document.addEventListener("DOMContentLoaded", async () => {
  try {
    await SidebarModule.init();
    TabsModule.init();
    KpiModule.refresh();
    await MapModule.init();
    TabsModule.markLoaded("map");
    WeatherTab.init();
  } catch (e) {
    console.error("App init failed:", e);
    showToast("Failed to initialize the platform — check the console.", true);
  }
  updateClock();
  setInterval(updateClock, 1000);
});
