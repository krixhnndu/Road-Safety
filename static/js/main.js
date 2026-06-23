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
    if (themeIcon) {
      themeIcon.innerHTML = theme === "light" ? `<i data-lucide="sun"></i>` : `<i data-lucide="moon"></i>`;
      if (typeof lucide !== "undefined") {
        lucide.createIcons();
      }
    }
    if (themeLabel) {
      themeLabel.textContent = theme === "light" ? "Light" : "Dark";
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
  // Initialize Lucide icons on boot
  if (typeof lucide !== "undefined") {
    lucide.createIcons();
  }
  initTheme();
  
  // Collapsible Navigation Sidebar
  const sidebar = document.getElementById("app-sidebar");
  const sidebarToggle = document.getElementById("sidebar-toggle");
  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener("click", () => {
      sidebar.classList.toggle("expanded");
      setTimeout(() => {
        document.dispatchEvent(new CustomEvent("app:mapResize"));
      }, 300);
    });
  }

  // Collapsible Filters Panel
  const filtersToggle = document.getElementById("filters-toggle-btn");
  const filtersPanel = document.getElementById("filters-panel");
  const closeFilters = document.getElementById("close-filters-btn");
  if (filtersToggle && filtersPanel) {
    filtersToggle.addEventListener("click", () => {
      filtersPanel.classList.toggle("collapsed");
      setTimeout(() => {
        document.dispatchEvent(new CustomEvent("app:mapResize"));
      }, 300);
    });
  }
  if (closeFilters && filtersPanel) {
    closeFilters.addEventListener("click", () => {
      filtersPanel.classList.add("collapsed");
      setTimeout(() => {
        document.dispatchEvent(new CustomEvent("app:mapResize"));
      }, 300);
    });
  }

  try {
    await SidebarModule.init();
    TabsModule.init();
    KpiModule.refresh();
    await MapModule.init();
    TabsModule.markLoaded("map");
    WeatherTab.init();
    RoadNetTab.init();
  } catch (e) {
    console.error("App init failed:", e);
    showToast("Failed to initialize the platform — check the console.", true);
  }
  updateClock();
  setInterval(updateClock, 1000);
});
