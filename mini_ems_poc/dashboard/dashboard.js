const REFRESH_INTERVAL_MS = 30000;
const PRICE_SLOT_MS = 15 * 60 * 1000;
const DEFAULT_CHANNELS = [
  { id: "tariff.current_price_ct_kwh", label: "Strompreis", unit: "ct/kWh", group: "Markt", kind: "average" },
  { id: "grid.active_power_kw", label: "Netzleistung", unit: "kW", group: "Netz", kind: "average" },
  { id: "site.outdoor_temperature_c", label: "Außentemperatur", unit: "°C", group: "Wetter", kind: "average" },
  { id: "site.buffer_1_top_temperature_c", label: "Puffer 1 oben", unit: "°C", group: "Puffer", kind: "average" },
  { id: "site.buffer_1_bottom_temperature_c", label: "Puffer 1 unten", unit: "°C", group: "Puffer", kind: "average" },
  { id: "site.buffer_2_top_temperature_c", label: "Puffer 2 oben", unit: "°C", group: "Puffer", kind: "average" },
  { id: "site.buffer_2_bottom_temperature_c", label: "Puffer 2 unten", unit: "°C", group: "Puffer", kind: "average" },
  { id: "site.heat_generation_flow_temperature_c", label: "Wärmeerzeugung Vorlauf", unit: "°C", group: "Wärme", kind: "average" },
  { id: "site.heat_generation_return_temperature_c", label: "Wärmeerzeugung Rücklauf", unit: "°C", group: "Wärme", kind: "average" },
  { id: "site.boiler_1_flow_temperature_c", label: "Gaskessel Vorlauf", unit: "°C", group: "Gaskessel", kind: "average" },
  { id: "site.boiler_1_return_temperature_c", label: "Gaskessel Rücklauf", unit: "°C", group: "Gaskessel", kind: "average" },
  { id: "site.boiler_2_flow_temperature_c", label: "Pelletkessel Vorlauf", unit: "°C", group: "Pellet", kind: "average" },
  { id: "site.boiler_2_return_temperature_c", label: "Pelletkessel Rücklauf", unit: "°C", group: "Pellet", kind: "average" },
  { id: "site.chp_flow_temperature_c", label: "BHKW Vorlauf", unit: "°C", group: "BHKW", kind: "average" },
  { id: "site.chp_return_temperature_c", label: "BHKW Rücklauf", unit: "°C", group: "BHKW", kind: "average" },
  { id: "site.chp_electric_energy_kwh", label: "BHKW elektrisch", unit: "kWh", group: "Energie", kind: "energy_counter" },
  { id: "site.chp_thermal_energy_kwh", label: "BHKW thermisch", unit: "kWh", group: "Energie", kind: "energy_counter" },
  { id: "site.pellet_thermal_energy_kwh", label: "Pellet thermisch", unit: "kWh", group: "Energie", kind: "energy_counter" },
  { id: "site.gas_thermal_energy_kwh", label: "Gas thermisch", unit: "kWh", group: "Energie", kind: "energy_counter" },
  { id: "ems.lockout_spotmarket", label: "Preissteuerung", unit: "", group: "Betrieb", kind: "state" },
  { id: "ems.lockout_grid", label: "Netzschutz", unit: "", group: "Betrieb", kind: "state" },
];

const CUSTOMER_CHANNEL_LABELS = new Map(DEFAULT_CHANNELS.map((channel) => [channel.id, channel]));

const VIEW_PRESETS = [
  {
    id: "preset:operations",
    label: "Betrieb",
    range: "24h",
    granularity: "5m",
    channels: ["tariff.current_price_ct_kwh", "grid.active_power_kw", "ems.lockout_spotmarket", "site.outdoor_temperature_c"],
  },
  {
    id: "preset:thermal",
    label: "Wärme",
    range: "24h",
    granularity: "5m",
    channels: [
      "site.buffer_1_top_temperature_c",
      "site.buffer_1_bottom_temperature_c",
      "site.buffer_2_top_temperature_c",
      "site.buffer_2_bottom_temperature_c",
      "site.heat_generation_flow_temperature_c",
      "site.heat_generation_return_temperature_c",
    ],
  },
  {
    id: "preset:generation",
    label: "Erzeugung",
    range: "7d",
    granularity: "1h",
    channels: [
      "site.chp_electric_energy_kwh",
      "site.chp_thermal_energy_kwh",
      "site.pellet_thermal_energy_kwh",
      "site.gas_thermal_energy_kwh",
    ],
  },
];

/* Fallback-Farben, falls die --series-*-Tokens nicht lesbar sind (siehe seriesColor). */
const SERIES_COLORS = ["#2563eb", "#16875a", "#b7791f", "#bf3f36", "#40556b", "#7c3aed", "#0891b2", "#be185d"];
const DATE_TIME = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const TIME_ONLY = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit" });
const DAY_ONLY = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit" });
const DAY_DATE = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });

const THEME_STORAGE_KEY = "miniEmsTheme";
const DASHBOARD_STORAGE_KEY = "miniEmsDashboard";

const PAGES = {
  dashboard: "Übersicht",
  analyse: "Analyse",
  berichte: "Berichte",
  konfiguration: "Konfiguration",
  system: "Systemstatus",
};

const PAGE_SUBTITLES = {
  analyse: "Messwerte und Datenqualität über frei wählbare Zeiträume prüfen.",
  berichte: "Tagesbericht anzeigen, herunterladen oder einen eigenen Bericht zusammenstellen.",
  konfiguration: "Standort Schritt für Schritt einrichten: Datenpunkte aufnehmen, zuordnen, testen und aktivieren.",
  system: "Systemzustand, Kommunikation und letzte Läufe kontrollieren.",
};

/* Priorisierte Reihenfolge (UX4): erst Wirtschaftlichkeit (Preis, Preissteuerung),
   dann Live-Betrieb (Netzleistung), dann Schutzfunktionen und Ergänzungen. */
const KPI_CATALOG = [
  { id: "price", label: "Aktueller Strompreis", accent: "accent-blue",
    value: (h) => formatNumber(h.current_price_ct_kwh, "ct/kWh", 3),
    sub: (h) => `Zeitfenster ${h.current_slot_label || "-"}` },
  { id: "spotmarket", label: "Preissteuerung", accent: "accent-green",
    value: (h) => formatBool(h.spotmarket_active_now),
    sub: (h) => (h.spotmarket_active_now ? "Preissteuerung aktiv" : "Normalbetrieb") },
  { id: "grid_power", label: "Netzleistung", accent: "accent-slate",
    value: (h) => formatNumber(h.grid_active_power_kw, "kW", 2),
    sub: (h) => (h.grid_read_status ? friendlyState(h.grid_read_status) : "derzeit nicht aktiv") },
  { id: "grid_lockout", label: "Netzschutz", accent: "accent-amber",
    value: (h) => (h.grid_lockout_active === null || h.grid_lockout_active === undefined ? "deaktiviert" : formatBool(h.grid_lockout_active)),
    sub: (h) => friendlyState(h.grid_lockout_state) },
  { id: "weather_temp", label: "Außentemperatur", accent: "accent-slate",
    value: (_h, ctx) => formatNumber(ctx.weather?.current?.temperature_c, "°C", 1),
    sub: (_h, ctx) => ctx.weather?.current?.weather_label || "Wetter" },
  { id: "price_min", label: "Günstigster Preis heute", accent: "accent-green",
    value: (_h, ctx) => formatNumber(ctx.priceMin, "ct/kWh", 3), sub: () => "im Tagesverlauf" },
  { id: "price_max", label: "Höchster Preis heute", accent: "accent-amber",
    value: (_h, ctx) => formatNumber(ctx.priceMax, "ct/kWh", 3), sub: () => "im Tagesverlauf" },
  { id: "tomorrow", label: "Preise morgen", accent: "accent-blue",
    value: (h) => (h.tomorrow_prices_available ? "verfügbar" : "wartet"), sub: () => "Day-Ahead" },
];

const DASHBOARD_WIDGETS = [
  { id: "price", label: "Börsenstrompreis" },
  { id: "weather", label: "Wetter" },
  { id: "windows", label: "Geplante Preisfenster" },
];

const DEFAULT_DASHBOARD = {
  kpis: ["price", "spotmarket", "grid_power", "grid_lockout"],
  widgets: { price: true, weather: true, windows: true },
  charts: [],
};

const CONFIG_CHANNEL_DEFAULTS = [
  { channel_id: "site.outdoor_temperature_c", object_type: "ai", instance: 1801, description: "Außentemperatur", plausible_min: -50, plausible_max: 60, include_in_health: true, read_interval_cycles: 1, max_age_seconds: 120 },
  { channel_id: "site.buffer_1_top_temperature_c", object_type: "ai", instance: 1101, description: "Puffer 1 oben", plausible_min: -20, plausible_max: 120, include_in_health: false, read_interval_cycles: 1, max_age_seconds: 120 },
  { channel_id: "site.buffer_1_bottom_temperature_c", object_type: "ai", instance: 1102, description: "Puffer 1 unten", plausible_min: -20, plausible_max: 120, include_in_health: false, read_interval_cycles: 1, max_age_seconds: 120 },
  { channel_id: "site.buffer_2_top_temperature_c", object_type: "ai", instance: 1103, description: "Puffer 2 oben", plausible_min: -20, plausible_max: 120, include_in_health: false, read_interval_cycles: 1, max_age_seconds: 120 },
  { channel_id: "site.buffer_2_bottom_temperature_c", object_type: "ai", instance: 1104, description: "Puffer 2 unten", plausible_min: -20, plausible_max: 120, include_in_health: false, read_interval_cycles: 1, max_age_seconds: 120 },
  { channel_id: "site.heat_generation_flow_temperature_c", object_type: "ai", instance: 1107, description: "Wärmeerzeugung Vorlauf", plausible_min: -20, plausible_max: 120, include_in_health: false, read_interval_cycles: 1, max_age_seconds: 120 },
  { channel_id: "site.heat_generation_return_temperature_c", object_type: "ai", instance: 1108, description: "Wärmeerzeugung Rücklauf", plausible_min: -20, plausible_max: 120, include_in_health: false, read_interval_cycles: 1, max_age_seconds: 120 },
  { channel_id: "site.boiler_1_flow_temperature_c", object_type: "ai", instance: 2101, description: "Gaskessel Vorlauf", plausible_min: -20, plausible_max: 120, include_in_health: false, read_interval_cycles: 1, max_age_seconds: 120 },
  { channel_id: "site.boiler_1_return_temperature_c", object_type: "ai", instance: 1201, description: "Gaskessel Rücklauf", plausible_min: -20, plausible_max: 120, include_in_health: false, read_interval_cycles: 1, max_age_seconds: 120 },
  { channel_id: "site.boiler_2_flow_temperature_c", object_type: "ai", instance: 2102, description: "Pelletkessel Vorlauf", plausible_min: -20, plausible_max: 120, include_in_health: false, read_interval_cycles: 1, max_age_seconds: 120 },
  { channel_id: "site.boiler_2_return_temperature_c", object_type: "ai", instance: 1202, description: "Pelletkessel Rücklauf", plausible_min: -20, plausible_max: 120, include_in_health: false, read_interval_cycles: 1, max_age_seconds: 120 },
  { channel_id: "site.chp_flow_temperature_c", object_type: "ai", instance: 1203, description: "BHKW Vorlauf", plausible_min: -20, plausible_max: 120, include_in_health: false, read_interval_cycles: 1, max_age_seconds: 120 },
  { channel_id: "site.chp_return_temperature_c", object_type: "ai", instance: 1204, description: "BHKW Rücklauf", plausible_min: -20, plausible_max: 120, include_in_health: false, read_interval_cycles: 1, max_age_seconds: 120 },
  { channel_id: "site.chp_electric_energy_kwh", object_type: "av", instance: 48, description: "BHKW elektrische Energie", plausible_min: 0, plausible_max: 1000000000, include_in_health: false, read_interval_cycles: 1, max_age_seconds: 120 },
  { channel_id: "site.chp_thermal_energy_kwh", object_type: "av", instance: 49, description: "BHKW thermische Energie", plausible_min: 0, plausible_max: 1000000000, include_in_health: false, read_interval_cycles: 1, max_age_seconds: 120 },
  { channel_id: "site.pellet_thermal_energy_kwh", object_type: "av", instance: 50, description: "Pelletkessel thermische Energie", plausible_min: 0, plausible_max: 1000000000, include_in_health: false, read_interval_cycles: 1, max_age_seconds: 120 },
  { channel_id: "site.gas_thermal_energy_kwh", object_type: "av", instance: 51, description: "Gaskessel thermische Energie", plausible_min: 0, plausible_max: 1000000000, include_in_health: false, read_interval_cycles: 1, max_age_seconds: 120 },
];

const DEFAULT_SITE_CONFIG = {
  site: {
    name: "Mini EMS Standort",
    access_status: "local",
    operator_note: "Keine echte Schalthandlung aus dieser Oberfläche.",
  },
  runtime: {
    environment: "local",
    bacnet_mode: "simulated",
    real_writes_enabled: false,
  },
  simulation: {
    values_file: "sim/sample_values.json",
    prices_file: "sim/sample_prices.json",
  },
  network: {
    controller_ip: "127.0.0.1",
    controller_port: 47808,
    local_ip: "127.0.0.1",
    local_port: 47809,
    response_timeout_seconds: 1,
    retries: 0,
  },
  points: {
    grid_active_power_kw: 300,
    current_price_av: 1000,
    grid_lockout_bv: 400,
    spotmarket_lockout_bv: 401,
  },
  timing: {
    cycle_seconds: 60,
    inter_read_delay_seconds: 0,
  },
  watchdog: {
    max_cycle_age_seconds: 300,
  },
  api: {
    host: "127.0.0.1",
    port: 8090,
    history_default_limit: 96,
  },
  price_source: {
    provider: "smard",
    region: "DE-LU",
    filter: 4169,
    resolution: "quarterhour",
    timeout_seconds: 30,
    price_factor: 0.1,
  },
  controllers: {
    grid_lockout: {
      enabled: false,
      threshold_kw: 5,
      clear_threshold_kw: 5.5,
      below_threshold_cycles_required: 3,
    },
    spotmarket_lockout: {
      negative_quarters_min_consecutive: 8,
      min_valid_quarters: 96,
      invalid_price_sentinel: null,
    },
  },
  safety: {
    fail_safe_output: false,
    comm_error_safe_mode_threshold: 2,
  },
  outputs: {
    current_price: { confirmation_mode: "ack_or_readback", criticality: "noncritical" },
    grid_lockout: { confirmation_mode: "ack_only", criticality: "critical" },
    spotmarket_lockout: { confirmation_mode: "ack_only", criticality: "critical" },
  },
  database: {
    sqlite_file: "data/local/mini_ems.local.sqlite",
  },
  logging: {
    directory: "logs/local",
    log_file: "mini_ems.local.log",
    state_file: "runtime/local/state.json",
    health_file: "runtime/local/health.json",
    price_cache_file: "data/local/spotmarket_price_cache.json",
    spotmarket_plan_file: "data/local/spotmarket_tomorrow_windows.json",
    spotmarket_override_file: "data/local/spotmarket_manual_override.json",
    level: "INFO",
    stdout: true,
  },
  additional_inputs: CONFIG_CHANNEL_DEFAULTS.map((channel) => ({ ...channel })),
};

const appState = {
  availableChannels: DEFAULT_CHANNELS,
  selectedChannels: new Set(VIEW_PRESETS[0].channels),
  savedViews: [],
  statusPayload: null,
  reportStudio: null,
  activeHistories: new Map(),
  weather: null,
  priceStats: null,
  dashboard: { ...DEFAULT_DASHBOARD },
  siteConfig: { config: null, dirty: false },
  /* Standardweg Berichte (UX3): gewählter Berichtstag für den Tagesbericht. */
  reportDay: { mode: "today", date: "" },
};

const priceChart = {
  instance: null,
  observer: null,
  target: null,
  points: [],
  options: null,
};

const BACKEND_REPORT_SECTIONS = ["summary", "line_chart", "table", "events"];
let reportCharts = [];

// Eigene Dashboard-Diagramme: laufende uPlot-Instanzen + zwischengespeicherte Daten.
let dashboardCharts = [];
const dashboardChartData = new Map();
let modalChartDraft = [];

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  appState.dashboard = loadDashboardConfig();
  appState.savedViews = loadSavedViews();
  bindUi();
  initSiteConfigPage();
  initRouter();
  setReportDefaults();
  renderViewSelect();
  applyView(VIEW_PRESETS[0]);
  refreshDashboard();
  window.setInterval(refreshDashboard, REFRESH_INTERVAL_MS);
});

function bindUi() {
  document.getElementById("refresh-button").addEventListener("click", refreshDashboard);
  document.getElementById("range-select").addEventListener("change", refreshWorkbench);
  document.getElementById("granularity-select").addEventListener("change", refreshWorkbench);
  document.getElementById("channel-search").addEventListener("input", renderChannelPicker);
  document.getElementById("clear-channels").addEventListener("click", () => {
    appState.selectedChannels.clear();
    renderChannelPicker();
    refreshWorkbench();
  });
  document.getElementById("view-select").addEventListener("change", (event) => {
    const view = findView(event.target.value);
    if (view) {
      applyView(view);
      refreshWorkbench();
    }
  });
  document.getElementById("save-view-button").addEventListener("click", saveCurrentView);
  document.querySelectorAll("[data-report-day]").forEach((button) => {
    button.addEventListener("click", () => setReportDayMode(button.dataset.reportDay));
  });
  const reportDateInput = document.getElementById("report-date");
  if (reportDateInput) {
    reportDateInput.addEventListener("change", () => {
      appState.reportDay.date = reportDateInput.value;
      updateReportQuickView();
    });
  }
  document.getElementById("report-form").addEventListener("submit", previewReport);
  document.getElementById("report-title").addEventListener("input", updateReportLinks);
  document.getElementById("report-start").addEventListener("change", updateReportLinks);
  document.getElementById("report-end").addEventListener("change", updateReportLinks);
  document.getElementById("report-granularity").addEventListener("change", updateReportLinks);
  document.querySelectorAll("input[name='report-section']").forEach((input) => input.addEventListener("change", updateReportLinks));
  document.getElementById("diagnostic-read-button").addEventListener("click", runDiagnosticRead);
  document.querySelectorAll(".theme-toggle button[data-theme-value]").forEach((button) => {
    button.addEventListener("click", () => applyTheme(button.dataset.themeValue));
  });
  document.getElementById("dashboard-config-button").addEventListener("click", openDashboardConfig);
  document.getElementById("chart-add-button").addEventListener("click", addModalChart);
  document.getElementById("dashboard-config-close").addEventListener("click", closeDashboardConfig);
  document.getElementById("dashboard-config-save").addEventListener("click", saveDashboardConfig);
  document.getElementById("dashboard-config-reset").addEventListener("click", resetDashboardConfig);
  document.getElementById("dashboard-config-modal").addEventListener("click", (event) => {
    if (event.target === event.currentTarget) {
      closeDashboardConfig();
    }
  });
  document.getElementById("site-config-validate").addEventListener("click", validateSiteConfig);
  document.getElementById("site-config-save").addEventListener("click", saveSiteConfig);
  document.getElementById("site-config-form").addEventListener("input", handleSiteConfigChange);
  document.getElementById("site-config-form").addEventListener("change", handleSiteConfigChange);
  bindSetupUi();
}

function initRouter() {
  window.addEventListener("hashchange", () => showPage(currentPageFromHash()));
  showPage(currentPageFromHash());
}

function currentPageFromHash() {
  const raw = (location.hash || "").replace(/^#\/?/, "").trim();
  return PAGES[raw] ? raw : "dashboard";
}

function showPage(page) {
  document.querySelectorAll(".page").forEach((element) => {
    element.classList.toggle("active", element.dataset.page === page);
  });
  document.querySelectorAll(".nav-link").forEach((link) => {
    link.classList.toggle("active", link.dataset.page === page);
  });
  setText("page-title", PAGES[page] || "Dashboard");
  updateOperatorMessageForPage(page);
  if (page === "dashboard") {
    rebuildPriceChart();
    redrawDashboardCharts();
  }
  if (page === "konfiguration") {
    updateSiteConfigPreview();
    renderSetupPage();
  }
}

function initTheme() {
  let stored = "light";
  try {
    stored = localStorage.getItem(THEME_STORAGE_KEY) === "dark" ? "dark" : "light";
  } catch (error) {
    stored = "light";
  }
  applyTheme(stored, { persist: false });
}

function applyTheme(theme, options = {}) {
  const resolved = theme === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", resolved);
  document.querySelectorAll(".theme-toggle button[data-theme-value]").forEach((button) => {
    button.setAttribute("aria-pressed", button.dataset.themeValue === resolved ? "true" : "false");
  });
  if (options.persist !== false) {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, resolved);
    } catch (error) {
      /* localStorage nicht verfügbar — Theme bleibt nur für diese Sitzung aktiv. */
    }
  }
  rebuildPriceChart();
  redrawDashboardCharts();
  /* Analyse-Sparklines neu zeichnen, damit die Reihenfarben aus den Tokens
     des aktiven Themes kommen (UI_STYLEGUIDE, 7.1). */
  if (appState.activeHistories.size) {
    renderSeriesGrid([...appState.activeHistories.values()]);
  }
}

let dashboardLoaded = false;

async function refreshDashboard() {
  const button = document.getElementById("refresh-button");
  button.disabled = true;
  setLoadingIndicator(true);
  try {
    const [statusPayload, dailyReport, weather, reportStudio] = await Promise.all([
      fetchJson("/api/status"),
      fetchJson("/api/report/daily"),
      fetchOptionalJson("/api/weather", { status: "unavailable" }),
      fetchOptionalJson("/api/report/studio", null),
    ]);
    appState.statusPayload = statusPayload;
    appState.reportStudio = reportStudio;
    appState.availableChannels = normalizeChannels(reportStudio?.config?.available_channels);

    renderStatus(statusPayload);
    renderSignals(statusPayload);
    renderWindows(statusPayload.spotmarket_plan || {});
    renderRecentCycles(statusPayload.recent_cycles || []);
    updateReportQuickView(dailyReport);
    renderWeather(weather);
    renderChannelPicker();
    renderReportChannelList();
    await renderPriceOverview(statusPayload);
    renderKpis(statusPayload);
    applyDashboardWidgets();
    await renderDashboardCharts();
    await refreshWorkbench();
    updateReportLinks();
    syncSetupReadOnly(statusPayload);
    dashboardLoaded = true;
  } catch (error) {
    renderGlobalError(error);
  } finally {
    button.disabled = false;
    setLoadingIndicator(false);
  }
}

/* Dezenter Ladehinweis (UX6): beim ersten Laden und beim Aktualisieren sichtbar,
   dass Daten kommen — kein Spinner, nur ein ruhiger Text im Kopfbereich. */
function setLoadingIndicator(active) {
  const indicator = document.getElementById("load-indicator");
  if (indicator) {
    indicator.textContent = dashboardLoaded ? "Daten werden aktualisiert" : "Daten werden geladen";
    indicator.hidden = !active;
  }
  const button = document.getElementById("refresh-button");
  if (button) {
    button.textContent = active ? "Lädt …" : "Aktualisieren";
  }
}

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json();
}

async function fetchOptionalJson(path, fallback) {
  try {
    return await fetchJson(path);
  } catch (error) {
    if (fallback === null) {
      return null;
    }
    return { ...fallback, error: error.message };
  }
}

