const REFRESH_INTERVAL_MS = 15000;
const HOURS_48_MS = 48 * 60 * 60 * 1000;
const PRICE_SLOT_MINUTES = 15;
const SVG_WIDTH = 1200;
const SVG_HEIGHT = 300;
const CHART_MARGIN = { top: 18, right: 18, bottom: 42, left: 62 };
const TIME_FORMATTER = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit" });
const SHORT_DATE_TIME_FORMATTER = new Intl.DateTimeFormat("de-DE", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json();
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

async function refreshDashboard() {
  const [statusPayload, reportPayload] = await Promise.all([
    fetchJson("/api/status"),
    fetchJson("/api/report/daily"),
  ]);

  const referenceNow = getReferenceNow(statusPayload);
  const [gridHistory, priceHistory] = await Promise.all([
    fetchGridHistory(referenceNow),
    fetchPriceHistory(referenceNow, statusPayload),
  ]);

  renderStatus(statusPayload);
  renderWindows(statusPayload.spotmarket_plan || {});
  renderSpotmarketSettings(statusPayload.spotmarket_settings || {});
  renderRecentCycles(statusPayload.recent_cycles || []);
  renderHistoryCharts(statusPayload, gridHistory.rows || [], priceHistory.rows || [], referenceNow);
  renderReport(reportPayload);
}

async function fetchGridHistory(referenceNow) {
  const end = new Date(referenceNow.getTime() + 5 * 60 * 1000);
  const start = new Date(referenceNow.getTime() - HOURS_48_MS);
  const query = new URLSearchParams({
    channel_id: "grid.active_power_kw",
    granularity: "5m",
    start: start.toISOString(),
    end: end.toISOString(),
    limit: "800",
  });
  return fetchJson(`/api/history?${query.toString()}`);
}

async function fetchPriceHistory(referenceNow, statusPayload) {
  const end = new Date(referenceNow.getTime() + 5 * 60 * 1000);
  const start = new Date(getPriceChartRange(referenceNow, statusPayload).startTime);
  const query = new URLSearchParams({
    channel_id: "tariff.current_price_ct_kwh",
    granularity: "raw",
    start: start.toISOString(),
    end: end.toISOString(),
    limit: "1800",
  });
  return fetchJson(`/api/history?${query.toString()}`);
}

function renderStatus(payload) {
  const health = payload.health || {};
  const state = payload.state || {};
  const status = health.status || "-";

  const statusBadge = document.getElementById("status-badge");
  statusBadge.textContent = status;
  statusBadge.className = `status-pill ${status}`;

  setText("current-price", formatNumber(health.current_price_ct_kwh, "ct/kWh"));
  setText("current-slot", `Slot ${health.current_slot_label || "-"}`);
  setText("grid-power", formatNumber(health.grid_active_power_kw, "kW"));
  setText("grid-read-status", health.grid_read_status || "-");
  setText("spotmarket-lockout", formatBool(health.spotmarket_active_now));
  setText("spotmarket-source", health.spotmarket_source || "-");
  setText("grid-lockout", formatBool(health.grid_lockout_active));
  setText("grid-lockout-state", health.grid_lockout_state || state.grid_lockout?.mode || "-");
  setText("operator-message", health.operator_message || "-");
  setText("spotmarket-summary", health.spotmarket_summary || "Keine Spotmarket-Daten");
}

function renderWindows(plan) {
  renderWindowList("windows-today", plan.today?.windows || []);
  renderWindowList("windows-tomorrow", plan.tomorrow?.windows || []);
}

function renderSpotmarketSettings(settings) {
  const select = document.getElementById("negative-hours-select");
  const state = document.getElementById("spotmarket-settings-state");
  if (!select || !state) {
    return;
  }
  const hours = toFiniteNumber(settings.min_consecutive_hours);
  if (Number.isFinite(hours)) {
    setSelectValue(select, hours);
    state.textContent = `Aktiv ab ${formatHours(hours)} (${settings.min_consecutive_quarters || "-"} Slots)`;
  } else {
    state.textContent = "Noch keine Einstellung geladen.";
  }
}

function renderWindowList(targetId, windows) {
  const container = document.getElementById(targetId);
  if (!windows.length) {
    container.innerHTML = '<div class="window-card"><strong>Keine Fenster</strong><span>Aktuell keine negativen Zeitfenster.</span></div>';
    return;
  }
  container.innerHTML = windows.map((window) => `
    <article class="window-card">
      <strong>${window.start_label} - ${window.end_label_exclusive}</strong>
      <span>${window.length_quarters} Viertelstunden</span>
      <span>Min ${formatNumber(window.min_price_ct_kwh, "ct/kWh")} / Max ${formatNumber(window.max_price_ct_kwh, "ct/kWh")}</span>
    </article>
  `).join("");
}

function renderRecentCycles(rows) {
  const body = document.getElementById("cycles-body");
  body.innerHTML = rows.map((row) => `
    <tr>
      <td>${row.cycle_id || "-"}</td>
      <td>${row.status || "-"}</td>
      <td>${row.current_slot_label || "-"}</td>
      <td>${formatNumber(row.current_price_ct_kwh, "ct/kWh")}</td>
      <td>${formatNumber(row.grid_active_power_kw, "kW")}</td>
      <td>${formatTimestamp(row.timestamp)}</td>
    </tr>
  `).join("");
}

function renderHistoryCharts(statusPayload, gridRows, priceRows, referenceNow) {
  const priceTimeline = buildPriceTimeline(statusPayload, priceRows, referenceNow);
  const gridTimeline = buildGridTimeline(gridRows, referenceNow);

  setText(
    "price-history-meta",
    priceTimeline.windows.length
      ? `${priceTimeline.windows.length} BV401-Fenster`
      : "Kein BV401-Fenster",
  );
  setText(
    "grid-history-meta",
    gridTimeline.series.length
      ? `${gridTimeline.series.length} Messpunkte`
      : "Keine 48h-Daten",
  );

  renderTimelineChart("price-history-chart", {
    emptyText: "Keine 48h-Preisdaten vorhanden.",
    unit: "ct/kWh",
    startTime: priceTimeline.startTime,
    endTime: priceTimeline.endTime,
    series: priceTimeline.series,
    step: true,
    showArea: true,
    fillBaselineValue: 0,
    areaClass: "price-area",
    lineClass: "price-line",
    pointClass: "price-point",
    windows: priceTimeline.windows,
    tracker: priceTimeline.tracker,
    stats: [
      { label: "Min", value: formatNumber(priceTimeline.min, "ct/kWh") },
      { label: "Max", value: formatNumber(priceTimeline.max, "ct/kWh") },
      { label: "Jetzt", value: formatNumber(priceTimeline.currentValue, "ct/kWh") },
      { label: "BV401", value: priceTimeline.windowSummary },
    ],
  });

  renderTimelineChart("grid-history-chart", {
    emptyText: "Keine 48h-Historie fuer Netzbezug vorhanden.",
    unit: "kW",
    startTime: gridTimeline.startTime,
    endTime: gridTimeline.endTime,
    series: gridTimeline.series,
    step: false,
    showArea: true,
    fillBaselineValue: 0,
    areaClass: "grid-area",
    lineClass: "grid-line-path",
    pointClass: "grid-point",
    tracker: gridTimeline.tracker,
    stats: [
      { label: "Min", value: formatNumber(gridTimeline.min, "kW") },
      { label: "Max", value: formatNumber(gridTimeline.max, "kW") },
      { label: "Letzter", value: formatNumber(gridTimeline.currentValue, "kW") },
      { label: "Zeitraum", value: "Letzte 48 Stunden" },
    ],
  });
}

function buildPriceTimeline(statusPayload, priceRows, referenceNow) {
  const priceCache = statusPayload.price_cache || {};
  const health = statusPayload.health || {};
  const plan = statusPayload.spotmarket_plan || {};
  const referenceTime = referenceNow.getTime();
  const { startTime, endTime } = getPriceChartRange(referenceNow, statusPayload);
  const historySeries = [...priceRows]
    .reverse()
    .map((row) => ({
      time: parseTimestamp(row.timestamp),
      value: pickHistoryValue(row),
      source: "history",
    }))
    .filter((point) => (
      Number.isFinite(point.time)
      && Number.isFinite(point.value)
      && point.time >= startTime
      && point.time <= referenceTime
    ));
  const futureBySlot = new Map();

  for (const day of [priceCache.today, priceCache.tomorrow]) {
    if (!day || typeof day.date !== "string" || !Array.isArray(day.slots)) {
      continue;
    }
    day.slots.forEach((value, slotIndex) => {
      const time = buildSlotTime(day.date, slotIndex);
      const numericValue = toFiniteNumber(value);
      if (time >= referenceTime && time <= endTime && Number.isFinite(numericValue)) {
        futureBySlot.set(time, {
          time,
          value: numericValue,
          source: "forecast",
        });
      }
    });
  }

  const series = mergeTimelineSeries(historySeries, [...futureBySlot.values()], startTime, endTime);
  const windows = buildWindowBands(plan).filter((window) => window.end > startTime && window.start < endTime);
  const currentValue = toFiniteNumber(health.current_price_ct_kwh);

  return {
    startTime,
    endTime,
    series,
    windows,
    min: minValue(series),
    max: maxValue(series),
    currentValue,
    tracker: {
      time: clamp(referenceNow.getTime(), startTime, endTime),
      value: currentValue,
      label: `Jetzt ${TIME_FORMATTER.format(referenceNow)}`,
      valueText: formatNumber(currentValue, "ct/kWh"),
    },
    windowSummary: windows.length
      ? windows.map((window) => window.rangeLabel).join(", ")
      : "Kein Fenster aktiv",
  };
}

function getPriceChartRange(referenceNow, statusPayload) {
  const todayStart = new Date(referenceNow.getFullYear(), referenceNow.getMonth(), referenceNow.getDate()).getTime();
  if (!hasTomorrowPrices(statusPayload)) {
    return {
      startTime: todayStart - (HOURS_48_MS / 2),
      endTime: todayStart + (HOURS_48_MS / 2),
    };
  }
  return {
    startTime: todayStart,
    endTime: todayStart + HOURS_48_MS,
  };
}

function hasTomorrowPrices(statusPayload) {
  const tomorrow = statusPayload?.price_cache?.tomorrow;
  const availableSlotCount = Number(tomorrow?.available_slot_count ?? 0);
  const foundSlotCount = Number(statusPayload?.price_cache?.price_source_status?.tomorrow_slots_found ?? 0);
  return availableSlotCount > 0 && foundSlotCount > 0;
}

function mergeTimelineSeries(historySeries, forecastSeries, startTime, endTime) {
  const byTime = new Map();
  for (const point of historySeries) {
    byTime.set(point.time, point);
  }
  for (const point of forecastSeries) {
    byTime.set(point.time, point);
  }
  const series = [...byTime.values()]
    .filter((point) => point.time >= startTime && point.time <= endTime)
    .sort((left, right) => left.time - right.time);
  if (!series.length) {
    return [];
  }
  return series;
}

function buildGridTimeline(rows, referenceNow) {
  const series = [...rows]
    .reverse()
    .map((row) => ({
      time: parseTimestamp(row.timestamp),
      value: pickHistoryValue(row),
    }))
    .filter((point) => Number.isFinite(point.time) && Number.isFinite(point.value));

  const currentValue = series.length ? series[series.length - 1].value : null;
  const endTime = referenceNow.getTime();
  return {
    startTime: endTime - HOURS_48_MS,
    endTime,
    series,
    min: minValue(series),
    max: maxValue(series),
    currentValue,
    tracker: {
      time: endTime,
      value: currentValue,
      label: `Jetzt ${TIME_FORMATTER.format(referenceNow)}`,
      valueText: formatNumber(currentValue, "kW"),
    },
  };
}

function buildWindowBands(plan) {
  const bands = [];
  for (const dayKey of ["today", "tomorrow"]) {
    const day = plan[dayKey];
    if (!day || typeof day.date !== "string" || !Array.isArray(day.windows)) {
      continue;
    }
    for (const window of day.windows) {
      const startSlot = Number(window.start_slot);
      const endSlot = Number(window.end_slot_exclusive);
      if (!Number.isFinite(startSlot) || !Number.isFinite(endSlot)) {
        continue;
      }
      bands.push({
        start: buildSlotTime(day.date, startSlot),
        end: buildSlotTime(day.date, endSlot),
        label: "BV401 AN",
        rangeLabel: `${window.start_label}-${window.end_label_exclusive}`,
      });
    }
  }
  return bands;
}

function renderTimelineChart(targetId, config) {
  const container = document.getElementById(targetId);
  const validSeries = config.series.filter((point) => Number.isFinite(point.value));

  if (!validSeries.length) {
    container.innerHTML = `<div class="timeline-chart-empty">${escapeHtml(config.emptyText)}</div>`;
    return;
  }

  const bounds = resolveBounds(validSeries.map((point) => point.value));
  const width = SVG_WIDTH;
  const height = SVG_HEIGHT;
  const plotWidth = width - CHART_MARGIN.left - CHART_MARGIN.right;
  const plotHeight = height - CHART_MARGIN.top - CHART_MARGIN.bottom;
  const scaleX = (time) => CHART_MARGIN.left + (((time - config.startTime) / Math.max(config.endTime - config.startTime, 1)) * plotWidth);
  const scaleY = (value) => CHART_MARGIN.top + plotHeight - (((value - bounds.min) / Math.max(bounds.max - bounds.min, 1e-9)) * plotHeight);
  const seriesEndTime = config.endTime;
  const path = config.step
    ? buildStepPath(config.series, scaleX, scaleY, seriesEndTime)
    : buildLinePath(validSeries, scaleX, scaleY);
  const areaBaselineValue = resolveAreaBaselineValue(bounds, config.fillBaselineValue);
  const areaPath = config.showArea
    ? config.step
      ? buildStepAreaPath(config.series, scaleX, scaleY, seriesEndTime, scaleY(areaBaselineValue))
      : buildLineAreaPath(validSeries, scaleX, scaleY, scaleY(areaBaselineValue))
    : "";

  const zeroLine = bounds.min <= 0 && bounds.max >= 0
    ? `<line class="zero-line" x1="${CHART_MARGIN.left}" y1="${scaleY(0).toFixed(1)}" x2="${(width - CHART_MARGIN.right).toFixed(1)}" y2="${scaleY(0).toFixed(1)}"></line>`
    : "";

  const gridLines = buildYTicks(bounds.min, bounds.max).map((tick) => {
    const y = scaleY(tick);
    return `
      <line class="chart-grid" x1="${CHART_MARGIN.left}" y1="${y.toFixed(1)}" x2="${(width - CHART_MARGIN.right).toFixed(1)}" y2="${y.toFixed(1)}"></line>
      <text class="value-label" x="${(CHART_MARGIN.left - 10).toFixed(1)}" y="${(y + 4).toFixed(1)}" text-anchor="end">${escapeHtml(formatAxisValue(tick))}</text>
    `;
  }).join("");

  const xTicks = buildTimeTicks(config.startTime, config.endTime, 5).map((tick, index, ticks) => {
    const x = scaleX(tick);
    const anchor = index === 0 ? "start" : index === ticks.length - 1 ? "end" : "middle";
    return `<text class="tick-label" x="${x.toFixed(1)}" y="${(height - 10).toFixed(1)}" text-anchor="${anchor}">${escapeHtml(SHORT_DATE_TIME_FORMATTER.format(new Date(tick)))}</text>`;
  }).join("");

  const windowRects = (config.windows || [])
    .filter((window) => window.end > config.startTime && window.start < config.endTime)
    .map((window) => {
      const x = scaleX(Math.max(window.start, config.startTime));
      const endX = scaleX(Math.min(window.end, config.endTime));
      const labelX = x + ((endX - x) / 2);
      return `
        <rect class="chart-window" x="${x.toFixed(1)}" y="${CHART_MARGIN.top}" width="${Math.max(endX - x, 2).toFixed(1)}" height="${plotHeight.toFixed(1)}" rx="10"></rect>
        <text class="chart-window-label" x="${labelX.toFixed(1)}" y="${(CHART_MARGIN.top + 16).toFixed(1)}" text-anchor="middle">${escapeHtml(window.label)}</text>
      `;
    }).join("");

  const tracker = buildTrackerMarkup(config.tracker, scaleX, scaleY, config.startTime, config.endTime, height, bounds, config.pointClass);

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      <line class="axis" x1="${CHART_MARGIN.left}" y1="${(height - CHART_MARGIN.bottom).toFixed(1)}" x2="${(width - CHART_MARGIN.right).toFixed(1)}" y2="${(height - CHART_MARGIN.bottom).toFixed(1)}"></line>
      ${gridLines}
      ${windowRects}
      ${zeroLine}
      ${areaPath ? `<path class="chart-area ${config.areaClass || ""}" d="${areaPath}"></path>` : ""}
      <path class="chart-line ${config.lineClass}" d="${path}"></path>
      ${tracker}
      <g class="hover-layer" style="display: none;">
        <line class="tracker hover-tracker" x1="0" y1="${CHART_MARGIN.top}" x2="0" y2="${(height - CHART_MARGIN.bottom).toFixed(1)}"></line>
        <circle class="current-point ${config.pointClass}" cx="0" cy="0" r="5"></circle>
        <rect class="tracker-callout" x="0" y="0" width="120" height="42" rx="8"></rect>
        <text class="tracker-callout-title" x="0" y="0"></text>
        <text class="tracker-callout-value" x="0" y="0"></text>
      </g>
      <rect class="chart-hover-capture" x="${CHART_MARGIN.left}" y="${CHART_MARGIN.top}" width="${plotWidth}" height="${plotHeight}" fill="transparent"></rect>
      ${xTicks}
    </svg>
    <div class="timeline-chart-footer">
      ${(config.stats || []).map((item) => `
        <article class="timeline-stat">
          <span class="timeline-stat-label">${escapeHtml(item.label)}</span>
          <strong class="timeline-stat-value">${escapeHtml(item.value)}</strong>
        </article>
      `).join("")}
    </div>
  `;
  installTimelineHover(container, {
    bounds,
    endTime: config.endTime,
    pointClass: config.pointClass,
    scaleX,
    scaleY,
    series: validSeries,
    startTime: config.startTime,
    unit: config.unit,
  });
}

function buildTrackerMarkup(tracker, scaleX, scaleY, startTime, endTime, chartHeight, bounds, pointClass) {
  if (!tracker || !Number.isFinite(tracker.time)) {
    return "";
  }
  const clampedTime = clamp(tracker.time, startTime, endTime);
  const x = scaleX(clampedTime);
  const label = tracker.label || "";
  const valueText = tracker.valueText || "";
  const boxWidth = Math.max(label.length, valueText.length, 10) * 7 + 20;
  const boxHeight = valueText ? 42 : 26;
  const boxX = clamp(x - (boxWidth / 2), CHART_MARGIN.left, SVG_WIDTH - CHART_MARGIN.right - boxWidth);
  const boxY = 8;
  let pointMarkup = "";
  if (Number.isFinite(tracker.value) && tracker.value >= bounds.min && tracker.value <= bounds.max) {
    pointMarkup = `<circle class="current-point ${pointClass}" cx="${x.toFixed(1)}" cy="${scaleY(tracker.value).toFixed(1)}" r="6"></circle>`;
  }
  return `
    <line class="tracker" x1="${x.toFixed(1)}" y1="${CHART_MARGIN.top}" x2="${x.toFixed(1)}" y2="${(chartHeight - CHART_MARGIN.bottom).toFixed(1)}"></line>
    <rect class="tracker-callout" x="${boxX.toFixed(1)}" y="${boxY.toFixed(1)}" width="${boxWidth.toFixed(1)}" height="${boxHeight.toFixed(1)}" rx="12"></rect>
    <text class="tracker-callout-title" x="${(boxX + 12).toFixed(1)}" y="${(boxY + 16).toFixed(1)}">${escapeHtml(label)}</text>
    ${valueText ? `<text class="tracker-callout-value" x="${(boxX + 12).toFixed(1)}" y="${(boxY + 33).toFixed(1)}">${escapeHtml(valueText)}</text>` : ""}
    ${pointMarkup}
  `;
}

function buildLinePath(series, scaleX, scaleY) {
  return series
    .map((point, index) => `${index === 0 ? "M" : "L"} ${scaleX(point.time).toFixed(1)} ${scaleY(point.value).toFixed(1)}`)
    .join(" ");
}

function buildStepPath(series, scaleX, scaleY, endTime) {
  let path = "";
  let segmentOpen = false;

  for (let index = 0; index < series.length; index += 1) {
    const point = series[index];
    const value = point.value;
    if (!Number.isFinite(value)) {
      segmentOpen = false;
      continue;
    }

    const nextPoint = series[index + 1];
    const nextTime = nextPoint ? nextPoint.time : Math.min(point.time + PRICE_SLOT_MINUTES * 60 * 1000, endTime);
    const x = scaleX(point.time);
    const y = scaleY(value);
    const endX = scaleX(nextTime);

    if (!segmentOpen) {
      path += `M ${x.toFixed(1)} ${y.toFixed(1)} `;
      segmentOpen = true;
    } else {
      path += `L ${x.toFixed(1)} ${y.toFixed(1)} `;
    }

    path += `H ${endX.toFixed(1)} `;

    if (nextPoint && Number.isFinite(nextPoint.value)) {
      path += `V ${scaleY(nextPoint.value).toFixed(1)} `;
    } else {
      segmentOpen = false;
    }
  }

  return path.trim();
}

function buildLineAreaPath(series, scaleX, scaleY, baselineY) {
  if (!series.length) {
    return "";
  }
  const firstX = scaleX(series[0].time);
  const lastX = scaleX(series[series.length - 1].time);
  return `M ${firstX.toFixed(1)} ${baselineY.toFixed(1)} L ${buildLinePath(series, scaleX, scaleY).slice(2)} L ${lastX.toFixed(1)} ${baselineY.toFixed(1)} Z`;
}

function buildStepAreaPath(series, scaleX, scaleY, endTime, baselineY) {
  let path = "";
  let segmentOpen = false;
  let segmentStartX = null;

  for (let index = 0; index < series.length; index += 1) {
    const point = series[index];
    if (!Number.isFinite(point.value)) {
      if (segmentOpen) {
        path += `L ${scaleX(series[index - 1].time).toFixed(1)} ${baselineY.toFixed(1)} Z `;
      }
      segmentOpen = false;
      segmentStartX = null;
      continue;
    }
    const nextPoint = series[index + 1];
    const nextTime = nextPoint ? nextPoint.time : Math.min(point.time + PRICE_SLOT_MINUTES * 60 * 1000, endTime);
    const endX = scaleX(nextTime);
    const y = scaleY(point.value);

    if (!segmentOpen) {
      const startX = scaleX(point.time);
      segmentStartX = startX;
      path += `M ${startX.toFixed(1)} ${baselineY.toFixed(1)} L ${startX.toFixed(1)} ${y.toFixed(1)} `;
      segmentOpen = true;
    }

    path += `H ${endX.toFixed(1)} `;
    if (nextPoint && Number.isFinite(nextPoint.value)) {
      path += `V ${scaleY(nextPoint.value).toFixed(1)} `;
    } else {
      path += `L ${endX.toFixed(1)} ${baselineY.toFixed(1)} L ${segmentStartX.toFixed(1)} ${baselineY.toFixed(1)} Z `;
      segmentOpen = false;
      segmentStartX = null;
    }
  }

  return path.trim();
}

function installTimelineHover(container, config) {
  const svg = container.querySelector("svg");
  const capture = container.querySelector(".chart-hover-capture");
  const layer = container.querySelector(".hover-layer");
  if (!svg || !capture || !layer || !config.series.length) {
    return;
  }

  const trackerLine = layer.querySelector(".hover-tracker");
  const point = layer.querySelector("circle");
  const box = layer.querySelector("rect");
  const title = layer.querySelector(".tracker-callout-title");
  const value = layer.querySelector(".tracker-callout-value");

  capture.addEventListener("mousemove", (event) => {
    const svgPoint = svg.createSVGPoint();
    svgPoint.x = event.clientX;
    svgPoint.y = event.clientY;
    const cursor = svgPoint.matrixTransform(svg.getScreenCTM().inverse());
    const cursorRatio = (cursor.x - CHART_MARGIN.left) / Math.max(SVG_WIDTH - CHART_MARGIN.left - CHART_MARGIN.right, 1);
    const cursorTime = config.startTime + (clamp(cursorRatio, 0, 1) * (config.endTime - config.startTime));
    const nearest = nearestTimelinePoint(config.series, cursorTime);
    if (!nearest) {
      layer.style.display = "none";
      return;
    }

    const x = config.scaleX(nearest.time);
    const y = config.scaleY(nearest.value);
    const label = SHORT_DATE_TIME_FORMATTER.format(new Date(nearest.time));
    const valueText = formatNumber(nearest.value, config.unit || "");
    const boxWidth = Math.max(label.length, valueText.length, 12) * 7 + 22;
    const boxHeight = 42;
    const boxX = clamp(x + 10, CHART_MARGIN.left, SVG_WIDTH - CHART_MARGIN.right - boxWidth);
    const boxY = clamp(y - 52, 4, SVG_HEIGHT - CHART_MARGIN.bottom - boxHeight);

    layer.style.display = "";
    trackerLine.setAttribute("x1", x.toFixed(1));
    trackerLine.setAttribute("x2", x.toFixed(1));
    point.setAttribute("cx", x.toFixed(1));
    point.setAttribute("cy", y.toFixed(1));
    box.setAttribute("x", boxX.toFixed(1));
    box.setAttribute("y", boxY.toFixed(1));
    box.setAttribute("width", boxWidth.toFixed(1));
    box.setAttribute("height", boxHeight.toFixed(1));
    title.setAttribute("x", (boxX + 12).toFixed(1));
    title.setAttribute("y", (boxY + 16).toFixed(1));
    title.textContent = label;
    value.setAttribute("x", (boxX + 12).toFixed(1));
    value.setAttribute("y", (boxY + 33).toFixed(1));
    value.textContent = valueText;
  });
  capture.addEventListener("mouseleave", () => {
    layer.style.display = "none";
  });
}

function nearestTimelinePoint(series, time) {
  let nearest = null;
  let nearestDistance = Number.POSITIVE_INFINITY;
  for (const point of series) {
    const distance = Math.abs(point.time - time);
    if (distance < nearestDistance) {
      nearest = point;
      nearestDistance = distance;
    }
  }
  return nearest;
}

function buildYTicks(min, max) {
  const ticks = [];
  const stepCount = 4;
  for (let index = 0; index <= stepCount; index += 1) {
    ticks.push(min + (((max - min) / stepCount) * index));
  }
  return ticks;
}

function buildTimeTicks(startTime, endTime, count) {
  const ticks = [];
  for (let index = 0; index < count; index += 1) {
    const ratio = count === 1 ? 0 : index / (count - 1);
    ticks.push(startTime + ((endTime - startTime) * ratio));
  }
  return ticks;
}

function resolveBounds(values) {
  let min = Math.min(...values);
  let max = Math.max(...values);

  if (min === max) {
    const padding = min === 0 ? 1 : Math.abs(min) * 0.15;
    min -= padding;
    max += padding;
  } else {
    const padding = (max - min) * 0.08;
    min -= padding;
    max += padding;
  }

  return { min, max };
}

function resolveAreaBaselineValue(bounds, baselineValue) {
  if (Number.isFinite(baselineValue) && baselineValue >= bounds.min && baselineValue <= bounds.max) {
    return baselineValue;
  }
  return bounds.min;
}

function minValue(series) {
  const values = series.map((point) => point.value).filter((value) => Number.isFinite(value));
  return values.length ? Math.min(...values) : null;
}

function maxValue(series) {
  const values = series.map((point) => point.value).filter((value) => Number.isFinite(value));
  return values.length ? Math.max(...values) : null;
}

function renderReport(report) {
  setText("report-date", report.date || "-");
  const summary = document.getElementById("report-summary");
  const statusCounts = report.status_counts || {};
  summary.innerHTML = [
    reportCard("Zyklen", report.cycle_count),
    reportCard("BACnet Events", report.bacnet_event_count),
    reportCard("Grid Mittelwert", formatNumber(report.grid_active_power_kw?.average, "kW")),
    reportCard("Preis Mittelwert", formatNumber(report.price_ct_kwh?.average, "ct/kWh")),
    reportCard("healthy", statusCounts.healthy || 0),
    reportCard("degraded", statusCounts.degraded || 0),
    reportCard("safe_mode", statusCounts.safe_mode || 0),
    reportCard("Fenster", (report.spotmarket_windows || []).length),
  ].join("");

  const eventsBody = document.getElementById("report-events");
  eventsBody.innerHTML = (report.recent_bacnet_events || []).map((event) => `
    <tr>
      <td>${formatTimestamp(event.timestamp)}</td>
      <td>${event.channel_id || "-"}</td>
      <td>${event.event_type || "-"}</td>
      <td>${event.severity || "-"}</td>
      <td>${event.message || "-"}</td>
    </tr>
  `).join("");
}

function reportCard(label, value) {
  return `<article class="report-item"><span>${label}</span><strong>${value ?? "-"}</strong></article>`;
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (!element) {
    return;
  }
  element.textContent = value ?? "-";
}

function formatBool(value) {
  if (value === true || value === 1) {
    return "AN";
  }
  if (value === false || value === 0) {
    return "AUS";
  }
  return "-";
}

function formatNumber(value, unit, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${Number(value).toFixed(digits)} ${unit}`;
}

function formatAxisValue(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  const absolute = Math.abs(Number(value));
  const digits = absolute >= 10 ? 0 : absolute >= 1 ? 1 : 2;
  return Number(value).toFixed(digits);
}

function formatTimestamp(value) {
  if (!value) {
    return "-";
  }
  return String(value).replace("T", " ").replace("Z", " UTC");
}

function parseTimestamp(value) {
  if (!value) {
    return Number.NaN;
  }
  const parsed = new Date(value);
  return parsed.getTime();
}

function buildSlotTime(dateIso, slotIndex) {
  const date = new Date(`${dateIso}T00:00:00`);
  date.setMinutes(date.getMinutes() + (slotIndex * PRICE_SLOT_MINUTES));
  return date.getTime();
}

function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0);
}

