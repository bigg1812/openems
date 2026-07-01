const REFRESH_INTERVAL_MS = 30000;
const PRICE_SLOT_MS = 15 * 60 * 1000;
const DEFAULT_CHANNELS = [
  { id: "tariff.current_price_ct_kwh", label: "Strompreis", unit: "ct/kWh", group: "Markt", kind: "average" },
  { id: "grid.active_power_kw", label: "Netzleistung", unit: "kW", group: "Netz", kind: "average" },
  { id: "site.outdoor_temperature_c", label: "Außentemperatur", unit: "C", group: "Wetter", kind: "average" },
  { id: "site.buffer_1_top_temperature_c", label: "Puffer 1 oben", unit: "C", group: "Puffer", kind: "average" },
  { id: "site.buffer_1_bottom_temperature_c", label: "Puffer 1 unten", unit: "C", group: "Puffer", kind: "average" },
  { id: "site.buffer_2_top_temperature_c", label: "Puffer 2 oben", unit: "C", group: "Puffer", kind: "average" },
  { id: "site.buffer_2_bottom_temperature_c", label: "Puffer 2 unten", unit: "C", group: "Puffer", kind: "average" },
  { id: "site.heat_generation_flow_temperature_c", label: "Wärmeerzeugung Vorlauf", unit: "C", group: "Wärme", kind: "average" },
  { id: "site.heat_generation_return_temperature_c", label: "Wärmeerzeugung Rücklauf", unit: "C", group: "Wärme", kind: "average" },
  { id: "site.boiler_1_flow_temperature_c", label: "Gaskessel Vorlauf", unit: "C", group: "Gaskessel", kind: "average" },
  { id: "site.boiler_1_return_temperature_c", label: "Gaskessel Rücklauf", unit: "C", group: "Gaskessel", kind: "average" },
  { id: "site.boiler_2_flow_temperature_c", label: "Pelletkessel Vorlauf", unit: "C", group: "Pellet", kind: "average" },
  { id: "site.boiler_2_return_temperature_c", label: "Pelletkessel Rücklauf", unit: "C", group: "Pellet", kind: "average" },
  { id: "site.chp_flow_temperature_c", label: "BHKW Vorlauf", unit: "C", group: "BHKW", kind: "average" },
  { id: "site.chp_return_temperature_c", label: "BHKW Rücklauf", unit: "C", group: "BHKW", kind: "average" },
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

const SERIES_COLORS = ["#2563eb", "#16875a", "#b7791f", "#bf3f36", "#40556b", "#7c3aed", "#0891b2", "#be185d"];
const DATE_TIME = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const TIME_ONLY = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit" });

const THEME_STORAGE_KEY = "miniEmsTheme";
const DASHBOARD_STORAGE_KEY = "miniEmsDashboard";

const PAGES = {
  dashboard: "Dashboard",
  analyse: "Analyse",
  berichte: "Berichte",
  system: "System",
};

const KPI_CATALOG = [
  { id: "price", label: "Aktueller Strompreis", accent: "accent-blue",
    value: (h) => formatNumber(h.current_price_ct_kwh, "ct/kWh", 3),
    sub: (h) => `Zeitfenster ${h.current_slot_label || "-"}` },
  { id: "spotmarket", label: "Preissteuerung", accent: "accent-green",
    value: (h) => formatBool(h.spotmarket_active_now),
    sub: (h) => (h.spotmarket_active_now ? "Preissteuerung aktiv" : "Normalbetrieb") },
  { id: "grid_lockout", label: "Netzschutz", accent: "accent-amber",
    value: (h) => (h.grid_lockout_active === null || h.grid_lockout_active === undefined ? "deaktiviert" : formatBool(h.grid_lockout_active)),
    sub: (h) => friendlyState(h.grid_lockout_state) },
  { id: "grid_power", label: "Netzleistung", accent: "accent-slate",
    value: (h) => formatNumber(h.grid_active_power_kw, "kW", 2),
    sub: (h) => (h.grid_read_status ? friendlyState(h.grid_read_status) : "derzeit nicht aktiv") },
  { id: "weather_temp", label: "Außentemperatur", accent: "accent-slate",
    value: (_h, ctx) => formatNumber(ctx.weather?.current?.temperature_c, "C", 1),
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
  kpis: ["price", "spotmarket", "grid_lockout", "grid_power"],
  widgets: { price: true, weather: true, windows: true },
  charts: [],
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
  if (page === "dashboard") {
    rebuildPriceChart();
    redrawDashboardCharts();
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
}

async function refreshDashboard() {
  const button = document.getElementById("refresh-button");
  button.disabled = true;
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
    renderDailyReport(dailyReport);
    renderWeather(weather);
    renderChannelPicker();
    renderReportChannelList();
    await renderPriceOverview(statusPayload);
    renderKpis(statusPayload);
    applyDashboardWidgets();
    await renderDashboardCharts();
    await refreshWorkbench();
    updateReportLinks();
  } catch (error) {
    renderGlobalError(error);
  } finally {
    button.disabled = false;
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
  const state = payload.state || {};
  const status = health.status || "-";
  setText("global-status", friendlyState(status));
  document.getElementById("global-status-dot").className = `status-dot ${cssToken(status)}`;
  setText("operator-message", buildOperatorMessage(health));
  setText("last-updated", health.timestamp ? `Stand ${formatTimestamp(health.timestamp)}` : "-");
  setText("health-line", [
    `Sicherer Modus: ${health.safe_mode_reason ? "aktiv" : "aus"}`,
    `Morgen: ${health.tomorrow_prices_available ? "Preise verfügbar" : "wartet"}`,
  ].join(" / "));

  setText("spotmarket-summary", buildPriceWindowSummary(health, appState.statusPayload?.spotmarket_plan || {}));
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
  target.innerHTML = cards.join("") || '<div class="empty-state">Keine Kennzahlen ausgewählt. Über „Dashboard anpassen“ hinzufügen.</div>';
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
  container.innerHTML = charts.map((chart) => {
    const meta = channelMeta(chart.channel);
    const typeLabel = chart.type === "bar" ? "Säulen" : "Linie";
    return `
      <article class="tool-panel dashboard-chart-tile">
        <div class="panel-head">
          <div>
            <h3>${escapeHtml(meta.label || chart.channel)}</h3>
            <p>${escapeHtml([meta.unit, typeLabel].filter(Boolean).join(" · "))}</p>
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
    frame.innerHTML = `<div class="chart-empty">${escapeHtml(data && data.error ? data.error : "Keine Daten im Zeitraum.")}</div>`;
    return;
  }
  if (typeof uPlot === "undefined") {
    frame.innerHTML = '<div class="chart-empty">Diagramm-Bibliothek nicht geladen.</div>';
    return;
  }
  const colors = reportChartColors();
  const color = SERIES_COLORS[index % SERIES_COLORS.length];
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
    xs = data.points.map((point) => Math.round(point.time / 1000));
    ys = data.points.map((point) => point.value);
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
        values: (_u, splits) => splits.map((value) => TIME_ONLY.format(new Date(value * 1000))) },
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
      text: `${todaySlots || "-"} Werte heute / ${tomorrowSlots || "-"} Werte morgen`,
    },
    {
      state: health.safe_mode_reason ? "error" : "ok",
      title: "Sicherer Betriebszustand",
      text: health.safe_mode_reason ? "Sicherer Modus ist aktiv" : "Anlage läuft normal",
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
  setText("price-chart-meta", timeline.points.length ? `${timeline.points.length} Werte` : "keine Werte");
  renderPriceChart(document.getElementById("price-chart"), timeline.points, {
    unit: "ct/kWh",
    step: true,
    windows: timeline.windows,
    now: referenceNow.getTime(),
    empty: "Keine Preisdaten für die Ansicht vorhanden.",
  });
  document.getElementById("price-chart-stats").innerHTML = [
    statCell("Minimum", formatNumber(timeline.min, "ct/kWh", 3)),
    statCell("Maximum", formatNumber(timeline.max, "ct/kWh", 3)),
    statCell("Aktuell", formatNumber(timeline.current, "ct/kWh", 3)),
    statCell("Preisfenster", timeline.windows.length ? timeline.windows.map((item) => item.label).join(", ") : "keins"),
  ].join("");
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
  const histories = await Promise.all(selected.map(async (channel, index) => {
    const payload = await fetchHistorySafe(channel.id, range.start, range.end, granularity, historyLimit(granularity));
    return {
      channel,
      color: SERIES_COLORS[index % SERIES_COLORS.length],
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
  document.getElementById("series-grid").innerHTML = histories.map((item) => {
    const points = item.rows.map((row) => ({ time: parseTime(row.timestamp), value: historyValue(row) })).filter(isFinitePoint);
    const stats = seriesStats(points);
    return `
      <article class="series-card">
        <div class="series-head">
          <div>
            <strong>${escapeHtml(item.channel.label || "Datenpunkt")}</strong>
            <span>${escapeHtml([item.channel.group, item.channel.unit || valueKindLabel(item.channel.kind)].filter(Boolean).join(" / "))}</span>
            ${qualityBadgeHtml(item.channel.id)}
          </div>
          <span class="badge">${escapeHtml(item.channel.unit || item.channel.kind || "")}</span>
        </div>
        ${item.error ? `<div class="empty-state compact">${escapeHtml(item.error)}</div>` : `<div class="mini-chart">${renderSparkline(points, item.color, item.channel.unit)}</div>`}
        <div class="chart-stats">
          ${statCell("Letzter", formatNumber(stats.last, item.channel.unit))}
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
      error: "Daten konnten nicht geladen werden.",
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
    target.innerHTML = '<div class="chart-empty">Diagramm-Bibliothek konnte nicht geladen werden.</div>';
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

  const xs = clean.map((point) => Math.round(point.time / 1000));
  const ys = clean.map((point) => point.value);
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
    tooltip.innerHTML = `<b>${escapeHtml(DATE_TIME.format(new Date(u.data[0][idx] * 1000)))}</b>`
      + `<span class="ems-tooltip-value">${escapeHtml(formatNumber(value, options.unit || "", 3))}</span>`;
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
        values: (_u, splits) => splits.map((value) => TIME_ONLY.format(new Date(value * 1000))),
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

function renderSparkline(points, color, unit) {
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
  const path = linePath(clean, x, y);
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

  // line_chart / bar_chart: ein Diagramm je Datenpunkt
  histories.forEach((item, index) => {
    const frame = document.createElement("div");
    frame.className = "chart-frame report-chart";
    body.appendChild(document.createElement("div")).className = "report-series-label";
    body.lastChild.textContent = item.meta.label || item.id;
    body.appendChild(frame);
    const color = SERIES_COLORS[index % SERIES_COLORS.length];
    if (item.error || !item.points.length) {
      frame.innerHTML = `<div class="chart-empty">${escapeHtml(item.error || "Keine Daten im Zeitraum.")}</div>`;
      return;
    }
    if (component === "bar_chart") {
      buildReportBars(frame, item, color);
    } else {
      buildReportLine(frame, item, color);
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

function buildReportLine(frame, item, color) {
  const colors = reportChartColors();
  const xs = item.points.map((point) => Math.round(point.time / 1000));
  const ys = item.points.map((point) => point.value);
  const chart = new uPlot({
    width: frame.clientWidth || 520,
    height: 220,
    padding: [12, 14, 4, 8],
    legend: { show: false },
    cursor: { y: false },
    scales: { x: { time: true } },
    axes: [
      { stroke: colors.axis, font: `12px ${colors.font}`, grid: { stroke: colors.grid, width: 1 }, ticks: { stroke: colors.grid },
        values: (_u, splits) => splits.map((value) => TIME_ONLY.format(new Date(value * 1000))) },
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
        values: (_u, splits) => splits.map((value) => (perDay ? DATE_TIME.format(new Date(value * 1000)).slice(0, 5) : TIME_ONLY.format(new Date(value * 1000)))) },
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
    empty.textContent = "Keine Daten im Zeitraum.";
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

function renderDailyReport(report) {
  const price = report.price_ct_kwh || {};
  const statusCounts = report.status_counts || {};
  document.getElementById("daily-report").innerHTML = [
    reportTile("Läufe", report.cycle_count),
    reportTile("Normale Läufe", statusCounts.healthy || 0),
    reportTile("Kommunikationshinweise", report.bacnet_event_count),
    reportTile("Durchschnittspreis", formatNumber(price.average, "ct/kWh", 3)),
    reportTile("Niedrigster Preis", formatNumber(price.min, "ct/kWh", 3)),
    reportTile("Preisfenster", (report.spotmarket_windows || []).length),
  ].join("");
}

function renderRecentCycles(rows) {
  const body = document.getElementById("cycles-body");
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="5">Keine Läufe vorhanden.</td></tr>';
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
    target.innerHTML = `<div class="empty-state">Wetter nicht verfügbar${payload?.error ? `: ${escapeHtml(payload.error)}` : ""}</div>`;
    return;
  }
  const current = payload.current || {};
  target.innerHTML = `
    <div class="weather-now">
      <span class="micro-label">${escapeHtml(payload.site || "Standort")} / ${escapeHtml(payload.source || "Wetter")}</span>
      <strong>${escapeHtml(formatNumber(current.temperature_c, "C", 1))}</strong>
      <span>${escapeHtml(current.weather_label || "-")} / gefühlt ${escapeHtml(formatNumber(current.apparent_temperature_c, "C", 1))}</span>
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

function linePath(points, scaleX, scaleY) {
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${scaleX(point.time).toFixed(1)} ${scaleY(point.value).toFixed(1)}`).join(" ");
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

function buildOperatorMessage(health) {
  if (health.safe_mode_reason) {
    return "Die Anlage ist im sicheren Modus. Bitte den Systemzustand prüfen.";
  }
  const price = formatNumber(health.current_price_ct_kwh, "ct/kWh", 3);
  const slot = health.current_slot_label ? ` für das Zeitfenster ${health.current_slot_label}` : "";
  const tomorrow = health.tomorrow_prices_available ? "Die Preise für morgen sind vorhanden." : "Die Preise für morgen werden noch erwartet.";
  return `Aktueller Strompreis${slot}: ${price}. ${tomorrow}`;
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
  setText("operator-message", "Die Daten konnten nicht geladen werden. Bitte die Verbindung zur lokalen Anlage prüfen.");
  setText("global-status", "Fehler");
  document.getElementById("global-status-dot").className = "status-dot error";
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