function normalizeChannels(rawChannels) {
  const channels = Array.isArray(rawChannels) && rawChannels.length ? rawChannels : DEFAULT_CHANNELS;
  const byId = new Map(DEFAULT_CHANNELS.map((channel) => [channel.id, channel]));
  channels.forEach((channel) => {
    if (channel && channel.id) {
      const customerCopy = CUSTOMER_CHANNEL_LABELS.get(channel.id) || {};
      byId.set(channel.id, { ...byId.get(channel.id), ...channel, ...customerCopy });
    }
  });
  return [...byId.values()].sort((a, b) => {
    const group = String(a.group || "").localeCompare(String(b.group || ""), "de");
    return group || String(a.label || a.id).localeCompare(String(b.label || b.id), "de");
  });
}

function renderStatus(payload) {
  const health = payload.health || {};
  const status = health.status || "-";
  const message = buildMainMessage(payload);
  setText("global-status", friendlyState(status));
  document.getElementById("global-status-dot").className = `status-dot ${cssToken(status)}`;
  updateOperatorMessageForPage(currentPageFromHash(), payload);
  setText("last-updated", health.timestamp ? `Stand ${formatTimestamp(health.timestamp)}` : "-");
  renderStatusHero(message, health);
  renderStartHints(buildStartHints(payload));
  // Technische Detailzeile auf der Systemseite: Zeitfenster/Preis (vorher im Kopfbereich),
  // sicherer Modus und Morgen-Preise bleiben hier vollständig sichtbar.
  setText("health-line", [
    `Zeitfenster ${health.current_slot_label || "-"}: ${formatNumber(health.current_price_ct_kwh, "ct/kWh", 3)}`,
    `Sicherer Modus: ${health.safe_mode_reason ? "aktiv" : "aus"}`,
    `Morgen: ${health.tomorrow_prices_available ? "Preise verfügbar" : "wartet"}`,
  ].join(" / "));

  setText("spotmarket-summary", buildPriceWindowSummary(health, appState.statusPayload?.spotmarket_plan || {}));
}

function renderStatusHero(message, health) {
  const target = document.getElementById("status-hero");
  if (!target) {
    return;
  }
  target.className = `status-hero ${message.level}`;
  const stand = health && health.timestamp ? `Stand ${formatTimestamp(health.timestamp)}` : "Noch keine Daten";
  target.innerHTML = `
    <div class="status-hero-text">
      <strong>${escapeHtml(message.headline)}</strong>
      <p>${escapeHtml(message.detail)}</p>
    </div>
    <span class="status-hero-meta">${escapeHtml(stand)}</span>
  `;
}

function renderStartHints(hints) {
  const target = document.getElementById("dashboard-hints");
  if (!target) {
    return;
  }
  if (!hints.length) {
    target.innerHTML = '<div class="hint-item neutral">Keine besonderen Hinweise.</div>';
    return;
  }
  target.innerHTML = hints.map((hint) => `
    <div class="hint-item ${escapeHtml(hint.level)}">${escapeHtml(hint.text)}</div>
  `).join("");
}

function renderKpis(payload) {
  const target = document.getElementById("kpi-grid");
  if (!target) {
    return;
  }
  const health = payload.health || {};
  const ctx = {
    weather: appState.weather,
    priceMin: appState.priceStats ? appState.priceStats.min : null,
    priceMax: appState.priceStats ? appState.priceStats.max : null,
  };
  const enabled = appState.dashboard.kpis.length ? appState.dashboard.kpis : DEFAULT_DASHBOARD.kpis;
  const cards = enabled
    .map((id) => KPI_CATALOG.find((kpi) => kpi.id === id))
    .filter(Boolean)
    .map((kpi) => `
      <article class="metric-card ${kpi.accent}">
        <span>${escapeHtml(kpi.label)}</span>
        <strong>${escapeHtml(kpi.value(health, ctx))}</strong>
        <small>${escapeHtml(kpi.sub(health, ctx))}</small>
      </article>
    `);
  target.innerHTML = cards.join("") || '<div class="empty-state">Noch keine Kennzahlen ausgewählt. Oben rechts über „Ansicht anpassen“ Kennzahlen hinzufügen.</div>';
}

function applyDashboardWidgets() {
  document.querySelectorAll("[data-widget]").forEach((element) => {
    element.hidden = appState.dashboard.widgets[element.dataset.widget] === false;
  });
  rebuildPriceChart();
}

function rangeToHours(range) {
  return range === "6h" ? 6 : range === "48h" ? 48 : range === "7d" ? 24 * 7 : 24;
}

async function renderDashboardCharts() {
  destroyDashboardCharts();
  const container = document.getElementById("dashboard-charts");
  if (!container) {
    return;
  }
  const charts = appState.dashboard.charts || [];
  if (!charts.length) {
    container.innerHTML = "";
    return;
  }
  const rangeLabels = { "6h": "Letzte 6 Std", "24h": "Letzte 24 Std", "48h": "Letzte 48 Std", "7d": "Letzte 7 Tage" };
  container.innerHTML = charts.map((chart) => {
    const meta = channelMeta(chart.channel);
    return `
      <article class="tool-panel dashboard-chart-tile">
        <div class="panel-head">
          <div>
            <h3>${escapeHtml(meta.label || "Datenpunkt")}</h3>
            <p>${escapeHtml([rangeLabels[chart.range] || "Letzte 24 Std", meta.unit || valueKindLabel(meta.kind)].filter(Boolean).join(" · "))}</p>
          </div>
          ${qualityBadgeHtml(chart.channel)}
        </div>
        <div class="chart-frame report-chart" data-chart-frame="${escapeHtml(chart.id)}"></div>
      </article>
    `;
  }).join("");

  const referenceNow = getReferenceNow(appState.statusPayload || {});
  await Promise.all(charts.map(async (chart) => {
    const hours = rangeToHours(chart.range);
    const start = new Date(referenceNow.getTime() - hours * 3600 * 1000);
    const granularity = hours > 48 ? "1h" : "5m";
    const payload = await fetchHistorySafe(chart.channel, start, referenceNow, granularity, historyLimit(granularity));
    const points = normalizeHistoryRows(payload.rows || [])
      .map((row) => ({ time: parseTime(row.timestamp), value: historyValue(row) }))
      .filter(isFinitePoint);
    dashboardChartData.set(chart.id, { points, error: payload.error });
  }));

  charts.forEach((chart, index) => drawDashboardChart(chart, index));
}

function redrawDashboardCharts() {
  (appState.dashboard.charts || []).forEach((chart, index) => drawDashboardChart(chart, index));
}

function destroyDashboardChart(id) {
  dashboardCharts = dashboardCharts.filter((entry) => {
    if (entry.id !== id) {
      return true;
    }
    try {
      if (entry.observer) {
        entry.observer.disconnect();
      }
      entry.instance.destroy();
    } catch (error) {
      /* Instanz bereits entfernt. */
    }
    return false;
  });
}

function destroyDashboardCharts() {
  dashboardCharts.forEach((entry) => {
    try {
      if (entry.observer) {
        entry.observer.disconnect();
      }
      entry.instance.destroy();
    } catch (error) {
      /* Instanz bereits entfernt. */
    }
  });
  dashboardCharts = [];
}

function drawDashboardChart(chart, index) {
  const frame = document.querySelector(`[data-chart-frame="${chart.id}"]`);
  if (!frame) {
    return;
  }
  destroyDashboardChart(chart.id);
  frame.innerHTML = "";
  const data = dashboardChartData.get(chart.id);
  if (!data || !data.points.length) {
    frame.innerHTML = `<div class="chart-empty">${escapeHtml(data && data.error ? data.error : "Für diesen Zeitraum liegen keine Werte vor. Über „Ansicht anpassen“ einen längeren Zeitraum wählen.")}</div>`;
    return;
  }
  if (typeof uPlot === "undefined") {
    frame.innerHTML = '<div class="chart-empty">Das Diagramm kann gerade nicht dargestellt werden. Bitte die Seite neu laden.</div>';
    return;
  }
  const colors = reportChartColors();
  const color = seriesColor(index);
  let xs;
  let ys;
  let seriesOptions;
  if (chart.type === "bar") {
    const span = data.points[data.points.length - 1].time - data.points[0].time;
    const bucketMs = span > 3 * 24 * 3600 * 1000 ? 24 * 3600 * 1000 : 3600 * 1000;
    const buckets = aggregateBuckets(data.points, bucketMs);
    xs = buckets.map((bucket) => Math.round(bucket.time / 1000));
    ys = buckets.map((bucket) => bucket.value);
    seriesOptions = { stroke: color, fill: hexToRgba(color, 0.55), width: 1, paths: uPlot.paths.bars({ size: [0.7, 40] }), points: { show: false } };
  } else {
    const granularity = rangeToHours(chart.range) > 48 ? "1h" : "5m";
    const series = buildSeriesWithGaps(data.points, gapThresholdMs(granularity));
    xs = series.xs;
    ys = series.ys;
    seriesOptions = { stroke: color, width: 2, fill: hexToRgba(color, 0.1), points: { show: false } };
  }
  const instance = new uPlot({
    width: frame.clientWidth || 520,
    height: 200,
    padding: [12, 14, 4, 8],
    legend: { show: false },
    cursor: { y: false },
    scales: { x: { time: true } },
    axes: [
      { stroke: colors.axis, font: `12px ${colors.font}`, grid: { stroke: colors.grid, width: 1 }, ticks: { stroke: colors.grid },
        values: (_u, splits) => splits.map((value) => formatTimeAxis(value)) },
      { stroke: colors.axis, font: `12px ${colors.font}`, size: 52, grid: { stroke: colors.grid, width: 1 }, ticks: { stroke: colors.grid },
        values: (_u, splits) => splits.map((value) => formatAxis(value)) },
    ],
    series: [{}, seriesOptions],
  }, [xs, ys], frame);

  let observer = null;
  if (typeof ResizeObserver !== "undefined") {
    observer = new ResizeObserver(() => {
      if (frame.clientWidth) {
        instance.setSize({ width: frame.clientWidth, height: 200 });
      }
    });
    observer.observe(frame);
  }
  dashboardCharts.push({ id: chart.id, instance, observer });
}

function renderSignals(payload) {
  const health = payload.health || {};
  const priceCache = payload.price_cache || {};
  const source = priceCache.price_source_status || {};
  const writeStatus = health.write_status || {};
  const currentPrice = writeStatus.current_price || {};
  const spotmarket = writeStatus.spotmarket_lockout || {};
  const tomorrowSlots = Number(source.tomorrow_slots_found ?? priceCache.tomorrow?.available_slot_count ?? 0);
  const todaySlots = Number(source.today_slots_found ?? priceCache.today?.available_slot_count ?? 0);
  const rows = [
    {
      state: currentPrice.last_error ? "error" : currentPrice.confirmed === false ? "warn" : "ok",
      title: "Preis an Anlage übergeben",
      text: `${currentPrice.confirmed === false ? "wartet auf Bestätigung" : "bestätigt"} / ${formatAge(health.last_price_handoff_at || currentPrice.last_confirmed_at)}`,
    },
    {
      state: spotmarket.last_error ? "error" : spotmarket.confirmed === false ? "warn" : "ok",
      title: "Preissteuerung",
      text: `${formatBool(spotmarket.desired_value)} / ${formatAge(spotmarket.last_confirmed_at)}`,
    },
    {
      state: todaySlots > 0 ? "ok" : "warn",
      title: "Preisdaten",
      text: todaySlots > 0
        ? `${todaySlots} Werte heute / ${tomorrowSlots || "keine"} Werte morgen`
        : "Noch keine Preise für heute abgerufen. Bitte die Preisquelle prüfen.",
    },
    {
      state: health.safe_mode_reason ? "error" : "ok",
      title: "Sicherer Betriebszustand",
      text: health.safe_mode_reason ? safeModeSignalText(health.safe_mode_reason) : "Anlage läuft normal",
    },
  ];
  document.getElementById("signal-list").innerHTML = rows.map((row) => `
    <article class="signal-card ${row.state}">
      <strong>${escapeHtml(row.title)}</strong>
      <span>${escapeHtml(row.text)}</span>
    </article>
  `).join("");
}

function renderWindows(plan) {
  renderWindowList("windows-today", plan.today?.windows || []);
  renderWindowList("windows-tomorrow", plan.tomorrow?.windows || []);
}

function renderWindowList(targetId, windows) {
  const target = document.getElementById(targetId);
  if (!windows.length) {
    target.innerHTML = '<div class="empty-state">Keine geplanten Preisfenster.</div>';
    return;
  }
  target.innerHTML = windows.map((window) => `
    <article class="window-card">
      <strong>${escapeHtml(window.start_label)} - ${escapeHtml(window.end_label_exclusive)}</strong>
      <span>${escapeHtml(window.length_quarters)} Viertelstunden / ab ${escapeHtml(formatNumber(window.min_price_ct_kwh, "ct/kWh", 3))}</span>
    </article>
  `).join("");
}

async function renderPriceOverview(payload) {
  const referenceNow = getReferenceNow(payload);
  const range = { start: new Date(referenceNow.getTime() - 12 * 60 * 60 * 1000), end: new Date(referenceNow.getTime() + 36 * 60 * 60 * 1000) };
  const history = await fetchHistorySafe("tariff.current_price_ct_kwh", range.start, new Date(referenceNow.getTime() + 5 * 60 * 1000), "raw", 1800);
  const timeline = buildPriceTimeline(payload, history.rows || [], range, referenceNow);
  appState.priceStats = { min: timeline.min, max: timeline.max, current: timeline.current };
  setText("price-chart-meta", timeline.points.length ? "Viertelstundenpreise · ct/kWh" : "keine Preisdaten");
  renderPriceChart(document.getElementById("price-chart"), timeline.points, {
    unit: "ct/kWh",
    step: true,
    windows: timeline.windows,
    now: referenceNow.getTime(),
    gapMs: 2.5 * PRICE_SLOT_MS,
    empty: "Für diese Ansicht liegen noch keine Preisdaten vor. Sobald die Day-Ahead-Preise abgerufen wurden, erscheint hier der Verlauf.",
  });
  renderPriceCaption(timeline);
  document.getElementById("price-chart-stats").innerHTML = [
    statCell("Günstigster Preis", formatNumber(timeline.min, "ct/kWh", 3)),
    statCell("Höchster Preis", formatNumber(timeline.max, "ct/kWh", 3)),
    statCell("Aktuelle Viertelstunde", formatNumber(timeline.current, "ct/kWh", 3)),
    statCell("Günstige Preisfenster", timeline.windows.length ? timeline.windows.map((item) => `${item.label} Uhr`).join(", ") : "keine geplant"),
  ].join("");
}

/* Erklärzeile unter dem Preisdiagramm (UX8): benennt die Markierungen in
   Betreiber-Sprache, statt sie nur über Farbe zu codieren. */
function renderPriceCaption(timeline) {
  const target = document.getElementById("price-chart-caption");
  if (!target) {
    return;
  }
  if (!timeline.points.length) {
    target.innerHTML = "";
    target.hidden = true;
    return;
  }
  const items = [];
  if (timeline.windows.length) {
    items.push('<span class="caption-item"><span class="caption-swatch" aria-hidden="true"></span>Günstiges Preisfenster</span>');
  }
  items.push('<span class="caption-item"><span class="caption-now" aria-hidden="true"></span>Jetzt (aktuelle Viertelstunde)</span>');
  target.innerHTML = items.join("");
  target.hidden = false;
}

function buildPriceTimeline(payload, historyRows, range, referenceNow) {
  const priceCache = payload.price_cache || {};
  const health = payload.health || {};
  const history = normalizeHistoryRows(historyRows)
    .map((row) => ({ time: parseTime(row.timestamp), value: historyValue(row) }))
    .filter((point) => isFinitePoint(point) && point.time >= range.start.getTime() && point.time <= referenceNow.getTime());
  const forecast = [];
  for (const day of [priceCache.today, priceCache.tomorrow]) {
    if (!day || typeof day.date !== "string" || !Array.isArray(day.slots)) {
      continue;
    }
    day.slots.forEach((value, index) => {
      const time = buildSlotTime(day.date, index);
      const numeric = toNumber(value);
      if (Number.isFinite(time) && Number.isFinite(numeric) && time >= referenceNow.getTime() && time <= range.end.getTime()) {
        forecast.push({ time, value: numeric });
      }
    });
  }
  const byTime = new Map();
  [...history, ...forecast].forEach((point) => byTime.set(point.time, point));
  const points = [...byTime.values()].sort((a, b) => a.time - b.time);
  const values = points.map((point) => point.value).filter(Number.isFinite);
  const windows = buildWindowBands(payload.spotmarket_plan || {}).filter((window) => window.end >= range.start.getTime() && window.start <= range.end.getTime());
  return {
    points,
    windows,
    min: values.length ? Math.min(...values) : null,
    max: values.length ? Math.max(...values) : null,
    current: toNumber(health.current_price_ct_kwh),
  };
}

function buildWindowBands(plan) {
  const bands = [];
  for (const day of [plan.today, plan.tomorrow]) {
    if (!day || typeof day.date !== "string" || !Array.isArray(day.windows)) {
      continue;
    }
    day.windows.forEach((window) => {
      const start = buildSlotTime(day.date, Number(window.start_slot));
      const end = buildSlotTime(day.date, Number(window.end_slot_exclusive));
      if (Number.isFinite(start) && Number.isFinite(end)) {
        bands.push({
          start,
          end,
          label: `${window.start_label}-${window.end_label_exclusive}`,
        });
      }
    });
  }
  return bands;
}

function renderChannelPicker() {
  const query = document.getElementById("channel-search").value.trim().toLowerCase();
  const channels = appState.availableChannels.filter((channel) => {
    const haystack = `${channel.id} ${channel.label} ${channel.group} ${channel.unit}`.toLowerCase();
    return !query || haystack.includes(query);
  });
  const byGroup = groupBy(channels, (channel) => channel.group || "EMS");
  document.getElementById("channel-list").innerHTML = [...byGroup.entries()].map(([group, groupChannels]) => `
    <div class="channel-group">
      <span class="micro-label">${escapeHtml(group)}</span>
      ${groupChannels.map((channel) => `
        <label class="channel-option">
          <input type="checkbox" value="${escapeHtml(channel.id)}" ${appState.selectedChannels.has(channel.id) ? "checked" : ""}>
          <span>
            ${escapeHtml(channel.label || "Datenpunkt")}
            <small>${escapeHtml([channel.group, channel.unit].filter(Boolean).join(" / "))}</small>
          </span>
        </label>
      `).join("")}
    </div>
  `).join("") || '<div class="empty-state">Keine passenden Datenpunkte.</div>';
  document.querySelectorAll("#channel-list input[type='checkbox']").forEach((input) => {
    input.addEventListener("change", () => {
      if (input.checked) {
        appState.selectedChannels.add(input.value);
      } else {
        appState.selectedChannels.delete(input.value);
      }
      refreshWorkbench();
    });
  });
  renderSelectedStrip();
}

function renderSelectedStrip() {
  const selected = selectedChannelMeta();
  const target = document.getElementById("selected-strip");
  if (!selected.length) {
    target.innerHTML = '<div class="empty-state">Wähle links die gewünschten Datenpunkte für diese Ansicht.</div>';
    return;
  }
  target.innerHTML = selected.map((channel) => `
    <article class="selected-chip">
      <span>${escapeHtml(channel.label || "Datenpunkt")}</span>
      <button type="button" aria-label="${escapeHtml(channel.label || "Datenpunkt")} entfernen" data-channel="${escapeHtml(channel.id)}">x</button>
    </article>
  `).join("");
  target.querySelectorAll("button[data-channel]").forEach((button) => {
    button.addEventListener("click", () => {
      appState.selectedChannels.delete(button.dataset.channel);
      renderChannelPicker();
      refreshWorkbench();
    });
  });
}

async function refreshWorkbench() {
  renderSelectedStrip();
  const selected = selectedChannelMeta();
  if (!selected.length) {
    document.getElementById("series-grid").innerHTML = '<div class="empty-state">Keine Datenpunkte ausgewählt.</div>';
    document.getElementById("series-summary-body").innerHTML = "";
    return;
  }
  const range = selectedRange();
  const granularity = document.getElementById("granularity-select").value;
  document.getElementById("series-grid").innerHTML = '<div class="empty-state">Daten werden geladen.</div>';
  const histories = await Promise.all(selected.map(async (channel) => {
    const payload = await fetchHistorySafe(channel.id, range.start, range.end, granularity, historyLimit(granularity));
    return {
      channel,
      rows: normalizeHistoryRows(payload.rows || []),
      error: payload.error || null,
    };
  }));
  appState.activeHistories = new Map(histories.map((item) => [item.channel.id, item]));
  renderSeriesGrid(histories);
  renderSeriesSummary(histories);
  updateReportLinks();
}

function renderSeriesGrid(histories) {
  const granularity = document.getElementById("granularity-select")?.value || "5m";
  document.getElementById("series-grid").innerHTML = histories.map((item, index) => {
    const points = item.rows.map((row) => ({ time: parseTime(row.timestamp), value: historyValue(row) })).filter(isFinitePoint);
    const stats = seriesStats(points);
    const gapMs = gapThresholdMs(granularity) ?? medianGapThreshold(points);
    return `
      <article class="series-card">
        <div class="series-head">
          <div>
            <strong>${escapeHtml(item.channel.label || "Datenpunkt")}</strong>
            <span>${escapeHtml([item.channel.group, item.channel.unit || valueKindLabel(item.channel.kind)].filter(Boolean).join(" / "))}</span>
            ${qualityBadgeHtml(item.channel.id)}
          </div>
        </div>
        ${item.error ? `<div class="empty-state compact">${escapeHtml(item.error)}</div>` : `<div class="mini-chart">${renderSparkline(points, seriesColor(index), item.channel.unit, gapMs)}</div>`}
        <div class="chart-stats">
          ${statCell("Letzter Wert", formatNumber(stats.last, item.channel.unit))}
          ${statCell("Min", formatNumber(stats.min, item.channel.unit))}
          ${statCell("Max", formatNumber(stats.max, item.channel.unit))}
          ${statCell("Messpunkte", String(points.length))}
        </div>
      </article>
    `;
  }).join("");
}

function renderSeriesSummary(histories) {
  const rows = histories.map((item) => {
    const points = item.rows.map((row) => ({ time: parseTime(row.timestamp), value: historyValue(row) })).filter(isFinitePoint);
    const stats = seriesStats(points);
    return `
      <tr>
        <td>${escapeHtml(item.channel.label || "Datenpunkt")}</td>
        <td>${escapeHtml(formatNumber(stats.last, item.channel.unit))}</td>
        <td>${escapeHtml(formatNumber(stats.min, item.channel.unit))}</td>
        <td>${escapeHtml(formatNumber(stats.max, item.channel.unit))}</td>
        <td>${escapeHtml(points.length)}</td>
      </tr>
    `;
  });
  document.getElementById("series-summary-body").innerHTML = rows.join("");
}

async function fetchHistory(channelId, start, end, granularity, limit) {
  const query = new URLSearchParams({
    channel_id: channelId,
    granularity,
    start: start.toISOString(),
    end: end.toISOString(),
    limit: String(limit),
  });
  return fetchJson(`/api/history?${query.toString()}`);
}

async function fetchHistorySafe(channelId, start, end, granularity, limit) {
  try {
    return await fetchHistory(channelId, start, end, granularity, limit);
  } catch (error) {
    return {
      rows: [],
      error: "Verlaufsdaten konnten nicht geladen werden. Bitte die Verbindung zur lokalen Anlage prüfen.",
    };
  }
}

