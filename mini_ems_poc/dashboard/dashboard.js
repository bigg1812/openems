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

const appState = {
  availableChannels: DEFAULT_CHANNELS,
  selectedChannels: new Set(VIEW_PRESETS[0].channels),
  savedViews: [],
  statusPayload: null,
  reportStudio: null,
  activeHistories: new Map(),
};

const priceChart = {
  instance: null,
  observer: null,
  target: null,
  points: [],
  options: null,
};

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  appState.savedViews = loadSavedViews();
  bindUi();
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
  document.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", () => {
      document.querySelectorAll(".nav-link").forEach((item) => item.classList.remove("active"));
      link.classList.add("active");
    });
  });
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

async function postJson(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const responsePayload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(responsePayload.message || `${path} returned ${response.status}`);
  }
  return responsePayload;
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

  setText("kpi-price", formatNumber(health.current_price_ct_kwh, "ct/kWh", 3));
  setText("kpi-slot", `Zeitfenster ${health.current_slot_label || "-"}`);
  setText("kpi-spotmarket", formatBool(health.spotmarket_active_now));
  setText("kpi-spotmarket-source", health.spotmarket_active_now ? "Preissteuerung aktiv" : "Normalbetrieb");
  setText("kpi-grid-lockout", health.grid_lockout_active === null || health.grid_lockout_active === undefined ? "deaktiviert" : formatBool(health.grid_lockout_active));
  setText("kpi-grid-state", friendlyState(health.grid_lockout_state || state.grid_lockout?.mode));
  setText("kpi-grid-power", formatNumber(health.grid_active_power_kw, "kW", 2));
  setText("kpi-grid-read", health.grid_read_status ? friendlyState(health.grid_read_status) : "derzeit nicht aktiv");
  setText("spotmarket-summary", buildPriceWindowSummary(health, appState.statusPayload?.spotmarket_plan || {}));
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
  target.innerHTML = '<article class="preview-card">Bericht wird berechnet.</article>';
  try {
    const config = buildReportConfig();
    const payload = await postJson("/api/report/preview", config);
    target.innerHTML = renderReportPreview(payload);
    updateReportLinks();
  } catch (error) {
    target.innerHTML = `<article class="preview-card error"><strong>Fehler</strong><span>${escapeHtml(error.message)}</span></article>`;
  } finally {
    button.disabled = false;
  }
}

function buildReportConfig() {
  const channels = [...document.querySelectorAll("input[name='report-channel']:checked")].map((input) => input.value);
  const sections = [...document.querySelectorAll("input[name='report-section']:checked")].map((input) => ({ component: input.value }));
  return {
    title: document.getElementById("report-title").value.trim() || "Mini EMS Betriebsbericht",
    start: datetimeLocalToIso(document.getElementById("report-start").value),
    end: datetimeLocalToIso(document.getElementById("report-end").value),
    granularity: document.getElementById("report-granularity").value,
    channels,
    sections,
  };
}

function renderReportPreview(report) {
  const sections = Array.isArray(report.sections) ? report.sections : [];
  if (!sections.length) {
    return '<article class="preview-card">Keine Berichtsbausteine vorhanden.</article>';
  }
  return sections.map((section) => {
    const count = section.cards?.length || section.rows?.length || section.series?.reduce((sum, serie) => sum + (serie.points?.length || 0), 0) || 0;
    return `
      <article class="preview-card ready">
        <strong>${escapeHtml(section.title || reportSectionLabel(section.component))}</strong>
        <span>${escapeHtml(reportSectionLabel(section.component))} / ${escapeHtml(count)} Elemente</span>
      </article>
    `;
  }).join("");
}

function updateReportLinks() {
  const config = buildReportConfig();
  const query = new URLSearchParams({
    title: config.title,
    start: config.start,
    end: config.end,
    granularity: config.granularity,
    channels: config.channels.join(","),
    sections: config.sections.map((section) => section.component).join(","),
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
    line_chart: "Diagramme",
    table: "Datentabelle",
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