function getReferenceNow(payload) {
  for (const candidate of [payload?.price_cache?.last_update_at, payload?.health?.timestamp]) {
    const parsed = new Date(candidate);
    if (Number.isFinite(parsed.getTime())) {
      return parsed;
    }
  }
  return new Date();
}

function pickHistoryValue(row) {
  for (const key of ["average_value", "last_value", "value"]) {
    const parsed = toFiniteNumber(row[key]);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return Number.NaN;
}

function toFiniteNumber(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function runDiagnostic() {
  const output = document.getElementById("diagnostic-output");
  output.textContent = "Diagnose laeuft...";
  try {
    const payload = await fetchJson("/api/diagnostics/read?channel_id=grid.active_power_kw&samples=3");
    output.textContent = JSON.stringify(payload, null, 2);
  } catch (error) {
    output.textContent = `Diagnose fehlgeschlagen: ${error.message}`;
  }
}

async function saveSpotmarketSettings(event) {
  event.preventDefault();
  const select = document.getElementById("negative-hours-select");
  const state = document.getElementById("spotmarket-settings-state");
  const button = document.getElementById("spotmarket-settings-save");
  const hours = Number(select.value);
  if (!Number.isFinite(hours) || hours <= 0) {
    state.textContent = "Bitte eine gueltige Dauer waehlen.";
    return;
  }

  button.disabled = true;
  state.textContent = "Speichere...";
  try {
    const settings = await postJson("/api/config/spotmarket-lockout", {
      min_consecutive_hours: hours,
    });
    renderSpotmarketSettings(settings);
    await refreshDashboard();
    state.textContent = `Gespeichert: ${formatHours(settings.min_consecutive_hours)} ab naechstem Zyklus.`;
  } catch (error) {
    state.textContent = `Speichern fehlgeschlagen: ${error.message}`;
  } finally {
    button.disabled = false;
  }
}

function setSelectValue(select, value) {
  const normalized = String(Number(value));
  const existing = [...select.options].find((option) => Number(option.value) === Number(value));
  if (!existing) {
    const option = document.createElement("option");
    option.value = normalized;
    option.textContent = formatHours(value);
    select.appendChild(option);
  }
  select.value = existing ? existing.value : normalized;
}

function formatHours(value) {
  const hours = Number(value);
  if (!Number.isFinite(hours)) {
    return "-";
  }
  if (hours === 1) {
    return "1 Stunde";
  }
  return `${hours.toLocaleString("de-DE", { maximumFractionDigits: 2 })} Stunden`;
}

document.getElementById("refresh-button").addEventListener("click", refreshDashboard);
document.getElementById("diagnostic-button").addEventListener("click", runDiagnostic);
document.getElementById("spotmarket-settings-form").addEventListener("submit", saveSpotmarketSettings);

refreshDashboard().catch((error) => {
  document.getElementById("operator-message").textContent = `Dashboard-Fehler: ${error.message}`;
});
setInterval(() => {
  refreshDashboard().catch((error) => {
    document.getElementById("operator-message").textContent = `Dashboard-Fehler: ${error.message}`;
  });
}, REFRESH_INTERVAL_MS);