function renderPriceChart(target, points, options = {}) {
  const clean = points.filter(isFinitePoint).sort((a, b) => a.time - b.time);
  destroyPriceChart();
  target.innerHTML = "";
  priceChart.target = target;
  priceChart.points = clean;
  priceChart.options = options;
  if (!clean.length) {
    target.innerHTML = `<div class="chart-empty">${escapeHtml(options.empty || "Keine Daten vorhanden.")}</div>`;
    return;
  }
  if (typeof uPlot === "undefined") {
    target.innerHTML = '<div class="chart-empty">Das Diagramm kann gerade nicht dargestellt werden. Bitte die Seite neu laden.</div>';
    return;
  }

  const css = getComputedStyle(document.documentElement);
  const token = (name, fallback) => (css.getPropertyValue(name).trim() || fallback);
  const accent = token("--accent", "#1769d6");
  const gridColor = token("--line", "#e4eaf1");
  const axisColor = token("--muted", "#5b6b7e");
  const okColor = token("--ok", "#0f8a5f");
  const neutral = token("--neutral", "#51647a");
  const fontFamily = token("--font", "system-ui, sans-serif");

  const { xs, ys } = buildSeriesWithGaps(clean, options.gapMs);
  const windows = options.windows || [];
  const nowSec = Number.isFinite(options.now) ? Math.round(options.now / 1000) : null;
  const ratio = window.devicePixelRatio || 1;

  const tooltip = document.createElement("div");
  tooltip.className = "ems-tooltip";

  const drawWindows = (u) => {
    if (!windows.length) {
      return;
    }
    const { ctx } = u;
    ctx.save();
    ctx.fillStyle = hexToRgba(okColor, 0.16);
    windows.forEach((band) => {
      const xa = u.valToPos(band.start / 1000, "x", true);
      const xb = u.valToPos(band.end / 1000, "x", true);
      const left = Math.max(u.bbox.left, Math.min(xa, xb));
      const right = Math.min(u.bbox.left + u.bbox.width, Math.max(xa, xb));
      if (right > left) {
        ctx.fillRect(left, u.bbox.top, right - left, u.bbox.height);
      }
    });
    ctx.restore();
  };

  const drawNow = (u) => {
    if (nowSec == null) {
      return;
    }
    const x = u.valToPos(nowSec, "x", true);
    if (x < u.bbox.left || x > u.bbox.left + u.bbox.width) {
      return;
    }
    const { ctx } = u;
    ctx.save();
    ctx.strokeStyle = neutral;
    ctx.lineWidth = Math.max(1, ratio);
    ctx.setLineDash([5 * ratio, 5 * ratio]);
    ctx.beginPath();
    ctx.moveTo(x, u.bbox.top);
    ctx.lineTo(x, u.bbox.top + u.bbox.height);
    ctx.stroke();
    ctx.restore();
  };

  const updateTooltip = (u) => {
    const idx = u.cursor.idx;
    if (idx == null || u.cursor.left < 0) {
      tooltip.style.display = "none";
      return;
    }
    const value = u.data[1][idx];
    if (!Number.isFinite(value)) {
      tooltip.style.display = "none";
      return;
    }
    tooltip.style.display = "block";
    const timeMs = u.data[0][idx] * 1000;
    const inWindow = windows.some((band) => timeMs >= band.start && timeMs < band.end);
    tooltip.innerHTML = `<b>${escapeHtml(DATE_TIME.format(new Date(timeMs)))}</b>`
      + `<span class="ems-tooltip-value">${escapeHtml(formatNumber(value, options.unit || "", 3))}</span>`
      + (inWindow ? '<span class="ems-tooltip-flag">Günstiges Preisfenster</span>' : "");
    let left = u.cursor.left + 14;
    if (left + tooltip.offsetWidth > u.over.clientWidth) {
      left = u.cursor.left - tooltip.offsetWidth - 14;
    }
    tooltip.style.left = `${Math.max(0, left)}px`;
    tooltip.style.top = `${Math.max(0, u.cursor.top + 8)}px`;
  };

  const opts = {
    width: target.clientWidth || 600,
    height: target.clientHeight || 290,
    padding: [12, 16, 4, 8],
    legend: { show: false },
    cursor: { y: false, points: { size: 7 } },
    scales: { x: { time: true } },
    axes: [
      {
        stroke: axisColor,
        font: `12px ${fontFamily}`,
        grid: { stroke: gridColor, width: 1 },
        ticks: { stroke: gridColor, width: 1 },
        values: (_u, splits) => splits.map((value) => formatTimeAxis(value)),
      },
      {
        stroke: axisColor,
        font: `12px ${fontFamily}`,
        size: 56,
        grid: { stroke: gridColor, width: 1 },
        ticks: { stroke: gridColor, width: 1 },
        values: (_u, splits) => splits.map((value) => formatAxis(value)),
      },
    ],
    series: [
      {},
      {
        label: options.unit || "Wert",
        stroke: accent,
        width: 2,
        fill: hexToRgba(accent, 0.12),
        paths: options.step ? uPlot.paths.stepped({ align: 1 }) : uPlot.paths.linear(),
        points: { show: false },
      },
    ],
    hooks: {
      drawClear: [drawWindows],
      draw: [drawNow],
      setCursor: [updateTooltip],
    },
  };

  priceChart.instance = new uPlot(opts, [xs, ys], target);
  priceChart.instance.over.appendChild(tooltip);

  if (typeof ResizeObserver !== "undefined") {
    priceChart.observer = new ResizeObserver(() => {
      if (priceChart.instance && target.clientWidth) {
        priceChart.instance.setSize({ width: target.clientWidth, height: target.clientHeight || 290 });
      }
    });
    priceChart.observer.observe(target);
  }
}

function rebuildPriceChart() {
  if (priceChart.target && priceChart.points.length && priceChart.options) {
    renderPriceChart(priceChart.target, priceChart.points, priceChart.options);
  }
}

function destroyPriceChart() {
  if (priceChart.observer) {
    priceChart.observer.disconnect();
    priceChart.observer = null;
  }
  if (priceChart.instance) {
    priceChart.instance.destroy();
    priceChart.instance = null;
  }
}

