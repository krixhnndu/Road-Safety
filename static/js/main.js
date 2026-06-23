/* main.js — application bootstrap. */
function updateClock() {
  const el = document.getElementById("topbar-clock");
  if (el) el.textContent = new Date().toLocaleTimeString();
}

function initTheme() {
  const toggleBtn = document.getElementById("theme-toggle");
  if (!toggleBtn) return;
  const themeIcon = toggleBtn.querySelector(".theme-icon");
  const themeLabel = toggleBtn.querySelector(".theme-label");

  function setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
    if (theme === "light") {
      if (themeIcon) themeIcon.textContent = "☀️";
      if (themeLabel) themeLabel.textContent = "Light";
    } else {
      if (themeIcon) themeIcon.textContent = "🌙";
      if (themeLabel) themeLabel.textContent = "Dark";
    }
    // Update Plotly chart colors in charts.js
    if (typeof updateThemeVariables === "function") {
      updateThemeVariables();
    }
  }

  // Load theme preference
  const savedTheme = localStorage.getItem("theme");
  const systemPrefersLight = window.matchMedia("(prefers-color-scheme: light)").matches;
  const initialTheme = savedTheme || (systemPrefersLight ? "light" : "dark");
  setTheme(initialTheme);

  toggleBtn.addEventListener("click", () => {
    const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
    const newTheme = currentTheme === "light" ? "dark" : "light";
    setTheme(newTheme);
    // Dispatch global refresh event to update active tabs/charts/map
    document.dispatchEvent(new CustomEvent("app:globalChanged"));
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
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