function hexToRgba(color, alpha) {
  const hex = String(color).trim().replace("#", "");
  if (hex.length !== 6 && hex.length !== 3) {
    return color;
  }
  const full = hex.length === 3 ? hex.split("").map((char) => char + char).join("") : hex;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/* Datenreihen-Farben zur Laufzeit aus den Styleguide-Tokens lesen (UI_STYLEGUIDE, 7.1),
   damit Diagramme in beiden Themes stimmen; SERIES_COLORS bleibt als Fallback. */
function seriesColor(index) {
  const fallback = SERIES_COLORS[index % SERIES_COLORS.length];
  if (typeof getComputedStyle !== "function" || !document.documentElement) {
    return fallback;
  }
  const token = getComputedStyle(document.documentElement)
    .getPropertyValue(`--series-${(index % SERIES_COLORS.length) + 1}`)
    .trim();
  return token || fallback;
}

/* X-Achsen-Beschriftung (UX8): Uhrzeit, am Tageswechsel stattdessen das Datum —
   so bleiben mehrtägige Zeiträume ohne Erklärung lesbar. */
function formatTimeAxis(valueSeconds) {
  const date = new Date(valueSeconds * 1000);
  if (date.getHours() === 0 && date.getMinutes() === 0) {
    return DAY_ONLY.format(date);
  }
  return TIME_ONLY.format(date);
}

/* Ab welchem zeitlichen Abstand gilt eine Messreihe als lückenhaft? (2,5-faches Zeitraster) */
function gapThresholdMs(granularity) {
  if (granularity === "5m") {
    return 2.5 * 5 * 60000;
  }
  if (granularity === "1h") {
    return 2.5 * 3600000;
  }
  if (granularity === "1d") {
    return 2.5 * 86400000;
  }
  return null;
}

/* Bei Einzelwerten: Lückenschwelle aus dem typischen Messabstand ableiten. */
function medianGapThreshold(points) {
  if (points.length < 3) {
    return Infinity;
  }
  const deltas = [];
  for (let index = 1; index < points.length; index += 1) {
    deltas.push(points[index].time - points[index - 1].time);
  }
  deltas.sort((a, b) => a - b);
  const median = deltas[Math.floor(deltas.length / 2)];
  return median > 0 ? median * 2.5 : Infinity;
}

/* Zeitreihe für uPlot aufbereiten (UX8): bei Lücken wird ein null-Wert eingefügt,
   damit die Linie ehrlich unterbricht statt über fehlende Daten zu interpolieren. */
function buildSeriesWithGaps(points, thresholdMs = null) {
  const xs = [];
  const ys = [];
  const threshold = Number.isFinite(thresholdMs) ? thresholdMs : medianGapThreshold(points);
  points.forEach((point, index) => {
    if (index > 0 && point.time - points[index - 1].time > threshold) {
      xs.push(Math.round((points[index - 1].time + point.time) / 2000));
      ys.push(null);
    }
    xs.push(Math.round(point.time / 1000));
    ys.push(point.value);
  });
  return { xs, ys };
}

function renderSparkline(points, color, unit, gapMs = Infinity) {
  const clean = points.filter(isFinitePoint).sort((a, b) => a.time - b.time);
  if (!clean.length) {
    return '<div class="chart-empty">Keine Daten.</div>';
  }
  const width = 520;
  const height = 170;
  const margin = { top: 12, right: 12, bottom: 24, left: 44 };
  const times = clean.map((point) => point.time);
  const values = clean.map((point) => point.value);
  const xMin = Math.min(...times);
  const xMax = Math.max(...times);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const pad = Math.max((rawMax - rawMin) * 0.14, rawMax === rawMin ? 1 : 0.2);
  const yMin = rawMin - pad;
  const yMax = rawMax + pad;
  const x = (time) => margin.left + ((time - xMin) / Math.max(xMax - xMin, 1)) * (width - margin.left - margin.right);
  const y = (value) => margin.top + (height - margin.top - margin.bottom) - ((value - yMin) / Math.max(yMax - yMin, 1e-9)) * (height - margin.top - margin.bottom);
  const path = linePath(clean, x, y, gapMs);
  const ticks = [yMin, (yMin + yMax) / 2, yMax];
  return `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      ${ticks.map((tick) => `<line class="chart-grid-line" x1="${margin.left}" y1="${y(tick).toFixed(1)}" x2="${width - margin.right}" y2="${y(tick).toFixed(1)}"></line><text class="chart-axis-label" x="${margin.left - 8}" y="${(y(tick) + 4).toFixed(1)}" text-anchor="end">${escapeHtml(formatAxis(tick))}</text>`).join("")}
      <path class="chart-line" d="${path}" stroke="${color}"></path>
      <text class="chart-axis-label" x="${width - margin.right}" y="${height - 8}" text-anchor="end">${escapeHtml(unit || "")}</text>
    </svg>
  `;
}

function renderViewSelect() {
  const select = document.getElementById("view-select");
  select.innerHTML = [
    ...VIEW_PRESETS.map((view) => `<option value="${escapeHtml(view.id)}">${escapeHtml(view.label)}</option>`),
    ...appState.savedViews.map((view) => `<option value="${escapeHtml(view.id)}">${escapeHtml(view.label)}</option>`),
  ].join("");
}

function findView(id) {
  return [...VIEW_PRESETS, ...appState.savedViews].find((view) => view.id === id);
}

function applyView(view) {
  appState.selectedChannels = new Set(view.channels);
  document.getElementById("range-select").value = view.range || "24h";
  document.getElementById("granularity-select").value = view.granularity || "5m";
  const select = document.getElementById("view-select");
  if ([...select.options].some((option) => option.value === view.id)) {
    select.value = view.id;
  }
  renderChannelPicker();
}

function saveCurrentView() {
  const input = document.getElementById("view-name");
  const label = input.value.trim();
  if (!label) {
    input.focus();
    return;
  }
  const view = {
    id: `saved:${Date.now()}`,
    label,
    range: document.getElementById("range-select").value,
    granularity: document.getElementById("granularity-select").value,
    channels: [...appState.selectedChannels],
  };
  appState.savedViews.push(view);
  localStorage.setItem("miniEmsViews", JSON.stringify(appState.savedViews));
  input.value = "";
  renderViewSelect();
  document.getElementById("view-select").value = view.id;
}

function loadSavedViews() {
  try {
    const parsed = JSON.parse(localStorage.getItem("miniEmsViews") || "[]");
    return Array.isArray(parsed) ? parsed.filter((view) => view && view.id && Array.isArray(view.channels)) : [];
  } catch {
    return [];
  }
}

function loadDashboardConfig() {
  try {
    const parsed = JSON.parse(localStorage.getItem(DASHBOARD_STORAGE_KEY) || "null");
    if (!parsed || typeof parsed !== "object") {
      return { kpis: [...DEFAULT_DASHBOARD.kpis], widgets: { ...DEFAULT_DASHBOARD.widgets } };
    }
    const validIds = new Set(KPI_CATALOG.map((kpi) => kpi.id));
    const kpis = Array.isArray(parsed.kpis) ? parsed.kpis.filter((id) => validIds.has(id)) : [...DEFAULT_DASHBOARD.kpis];
    const widgets = { ...DEFAULT_DASHBOARD.widgets };
    if (parsed.widgets && typeof parsed.widgets === "object") {
      DASHBOARD_WIDGETS.forEach((widget) => {
        if (typeof parsed.widgets[widget.id] === "boolean") {
          widgets[widget.id] = parsed.widgets[widget.id];
        }
      });
    }
    const charts = Array.isArray(parsed.charts)
      ? parsed.charts
        .filter((chart) => chart && typeof chart.channel === "string")
        .map((chart) => ({
          id: String(chart.id || `chart-${chart.channel}`),
          channel: chart.channel,
          type: chart.type === "bar" ? "bar" : "line",
          range: ["6h", "24h", "48h", "7d"].includes(chart.range) ? chart.range : "24h",
        }))
      : [];
    return { kpis, widgets, charts };
  } catch {
    return { kpis: [...DEFAULT_DASHBOARD.kpis], widgets: { ...DEFAULT_DASHBOARD.widgets }, charts: [] };
  }
}

function persistDashboardConfig() {
  try {
    localStorage.setItem(DASHBOARD_STORAGE_KEY, JSON.stringify(appState.dashboard));
  } catch (error) {
    /* localStorage nicht verfügbar — Konfiguration bleibt nur für diese Sitzung aktiv. */
  }
}

function openDashboardConfig() {
  const kpiList = document.getElementById("kpi-config-list");
  kpiList.innerHTML = KPI_CATALOG.map((kpi) => `
    <label class="check">
      <input type="checkbox" name="config-kpi" value="${escapeHtml(kpi.id)}" ${appState.dashboard.kpis.includes(kpi.id) ? "checked" : ""}>
      <span>${escapeHtml(kpi.label)}</span>
    </label>
  `).join("");
  const widgetList = document.getElementById("widget-config-list");
  widgetList.innerHTML = DASHBOARD_WIDGETS.map((widget) => `
    <label class="check">
      <input type="checkbox" name="config-widget" value="${escapeHtml(widget.id)}" ${appState.dashboard.widgets[widget.id] !== false ? "checked" : ""}>
      <span>${escapeHtml(widget.label)}</span>
    </label>
  `).join("");

  const channelSelect = document.getElementById("chart-add-channel");
  channelSelect.innerHTML = appState.availableChannels.map((channel) => `
    <option value="${escapeHtml(channel.id)}">${escapeHtml(channel.label || channel.id)}${channel.unit ? ` (${escapeHtml(channel.unit)})` : ""}</option>
  `).join("");
  modalChartDraft = appState.dashboard.charts.map((chart) => ({ ...chart }));
  renderChartConfigList();

  document.getElementById("dashboard-config-modal").hidden = false;
}

function renderChartConfigList() {
  const list = document.getElementById("chart-config-list");
  if (!modalChartDraft.length) {
    list.innerHTML = '<div class="empty-state compact">Noch keine eigenen Diagramme.</div>';
    return;
  }
  const typeLabel = { line: "Linie", bar: "Säulen" };
  const rangeLabel = { "6h": "6 Std", "24h": "24 Std", "48h": "48 Std", "7d": "7 Tage" };
  list.innerHTML = modalChartDraft.map((chart) => {
    const meta = channelMeta(chart.channel);
    return `
      <div class="chart-config-item">
        <span>${escapeHtml(meta.label || chart.channel)} · ${escapeHtml(typeLabel[chart.type] || chart.type)} · ${escapeHtml(rangeLabel[chart.range] || chart.range)}</span>
        <button type="button" class="link-button" data-remove-chart="${escapeHtml(chart.id)}">Entfernen</button>
      </div>
    `;
  }).join("");
  list.querySelectorAll("button[data-remove-chart]").forEach((button) => {
    button.addEventListener("click", () => {
      modalChartDraft = modalChartDraft.filter((chart) => chart.id !== button.dataset.removeChart);
      renderChartConfigList();
    });
  });
}

function addModalChart() {
  const channel = document.getElementById("chart-add-channel").value;
  if (!channel) {
    return;
  }
  modalChartDraft.push({
    id: `chart-${Date.now()}-${modalChartDraft.length}`,
    channel,
    type: document.getElementById("chart-add-type").value === "bar" ? "bar" : "line",
    range: document.getElementById("chart-add-range").value,
  });
  renderChartConfigList();
}

function closeDashboardConfig() {
  document.getElementById("dashboard-config-modal").hidden = true;
}

function saveDashboardConfig() {
  const selectedKpis = [...document.querySelectorAll("input[name='config-kpi']:checked")].map((input) => input.value);
  // Reihenfolge aus dem Katalog beibehalten, damit das Layout stabil bleibt.
  appState.dashboard.kpis = KPI_CATALOG.map((kpi) => kpi.id).filter((id) => selectedKpis.includes(id));
  const widgets = { ...DEFAULT_DASHBOARD.widgets };
  DASHBOARD_WIDGETS.forEach((widget) => {
    widgets[widget.id] = document.querySelector(`input[name='config-widget'][value='${widget.id}']`)?.checked ?? true;
  });
  appState.dashboard.widgets = widgets;
  appState.dashboard.charts = modalChartDraft.map((chart) => ({ ...chart }));
  persistDashboardConfig();
  if (appState.statusPayload) {
    renderKpis(appState.statusPayload);
  }
  applyDashboardWidgets();
  renderDashboardCharts();
  closeDashboardConfig();
}

function resetDashboardConfig() {
  appState.dashboard = { kpis: [...DEFAULT_DASHBOARD.kpis], widgets: { ...DEFAULT_DASHBOARD.widgets }, charts: [] };
  persistDashboardConfig();
  openDashboardConfig();
  if (appState.statusPayload) {
    renderKpis(appState.statusPayload);
  }
  applyDashboardWidgets();
  renderDashboardCharts();
}

function initSiteConfigPage() {
  appState.siteConfig.config = cloneSiteConfig(DEFAULT_SITE_CONFIG);
  populateSiteConfigForm(appState.siteConfig.config);
  setText("site-config-source", "Prototypvorlage");
  setSiteConfigFeedback("Noch nicht geprüft.", "neutral");
  loadSiteConfigFromBackend();
}

async function loadSiteConfigFromBackend() {
  try {
    const response = await fetch("/api/config/site", { cache: "no-store" });
    if (response.status === 404) {
      setSiteConfigFeedback("Backend-Konfiguration noch nicht angebunden; Prototypvorlage aktiv.", "neutral");
      markSetupLoadFailed();
      return;
    }
    if (!response.ok) {
      throw new Error(`Serverstatus ${response.status}`);
    }
    const payload = await response.json();
    seedSetupFromSiteConfig(payload);
    if (appState.siteConfig.dirty) {
      return;
    }
    const config = normalizeSiteConfig(payload.config || payload);
    appState.siteConfig.config = config;
    populateSiteConfigForm(config);
    setText("site-config-source", payload.save_enabled ? "Backend-Konfiguration" : "Backend-Konfiguration ohne Speichertoken");
    setSiteConfigFeedback("Konfiguration vom Backend geladen.", "neutral");
  } catch (error) {
    setText("site-config-source", "Prototypvorlage");
    setSiteConfigFeedback(`Backend-Konfiguration konnte nicht geladen werden: ${error.message}`, "neutral");
    markSetupLoadFailed();
  }
}

function populateSiteConfigForm(config) {
  const normalized = normalizeSiteConfig(config);
  setInputValue("config-site-name", normalized.site.name);
  setSelectValue("config-access-status", normalized.site.access_status);
  setInputValue("config-operator-note", normalized.site.operator_note);
  setSelectValue("config-runtime-environment", normalized.runtime.environment);
  setSelectValue("config-bacnet-mode", normalized.runtime.bacnet_mode);
  setInputChecked("config-real-writes-enabled", normalized.runtime.real_writes_enabled);
  setInputValue("config-api-host", normalized.api.host);
  setInputValue("config-api-port", normalized.api.port);
  setInputValue("config-controller-ip", normalized.network.controller_ip);
  setInputValue("config-controller-port", normalized.network.controller_port);
  setInputValue("config-local-ip", normalized.network.local_ip);
  setInputValue("config-local-port", normalized.network.local_port);
  setInputValue("config-cycle-seconds", normalized.timing.cycle_seconds);
  setInputValue("config-inter-read-delay", normalized.timing.inter_read_delay_seconds);
  setInputValue("config-watchdog-seconds", normalized.watchdog.max_cycle_age_seconds);
  setInputValue("config-history-limit", normalized.api.history_default_limit);
  setSelectValue("config-price-provider", normalized.price_source.provider);
  setInputValue("config-price-region", normalized.price_source.region);
  setInputValue("config-price-filter", normalized.price_source.filter);
  setSelectValue("config-price-resolution", normalized.price_source.resolution);
  setInputValue("config-price-timeout", normalized.price_source.timeout_seconds);
  setInputValue("config-price-factor", normalized.price_source.price_factor);
  setInputChecked("config-grid-enabled", normalized.controllers.grid_lockout.enabled);
  setInputValue("config-grid-threshold", normalized.controllers.grid_lockout.threshold_kw);
  setInputValue("config-grid-clear-threshold", normalized.controllers.grid_lockout.clear_threshold_kw);
  setInputValue("config-grid-clear-cycles", normalized.controllers.grid_lockout.below_threshold_cycles_required);
  setInputValue("config-spotmarket-consecutive", normalized.controllers.spotmarket_lockout.negative_quarters_min_consecutive);
  setInputValue("config-spotmarket-min-valid", normalized.controllers.spotmarket_lockout.min_valid_quarters);
  setInputValue("config-invalid-price-sentinel", normalized.controllers.spotmarket_lockout.invalid_price_sentinel ?? "");
  setInputValue("config-safe-mode-threshold", normalized.safety.comm_error_safe_mode_threshold);
  renderSiteConfigChannels(normalized.additional_inputs);
  updateSiteConfigPreview();
}

function normalizeSiteConfig(config) {
  const base = cloneSiteConfig(DEFAULT_SITE_CONFIG);
  const raw = config && typeof config === "object" ? config : {};
  return {
    ...base,
    ...raw,
    site: { ...base.site, ...(raw.site || {}) },
    runtime: { ...base.runtime, ...(raw.runtime || {}) },
    simulation: { ...base.simulation, ...(raw.simulation || {}) },
    network: { ...base.network, ...(raw.network || {}) },
    points: { ...base.points, ...(raw.points || {}) },
    timing: { ...base.timing, ...(raw.timing || {}) },
    watchdog: { ...base.watchdog, ...(raw.watchdog || {}) },
    api: { ...base.api, ...(raw.api || {}) },
    price_source: { ...base.price_source, ...(raw.price_source || {}) },
    controllers: {
      grid_lockout: { ...base.controllers.grid_lockout, ...(raw.controllers?.grid_lockout || {}) },
      spotmarket_lockout: { ...base.controllers.spotmarket_lockout, ...(raw.controllers?.spotmarket_lockout || {}) },
    },
    safety: { ...base.safety, ...(raw.safety || {}) },
    outputs: { ...base.outputs, ...(raw.outputs || {}) },
    database: { ...base.database, ...(raw.database || {}) },
    logging: { ...base.logging, ...(raw.logging || {}) },
    additional_inputs: normalizeSiteConfigChannels(raw.additional_inputs || base.additional_inputs),
  };
}

function renderSiteConfigChannels(channels) {
  const target = document.getElementById("config-channel-list");
  if (!target) {
    return;
  }
  const normalized = normalizeSiteConfigChannels(channels);
  target.innerHTML = normalized.map((channel) => {
    const meta = channelMeta(channel.channel_id);
    const title = meta.label || channel.description || "Zusatzkanal";
    const detail = [meta.group || "Messpunkt", meta.unit || valueKindLabel(meta.kind)].filter(Boolean).join(" / ");
    const description = channel.description || title;
    return `
      <div class="config-channel-row" data-channel-id="${escapeHtml(channel.channel_id)}" data-description="${escapeHtml(description)}">
        <div class="config-channel-row-head">
          <label class="check config-channel-main">
            <input type="checkbox" data-config-field="enabled" ${checkedAttribute(channel.enabled !== false)}>
            <span>
              <strong>${escapeHtml(title)}</strong>
              <small>${escapeHtml(detail)}<br><span class="config-channel-key">${escapeHtml(channel.channel_id)}</span></small>
            </span>
          </label>
          <span class="config-channel-summary">${escapeHtml(formatPointSummary(channel))}</span>
        </div>
        <div class="config-point-fields">
          <label>
            Protokoll
            <select data-config-field="protocol">
              <option value="bacnet" ${selectedAttribute(channel.protocol === "bacnet")}>BACnet</option>
            </select>
          </label>
          <label>
            Zielgerät
            <input type="text" data-config-field="controller_ip" placeholder="Standardgerät" value="${escapeHtml(inputValue(channel.controller_ip))}">
          </label>
          <label>
            Port
            <input type="number" min="1" max="65535" data-config-field="controller_port" placeholder="Standard" value="${escapeHtml(inputValue(channel.controller_port))}">
          </label>
          <label>
            Objekttyp
            <select data-config-field="object_type">
              <option value="ai" ${selectedAttribute(channel.object_type === "ai")}>AI Messwert</option>
              <option value="av" ${selectedAttribute(channel.object_type === "av")}>AV Wert</option>
              <option value="bv" ${selectedAttribute(channel.object_type === "bv")}>BV Status</option>
            </select>
          </label>
          <label>
            Adresse / Instanz
            <input type="number" min="0" data-config-field="instance" value="${escapeHtml(inputValue(channel.instance))}">
          </label>
          <label>
            Abfrageintervall
            <input type="number" min="1" data-config-field="read_interval_cycles" value="${escapeHtml(inputValue(channel.read_interval_cycles))}">
          </label>
          <label>
            Max. Alter (s)
            <input type="number" min="1" data-config-field="max_age_seconds" value="${escapeHtml(inputValue(channel.max_age_seconds))}">
          </label>
          <label>
            Plausibel von
            <input type="number" step="0.1" data-config-field="plausible_min" value="${escapeHtml(inputValue(channel.plausible_min))}">
          </label>
          <label>
            Plausibel bis
            <input type="number" step="0.1" data-config-field="plausible_max" value="${escapeHtml(inputValue(channel.plausible_max))}">
          </label>
          <label class="check config-check config-point-health">
            <input type="checkbox" data-config-field="include_in_health" ${checkedAttribute(channel.include_in_health)}>
            <span>Im Status überwachen</span>
          </label>
        </div>
      </div>
    `;
  }).join("");
}

function normalizeSiteConfigChannels(channels) {
  const source = Array.isArray(channels) && channels.length ? channels : CONFIG_CHANNEL_DEFAULTS;
  const byId = new Map();
  source.forEach((channel) => {
    if (!channel || typeof channel.channel_id !== "string") {
      return;
    }
    const current = byId.get(channel.channel_id) || defaultChannelConfig(channel.channel_id);
    byId.set(channel.channel_id, {
      ...current,
      ...channel,
      protocol: protocolValue(channel.protocol || current.protocol),
      object_type: bacnetObjectTypeValue(channel.object_type || current.object_type),
      enabled: channel.enabled !== false,
    });
  });
  return [...byId.values()].sort((a, b) => {
    const metaA = channelMeta(a.channel_id);
    const metaB = channelMeta(b.channel_id);
    const group = String(metaA.group || "").localeCompare(String(metaB.group || ""), "de");
    return group || String(metaA.label || a.channel_id).localeCompare(String(metaB.label || b.channel_id), "de");
  });
}

function defaultChannelConfig(channelId) {
  const meta = channelMeta(channelId);
  const isEnergy = meta.kind === "energy_counter";
  const isState = meta.kind === "state";
  return {
    channel_id: channelId,
    protocol: "bacnet",
    object_type: isState ? "bv" : isEnergy ? "av" : "ai",
    instance: "",
    description: meta.label || "Zusatzkanal",
    controller_ip: "",
    controller_port: "",
    plausible_min: isEnergy ? 0 : "",
    plausible_max: isEnergy ? 1000000000 : "",
    include_in_health: false,
    read_interval_cycles: 1,
    max_age_seconds: 120,
    enabled: true,
  };
}

function handleSiteConfigChange() {
  appState.siteConfig.dirty = true;
  setSiteConfigFeedback("Änderungen noch nicht geprüft.", "neutral");
  updateSiteConfigPreview();
}

function buildSiteConfigPayload() {
  const base = normalizeSiteConfig(appState.siteConfig.config || DEFAULT_SITE_CONFIG);
  const environment = selectValue("config-runtime-environment", base.runtime.environment);
  return {
    patch: {
      runtime: {
        environment,
        bacnet_mode: selectValue("config-bacnet-mode", base.runtime.bacnet_mode),
        real_writes_enabled: checkboxValue("config-real-writes-enabled"),
      },
      network: {
        controller_ip: textValue("config-controller-ip", base.network.controller_ip),
        controller_port: integerValue("config-controller-port", base.network.controller_port),
        local_ip: textValue("config-local-ip", base.network.local_ip),
        local_port: integerValue("config-local-port", base.network.local_port),
      },
      timing: {
        cycle_seconds: integerValue("config-cycle-seconds", base.timing.cycle_seconds),
        inter_read_delay_seconds: numericValue("config-inter-read-delay", base.timing.inter_read_delay_seconds),
      },
      watchdog: {
        max_cycle_age_seconds: numericValue("config-watchdog-seconds", base.watchdog.max_cycle_age_seconds),
      },
      api: {
        host: textValue("config-api-host", base.api.host),
        port: integerValue("config-api-port", base.api.port),
        history_default_limit: integerValue("config-history-limit", base.api.history_default_limit),
      },
      price_source: {
        provider: selectValue("config-price-provider", base.price_source.provider),
        region: textValue("config-price-region", base.price_source.region),
        filter: integerValue("config-price-filter", base.price_source.filter),
        resolution: selectValue("config-price-resolution", base.price_source.resolution),
        timeout_seconds: numericValue("config-price-timeout", base.price_source.timeout_seconds),
        price_factor: numericValue("config-price-factor", base.price_source.price_factor),
      },
      controllers: {
        grid_lockout: {
          enabled: checkboxValue("config-grid-enabled"),
          threshold_kw: numericValue("config-grid-threshold", base.controllers.grid_lockout.threshold_kw),
          clear_threshold_kw: numericValue("config-grid-clear-threshold", base.controllers.grid_lockout.clear_threshold_kw),
          below_threshold_cycles_required: integerValue("config-grid-clear-cycles", base.controllers.grid_lockout.below_threshold_cycles_required),
        },
        spotmarket_lockout: {
          negative_quarters_min_consecutive: integerValue("config-spotmarket-consecutive", base.controllers.spotmarket_lockout.negative_quarters_min_consecutive),
          min_valid_quarters: integerValue("config-spotmarket-min-valid", base.controllers.spotmarket_lockout.min_valid_quarters),
          invalid_price_sentinel: optionalNumericValue("config-invalid-price-sentinel"),
        },
      },
      safety: {
        comm_error_safe_mode_threshold: integerValue("config-safe-mode-threshold", base.safety.comm_error_safe_mode_threshold),
      },
      additional_inputs: readSiteConfigChannels(),
    },
  };
}

function readSiteConfigChannels() {
  return [...document.querySelectorAll(".config-channel-row")].map((row) => {
    if (!row.querySelector("[data-config-field='enabled']")?.checked) {
      return null;
    }
    return {
      channel_id: row.dataset.channelId,
      protocol: row.querySelector("[data-config-field='protocol']")?.value || "bacnet",
      object_type: row.querySelector("[data-config-field='object_type']")?.value || "ai",
      instance: integerFromElement(row.querySelector("[data-config-field='instance']"), 0),
      description: row.dataset.description || channelMeta(row.dataset.channelId).label || "Zusatzkanal",
      controller_ip: optionalTextFromElement(row.querySelector("[data-config-field='controller_ip']")),
      controller_port: optionalIntegerFromElement(row.querySelector("[data-config-field='controller_port']")),
      plausible_min: optionalNumberFromElement(row.querySelector("[data-config-field='plausible_min']")),
      plausible_max: optionalNumberFromElement(row.querySelector("[data-config-field='plausible_max']")),
      include_in_health: row.querySelector("[data-config-field='include_in_health']")?.checked === true,
      read_interval_cycles: integerFromElement(row.querySelector("[data-config-field='read_interval_cycles']"), 1),
      max_age_seconds: integerFromElement(row.querySelector("[data-config-field='max_age_seconds']"), 120),
    };
  }).filter(Boolean);
}

function updateSiteConfigPreview() {
  const target = document.getElementById("site-config-preview");
  if (!target) {
    return;
  }
  target.textContent = JSON.stringify(buildSiteConfigPayload(), null, 2);
}

async function validateSiteConfig() {
  const form = document.getElementById("site-config-form");
  if (!form.reportValidity()) {
    setSiteConfigFeedback("Bitte die markierten Felder korrigieren.", "warn");
    return;
  }
  const button = document.getElementById("site-config-validate");
  button.disabled = true;
  setSiteConfigFeedback("Konfiguration wird geprüft...", "neutral");
  try {
    const payload = buildSiteConfigPayload();
    const response = await postJson("/api/config/site/validate", payload);
    appState.siteConfig.dirty = false;
    setText("site-config-source", "Vom Backend geprüft");
    setSiteConfigFeedback(siteConfigResponseMessage(response, "validate"), siteConfigResponseState(response));
  } catch (error) {
    setSiteConfigFeedback(error.message, "warn");
  } finally {
    button.disabled = false;
  }
}

async function saveSiteConfig() {
  const form = document.getElementById("site-config-form");
  if (!form.reportValidity()) {
    setSiteConfigFeedback("Bitte die markierten Felder korrigieren.", "warn");
    return;
  }
  const token = document.getElementById("site-config-token").value.trim();
  if (!token) {
    setSiteConfigFeedback("Bitte zuerst den Admin-Token eintragen. Ohne Token wird nichts gespeichert.", "warn");
    document.getElementById("site-config-token").focus();
    return;
  }
  const button = document.getElementById("site-config-save");
  button.disabled = true;
  setSiteConfigFeedback("Konfiguration wird gespeichert...", "neutral");
  try {
    const payload = buildSiteConfigPayload();
    const response = await postJson("/api/config/site/save", payload, { token });
    appState.siteConfig.dirty = false;
    setText("site-config-source", "Vom Backend gespeichert");
    setSiteConfigFeedback(siteConfigResponseMessage(response, "save"), siteConfigResponseState(response));
  } catch (error) {
    setSiteConfigFeedback(error.message, "warn");
  } finally {
    button.disabled = false;
  }
}

async function postJson(path, payload, options = {}) {
  const headers = { "Content-Type": "application/json" };
  if (options.token) {
    headers["X-Mini-Ems-Admin-Token"] = options.token;
  }
  const response = await fetch(path, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  const text = await response.text();
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Der Backend-Endpunkt ${path} ist noch nicht vorhanden. Die Eingaben bleiben erhalten; es wurde nichts an der Anlage geändert.`);
    }
    throw new Error(friendlyPostError(path, response.status, text));
  }
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

function friendlyPostError(path, status, text) {
  const clean = String(text || "").trim();
  try {
    const payload = JSON.parse(clean);
    return payload.message || payload.error || `${path} konnte nicht verarbeitet werden. Serverstatus ${status}.`;
  } catch {
    /* Antwort war kein JSON. */
  }
  if (!clean || clean.startsWith("<!doctype") || clean.startsWith("<html")) {
    return `${path} konnte nicht verarbeitet werden. Serverstatus ${status}.`;
  }
  return clean.length > 220 ? `${clean.slice(0, 220)}...` : clean;
}

function siteConfigResponseMessage(response, action) {
  const errors = Array.isArray(response?.errors) ? response.errors : [];
  const warnings = Array.isArray(response?.warnings) ? response.warnings : [];
  if (errors.length) {
    return `Bitte prüfen: ${errors.map((item) => String(item)).join(" / ")}`;
  }
  if (response?.valid === false || response?.saved === false) {
    return response?.message ? String(response.message) : "Die Konfiguration wurde vom Backend abgelehnt.";
  }
  if (warnings.length) {
    return `Geprüft mit Hinweisen: ${warnings.map((item) => String(item)).join(" / ")}`;
  }
  if (response?.message) {
    return String(response.message);
  }
  if (action === "save" && response?.saved === true) {
    return response.restart_required
      ? "Konfiguration gespeichert. Ein Neustart der Mini-EMS-Runtime ist erforderlich."
      : "Konfiguration gespeichert.";
  }
  return action === "save" ? "Konfiguration wurde vom Backend angenommen." : "Konfiguration ist formal in Ordnung.";
}

function siteConfigResponseState(response) {
  if (response?.valid === false || response?.saved === false) {
    return "warn";
  }
  if (Array.isArray(response?.errors) && response.errors.length) {
    return "warn";
  }
  if (Array.isArray(response?.warnings) && response.warnings.length) {
    return "warn";
  }
  return "ok";
}

function setSiteConfigFeedback(message, state = "neutral") {
  const target = document.getElementById("site-config-feedback");
  if (!target) {
    return;
  }
  target.className = `config-feedback ${state}`;
  target.textContent = message || "-";
}

/* ============================================================
   Standort einrichten (UX14/UX15/UX16): geführte Inbetriebnahme.
   Standort -> Geräte -> Datenpunkte -> Testen -> Aktivieren.
   Die Tabelle zeigt die fachliche Bedeutung zuerst; Technikdetails
   liegen im einklappbaren Technikbereich je Zeile.
   ============================================================ */

const SETUP_STEPS = [
  { id: "standort", label: "Standort" },
  { id: "geraete", label: "Geräte" },
  { id: "punkte", label: "Datenpunkte" },
  { id: "testen", label: "Testen" },
  { id: "aktivieren", label: "Aktivieren" },
];

const SETUP_STATUS_WORDS = {
  assigned: "zugeordnet",
  review: "prüfen",
  write: "Schreibpunkt",
  tested: "geprüft",
  failed: "keine Antwort",
};

const SETUP_STATUS_BADGE = {
  assigned: "",
  review: "warn",
  write: "",
  tested: "ok",
  failed: "error",
};

/* Zugriffsart der Mini-EMS-Kernkanäle; alle weiteren Kanäle werden nur gelesen. */
const SETUP_CHANNEL_ACCESS = {
  "grid.active_power_kw": "read",
  "tariff.current_price_ct_kwh": "readwrite",
  "ems.lockout_grid": "write",
  "ems.lockout_spotmarket": "write",
};

const SETUP_CORE_POINTS = [
  { key: "grid_active_power_kw", channelId: "grid.active_power_kw", objectType: "av" },
  { key: "current_price_av", channelId: "tariff.current_price_ct_kwh", objectType: "av" },
  { key: "grid_lockout_bv", channelId: "ems.lockout_grid", objectType: "bv" },
  { key: "spotmarket_lockout_bv", channelId: "ems.lockout_spotmarket", objectType: "bv" },
];

const SETUP_SUPPORTED_TYPES = new Set(["ai", "av", "bv"]);
/* Lastdisziplin (BACNET_STACK_EVAL): Punkte nacheinander mit Pause lesen. */
const SETUP_TEST_PAUSE_MS = 350;

const setupState = {
  loaded: false,
  loadFailed: false,
  siteConfig: null,
  saveEnabled: false,
  readOnly: false,
  devices: [],
  rows: [],
  filters: { status: "alle", group: "alle", sort: "gruppe" },
  test: { running: false, abort: false, summary: null, summaryTone: "neutral" },
  preview: { valid: null, message: null, tone: "neutral", patch: null },
  activation: { done: false },
};

/* ---------- Zustandsableitung (rein, ohne DOM) ---------- */

function setupChannelLabel(channelId) {
  const meta = CUSTOMER_CHANNEL_LABELS.get(channelId);
  return (meta && meta.label) || "Datenpunkt";
}

function setupObjectTypeLabel(objectType) {
  return String(objectType || "").toUpperCase() || "-";
}

function setupToInt(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.round(number) : fallback;
}

function setupOptionalNumber(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

/* Aktive Konfiguration -> Geräte und Mapping-Zeilen (Vorbelegung der Tabelle). */
function buildSetupFromSiteConfig(config) {
  const safe = config && typeof config === "object" ? config : {};
  const network = safe.network && typeof safe.network === "object" ? safe.network : {};
  const host = typeof network.controller_ip === "string" ? network.controller_ip : "";
  const port = setupToInt(network.controller_port, 47808);
  const devices = [{ id: "anlage", name: "Anlagensteuerung", host, port, origin: "active" }];
  const deviceByTarget = new Map([[`${host}:${port}`, "anlage"]]);
  const rows = [];

  const points = safe.points && typeof safe.points === "object" ? safe.points : {};
  SETUP_CORE_POINTS.forEach((core) => {
    const instance = setupOptionalNumber(points[core.key]);
    if (instance === null) {
      return;
    }
    rows.push(makeSetupRow({
      id: `aktiv:${core.channelId}`,
      deviceId: "anlage",
      protocol: "bacnet",
      objectType: core.objectType,
      instance,
      name: setupChannelLabel(core.channelId),
      access: SETUP_CHANNEL_ACCESS[core.channelId],
      channelId: core.channelId,
      origin: "active",
      sourceLabel: "Aktive Konfiguration",
    }));
  });

  const inputs = Array.isArray(safe.additional_inputs) ? safe.additional_inputs : [];
  inputs.forEach((input) => {
    if (!input || typeof input !== "object" || typeof input.channel_id !== "string") {
      return;
    }
    const protocol = protocolValue(input.protocol);
    let deviceId = "anlage";
    if (protocol === "bacnet" && typeof input.controller_ip === "string" && input.controller_ip.trim()) {
      const targetHost = input.controller_ip.trim();
      const targetPort = setupToInt(input.controller_port, port);
      const key = `${targetHost}:${targetPort}`;
      if (!deviceByTarget.has(key)) {
        const id = `geraet_${devices.length + 1}`;
        devices.push({ id, name: `Weiteres Gerät (${targetHost})`, host: targetHost, port: targetPort, origin: "active" });
        deviceByTarget.set(key, id);
      }
      deviceId = deviceByTarget.get(key);
    }
    rows.push(makeSetupRow({
      id: `aktiv:${input.channel_id}`,
      deviceId,
      protocol,
      objectType: protocol === "bacnet" ? bacnetObjectTypeValue(input.object_type) : String(input.protocol || ""),
      instance: setupOptionalNumber(input.instance) ?? "",
      name: setupTextOr(input.description, setupChannelLabel(input.channel_id)),
      access: "read",
      channelId: input.channel_id,
      origin: "active",
      sourceLabel: "Aktive Konfiguration",
      plausibleMin: setupOptionalNumber(input.plausible_min),
      plausibleMax: setupOptionalNumber(input.plausible_max),
      maxAgeSeconds: setupOptionalNumber(input.max_age_seconds),
      readIntervalCycles: setupToInt(input.read_interval_cycles, 1),
      includeInHealth: input.include_in_health === true,
    }));
  });

  return { devices, rows };
}

function setupTextOr(value, fallback) {
  const text = value === null || value === undefined ? "" : String(value).trim();
  return text || fallback;
}

function makeSetupRow(fields) {
  const protocol = fields.protocol || "bacnet";
  const objectType = fields.objectType || "";
  return {
    id: String(fields.id),
    deviceId: fields.deviceId || "anlage",
    protocol,
    objectType,
    instance: fields.instance === undefined ? "" : fields.instance,
    name: fields.name || "Datenpunkt",
    unit: fields.unit || "",
    access: fields.access || "read",
    channelId: fields.channelId || "",
    origin: fields.origin || "import",
    sourceLabel: fields.sourceLabel || "",
    comment: fields.comment || "",
    listValue: fields.listValue ?? null,
    plausibleMin: fields.plausibleMin ?? null,
    plausibleMax: fields.plausibleMax ?? null,
    maxAgeSeconds: fields.maxAgeSeconds ?? null,
    readIntervalCycles: fields.readIntervalCycles || 1,
    includeInHealth: fields.includeInHealth === true,
    supported: protocol === "bacnet" && SETUP_SUPPORTED_TYPES.has(objectType),
    test: null,
    detailsOpen: false,
  };
}

/* Import-/Discovery-Antwort -> neue Geräte und Kandidaten-Zeilen. */
function importResultToSetup(payload, existingRowIds, existingDeviceIds) {
  const safe = payload && typeof payload === "object" ? payload : {};
  const devices = [];
  (Array.isArray(safe.devices) ? safe.devices : []).forEach((device) => {
    if (!device || typeof device.id !== "string" || existingDeviceIds.has(device.id)) {
      return;
    }
    devices.push({
      id: device.id,
      name: setupTextOr(device.name, device.id),
      host: setupTextOr(device.host, ""),
      port: setupToInt(device.port, 47808),
      origin: "import",
    });
  });

  const suggestions = new Map();
  (Array.isArray(safe.suggested_mappings) ? safe.suggested_mappings : []).forEach((mapping) => {
    if (mapping && typeof mapping.channel_id === "string" && typeof mapping.source_point_id === "string"
      && CUSTOMER_CHANNEL_LABELS.has(mapping.channel_id)) {
      suggestions.set(mapping.source_point_id, mapping.channel_id);
    }
  });

  const rows = [];
  const candidates = Array.isArray(safe.candidates) ? safe.candidates : [];
  candidates.forEach((candidate) => {
    if (!candidate || typeof candidate.id !== "string" || existingRowIds.has(candidate.id)) {
      return;
    }
    const source = candidate.source && typeof candidate.source === "object" ? candidate.source : {};
    const sourceParts = [setupTextOr(source.filename, "Import")];
    if (Number.isFinite(Number(source.row))) {
      sourceParts.push(`Zeile ${Number(source.row)}`);
    }
    const row = makeSetupRow({
      id: candidate.id,
      deviceId: setupTextOr(candidate.device_id, ""),
      protocol: "bacnet",
      objectType: String(candidate.object_type || "").toLowerCase(),
      instance: setupOptionalNumber(candidate.instance) ?? "",
      name: setupTextOr(candidate.name, "Datenpunkt"),
      unit: setupTextOr(candidate.unit, ""),
      access: ["read", "write", "readwrite"].includes(candidate.access) ? candidate.access : "read",
      channelId: suggestions.get(candidate.id) || "",
      origin: "import",
      sourceLabel: sourceParts.join(" · "),
      comment: setupTextOr(source.comment, ""),
      listValue: setupOptionalNumber(candidate.value),
    });
    if (row.channelId) {
      applySetupChannelDefaults(row);
    }
    rows.push(row);
  });

  return {
    devices,
    rows,
    errors: Array.isArray(safe.errors) ? safe.errors.map(String) : [],
    warnings: Array.isArray(safe.warnings) ? safe.warnings.map(String) : [],
    valid: safe.valid === true,
  };
}

/* Beim Zuordnen sinnvolle Plausibilitäts-/Aktualitätswerte vorbelegen. */
function applySetupChannelDefaults(row) {
  const defaults = CONFIG_CHANNEL_DEFAULTS.find((entry) => entry.channel_id === row.channelId);
  if (!defaults) {
    return;
  }
  if (row.plausibleMin === null && defaults.plausible_min !== "") {
    row.plausibleMin = setupOptionalNumber(defaults.plausible_min);
  }
  if (row.plausibleMax === null && defaults.plausible_max !== "") {
    row.plausibleMax = setupOptionalNumber(defaults.plausible_max);
  }
  if (row.maxAgeSeconds === null) {
    row.maxAgeSeconds = setupOptionalNumber(defaults.max_age_seconds);
  }
}

function setupEffectiveAccess(row) {
  if (row.channelId && SETUP_CHANNEL_ACCESS[row.channelId]) {
    return SETUP_CHANNEL_ACCESS[row.channelId];
  }
  if (row.channelId) {
    return "read";
  }
  return row.access || "read";
}

function setupRowStatus(row) {
  if (setupEffectiveAccess(row) === "write") {
    return "write";
  }
  if (row.test) {
    if (row.test.tone === "ok") {
      return "tested";
    }
    if (row.test.tone === "alert") {
      return "failed";
    }
    return "review";
  }
  if (!row.supported) {
    return "review";
  }
  return row.channelId ? "assigned" : "review";
}

function setupRowGroup(row) {
  if (row.channelId) {
    const meta = CUSTOMER_CHANNEL_LABELS.get(row.channelId);
    return (meta && meta.group) || "EMS";
  }
  return "Nicht zugeordnet";
}

function setupCounts(rows) {
  const counts = { found: rows.length, assigned: 0, review: 0, write: 0, tested: 0, failed: 0, testable: 0 };
  rows.forEach((row) => {
    const status = setupRowStatus(row);
    if (status === "write") {
      counts.write += 1;
    } else if (status === "tested") {
      counts.tested += 1;
    } else if (status === "failed") {
      counts.failed += 1;
    } else if (status === "assigned") {
      counts.assigned += 1;
    } else {
      counts.review += 1;
    }
    if (row.channelId && setupEffectiveAccess(row) !== "write") {
      counts.testable += 1;
    }
  });
  return counts;
}

/* Zuordnung als Mapping-Entwurf für Vorschau/Aktivierung; problems = verständliche Hürden. */
function buildSetupMappingDraft(devices, rows) {
  const problems = [];
  const assigned = rows.filter((row) => row.channelId && row.supported);
  if (!assigned.length) {
    problems.push("Noch kein Datenpunkt zugeordnet. Bitte in der Tabelle mindestens einem Punkt eine Bedeutung geben.");
  }
  const channelCounts = new Map();
  assigned.forEach((row) => {
    channelCounts.set(row.channelId, (channelCounts.get(row.channelId) || 0) + 1);
  });
  channelCounts.forEach((count, channelId) => {
    if (count > 1) {
      problems.push(`„${setupChannelLabel(channelId)}“ ist mehrfach zugeordnet. Bitte nur einen Punkt je Bedeutung wählen.`);
    }
  });
  const usedDeviceIds = new Set(assigned.map((row) => row.deviceId));
  const draftDevices = devices.filter((device) => usedDeviceIds.has(device.id));
  draftDevices.forEach((device) => {
    if (!String(device.host || "").trim()) {
      problems.push(`Für „${device.name}“ fehlt die Geräteadresse. Bitte im Schritt Geräte ergänzen.`);
    }
  });
  assigned.forEach((row) => {
    if (setupOptionalNumber(row.instance) === null) {
      problems.push(`Für „${setupChannelLabel(row.channelId)}“ fehlt die Adresse (Instanz) im Technikbereich.`);
    }
  });

  const draft = {
    devices: draftDevices.map((device) => ({
      id: device.id,
      name: device.name,
      protocol: "bacnet",
      host: String(device.host || "").trim(),
      port: setupToInt(device.port, 47808),
    })),
    raw_points: assigned.map((row) => ({
      id: row.id,
      device_id: row.deviceId,
      object_type: row.objectType,
      instance: setupToInt(row.instance, 0),
      name: row.name,
      unit: row.unit || "",
    })),
    mappings: assigned.map((row) => {
      const entry = {
        channel_id: row.channelId,
        source_point_id: row.id,
        label: setupChannelLabel(row.channelId),
        access: setupEffectiveAccess(row),
        read_interval_cycles: setupToInt(row.readIntervalCycles, 1),
        include_in_health: row.includeInHealth === true,
      };
      if (row.plausibleMin !== null) {
        entry.plausible_min = row.plausibleMin;
      }
      if (row.plausibleMax !== null) {
        entry.plausible_max = row.plausibleMax;
      }
      if (row.maxAgeSeconds !== null) {
        entry.max_age_seconds = row.maxAgeSeconds;
      }
      return entry;
    }),
  };
  return { draft, problems };
}

/* Welche Kanäle kann die laufende Anlage jetzt schon live lesen? */
function setupActiveChannelInfo(config) {
  const info = new Map();
  const safe = config && typeof config === "object" ? config : {};
  const points = safe.points && typeof safe.points === "object" ? safe.points : {};
  SETUP_CORE_POINTS.forEach((core) => {
    const instance = setupOptionalNumber(points[core.key]);
    if (instance !== null && SETUP_CHANNEL_ACCESS[core.channelId] !== "write") {
      info.set(core.channelId, { instance });
    }
  });
  (Array.isArray(safe.additional_inputs) ? safe.additional_inputs : []).forEach((input) => {
    if (input && typeof input === "object" && typeof input.channel_id === "string") {
      info.set(input.channel_id, { instance: setupOptionalNumber(input.instance) });
    }
  });
  return info;
}

/* Live-Read-Ergebnis in Inbetriebnahme-Sprache übersetzen (UX16). */
function translateSetupDiagnostic(row, payload) {
  const safe = payload && typeof payload === "object" ? payload : {};
  const value = toNumber(safe.value);
  const meta = row.channelId ? CUSTOMER_CHANNEL_LABELS.get(row.channelId) : null;
  const unit = row.unit || (meta && meta.unit) || "";
  const valueLabel = Number.isFinite(value) ? formatNumber(value, unit, 2) : "";
  const status = String(safe.status || "").toLowerCase();
  const errorText = String(safe.error || "");

  if (!Number.isFinite(value) || status === "error") {
    return { tone: "alert", text: "Keine Antwort von der Anlage. Bitte Adresse und Verbindung prüfen.", valueLabel: "" };
  }
  const min = row.plausibleMin;
  const max = row.plausibleMax;
  const outOfRange = (min !== null && value < min) || (max !== null && value > max);
  if (safe.plausible === false || errorText.includes("value_out_of_range") || outOfRange) {
    return { tone: "warn", text: "Wert kommt an, aber bitte Einheit und erwarteten Bereich prüfen.", valueLabel };
  }
  if (String(safe.quality || "").toLowerCase() === "stale" || errorText.includes("value_stale")) {
    return { tone: "warn", text: "Wert kommt an, ist aber veraltet. Bitte die Aktualität der Quelle prüfen.", valueLabel };
  }
  if (status === "warning") {
    return { tone: "warn", text: "Wert kommt an, aber nicht alle Einzelmessungen kamen an.", valueLabel };
  }
  const hasRange = min !== null || max !== null;
  return {
    tone: "ok",
    text: hasRange ? "Wert kommt an und liegt im erwarteten Bereich." : "Wert kommt an.",
    valueLabel,
  };
}

function translateSetupReadFailure(httpStatus, message) {
  if (httpStatus === 403) {
    return { tone: "warn", text: "Test über den Netzwerkzugriff nicht möglich. Prüfung nur lokal bzw. administrativ an der Anlage.", valueLabel: "" };
  }
  if (String(message || "").includes("Unknown channel_id")) {
    return { tone: "warn", text: "Noch nicht aktiv. Dieser Punkt ist nach Aktivierung und Neustart prüfbar.", valueLabel: "" };
  }
  return { tone: "alert", text: "Keine Antwort von der Anlage. Bitte Adresse und Verbindung prüfen.", valueLabel: "" };
}

/* Schrittzustände für den Fortschrittsbalken (UX14). */
function computeSetupSteps(state) {
  const counts = setupCounts(state.rows);
  const steps = [];

  let standort = { state: "open", detail: "Konfiguration wird geladen." };
  if (state.loaded) {
    const runtime = state.siteConfig && state.siteConfig.runtime ? state.siteConfig.runtime : {};
    standort = { state: "done", detail: setupEnvironmentLabel(runtime.environment) };
  } else if (state.loadFailed) {
    standort = { state: "error", detail: "Konfiguration nicht erreichbar." };
  }
  steps.push({ id: "standort", label: "Standort", ...standort });

  const usedDeviceIds = new Set(state.rows.filter((row) => row.channelId && row.supported).map((row) => row.deviceId));
  const usedDevices = state.devices.filter((device) => usedDeviceIds.has(device.id));
  const missingHost = usedDevices.filter((device) => !String(device.host || "").trim());
  if (missingHost.length) {
    steps.push({ id: "geraete", label: "Geräte", state: "error", detail: `Adresse fehlt: ${missingHost[0].name}` });
  } else if (usedDevices.length) {
    steps.push({ id: "geraete", label: "Geräte", state: "done", detail: usedDevices.length === 1 ? "1 Gerät" : `${usedDevices.length} Geräte` });
  } else {
    steps.push({ id: "geraete", label: "Geräte", state: "open", detail: "Noch kein Gerät in Verwendung." });
  }

  const openPoints = counts.review;
  if (!counts.found) {
    steps.push({ id: "punkte", label: "Datenpunkte", state: "open", detail: "Punktliste hochladen." });
  } else if (openPoints === 0 && counts.assigned + counts.write + counts.tested + counts.failed > 0) {
    steps.push({ id: "punkte", label: "Datenpunkte", state: "done", detail: `${counts.found} Punkte zugeordnet.` });
  } else {
    steps.push({ id: "punkte", label: "Datenpunkte", state: "open", detail: `${openPoints} von ${counts.found} zu prüfen.` });
  }

  if (state.readOnly) {
    steps.push({ id: "testen", label: "Testen", state: "locked", detail: "Nur lokal/administrativ möglich." });
  } else if (counts.failed) {
    steps.push({ id: "testen", label: "Testen", state: "error", detail: `${counts.failed} ohne Antwort.` });
  } else if (counts.testable && counts.tested >= counts.testable) {
    steps.push({ id: "testen", label: "Testen", state: "done", detail: `${counts.tested} Punkte geprüft.` });
  } else if (counts.tested) {
    steps.push({ id: "testen", label: "Testen", state: "open", detail: `${counts.tested} von ${counts.testable} geprüft.` });
  } else {
    steps.push({ id: "testen", label: "Testen", state: "open", detail: "Noch nicht geprüft." });
  }

  if (state.activation.done) {
    steps.push({ id: "aktivieren", label: "Aktivieren", state: "done", detail: "Aktiviert, Neustart erforderlich." });
  } else if (state.readOnly) {
    steps.push({ id: "aktivieren", label: "Aktivieren", state: "locked", detail: "Nur lokal/administrativ möglich." });
  } else if (state.loaded && !state.saveEnabled) {
    steps.push({ id: "aktivieren", label: "Aktivieren", state: "locked", detail: "Kein Admin-Token auf der Anlage eingerichtet." });
  } else if (state.preview.valid === true) {
    steps.push({ id: "aktivieren", label: "Aktivieren", state: "open", detail: "Geprüft, bereit zur Aktivierung." });
  } else if (state.preview.valid === false) {
    steps.push({ id: "aktivieren", label: "Aktivieren", state: "error", detail: "Prüfung meldet Fehler." });
  } else {
    steps.push({ id: "aktivieren", label: "Aktivieren", state: "open", detail: "Zuordnung noch nicht geprüft." });
  }

  return steps;
}

function setupEnvironmentLabel(environment) {
  const labels = { local: "Laptop-Simulation", ipc: "Produktiver IPC", test: "Testumgebung" };
  return labels[String(environment || "").toLowerCase()] || "Betriebsumgebung unbekannt";
}

/* Hauptbotschaft der Seite: "Ist dieser Standort bereit?" (UX14). */
function buildSetupHeroMessage(steps, counts, state) {
  if (state.readOnly) {
    return {
      level: "warn",
      headline: "Nur-Lese-Zugriff: Inbetriebnahme hier nicht möglich.",
      detail: "Ansehen ist möglich. Datenpunkte ändern, testen und aktivieren geht nur über den lokalen bzw. administrativen Zugriff auf der Anlage.",
    };
  }
  if (state.activation.done) {
    return {
      level: "ok",
      headline: "Zuordnung aktiviert. Ein Neustart der Steuerung ist erforderlich.",
      detail: "Nach dem Neustart liest die Anlage die neue Zuordnung. Danach die Punkte erneut testen.",
    };
  }
  const doneCount = steps.filter((step) => step.state === "done").length;
  const errorStep = steps.find((step) => step.state === "error");
  const countsLine = `${counts.found} Datenpunkte gefunden · ${counts.assigned + counts.write + counts.tested + counts.failed} zugeordnet · ${counts.review} zu prüfen · ${doneCount} von ${steps.length} Schritten erledigt.`;
  if (errorStep) {
    return {
      level: "warn",
      headline: "Der Standort ist noch nicht bereit.",
      detail: `${countsLine} Bitte zuerst den Schritt „${errorStep.label}“ klären: ${errorStep.detail}`,
    };
  }
  if (doneCount === steps.length) {
    return {
      level: "ok",
      headline: "Dieser Standort ist bereit, gelesen und geregelt zu werden.",
      detail: countsLine,
    };
  }
  const nextStep = steps.find((step) => step.state !== "done");
  return {
    level: "neutral",
    headline: "Der Standort ist noch nicht vollständig eingerichtet.",
    detail: `${countsLine} Nächster Schritt: ${nextStep ? nextStep.label : "-"}.`,
  };
}

/* ---------- Laden und Zusammenführen ---------- */

function seedSetupFromSiteConfig(payload) {
  const safe = payload && typeof payload === "object" ? payload : {};
  setupState.siteConfig = safe.config && typeof safe.config === "object" ? safe.config : null;
  setupState.saveEnabled = safe.save_enabled === true;
  setupState.loaded = setupState.siteConfig !== null;
  setupState.loadFailed = !setupState.loaded;
  if (setupState.loaded) {
    const seeded = buildSetupFromSiteConfig(setupState.siteConfig);
    const importedDevices = setupState.devices.filter((device) => device.origin === "import");
    const importedRows = setupState.rows.filter((row) => row.origin !== "active");
    setupState.devices = [...seeded.devices, ...importedDevices];
    setupState.rows = [...seeded.rows, ...importedRows];
  }
  renderSetupPage();
}

function markSetupLoadFailed() {
  if (!setupState.loaded) {
    setupState.loadFailed = true;
    renderSetupPage();
  }
}

function syncSetupReadOnly(statusPayload) {
  const readOnly = statusPayload && statusPayload.api_read_only === true;
  if (readOnly !== setupState.readOnly) {
    setupState.readOnly = readOnly;
    renderSetupPage();
  }
}

function setupRowById(rowId) {
  return setupState.rows.find((row) => row.id === rowId) || null;
}

function setupMainDevice() {
  return setupState.devices.find((device) => device.id === "anlage") || setupState.devices[0] || { host: "", port: 47808 };
}

/* ---------- Import und Discovery ---------- */

async function handleSetupPointlistUpload(input) {
  const file = input.files && input.files[0];
  if (!file) {
    return;
  }
  setSetupImportFeedback(`Punktliste „${file.name}“ wird gelesen …`, "neutral");
  try {
    const contentBase64 = await setupFileToBase64(file);
    const mainDevice = setupMainDevice();
    const payload = await postJson("/api/config/pointlist/import", {
      filename: file.name,
      content_base64: contentBase64,
      default_device: { id: "punktliste", name: "Importiertes Gerät", host: mainDevice.host || "", port: mainDevice.port || 47808 },
    });
    applySetupImport(payload, `Punktliste „${file.name}“`);
  } catch (error) {
    setSetupImportFeedback(error.message, "warn");
  } finally {
    input.value = "";
  }
}

async function handleSetupDiscovery() {
  setSetupImportFeedback("Die Anlage wird durchsucht (nur lesend) …", "neutral");
  const mainDevice = setupMainDevice();
  try {
    const payload = await postJson("/api/config/discovery/bacnet/preview", {
      target_host: mainDevice.host || "",
      target_port: mainDevice.port || 47808,
    });
    applySetupImport(payload, "Discovery");
  } catch (error) {
    setSetupImportFeedback(error.message, "warn");
  }
}

function applySetupImport(payload, sourceName) {
  const merged = importResultToSetup(
    payload,
    new Set(setupState.rows.map((row) => row.id)),
    new Set(setupState.devices.map((device) => device.id)),
  );
  if (!merged.valid && !merged.rows.length) {
    setSetupImportFeedback(
      merged.errors.length ? merged.errors.join(" / ") : `${sourceName}: keine verwertbaren Datenpunkte gefunden.`,
      "warn",
    );
    renderSetupPage();
    return;
  }
  setupState.devices = [...setupState.devices, ...merged.devices];
  setupState.rows = [...setupState.rows, ...merged.rows];
  setupState.preview = { valid: null, message: null, tone: "neutral", patch: null };
  const assignedCount = merged.rows.filter((row) => row.channelId).length;
  const parts = [`${sourceName}: ${merged.rows.length} Punkte übernommen, ${assignedCount} davon bereits zugeordnet.`];
  if (merged.warnings.length) {
    const shown = merged.warnings.slice(0, 3).join(" / ");
    parts.push(merged.warnings.length > 3 ? `Hinweise: ${shown} (und ${merged.warnings.length - 3} weitere)` : `Hinweise: ${shown}`);
  }
  setSetupImportFeedback(parts.join(" "), merged.warnings.length ? "warn" : "ok");
  renderSetupPage();
}

function setupFileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Die Datei konnte nicht gelesen werden."));
    reader.onload = () => {
      const bytes = new Uint8Array(reader.result);
      let binary = "";
      const chunkSize = 0x8000;
      for (let index = 0; index < bytes.length; index += chunkSize) {
        binary += String.fromCharCode.apply(null, bytes.subarray(index, index + chunkSize));
      }
      resolve(btoa(binary));
    };
    reader.readAsArrayBuffer(file);
  });
}

/* ---------- Alle Punkte testen (UX16) ---------- */

async function runSetupTests() {
  if (setupState.test.running || setupState.readOnly) {
    return;
  }
  const activeInfo = setupActiveChannelInfo(setupState.siteConfig);
  const targets = [];
  setupState.rows.forEach((row) => {
    if (!row.channelId) {
      return;
    }
    if (setupEffectiveAccess(row) === "write") {
      row.test = { tone: "neutral", text: "Schreibpunkt erkannt. Freigabe erforderlich – wird beim Test nicht angesprochen.", valueLabel: "" };
      return;
    }
    targets.push(row);
  });
  if (!targets.length) {
    setSetupTestSummary("Kein Punkt ist testbar. Bitte zuerst Datenpunkte zuordnen.", "warn");
    renderSetupPage();
    return;
  }

  setupState.test.running = true;
  setupState.test.abort = false;
  setupState.test.summary = null;
  setSetupTestControls(true);
  let done = 0;
  const runTones = { ok: 0, warn: 0, alert: 0 };

  for (const row of targets) {
    if (setupState.test.abort) {
      break;
    }
    setSetupTestProgress(`Prüfe ${done + 1} von ${targets.length}: ${setupChannelLabel(row.channelId)}`);
    const info = activeInfo.get(row.channelId);
    if (!info) {
      row.test = { tone: "warn", text: "Noch nicht aktiv. Dieser Punkt ist nach Aktivierung und Neustart prüfbar.", valueLabel: "" };
    } else {
      const outcome = await fetchSetupDiagnostic(row.channelId);
      if (outcome.ok) {
        row.test = translateSetupDiagnostic(row, outcome.payload);
        const draftInstance = setupOptionalNumber(row.instance);
        if (info.instance !== null && draftInstance !== null && info.instance !== draftInstance) {
          row.test = {
            ...row.test,
            text: `${row.test.text} Getestet wurde die derzeit aktive Adresse; die geänderte Adresse gilt erst nach Aktivierung.`,
          };
        }
      } else {
        row.test = translateSetupReadFailure(outcome.status, outcome.message);
      }
    }
    if (row.test && runTones[row.test.tone] !== undefined) {
      runTones[row.test.tone] += 1;
    }
    done += 1;
    renderSetupTableAndSteps();
    if (done < targets.length && !setupState.test.abort) {
      await setupWait(SETUP_TEST_PAUSE_MS);
    }
  }

  const writeCount = setupCounts(setupState.rows).write;
  const aborted = setupState.test.abort && done < targets.length;
  const summaryParts = [
    aborted
      ? `Prüfung abgebrochen: ${done} von ${targets.length} Punkten geprüft.`
      : `Prüfung abgeschlossen: ${done} von ${targets.length} Punkten geprüft.`,
    `${runTones.ok} in Ordnung`,
    `${runTones.warn} bitte prüfen`,
    `${runTones.alert} ohne Antwort`,
  ];
  if (writeCount) {
    summaryParts.push(`${writeCount} Schreibpunkte übersprungen`);
  }
  const tone = !aborted && runTones.warn === 0 && runTones.alert === 0 ? "ok" : "warn";
  setupState.test.running = false;
  setupState.test.abort = false;
  setSetupTestControls(false);
  setSetupTestSummary(`${summaryParts[0]} ${summaryParts.slice(1).join(" · ")}.`, tone);
  renderSetupPage();
}

function setupWait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchSetupDiagnostic(channelId) {
  try {
    const query = new URLSearchParams({ channel_id: channelId, samples: "2" });
    const response = await fetch(`/api/diagnostics/read?${query.toString()}`, { cache: "no-store" });
    const text = await response.text();
    let payload = null;
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
    if (!response.ok) {
      return { ok: false, status: response.status, message: payload ? payload.message || payload.error || "" : text };
    }
    return { ok: true, payload };
  } catch (error) {
    return { ok: false, status: 0, message: error.message };
  }
}

/* ---------- Vorschau und Aktivierung ---------- */

async function runSetupPreview() {
  const { draft, problems } = buildSetupMappingDraft(setupState.devices, setupState.rows);
  if (problems.length) {
    setupState.preview = { valid: false, message: problems.join(" "), tone: "warn", patch: null };
    renderSetupPage();
    return null;
  }
  setSetupActivateFeedback("Zuordnung wird geprüft …", "neutral");
  try {
    const response = await postJson("/api/config/mapping/preview", draft);
    const errors = Array.isArray(response.errors) ? response.errors.map(String) : [];
    const warnings = Array.isArray(response.warnings) ? response.warnings.map(String) : [];
    if (response.valid === true) {
      setupState.preview = {
        valid: true,
        message: warnings.length
          ? `Geprüft mit Hinweisen: ${warnings.join(" / ")}`
          : "Die Zuordnung ist vollständig und in Ordnung. Sie kann mit Admin-Token aktiviert werden.",
        tone: warnings.length ? "warn" : "ok",
        patch: response.patch || null,
      };
    } else {
      setupState.preview = {
        valid: false,
        message: errors.length ? `Bitte prüfen: ${errors.join(" / ")}` : "Die Zuordnung wurde vom Backend abgelehnt.",
        tone: "warn",
        patch: null,
      };
    }
    if (setupHasNonBacnetActiveInputs()) {
      setupState.preview.message += " Hinweis: Punkte mit anderem Protokoll werden von dieser Aktivierung nicht übernommen und bleiben in der Direktbearbeitung.";
    }
    renderSetupPage();
    return setupState.preview.valid ? draft : null;
  } catch (error) {
    setupState.preview = { valid: false, message: error.message, tone: "warn", patch: null };
    renderSetupPage();
    return null;
  }
}

function setupHasNonBacnetActiveInputs() {
  return setupState.rows.some((row) => row.origin === "active" && row.protocol !== "bacnet");
}

async function runSetupActivation() {
  const tokenInput = document.getElementById("setup-activate-token");
  const token = tokenInput ? tokenInput.value.trim() : "";
  if (!token) {
    setSetupActivateFeedback("Bitte zuerst den Admin-Token eintragen. Ohne Token wird nichts aktiviert.", "warn");
    if (tokenInput) {
      tokenInput.focus();
    }
    return;
  }
  const { draft, problems } = buildSetupMappingDraft(setupState.devices, setupState.rows);
  if (problems.length) {
    setSetupActivateFeedback(problems.join(" "), "warn");
    return;
  }
  const button = document.getElementById("setup-activate-button");
  if (button) {
    button.disabled = true;
  }
  setSetupActivateFeedback("Zuordnung wird aktiviert …", "neutral");
  try {
    const response = await postJson("/api/config/mapping/activate", draft, { token });
    if (response.activated === true) {
      setupState.activation.done = true;
      const backup = response.backup_file ? ` Sicherung: ${response.backup_file}.` : "";
      setupState.preview = { valid: true, message: null, tone: "ok", patch: setupState.preview.patch };
      setSetupActivateFeedback(
        `Zuordnung aktiviert. Ein Neustart der Mini-EMS-Runtime ist erforderlich, damit die neuen Datenpunkte gelesen werden.${backup}`,
        "ok",
      );
    } else {
      const errors = Array.isArray(response.errors) ? response.errors.map(String) : [];
      setSetupActivateFeedback(errors.length ? `Bitte prüfen: ${errors.join(" / ")}` : "Die Aktivierung wurde abgelehnt.", "warn");
    }
  } catch (error) {
    setSetupActivateFeedback(error.message, "warn");
  } finally {
    if (button) {
      button.disabled = false;
    }
    renderSetupPage();
  }
}

/* ---------- Rendering ---------- */

function renderSetupPage() {
  if (!document.getElementById("setup-steps")) {
    return;
  }
  const steps = computeSetupSteps(setupState);
  const counts = setupCounts(setupState.rows);
  renderSetupHero(steps, counts);
  renderSetupSteps(steps);
  renderSetupStandort();
  renderSetupDevices();
  renderSetupGroupFilter();
  renderSetupTable();
  renderSetupCounts(counts);
  renderSetupActionAvailability();
  renderSetupActivateArea();
}

function renderSetupTableAndSteps() {
  const steps = computeSetupSteps(setupState);
  renderSetupSteps(steps);
  renderSetupHero(steps, setupCounts(setupState.rows));
  renderSetupTable();
}

function renderSetupHero(steps, counts) {
  const target = document.getElementById("setup-hero");
  if (!target) {
    return;
  }
  const message = buildSetupHeroMessage(steps, counts, setupState);
  target.className = `status-hero ${message.level}`;
  target.innerHTML = `
    <div class="status-hero-text">
      <strong>${escapeHtml(message.headline)}</strong>
      <p>${escapeHtml(message.detail)}</p>
    </div>
  `;
}

function renderSetupSteps(steps) {
  const target = document.getElementById("setup-steps");
  if (!target) {
    return;
  }
  const stateWords = { done: "erledigt", open: "offen", error: "bitte klären", locked: "gesperrt" };
  const stateClasses = { done: "done", open: "", error: "alert", locked: "warn" };
  target.innerHTML = steps.map((step, index) => `
    <li>
      <button type="button" class="setup-step ${stateClasses[step.state] || ""}" data-setup-step="${escapeHtml(step.id)}">
        <span class="micro-label">Schritt ${index + 1} · ${escapeHtml(stateWords[step.state] || "offen")}</span>
        <strong>${escapeHtml(step.label)}</strong>
        <small>${escapeHtml(step.detail)}</small>
      </button>
    </li>
  `).join("");
  target.querySelectorAll("button[data-setup-step]").forEach((button) => {
    button.addEventListener("click", () => {
      const panel = document.getElementById(`setup-panel-${button.dataset.setupStep}`);
      if (panel) {
        panel.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });
}

function renderSetupStandort() {
  const target = document.getElementById("setup-standort-summary");
  if (!target) {
    return;
  }
  if (!setupState.loaded) {
    target.innerHTML = `<div class="empty-state compact">${escapeHtml(setupState.loadFailed
      ? "Die aktive Konfiguration ist nicht erreichbar. Bitte die Verbindung zur Anlage prüfen."
      : "Die aktive Konfiguration wird geladen.")}</div>`;
    return;
  }
  const config = setupState.siteConfig || {};
  const runtime = config.runtime || {};
  const network = config.network || {};
  const api = config.api || {};
  const modeLabels = { simulated: "Simulation ohne echte Schreibfreigabe", real: "Produktive Anlagenkommunikation" };
  target.innerHTML = [
    reportTile("Betriebsumgebung", setupEnvironmentLabel(runtime.environment)),
    reportTile("Anlagenkommunikation", modeLabels[String(runtime.bacnet_mode || "").toLowerCase()] || "-"),
    reportTile("Zielgerät Anlage", network.controller_ip ? `${network.controller_ip}:${network.controller_port ?? ""}` : "-"),
    reportTile("Dashboard/API", api.host ? `${api.host}:${api.port ?? ""}` : "-"),
  ].join("");
}

function renderSetupDevices() {
  const target = document.getElementById("setup-device-list");
  if (!target) {
    return;
  }
  if (!setupState.devices.length) {
    target.innerHTML = '<div class="empty-state compact">Noch keine Geräte bekannt. Die Geräte erscheinen mit der aktiven Konfiguration oder einem Punktlisten-Import.</div>';
    return;
  }
  const originLabels = { active: "aktive Konfiguration", import: "aus Punktliste/Discovery" };
  target.innerHTML = setupState.devices.map((device) => {
    const pointCount = setupState.rows.filter((row) => row.deviceId === device.id).length;
    return `
      <div class="config-channel-row" data-setup-device="${escapeHtml(device.id)}">
        <div class="setup-device-head">
          <strong>${escapeHtml(device.name)}</strong>
          <small>${escapeHtml(originLabels[device.origin] || "Gerät")} · ${pointCount === 1 ? "1 Datenpunkt" : `${pointCount} Datenpunkte`}</small>
        </div>
        <div class="config-point-fields setup-device-fields">
          <label>
            Geräteadresse (IP)
            <input type="text" data-setup-device-field="host" value="${escapeHtml(inputValue(device.host))}" placeholder="z. B. 192.168.244.20" ${setupState.readOnly ? "disabled" : ""}>
          </label>
          <label>
            Port
            <input type="number" min="1" max="65535" data-setup-device-field="port" value="${escapeHtml(inputValue(device.port))}" ${setupState.readOnly ? "disabled" : ""}>
          </label>
        </div>
      </div>
    `;
  }).join("");
  target.querySelectorAll("[data-setup-device-field]").forEach((input) => {
    input.addEventListener("change", () => {
      const deviceId = input.closest("[data-setup-device]")?.dataset.setupDevice;
      const device = setupState.devices.find((entry) => entry.id === deviceId);
      if (!device) {
        return;
      }
      if (input.dataset.setupDeviceField === "host") {
        device.host = input.value.trim();
      } else {
        device.port = setupToInt(input.value, 47808);
      }
      setupState.preview = { valid: null, message: null, tone: "neutral", patch: null };
      renderSetupTableAndSteps();
      renderSetupActivateArea();
    });
  });
}

function renderSetupGroupFilter() {
  const select = document.getElementById("setup-group-filter");
  if (!select) {
    return;
  }
  const groups = [...new Set(setupState.rows.map((row) => setupRowGroup(row)))].sort((a, b) => a.localeCompare(b, "de"));
  const current = setupState.filters.group;
  select.innerHTML = ['<option value="alle">Alle Gruppen</option>', ...groups.map((group) => `<option value="${escapeHtml(group)}">${escapeHtml(group)}</option>`)].join("");
  select.value = groups.includes(current) ? current : "alle";
  setupState.filters.group = select.value;
}

function setupFilteredRows() {
  const { status, group, sort } = setupState.filters;
  const statusOrder = { failed: 0, review: 1, assigned: 2, write: 3, tested: 4 };
  const rows = setupState.rows.filter((row) => {
    const rowStatus = setupRowStatus(row);
    if (status !== "alle" && rowStatus !== status) {
      return false;
    }
    if (group !== "alle" && setupRowGroup(row) !== group) {
      return false;
    }
    return true;
  });
  const label = (row) => (row.channelId ? setupChannelLabel(row.channelId) : row.name);
  rows.sort((a, b) => {
    if (sort === "status") {
      const order = (statusOrder[setupRowStatus(a)] ?? 9) - (statusOrder[setupRowStatus(b)] ?? 9);
      return order || label(a).localeCompare(label(b), "de");
    }
    if (sort === "name") {
      return label(a).localeCompare(label(b), "de");
    }
    const groupOrder = setupRowGroup(a).localeCompare(setupRowGroup(b), "de");
    return groupOrder || label(a).localeCompare(label(b), "de");
  });
  return rows;
}

function setupDeviceName(deviceId) {
  const device = setupState.devices.find((entry) => entry.id === deviceId);
  return device ? device.name : "Gerät";
}

function setupChannelOptionsHtml(row) {
  const assignedElsewhere = new Map();
  setupState.rows.forEach((other) => {
    if (other.id !== row.id && other.channelId) {
      assignedElsewhere.set(other.channelId, true);
    }
  });
  const byGroup = groupBy(DEFAULT_CHANNELS, (channel) => channel.group || "EMS");
  const groupsHtml = [...byGroup.entries()].map(([group, channels]) => `
    <optgroup label="${escapeHtml(group)}">
      ${channels.map((channel) => {
        const taken = assignedElsewhere.has(channel.id) ? " · bereits zugeordnet" : "";
        return `<option value="${escapeHtml(channel.id)}" ${channel.id === row.channelId ? "selected" : ""}>${escapeHtml(channel.label + taken)}</option>`;
      }).join("")}
    </optgroup>
  `).join("");
  return `<option value="">Nicht zugeordnet</option>${groupsHtml}`;
}

function renderSetupTable() {
  const body = document.getElementById("setup-mapping-body");
  if (!body) {
    return;
  }
  const rows = setupFilteredRows();
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="6"><div class="empty-state compact">${escapeHtml(setupState.rows.length
      ? "Kein Datenpunkt passt zu diesem Filter. Filter oben zurücksetzen."
      : "Noch keine Datenpunkte. Punktliste hochladen oder die Anlage durchsuchen.")}</div></td></tr>`;
    return;
  }
  body.innerHTML = rows.map((row) => {
    const status = setupRowStatus(row);
    const badgeClass = SETUP_STATUS_BADGE[status];
    const mainLabel = row.channelId ? setupChannelLabel(row.channelId) : row.name;
    const subLabel = row.channelId && row.name !== mainLabel ? row.name : setupRowGroup(row);
    const address = `${setupObjectTypeLabel(row.objectType)} ${inputValue(row.instance) === "" ? "-" : row.instance}`;
    const sourceParts = [setupDeviceName(row.deviceId), address];
    if (row.test && row.test.valueLabel) {
      sourceParts.push(row.test.valueLabel);
    } else if (row.listValue !== null) {
      sourceParts.push(`${formatNumber(row.listValue, row.unit, 2)} laut Liste`);
    }
    const resultTone = row.test ? row.test.tone : "";
    const selectDisabled = !row.supported || setupState.readOnly ? "disabled" : "";
    return `
      <tr class="mapping-row" data-setup-row="${escapeHtml(row.id)}">
        <td class="mapping-main">
          <strong>${escapeHtml(mainLabel)}</strong>
          <small>${escapeHtml(subLabel)}</small>
        </td>
        <td class="mapping-assign">
          <select data-setup-assign aria-label="Bedeutung für ${escapeHtml(row.name)} wählen" ${selectDisabled}>
            ${setupChannelOptionsHtml(row)}
          </select>
          ${row.supported ? "" : '<small class="mapping-unsupported">Dieser Punkttyp ist noch nicht aktivierbar.</small>'}
        </td>
        <td class="mapping-source">${escapeHtml(sourceParts.join(" · "))}</td>
        <td><span class="badge ${badgeClass}">${escapeHtml(SETUP_STATUS_WORDS[status])}</span></td>
        <td class="mapping-result ${escapeHtml(resultTone)}">${escapeHtml(row.test ? row.test.text : "–")}</td>
        <td class="mapping-detail-toggle">
          <button type="button" class="link-button" data-setup-details aria-expanded="${row.detailsOpen ? "true" : "false"}">Technik</button>
        </td>
      </tr>
      <tr class="mapping-detail-row" data-setup-detail="${escapeHtml(row.id)}" ${row.detailsOpen ? "" : "hidden"}>
        <td colspan="6">
          ${setupDetailHtml(row)}
        </td>
      </tr>
    `;
  }).join("");
  bindSetupTableEvents(body);
}

function setupDetailHtml(row) {
  if (row.protocol !== "bacnet") {
    return `<p class="config-note">Dieser Punkt wird über ein anderes Protokoll gelesen (${escapeHtml(protocolLabel(row.protocol))}). Änderungen bitte über die Direktbearbeitung unten.</p>`;
  }
  const disabled = setupState.readOnly ? "disabled" : "";
  return `
    <div class="config-point-fields mapping-detail-grid">
      <label>
        Objekttyp
        <select data-setup-field="objectType" ${row.supported ? disabled : "disabled"}>
          <option value="ai" ${selectedAttribute(row.objectType === "ai")}>AI Messwert</option>
          <option value="av" ${selectedAttribute(row.objectType === "av")}>AV Wert</option>
          <option value="bv" ${selectedAttribute(row.objectType === "bv")}>BV Status</option>
          ${SETUP_SUPPORTED_TYPES.has(row.objectType) ? "" : `<option value="${escapeHtml(row.objectType)}" selected>${escapeHtml(setupObjectTypeLabel(row.objectType))}</option>`}
        </select>
      </label>
      <label>
        Adresse / Instanz
        <input type="number" min="0" data-setup-field="instance" value="${escapeHtml(inputValue(row.instance))}" ${disabled}>
      </label>
      <label>
        Einheit
        <input type="text" data-setup-field="unit" value="${escapeHtml(inputValue(row.unit))}" placeholder="z. B. kW" ${disabled}>
      </label>
      <label>
        Plausibel von
        <input type="number" step="0.1" data-setup-field="plausibleMin" value="${escapeHtml(inputValue(row.plausibleMin))}" ${disabled}>
      </label>
      <label>
        Plausibel bis
        <input type="number" step="0.1" data-setup-field="plausibleMax" value="${escapeHtml(inputValue(row.plausibleMax))}" ${disabled}>
      </label>
      <label>
        Max. Alter (s)
        <input type="number" min="1" data-setup-field="maxAgeSeconds" value="${escapeHtml(inputValue(row.maxAgeSeconds))}" ${disabled}>
      </label>
      <label>
        Abfrageintervall
        <input type="number" min="1" data-setup-field="readIntervalCycles" value="${escapeHtml(inputValue(row.readIntervalCycles))}" ${disabled}>
      </label>
      <label class="check config-check config-point-health">
        <input type="checkbox" data-setup-field="includeInHealth" ${checkedAttribute(row.includeInHealth)} ${disabled}>
        <span>Im Status überwachen</span>
      </label>
    </div>
    <p class="config-note">Quelle: ${escapeHtml(row.sourceLabel || "-")}${row.comment ? ` · ${escapeHtml(row.comment)}` : ""} · Bezeichnung laut Liste: ${escapeHtml(row.name)}</p>
  `;
}

function bindSetupTableEvents(body) {
  body.querySelectorAll("button[data-setup-details]").forEach((button) => {
    button.addEventListener("click", () => {
      const row = setupRowById(button.closest("[data-setup-row]")?.dataset.setupRow);
      if (row) {
        row.detailsOpen = !row.detailsOpen;
        renderSetupTable();
      }
    });
  });
  body.querySelectorAll("select[data-setup-assign]").forEach((select) => {
    select.addEventListener("change", () => {
      const row = setupRowById(select.closest("[data-setup-row]")?.dataset.setupRow);
      if (!row) {
        return;
      }
      row.channelId = select.value;
      row.test = null;
      if (row.channelId) {
        applySetupChannelDefaults(row);
      }
      setupState.preview = { valid: null, message: null, tone: "neutral", patch: null };
      renderSetupPage();
    });
  });
  body.querySelectorAll("[data-setup-field]").forEach((input) => {
    input.addEventListener("change", () => {
      const row = setupRowById(input.closest("[data-setup-detail]")?.dataset.setupDetail);
      if (!row) {
        return;
      }
      const field = input.dataset.setupField;
      if (field === "includeInHealth") {
        row.includeInHealth = input.checked === true;
      } else if (field === "objectType") {
        row.objectType = bacnetObjectTypeValue(input.value);
        row.supported = SETUP_SUPPORTED_TYPES.has(row.objectType);
      } else if (field === "unit") {
        row.unit = input.value.trim();
      } else if (field === "instance") {
        row.instance = setupOptionalNumber(input.value) ?? "";
      } else if (field === "readIntervalCycles") {
        row.readIntervalCycles = setupToInt(input.value, 1);
      } else {
        row[field] = setupOptionalNumber(input.value);
      }
      row.test = null;
      setupState.preview = { valid: null, message: null, tone: "neutral", patch: null };
      renderSetupPage();
    });
  });
}

function renderSetupCounts(counts) {
  const target = document.getElementById("setup-mapping-count");
  if (!target) {
    return;
  }
  const assignedTotal = counts.assigned + counts.write + counts.tested + counts.failed;
  target.textContent = `${counts.found} Datenpunkte · ${assignedTotal} zugeordnet · ${counts.review} zu prüfen · ${counts.write} Schreibpunkte · ${counts.tested} geprüft`;
}

function renderSetupActionAvailability() {
  const readOnly = setupState.readOnly;
  const fileButton = document.querySelector(".setup-file-button");
  if (fileButton) {
    fileButton.hidden = readOnly;
  }
  ["setup-discovery-button", "setup-test-button", "setup-preview-button", "setup-activate-button"].forEach((id) => {
    const element = document.getElementById(id);
    if (element) {
      element.hidden = readOnly;
    }
  });
  const tokenField = document.getElementById("setup-activate-token");
  if (tokenField) {
    tokenField.closest(".token-field").hidden = readOnly;
  }
  if (!setupState.test.running) {
    const summary = document.getElementById("setup-test-summary");
    if (summary && setupState.test.summary) {
      summary.className = `config-feedback ${setupState.test.summaryTone}`;
      summary.textContent = setupState.test.summary;
    }
  }
}

function renderSetupActivateArea() {
  const feedback = document.getElementById("setup-activate-feedback");
  if (feedback && !setupState.test.running) {
    if (setupState.preview.message) {
      feedback.className = `config-feedback ${setupState.preview.tone}`;
      feedback.textContent = setupState.preview.message;
    } else if (setupState.readOnly) {
      feedback.className = "config-feedback warn";
      feedback.textContent = "Nur-Lese-Zugriff: Aktivierung ist nur lokal bzw. administrativ an der Anlage möglich.";
    } else if (setupState.loaded && !setupState.saveEnabled) {
      feedback.className = "config-feedback warn";
      feedback.textContent = "Gesperrt: Auf der Anlage ist kein Admin-Token eingerichtet. Die Aktivierung ist nur nach Einrichtung des Tokens möglich.";
    } else if (!setupState.activation.done) {
      feedback.className = "config-feedback neutral";
      feedback.textContent = "Noch nicht geprüft. Erst „Zuordnung prüfen“, dann mit Admin-Token aktivieren.";
    }
  }
  const pre = document.getElementById("setup-patch-preview");
  if (pre) {
    const { draft } = buildSetupMappingDraft(setupState.devices, setupState.rows);
    pre.textContent = JSON.stringify({ entwurf: draft, gepruefter_patch: setupState.preview.patch }, null, 2);
  }
}

function setSetupImportFeedback(message, tone) {
  const target = document.getElementById("setup-import-feedback");
  if (target) {
    target.className = `config-feedback ${tone}`;
    target.textContent = message;
  }
}

function setSetupTestSummary(message, tone) {
  setupState.test.summary = message;
  setupState.test.summaryTone = tone;
  const target = document.getElementById("setup-test-summary");
  if (target) {
    target.className = `config-feedback ${tone}`;
    target.textContent = message;
  }
}

function setSetupTestProgress(message) {
  const target = document.getElementById("setup-test-progress");
  if (target) {
    target.hidden = !message;
    target.textContent = message || "";
  }
}

function setSetupTestControls(running) {
  const testButton = document.getElementById("setup-test-button");
  const abortButton = document.getElementById("setup-test-abort");
  if (testButton) {
    testButton.disabled = running;
    testButton.textContent = running ? "Prüfung läuft …" : "Alle Punkte testen";
  }
  if (abortButton) {
    abortButton.hidden = !running;
  }
  if (!running) {
    setSetupTestProgress("");
  }
}

function setSetupActivateFeedback(message, tone) {
  const target = document.getElementById("setup-activate-feedback");
  if (target) {
    target.className = `config-feedback ${tone}`;
    target.textContent = message;
  }
}

function bindSetupUi() {
  const fileInput = document.getElementById("setup-pointlist-file");
  if (!fileInput) {
    return;
  }
  fileInput.addEventListener("change", () => handleSetupPointlistUpload(fileInput));
  document.getElementById("setup-discovery-button").addEventListener("click", handleSetupDiscovery);
  document.getElementById("setup-test-button").addEventListener("click", runSetupTests);
  document.getElementById("setup-test-abort").addEventListener("click", () => {
    setupState.test.abort = true;
  });
  document.getElementById("setup-preview-button").addEventListener("click", runSetupPreview);
  document.getElementById("setup-activate-button").addEventListener("click", runSetupActivation);
  document.querySelectorAll("#setup-status-filter button[data-status-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      setupState.filters.status = button.dataset.statusFilter;
      document.querySelectorAll("#setup-status-filter button[data-status-filter]").forEach((other) => {
        other.setAttribute("aria-pressed", other === button ? "true" : "false");
      });
      renderSetupTable();
    });
  });
  document.getElementById("setup-group-filter").addEventListener("change", (event) => {
    setupState.filters.group = event.target.value;
    renderSetupTable();
  });
  document.getElementById("setup-sort-select").addEventListener("change", (event) => {
    setupState.filters.sort = event.target.value;
    renderSetupTable();
  });
  renderSetupPage();
}

function cloneSiteConfig(config) {
  return JSON.parse(JSON.stringify(config));
}

function setInputValue(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.value = value ?? "";
  }
}

function setInputChecked(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.checked = value === true;
  }
}

function setSelectValue(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.value = value;
  }
}

function textValue(id, fallback = "") {
  const value = document.getElementById(id)?.value.trim();
  return value || fallback;
}

function selectValue(id, fallback = "") {
  return document.getElementById(id)?.value || fallback;
}

function checkboxValue(id) {
  return document.getElementById(id)?.checked === true;
}

function numericValue(id, fallback) {
  const raw = document.getElementById(id)?.value;
  if (raw === undefined || raw === null || raw === "") {
    return fallback;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : fallback;
}

function integerValue(id, fallback) {
  const value = numericValue(id, fallback);
  return Number.isFinite(value) ? Math.round(value) : fallback;
}

function optionalNumericValue(id) {
  const raw = document.getElementById(id)?.value;
  if (raw === undefined || raw === null || raw === "") {
    return null;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function integerFromElement(element, fallback) {
  const value = Number(element?.value);
  return Number.isFinite(value) ? Math.round(value) : fallback;
}

function optionalNumberFromElement(element) {
  const raw = element?.value;
  if (raw === undefined || raw === null || raw === "") {
    return null;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function optionalIntegerFromElement(element) {
  const raw = element?.value;
  if (raw === undefined || raw === null || raw === "") {
    return null;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? Math.round(value) : null;
}

function optionalTextFromElement(element) {
  const raw = element?.value;
  if (raw === undefined || raw === null) {
    return null;
  }
  const value = String(raw).trim();
  return value || null;
}

function inputValue(value) {
  return value === null || value === undefined ? "" : value;
}

function checkedAttribute(value) {
  return value ? "checked" : "";
}

function selectedAttribute(value) {
  return value ? "selected" : "";
}

function selectedChannelMeta() {
  const byId = new Map(appState.availableChannels.map((channel) => [channel.id, channel]));
  return [...appState.selectedChannels].map((id) => byId.get(id) || { id, label: "Datenpunkt", unit: "", group: "EMS" });
}

function renderReportChannelList() {
  const target = document.getElementById("report-channel-list");
  const signature = appState.availableChannels.map((channel) => channel.id).join("|");
  if (target.dataset.signature === signature) {
    return;
  }
  const defaults = new Set(VIEW_PRESETS[2].channels.concat(["tariff.current_price_ct_kwh", "site.outdoor_temperature_c"]));
  target.innerHTML = appState.availableChannels.map((channel) => `
    <label class="check">
      <input type="checkbox" name="report-channel" value="${escapeHtml(channel.id)}" ${defaults.has(channel.id) ? "checked" : ""}>
      <span>${escapeHtml(channel.label || "Datenpunkt")}${channel.unit ? ` (${escapeHtml(channel.unit)})` : ""}</span>
    </label>
  `).join("");
  target.dataset.signature = signature;
  target.querySelectorAll("input").forEach((input) => input.addEventListener("change", updateReportLinks));
}

function setReportDefaults() {
  const end = new Date();
  const start = new Date(end.getTime() - 24 * 60 * 60 * 1000);
  document.getElementById("report-start").value = toDatetimeLocal(start);
  document.getElementById("report-end").value = toDatetimeLocal(end);
}

async function previewReport(event) {
  event.preventDefault();
  const button = document.getElementById("report-preview-button");
  const target = document.getElementById("report-preview");
  button.disabled = true;
  target.innerHTML = '<article class="preview-card">Bericht wird erstellt …</article>';
  try {
    await renderReportBuilderPreview(target, buildReportConfig());
    updateReportLinks();
  } catch (error) {
    target.innerHTML = `<article class="preview-card error"><strong>Fehler</strong><span>${escapeHtml(error.message)}</span></article>`;
  } finally {
    button.disabled = false;
  }
}

function destroyReportCharts() {
  reportCharts.forEach((chart) => {
    try {
      chart.destroy();
    } catch (error) {
      /* Instanz bereits entfernt. */
    }
  });
  reportCharts = [];
}

async function renderReportBuilderPreview(target, config) {
  destroyReportCharts();
  const start = new Date(config.start);
  const end = new Date(config.end);
  const components = config.sections.map((section) => section.component);
  if (!components.length) {
    target.innerHTML = '<article class="preview-card">Keine Bausteine gewählt. Links Bausteine und Datenpunkte auswählen.</article>';
    return;
  }
  const channels = config.channels.length ? config.channels : ["tariff.current_price_ct_kwh"];
  const needsData = components.some((component) => ["summary", "line_chart", "bar_chart", "heatmap", "table"].includes(component));
  const histories = needsData
    ? await Promise.all(channels.map(async (id) => {
      const meta = channelMeta(id);
      const payload = await fetchHistorySafe(id, start, end, config.granularity, historyLimit(config.granularity));
      const points = normalizeHistoryRows(payload.rows || [])
        .map((row) => ({ time: parseTime(row.timestamp), value: historyValue(row) }))
        .filter(isFinitePoint);
      return { id, meta, points, error: payload.error };
    }))
    : [];

  target.innerHTML = reportPreviewHeader(config)
    + components.map((component) => `<article class="report-block" data-block="${escapeHtml(component)}"></article>`).join("");

  const blockEls = target.querySelectorAll(".report-block");
  components.forEach((component, index) => {
    renderReportBlock(blockEls[index], component, config, histories);
  });
}

function reportPreviewHeader(config) {
  const range = `${formatTimestamp(config.start)} – ${formatTimestamp(config.end)}`;
  return `
    <div class="report-doc-head">
      <strong>${escapeHtml(config.title)}</strong>
      <span>Berichtszeitraum ${escapeHtml(range)}</span>
    </div>
  `;
}

function renderReportBlock(el, component, config, histories) {
  const title = reportSectionLabel(component);
  el.innerHTML = `<div class="report-block-head"><h4>${escapeHtml(title)}</h4></div><div class="report-block-body"></div>`;
  const body = el.querySelector(".report-block-body");

  if (component === "text") {
    const text = (config.text || "").trim();
    body.innerHTML = text
      ? `<p class="report-text">${escapeHtml(text).replace(/\n/g, "<br>")}</p>`
      : '<div class="empty-state compact">Kein Text hinterlegt. Links unter „Eigener Text“ ergänzen.</div>';
    return;
  }

  if (component === "events") {
    body.innerHTML = '<div class="empty-state compact">Kommunikationshinweise werden im PDF-/HTML-Export ergänzt.</div>';
    return;
  }

  if (!histories.length) {
    body.innerHTML = '<div class="empty-state compact">Keine Datenpunkte ausgewählt.</div>';
    return;
  }

  if (component === "summary") {
    body.innerHTML = `<div class="daily-report report-tiles">${histories.map((item) => {
      const stats = seriesStats(item.points);
      const avg = item.points.length ? item.points.reduce((sum, point) => sum + point.value, 0) / item.points.length : null;
      return reportTile(item.meta.label || item.id, `${formatNumber(stats.last, item.meta.unit)} · Ø ${formatNumber(avg, item.meta.unit)}`);
    }).join("")}</div>`;
    return;
  }

  if (component === "table") {
    body.innerHTML = `<div class="table-wrap"><table><thead><tr>
        <th>Datenpunkt</th><th>Letzter</th><th>Min</th><th>Max</th><th>Ø</th><th>Messpunkte</th>
      </tr></thead><tbody>${histories.map((item) => {
        const stats = seriesStats(item.points);
        const avg = item.points.length ? item.points.reduce((sum, point) => sum + point.value, 0) / item.points.length : null;
        return `<tr>
          <td>${escapeHtml(item.meta.label || item.id)}</td>
          <td>${escapeHtml(formatNumber(stats.last, item.meta.unit))}</td>
          <td>${escapeHtml(formatNumber(stats.min, item.meta.unit))}</td>
          <td>${escapeHtml(formatNumber(stats.max, item.meta.unit))}</td>
          <td>${escapeHtml(formatNumber(avg, item.meta.unit))}</td>
          <td>${escapeHtml(item.points.length)}</td>
        </tr>`;
      }).join("")}</tbody></table></div>`;
    return;
  }

  if (component === "heatmap") {
    histories.forEach((item) => body.appendChild(buildHeatmapBlock(item)));
    return;
  }

  // line_chart / bar_chart: ein Diagramm je Datenpunkt — bewusst eine Kurve pro
  // Diagramm, damit die Ansicht lesbar bleibt (UX8, Roadmap-Risiko "zu viele Linien").
  histories.forEach((item, index) => {
    const frame = document.createElement("div");
    frame.className = "chart-frame report-chart";
    body.appendChild(document.createElement("div")).className = "report-series-label";
    body.lastChild.textContent = [item.meta.label || "Datenpunkt", item.meta.unit].filter(Boolean).join(" · ");
    body.appendChild(frame);
    const color = seriesColor(index);
    if (item.error || !item.points.length) {
      frame.innerHTML = `<div class="chart-empty">${escapeHtml(item.error || "Für den gewählten Zeitraum liegen keine Werte vor. Bitte einen längeren Zeitraum wählen.")}</div>`;
      return;
    }
    if (component === "bar_chart") {
      buildReportBars(frame, item, color);
    } else {
      buildReportLine(frame, item, color, gapThresholdMs(config.granularity));
    }
  });
}

function reportChartColors() {
  const css = getComputedStyle(document.documentElement);
  const token = (name, fallback) => (css.getPropertyValue(name).trim() || fallback);
  return {
    grid: token("--line", "#e4eaf1"),
    axis: token("--muted", "#5b6b7e"),
    font: token("--font", "Inter, sans-serif"),
  };
}

function buildReportLine(frame, item, color, gapMs = null) {
  const colors = reportChartColors();
  const { xs, ys } = buildSeriesWithGaps(item.points, gapMs);
  const chart = new uPlot({
    width: frame.clientWidth || 520,
    height: 220,
    padding: [12, 14, 4, 8],
    legend: { show: false },
    cursor: { y: false },
    scales: { x: { time: true } },
    axes: [
      { stroke: colors.axis, font: `12px ${colors.font}`, grid: { stroke: colors.grid, width: 1 }, ticks: { stroke: colors.grid },
        values: (_u, splits) => splits.map((value) => formatTimeAxis(value)) },
      { stroke: colors.axis, font: `12px ${colors.font}`, size: 52, grid: { stroke: colors.grid, width: 1 }, ticks: { stroke: colors.grid },
        values: (_u, splits) => splits.map((value) => formatAxis(value)) },
    ],
    series: [{}, { stroke: color, width: 2, fill: hexToRgba(color, 0.1), points: { show: false } }],
  }, [xs, ys], frame);
  reportCharts.push(chart);
  observeReportChart(frame, chart);
}

function buildReportBars(frame, item, color) {
  const colors = reportChartColors();
  const range = item.points[item.points.length - 1].time - item.points[0].time;
  const bucketMs = range > 3 * 24 * 3600 * 1000 ? 24 * 3600 * 1000 : 3600 * 1000;
  const buckets = aggregateBuckets(item.points, bucketMs);
  const xs = buckets.map((bucket) => Math.round(bucket.time / 1000));
  const ys = buckets.map((bucket) => bucket.value);
  const perDay = bucketMs >= 24 * 3600 * 1000;
  const chart = new uPlot({
    width: frame.clientWidth || 520,
    height: 220,
    padding: [12, 14, 4, 8],
    legend: { show: false },
    cursor: { y: false },
    scales: { x: { time: true } },
    axes: [
      { stroke: colors.axis, font: `12px ${colors.font}`, grid: { show: false }, ticks: { stroke: colors.grid },
        values: (_u, splits) => splits.map((value) => (perDay ? DAY_ONLY.format(new Date(value * 1000)) : formatTimeAxis(value))) },
      { stroke: colors.axis, font: `12px ${colors.font}`, size: 52, grid: { stroke: colors.grid, width: 1 }, ticks: { stroke: colors.grid },
        values: (_u, splits) => splits.map((value) => formatAxis(value)) },
    ],
    series: [{}, { stroke: color, fill: hexToRgba(color, 0.55), width: 1, paths: uPlot.paths.bars({ size: [0.7, 40] }), points: { show: false } }],
  }, [xs, ys], frame);
  reportCharts.push(chart);
  observeReportChart(frame, chart);
}

function observeReportChart(frame, chart) {
  if (typeof ResizeObserver === "undefined") {
    return;
  }
  const observer = new ResizeObserver(() => {
    if (frame.clientWidth) {
      chart.setSize({ width: frame.clientWidth, height: 220 });
    }
  });
  observer.observe(frame);
}

function aggregateBuckets(points, bucketMs) {
  const map = new Map();
  points.forEach((point) => {
    const key = Math.floor(point.time / bucketMs) * bucketMs;
    const entry = map.get(key) || { sum: 0, count: 0 };
    entry.sum += point.value;
    entry.count += 1;
    map.set(key, entry);
  });
  return [...map.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([time, entry]) => ({ time, value: entry.sum / entry.count }));
}

function buildHeatmapBlock(item) {
  const wrap = document.createElement("div");
  wrap.className = "heatmap-block";
  const label = document.createElement("div");
  label.className = "report-series-label";
  label.textContent = item.meta.label || item.id;
  wrap.appendChild(label);

  if (!item.points.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state compact";
    empty.textContent = "Für den gewählten Zeitraum liegen keine Werte vor. Bitte einen längeren Zeitraum wählen.";
    wrap.appendChild(empty);
    return wrap;
  }

  // Raster: Zeilen = Tage, Spalten = Stunde des Tages (0–23), Wert = Mittel.
  const days = [];
  const cells = new Map();
  let min = Infinity;
  let max = -Infinity;
  item.points.forEach((point) => {
    const date = new Date(point.time);
    const dayKey = date.toISOString().slice(0, 10);
    if (!cells.has(dayKey)) {
      cells.set(dayKey, new Array(24).fill(null).map(() => ({ sum: 0, count: 0 })));
      days.push(dayKey);
    }
    const cell = cells.get(dayKey)[date.getHours()];
    cell.sum += point.value;
    cell.count += 1;
  });
  const valueAt = (dayKey, hour) => {
    const cell = cells.get(dayKey)[hour];
    return cell.count ? cell.sum / cell.count : null;
  };
  days.forEach((dayKey) => {
    for (let hour = 0; hour < 24; hour += 1) {
      const value = valueAt(dayKey, hour);
      if (value !== null) {
        min = Math.min(min, value);
        max = Math.max(max, value);
      }
    }
  });

  const grid = document.createElement("div");
  grid.className = "heatmap-grid";
  grid.style.gridTemplateColumns = `auto repeat(24, 1fr)`;
  grid.appendChild(heatmapCell("", "heatmap-corner"));
  for (let hour = 0; hour < 24; hour += 1) {
    grid.appendChild(heatmapCell(hour % 6 === 0 ? String(hour) : "", "heatmap-hour"));
  }
  days.forEach((dayKey) => {
    grid.appendChild(heatmapCell(dayKey.slice(8, 10) + "." + dayKey.slice(5, 7), "heatmap-day"));
    for (let hour = 0; hour < 24; hour += 1) {
      const value = valueAt(dayKey, hour);
      const cell = heatmapCell("", "heatmap-cell");
      if (value === null) {
        cell.classList.add("empty");
      } else {
        cell.style.background = heatmapColor(value, min, max);
        cell.title = `${dayKey} ${String(hour).padStart(2, "0")}:00 — ${formatNumber(value, item.meta.unit)}`;
      }
      grid.appendChild(cell);
    }
  });
  wrap.appendChild(grid);

  const legend = document.createElement("div");
  legend.className = "heatmap-legend";
  legend.innerHTML = `<span>${escapeHtml(formatNumber(min, item.meta.unit))}</span><div class="heatmap-scale"></div><span>${escapeHtml(formatNumber(max, item.meta.unit))}</span>`;
  wrap.appendChild(legend);
  return wrap;
}

function heatmapCell(text, className) {
  const cell = document.createElement("div");
  cell.className = className;
  if (text) {
    cell.textContent = text;
  }
  return cell;
}

function heatmapColor(value, min, max) {
  const ratio = max > min ? (value - min) / (max - min) : 0.5;
  // Blau (niedrig) → Amber (hoch), gut lesbar in beiden Themes.
  const hue = 210 - ratio * 180;
  const light = 78 - ratio * 32;
  return `hsl(${hue.toFixed(0)}, 70%, ${light.toFixed(0)}%)`;
}

function buildReportConfig() {
  const channels = [...document.querySelectorAll("input[name='report-channel']:checked")].map((input) => input.value);
  const sections = [...document.querySelectorAll("input[name='report-section']:checked")].map((input) => ({ component: input.value }));
  return {
    title: document.getElementById("report-title").value.trim() || "Mini EMS Betriebsbericht",
    start: datetimeLocalToIso(document.getElementById("report-start").value),
    end: datetimeLocalToIso(document.getElementById("report-end").value),
    granularity: document.getElementById("report-granularity").value,
    text: document.getElementById("report-text") ? document.getElementById("report-text").value : "",
    channels,
    sections,
  };
}

function updateReportLinks() {
  const config = buildReportConfig();
  // Export laeuft ueber das Backend — nur dort unterstuetzte Bausteine uebergeben.
  const exportSections = config.sections
    .map((section) => section.component)
    .filter((component) => BACKEND_REPORT_SECTIONS.includes(component));
  const query = new URLSearchParams({
    title: config.title,
    start: config.start,
    end: config.end,
    granularity: config.granularity,
    channels: config.channels.join(","),
    sections: exportSections.join(","),
  });
  document.getElementById("report-html-link").href = `/api/report/html?${query.toString()}`;
  document.getElementById("report-pdf-link").href = `/api/report/pdf?${query.toString()}`;
}

/* ===== Standardweg Berichte (UX3): Tagesbericht in zwei bis drei Klicks ===== */

function setReportDayMode(mode) {
  const resolved = ["today", "yesterday", "date"].includes(mode) ? mode : "today";
  appState.reportDay.mode = resolved;
  document.querySelectorAll("[data-report-day]").forEach((button) => {
    button.setAttribute("aria-pressed", button.dataset.reportDay === resolved ? "true" : "false");
  });
  const dateInput = document.getElementById("report-date");
  if (dateInput) {
    dateInput.hidden = resolved !== "date";
    if (resolved === "date") {
      if (!dateInput.value) {
        dateInput.value = appState.reportDay.date || reportBaseDateIso();
      }
      appState.reportDay.date = dateInput.value;
      if (typeof dateInput.focus === "function") {
        dateInput.focus();
      }
    }
  }
  updateReportQuickView();
}

/* Betriebstag der Anlage: bevorzugt health.today_date (deckt Simulationszeit ab),
   sonst das Datum des letzten gemeldeten Zustands. */
function reportBaseDateIso() {
  const healthDate = appState.statusPayload?.health?.today_date;
  if (typeof healthDate === "string" && /^\d{4}-\d{2}-\d{2}$/.test(healthDate)) {
    return healthDate;
  }
  return toDateIso(getReferenceNow(appState.statusPayload || {}));
}

/* Gewählter Berichtstag als YYYY-MM-DD; null bedeutet "Heute" — dann bestimmt
   das Backend den aktuellen Betriebstag selbst (gleiches Verhalten wie UX2). */
function selectedReportDateIso() {
  const mode = appState.reportDay.mode;
  if (mode === "yesterday") {
    const base = new Date(`${reportBaseDateIso()}T12:00:00`);
    base.setDate(base.getDate() - 1);
    return toDateIso(base);
  }
  if (mode === "date" && /^\d{4}-\d{2}-\d{2}$/.test(appState.reportDay.date || "")) {
    return appState.reportDay.date;
  }
  return null;
}

function reportDayHeading(dateIso) {
  const mode = appState.reportDay.mode;
  if (mode === "yesterday" && dateIso) {
    return "Gestern im Überblick";
  }
  if (mode === "date" && dateIso) {
    const time = parseTime(`${dateIso}T12:00:00`);
    return Number.isFinite(time) ? `${DAY_DATE.format(new Date(time))} im Überblick` : "Berichtstag im Überblick";
  }
  return "Heute im Überblick";
}

let reportQuickRequestId = 0;

/* Links und Tageskennzahlen des Standardwegs auf den gewählten Berichtstag stellen.
   todayReport: bereits geladener Tagesreport für "Heute" (spart den zweiten Abruf). */
async function updateReportQuickView(todayReport = null) {
  const dateIso = selectedReportDateIso();
  const suffix = dateIso ? `?date=${dateIso}` : "";
  setHref("report-open-link", `/api/report/html${suffix}`);
  setHref("report-pdf-quick-link", `/api/report/pdf${suffix}`);
  setHref("report-csv-link", `/api/report/daily.csv${suffix}`);
  setText("daily-report-label", reportDayHeading(dateIso));
  if (!dateIso && todayReport) {
    renderDailyReport(todayReport);
    return;
  }
  const requestId = ++reportQuickRequestId;
  const payload = await fetchOptionalJson(`/api/report/daily${suffix}`, null);
  if (requestId !== reportQuickRequestId) {
    return;
  }
  renderDailyReport(payload, dateIso
    ? "Für diesen Tag liegen keine Betriebsdaten vor. Bitte einen anderen Berichtstag wählen."
    : undefined);
}

function setHref(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.href = value;
  }
}

function renderDailyReport(report, emptyText) {
  const target = document.getElementById("daily-report");
  if (!target) {
    return;
  }
  const safeReport = report && typeof report === "object" ? report : {};
  const price = safeReport.price_ct_kwh || {};
  const statusCounts = safeReport.status_counts || {};
  if (!toNumber(safeReport.cycle_count)) {
    target.innerHTML = `<div class="empty-state">${escapeHtml(emptyText || "Für heute liegen noch keine Betriebsdaten vor. Sobald die Anlage läuft, erscheinen hier die Tageskennzahlen.")}</div>`;
    return;
  }
  target.innerHTML = [
    reportTile("Läufe", safeReport.cycle_count),
    reportTile("Normale Läufe", statusCounts.healthy || 0),
    reportTile("Kommunikationshinweise", safeReport.bacnet_event_count),
    reportTile("Durchschnittspreis", formatNumber(price.average, "ct/kWh", 3)),
    reportTile("Niedrigster Preis", formatNumber(price.min, "ct/kWh", 3)),
    reportTile("Preisfenster", (safeReport.spotmarket_windows || []).length),
  ].join("");
}

function renderRecentCycles(rows) {
  const body = document.getElementById("cycles-body");
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="5">Noch keine Läufe aufgezeichnet. Sobald die Steuerung läuft, erscheinen hier die letzten Regelzyklen.</td></tr>';
    return;
  }
  body.innerHTML = rows.map((row) => `
    <tr>
      <td>${escapeHtml(row.cycle_id || "-")}</td>
      <td><span class="badge ${cssToken(row.status)}">${escapeHtml(friendlyState(row.status))}</span></td>
      <td>${escapeHtml(row.current_slot_label || "-")}</td>
      <td>${escapeHtml(formatNumber(row.current_price_ct_kwh, "ct/kWh", 3))}</td>
      <td>${escapeHtml(formatTimestamp(row.timestamp))}</td>
    </tr>
  `).join("");
}

function renderWeather(payload) {
  appState.weather = payload;
  const target = document.getElementById("weather-panel");
  if (!payload || payload.status !== "ok") {
    target.innerHTML = '<div class="empty-state">Wetterdaten sind derzeit nicht verfügbar. Sie werden beim nächsten Abruf erneut geladen.</div>';
    return;
  }
  const current = payload.current || {};
  target.innerHTML = `
    <div class="weather-now">
      <span class="micro-label">${escapeHtml(payload.site || "Standort")} / ${escapeHtml(payload.source || "Wetter")}</span>
      <strong>${escapeHtml(formatNumber(current.temperature_c, "°C", 1))}</strong>
      <span>${escapeHtml(current.weather_label || "-")} / gefühlt ${escapeHtml(formatNumber(current.apparent_temperature_c, "°C", 1))}</span>
    </div>
    <div class="weather-details">
      ${reportTile("Luftfeuchte", formatNumber(current.humidity_percent, "%", 0))}
      ${reportTile("Wind", formatNumber(current.wind_speed_kmh, "km/h", 1))}
      ${reportTile("Regen", formatNumber(current.precipitation_mm, "mm", 1))}
      ${reportTile("Stand", payload.fetched_at ? formatTimestamp(payload.fetched_at) : "-")}
    </div>
  `;
}

async function runDiagnosticRead() {
  const target = document.getElementById("diagnostic-output");
  target.textContent = "Prüfung läuft...";
  try {
    const payload = await fetchJson("/api/diagnostics/read?channel_id=tariff.current_price_ct_kwh&samples=3");
    target.innerHTML = renderDiagnosticResult(payload);
  } catch (error) {
    target.innerHTML = renderDiagnosticError(error);
  }
}

function selectedRange() {
  const end = getReferenceNow(appState.statusPayload || {});
  const value = document.getElementById("range-select").value;
  const hours = value === "6h" ? 6 : value === "48h" ? 48 : value === "7d" ? 24 * 7 : 24;
  return {
    start: new Date(end.getTime() - hours * 60 * 60 * 1000),
    end,
  };
}

function historyLimit(granularity) {
  if (granularity === "raw") {
    return 5000;
  }
  if (granularity === "5m") {
    return 2500;
  }
  return 1000;
}

function getReferenceNow(payload) {
  const time = parseTime(payload?.health?.timestamp || payload?.health?.last_healthy_at);
  return new Date(Number.isFinite(time) ? time : Date.now());
}

function normalizeHistoryRows(rows) {
  return [...rows].sort((a, b) => parseTime(a.timestamp) - parseTime(b.timestamp));
}

function historyValue(row) {
  return toNumber(row.average_value ?? row.last_value ?? row.value ?? row.desired_value);
}

function seriesStats(points) {
  const values = points.map((point) => point.value).filter(Number.isFinite);
  if (!values.length) {
    return { min: null, max: null, last: null };
  }
  return {
    min: Math.min(...values),
    max: Math.max(...values),
    last: values[values.length - 1],
  };
}

function isFinitePoint(point) {
  return Number.isFinite(point.time) && Number.isFinite(point.value);
}

/* SVG-Pfad einer Linie; bei Lücken (Abstand > gapMs) beginnt ein neues Segment,
   damit fehlende Daten nicht als durchgezogene Linie erscheinen (UX8). */
function linePath(points, scaleX, scaleY, gapMs = Infinity) {
  let previousTime = null;
  return points.map((point) => {
    const command = previousTime !== null && point.time - previousTime <= gapMs ? "L" : "M";
    previousTime = point.time;
    return `${command} ${scaleX(point.time).toFixed(1)} ${scaleY(point.value).toFixed(1)}`;
  }).join(" ");
}

function buildSlotTime(dateIso, slotIndex) {
  const start = new Date(`${dateIso}T00:00:00`);
  return start.getTime() + Number(slotIndex) * PRICE_SLOT_MS;
}

function groupBy(items, keyFn) {
  const map = new Map();
  items.forEach((item) => {
    const key = keyFn(item);
    if (!map.has(key)) {
      map.set(key, []);
    }
    map.get(key).push(item);
  });
  return map;
}

function statCell(label, value) {
  return `<article class="stat-cell"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value ?? "-")}</strong></article>`;
}

function reportTile(label, value) {
  return `<article class="report-tile"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value ?? "-")}</strong></article>`;
}

/* Hauptbotschaft der Startseite (UX4): genau eine Aussage zu "Läuft die Anlage?",
   abgeleitet aus Health-Status, sicherem Modus und Datenqualität.
   Formulierungen aus PRODUCT_UX_KONZEPT.md, Abschnitt 2 (UX10-Wording-Set).
   Robust gegen fehlende/teilweise Payloads (ältere health.json, null-Werte). */
function buildMainMessage(payload) {
  const health = payload && typeof payload.health === "object" && payload.health !== null ? payload.health : {};
  const status = typeof health.status === "string" ? health.status.toLowerCase() : "";

  if (!status) {
    return {
      level: "warn",
      headline: "Keine aktuellen Daten vom System.",
      detail: "Das System hat noch keinen Zustand gemeldet. Die angezeigten Werte können veraltet sein. Bitte den Betrieb der Steuerung prüfen.",
    };
  }
  if (health.stale_runtime === true) {
    return {
      level: "warn",
      headline: "Keine aktuellen Daten vom System.",
      detail: "Das System hat sich seit einiger Zeit nicht gemeldet. Die angezeigten Werte können veraltet sein. Bitte den Betrieb der Steuerung prüfen.",
    };
  }
  if (status === "safe_mode" || health.safe_mode_reason) {
    const reason = String(health.safe_mode_reason || "");
    if (reason.startsWith("startup_validation")) {
      return {
        level: "warn",
        headline: "Anlaufprüfung aktiv.",
        detail: "Nach dem Start prüft das System zuerst alle Verbindungen und Werte, bevor es eingreift.",
      };
    }
    if (reason.startsWith("price_provider")) {
      return {
        level: "alert",
        headline: "Sicherer Modus: Preisdaten nicht verfügbar.",
        detail: "Die aktuellen Strompreise konnten nicht abgerufen werden. Die Steuerung pausiert, bis wieder Preise vorliegen.",
      };
    }
    if (reason.startsWith("grid_read")) {
      return {
        level: "alert",
        headline: "Sicherer Modus: Netzleistung nicht lesbar.",
        detail: "Der Messwert der Netzleistung kommt nicht an. Bitte die Verbindung zur Anlage prüfen.",
      };
    }
    if (reason.startsWith("write_failure")) {
      return {
        level: "alert",
        headline: "Sicherer Modus: Übergabe an die Anlage gestört.",
        detail: "Werte konnten nicht an die Anlage übergeben werden. Bitte die Verbindung zur Anlage prüfen.",
      };
    }
    return {
      level: "alert",
      headline: "Die Anlage ist im sicheren Modus.",
      detail: "Die Steuerung wurde vorsorglich angehalten. Die Anlage läuft eigenständig weiter. Bitte den Systemzustand prüfen.",
    };
  }
  if (status === "degraded") {
    return {
      level: "warn",
      headline: "Die Anlage läuft im eingeschränkten Betrieb.",
      detail: "Einzelne Werte konnten nicht übertragen werden. Details stehen im Systemzustand.",
    };
  }
  if (collectQualityChannels(health, "bad").length) {
    return {
      level: "warn",
      headline: "Die Anlage läuft, aber einzelne Messwerte sind gestört.",
      detail: "Für mindestens einen Messpunkt liegt kein gültiger Wert vor. Bitte die Verbindung zur Anlage prüfen.",
    };
  }
  if (status === "healthy") {
    return {
      level: "ok",
      headline: "Die Anlage läuft im Normalbetrieb.",
      detail: "Alle Werte werden regelmäßig gelesen und übergeben.",
    };
  }
  return {
    level: "neutral",
    headline: "Der Anlagenzustand wird ermittelt.",
    detail: "Der letzte Lauf meldet keinen bekannten Zustand. Details stehen im Systemzustand.",
  };
}

/* Kurztext für die Signalkarte "Sicherer Betriebszustand" (UX6): benennt den Grund
   in Betreiber-Sprache und den nächsten Schritt. Wording aus PRODUCT_UX_KONZEPT.md 2.2. */
function safeModeSignalText(reason) {
  const value = String(reason || "");
  if (value.startsWith("startup_validation")) {
    return "Anlaufprüfung: Verbindungen und Werte werden nach dem Start geprüft.";
  }
  if (value.startsWith("price_provider")) {
    return "Sicherer Modus: Preisdaten fehlen. Pausiert, bis wieder Preise vorliegen.";
  }
  if (value.startsWith("grid_read")) {
    return "Sicherer Modus: Netzleistung nicht lesbar. Bitte Verbindung zur Anlage prüfen.";
  }
  if (value.startsWith("write_failure")) {
    return "Sicherer Modus: Übergabe gestört. Bitte Verbindung zur Anlage prüfen.";
  }
  return "Sicherer Modus aktiv. Bitte den Systemzustand prüfen.";
}

/* Konkrete Hinweise der Startseite (UX4): Preisfenster, Datenqualität,
   Übergabe an die Anlage und Morgen-Preise — in Betreiber-Sprache, ohne interne IDs. */
function buildStartHints(payload) {
  const source = payload && typeof payload === "object" && payload !== null ? payload : {};
  const health = typeof source.health === "object" && source.health !== null ? source.health : {};
  const plan = typeof source.spotmarket_plan === "object" && source.spotmarket_plan !== null ? source.spotmarket_plan : {};
  const hints = [];

  // Preisfenster: aktiv, als Nächstes geplant oder ehrlich "keine geplant".
  const todayWindows = Array.isArray(plan.today?.windows) ? plan.today.windows : [];
  const tomorrowWindows = Array.isArray(plan.tomorrow?.windows) ? plan.tomorrow.windows : [];
  const nextWindow = pickWindow(health.spotmarket_next_window) || pickWindow(plan.next_today_window);
  if (health.spotmarket_active_now === true) {
    const until = nextWindow ? ` bis ${nextWindow.end_label_exclusive} Uhr` : "";
    hints.push({ level: "ok", text: `Preissteuerung aktiv: Die Anlage befindet sich gerade in einem geplanten Preisfenster${until}.` });
  } else if (nextWindow) {
    hints.push({ level: "neutral", text: `Nächstes günstiges Preisfenster heute: ${nextWindow.start_label} bis ${nextWindow.end_label_exclusive} Uhr.` });
  } else if (pickWindow(tomorrowWindows[0])) {
    const first = pickWindow(tomorrowWindows[0]);
    hints.push({ level: "neutral", text: `Nächstes günstiges Preisfenster morgen: ${first.start_label} bis ${first.end_label_exclusive} Uhr.` });
  } else if (plan.today?.date && !todayWindows.length && !tomorrowWindows.length) {
    hints.push({ level: "neutral", text: "Für heute und morgen sind keine günstigen Preisfenster geplant." });
  }

  // Datenqualität einzelner Messwerte: das Badge-Muster ("Wert veraltet", "Messwert gestört") fortführen.
  const badInputs = collectQualityChannels(health, "bad");
  if (badInputs.length) {
    hints.push({ level: "alert", text: `Messwert gestört: ${describeQualityChannels(badInputs)}. Bitte die Verbindung zur Anlage prüfen.` });
  }
  const staleInputs = collectQualityChannels(health, "stale");
  if (staleInputs.length) {
    hints.push({ level: "warn", text: `Wert veraltet: ${describeQualityChannels(staleInputs)}. Diese Werte werden angezeigt, aber nicht mehr für Entscheidungen genutzt.` });
  }

  // Übergabe des Strompreises an die Anlage.
  const writeStatus = typeof health.write_status === "object" && health.write_status !== null ? health.write_status : {};
  const currentPrice = typeof writeStatus.current_price === "object" && writeStatus.current_price !== null ? writeStatus.current_price : {};
  if (currentPrice.last_error) {
    hints.push({ level: "alert", text: "Übergabe an die Anlage gestört: Der letzte Übertragungsversuch ist fehlgeschlagen. Details stehen im Systemzustand." });
  } else if (currentPrice.confirmed === false) {
    hints.push({ level: "warn", text: "Die Preisübergabe wartet auf Bestätigung der Anlage." });
  }

  // Preise für morgen.
  if (health.tomorrow_prices_available === false) {
    hints.push({ level: "neutral", text: "Die Strompreise für morgen werden noch erwartet." });
  }

  return hints;
}

function pickWindow(window) {
  if (!window || typeof window !== "object") {
    return null;
  }
  if (typeof window.start_label !== "string" || typeof window.end_label_exclusive !== "string") {
    return null;
  }
  return window;
}

function collectQualityChannels(health, quality) {
  const inputs = health && typeof health.additional_inputs === "object" && health.additional_inputs !== null
    ? health.additional_inputs
    : {};
  return Object.entries(inputs)
    .filter(([, entry]) => entry && typeof entry === "object" && typeof entry.quality === "string" && entry.quality.toLowerCase() === quality)
    .map(([channelId, entry]) => ({ channelId, ageSeconds: toNumber(entry.age_seconds) }));
}

/* Messpunkte in Betreiber-Sprache aufzählen — unbekannte Kanäle nie als interne ID zeigen. */
function describeQualityChannels(entries) {
  const labels = entries
    .map((entry) => CUSTOMER_CHANNEL_LABELS.get(entry.channelId)?.label)
    .filter(Boolean);
  const unknownCount = entries.length - labels.length;
  if (!labels.length) {
    return entries.length === 1 ? "ein Messpunkt" : `${entries.length} Messpunkte`;
  }
  if (unknownCount > 0) {
    return `${labels.join(", ")} und ${unknownCount} ${unknownCount === 1 ? "weiterer Messpunkt" : "weitere Messpunkte"}`;
  }
  return labels.join(", ");
}

function updateOperatorMessageForPage(page, payload = appState.statusPayload || {}) {
  const message = page === "dashboard"
    ? buildMainMessage(payload).headline
    : PAGE_SUBTITLES[page] || "Mini EMS Leitstand";
  setText("operator-message", message);
}

function protocolValue(value) {
  const normalized = String(value || "bacnet").trim().toLowerCase();
  return normalized || "bacnet";
}

function protocolLabel(value) {
  return protocolValue(value) === "bacnet" ? "BACnet" : String(value || "Protokoll");
}

function bacnetObjectTypeValue(value) {
  if (value === 0) {
    return "ai";
  }
  if (value === 2) {
    return "av";
  }
  if (value === 5) {
    return "bv";
  }
  const normalized = String(value || "").trim().toLowerCase();
  if (["analog_input", "analog-input", "ai"].includes(normalized)) {
    return "ai";
  }
  if (["analog_value", "analog-value", "av"].includes(normalized)) {
    return "av";
  }
  if (["binary_value", "binary-value", "bv"].includes(normalized)) {
    return "bv";
  }
  return "ai";
}

function bacnetObjectTypeLabel(value) {
  return { ai: "AI", av: "AV", bv: "BV" }[bacnetObjectTypeValue(value)] || "AI";
}

function formatPointSummary(channel) {
  const target = channel.controller_ip
    ? `${channel.controller_ip}${channel.controller_port ? `:${channel.controller_port}` : ""}`
    : "Standardgerät";
  const instance = inputValue(channel.instance) === "" ? "-" : channel.instance;
  return `${protocolLabel(channel.protocol)} / ${target} / ${bacnetObjectTypeLabel(channel.object_type)} ${instance}`;
}

function buildPriceWindowSummary(health, plan) {
  const todayWindows = plan.today?.windows || [];
  const tomorrowWindows = plan.tomorrow?.windows || [];
  const active = health.spotmarket_active_now ? "Die Preissteuerung ist aktuell aktiv." : "Die Anlage läuft aktuell ohne aktive Preissteuerung.";
  const today = todayWindows.length ? `Heute: ${todayWindows.map(windowLabel).join(", ")}.` : "Heute sind keine Preisfenster geplant.";
  const tomorrow = tomorrowWindows.length ? `Morgen: ${tomorrowWindows.map(windowLabel).join(", ")}.` : "Für morgen sind keine Preisfenster geplant.";
  return `${active} ${today} ${tomorrow}`;
}

function renderDiagnosticResult(payload) {
  const channel = channelMeta(payload?.channel_id);
  const status = friendlyState(payload?.status);
  const successful = Number(payload?.successful_sample_count || 0);
  const expected = Number(payload?.sample_count || 0);
  const values = [
    reportTile("Datenpunkt", channel.label || "Strompreis"),
    reportTile("Status", status),
    reportTile("Messwerte", `${successful} von ${expected || successful}`),
    reportTile("Letzter Wert", formatNumber(payload?.value, channel.unit || "ct/kWh", 3)),
    reportTile("Mittelwert", formatNumber(payload?.average_value, channel.unit || "ct/kWh", 3)),
    reportTile("Plausibilität", payload?.plausible === false ? "prüfen" : "in Ordnung"),
  ];
  const message = payload?.error
    ? `<div class="diagnostic-message warn">${escapeHtml(friendlyDiagnosticError(payload.error))}</div>`
    : '<div class="diagnostic-message ok">Die Preisprüfung war erfolgreich.</div>';
  return `<div class="diagnostic-cards">${values.join("")}</div>${message}`;
}

function renderDiagnosticError(error) {
  return `<div class="diagnostic-message warn">${escapeHtml(error?.message || "Die Preisprüfung konnte nicht ausgeführt werden.")}</div>`;
}

function friendlyDiagnosticError(error) {
  const text = String(error || "");
  if (!text) {
    return "Die Prüfung liefert keine Detailmeldung.";
  }
  if (text.includes("value_out_of_range")) {
    return "Der Messwert liegt außerhalb des erwarteten Bereichs.";
  }
  if (text.toLowerCase().includes("timeout")) {
    return "Die Anlage hat nicht rechtzeitig geantwortet.";
  }
  return "Die Prüfung meldet: " + text.replace(/[_-]/g, " ");
}

function channelMeta(channelId) {
  return appState.availableChannels.find((channel) => channel.id === channelId)
    || CUSTOMER_CHANNEL_LABELS.get(channelId)
    || { label: "Datenpunkt", unit: "" };
}

function windowLabel(window) {
  return `${window.start_label || "-"} bis ${window.end_label_exclusive || "-"}`;
}

function channelQuality(channelId) {
  const inputs = appState.statusPayload?.health?.additional_inputs;
  if (!inputs || typeof inputs !== "object") {
    return null;
  }
  const entry = inputs[channelId];
  if (!entry || typeof entry !== "object") {
    return null;
  }
  const quality = typeof entry.quality === "string" ? entry.quality.toLowerCase() : null;
  const ageSeconds = toNumber(entry.age_seconds);
  return { quality, ageSeconds: Number.isFinite(ageSeconds) ? ageSeconds : null };
}

function qualityBadgeHtml(channelId) {
  const info = channelQuality(channelId);
  if (!info || info.quality === "good" || info.quality === null) {
    return "";
  }
  if (info.quality === "stale") {
    const age = Number.isFinite(info.ageSeconds) ? ` (${escapeHtml(formatAgeSeconds(info.ageSeconds))})` : "";
    return `<span class="quality-badge stale" title="Der Messwert wurde länger nicht aktualisiert.">Wert veraltet${age}</span>`;
  }
  if (info.quality === "bad") {
    return '<span class="quality-badge bad" title="Für diesen Messpunkt liegt kein gültiger Wert vor. Bitte die Verbindung zur Anlage prüfen.">Messwert gestört</span>';
  }
  return "";
}

function formatAgeSeconds(seconds) {
  const value = toNumber(seconds);
  if (!Number.isFinite(value) || value < 0) {
    return "";
  }
  if (value < 90) {
    return "seit unter 1 Min";
  }
  const minutes = Math.round(value / 60);
  if (minutes < 90) {
    return `seit ${minutes} Min`;
  }
  const hours = Math.round(minutes / 60);
  if (hours < 48) {
    return `seit ${hours} Std`;
  }
  return `seit ${Math.round(hours / 24)} Tagen`;
}

function friendlyState(value) {
  const key = String(value || "").toLowerCase();
  if (!key) {
    return "-";
  }
  if (key === "disabled") {
    return "deaktiviert";
  }
  if (key === "monitoring") {
    return "beobachtet";
  }
  if (key === "ok" || key === "healthy") {
    return "in Ordnung";
  }
  if (key === "active" || key === "on") {
    return "aktiv";
  }
  if (key === "inactive" || key === "off") {
    return "aus";
  }
  return String(value).replace(/_/g, " ");
}

function valueKindLabel(kind) {
  if (kind === "energy_counter") {
    return "Zähler";
  }
  if (kind === "state") {
    return "Status";
  }
  return "Messwert";
}

function reportSectionLabel(component) {
  return {
    summary: "Kennzahlen",
    line_chart: "Liniendiagramm",
    bar_chart: "Säulendiagramm",
    heatmap: "Heatmap",
    table: "Datentabelle",
    text: "Textbaustein",
    events: "Kommunikationshinweise",
  }[component] || "Abschnitt";
}

function renderGlobalError(error) {
  setText("operator-message", "Verbindung unterbrochen.");
  setText("global-status", "Fehler");
  document.getElementById("global-status-dot").className = "status-dot error";
  renderStatusHero({
    level: "alert",
    headline: "Verbindung unterbrochen.",
    detail: "Die Daten konnten nicht geladen werden. Bitte die Verbindung zur lokalen Anlage prüfen.",
  }, {});
  renderStartHints([]);
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = value ?? "-";
  }
}

function formatNumber(value, unit = "", decimals = 2) {
  const number = toNumber(value);
  if (!Number.isFinite(number)) {
    return "-";
  }
  const digits = Math.abs(number) >= 1000 ? 0 : decimals;
  const rendered = number.toLocaleString("de-DE", { maximumFractionDigits: digits, minimumFractionDigits: Math.min(digits, 1) });
  return unit ? `${rendered} ${unit}` : rendered;
}

function formatAxis(value) {
  const number = toNumber(value);
  if (!Number.isFinite(number)) {
    return "-";
  }
  if (Math.abs(number) >= 1000) {
    return number.toLocaleString("de-DE", { maximumFractionDigits: 0 });
  }
  if (Math.abs(number) >= 10) {
    return number.toLocaleString("de-DE", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
  }
  return number.toLocaleString("de-DE", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
}

function formatBool(value) {
  if (value === true || value === 1) {
    return "aktiv";
  }
  if (value === false || value === 0) {
    return "aus";
  }
  return "-";
}

function formatTimestamp(value) {
  const time = parseTime(value);
  return Number.isFinite(time) ? DATE_TIME.format(new Date(time)) : "-";
}

function formatAge(value) {
  const time = parseTime(value);
  if (!Number.isFinite(time)) {
    return "-";
  }
  const minutes = Math.max(0, Math.round((Date.now() - time) / 60000));
  if (minutes < 2) {
    return "gerade eben";
  }
  if (minutes < 120) {
    return `vor ${minutes} min`;
  }
  return `vor ${Math.round(minutes / 60)} h`;
}

function parseTime(value) {
  if (!value) {
    return Number.NaN;
  }
  const parsed = Date.parse(String(value));
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

function toNumber(value) {
  if (value === null || value === undefined || value === "") {
    return Number.NaN;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : Number.NaN;
}

function toDatetimeLocal(date) {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function toDateIso(date) {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

function datetimeLocalToIso(value) {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString() : new Date().toISOString();
}

function cssToken(value) {
  return String(value || "").replace(/[^a-zA-Z0-9_-]/g, "_");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
