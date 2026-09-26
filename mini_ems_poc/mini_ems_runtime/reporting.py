"""HTML presentation and German labels; no database access or plant I/O."""
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Dict, Optional

from .price_time import to_berlin


def render_report_html(report: dict, overview: dict, template_path: Optional[Path] = None) -> str:
    # Optional source-install extension. The release profile uses the stdlib renderer.
    if template_path is not None:
        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape
        except ImportError:
            pass
        else:
            environment = Environment(
                loader=FileSystemLoader(str(template_path.parent)),
                autoescape=select_autoescape(["html", "xml"], default=True),
            )
            return environment.get_template(template_path.name).render(report=report, overview=overview)
    return _render_html(report, overview)


_REPORT_STYLES = """
    :root {
      --ink: #1c2530;
      --muted: #667485;
      --line: #dce3ea;
      --line-soft: #e8edf2;
      --panel: #ffffff;
      --soft: #f7f9fb;
      --accent: #3b6ea5;
      --good: #3f7a5f;
      --warn: #b07a1e;
      --bad: #b0463c;
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; }
    body {
      background: #eef2f6;
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      font-size: 12px;
      line-height: 1.5;
    }
    .report {
      width: min(820px, 100%);
      margin: 0 auto;
      padding: 24px;
    }
    .eyebrow {
      display: block;
      color: var(--muted);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.09em;
      text-transform: uppercase;
    }
    h1 { margin: 6px 0 0; font-size: 26px; font-weight: 650; letter-spacing: -0.01em; }
    h2 { margin: 0 0 12px; font-size: 15px; font-weight: 650; }
    h3 { margin: 0 0 8px; font-size: 12px; font-weight: 650; color: var(--muted); }
    p { margin: 0; }
    .muted { color: var(--muted); }
    .cover {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 24px;
      padding: 22px 24px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
    }
    .cover-sub { margin-top: 4px; color: var(--muted); font-size: 13px; }
    .cover-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 20px 32px;
      margin: 18px 0 0;
    }
    .cover-meta div { min-width: 120px; }
    .cover-meta dt {
      margin: 0;
      color: var(--muted);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .cover-meta dd { margin: 3px 0 0; font-weight: 600; }
    .cover-status {
      flex: 0 0 auto;
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 4px;
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--soft);
      min-width: 150px;
    }
    .status-dot {
      width: 10px; height: 10px; border-radius: 50%;
      background: var(--muted);
    }
    .status-good .status-dot { background: var(--good); }
    .status-warn .status-dot { background: var(--warn); }
    .status-bad .status-dot { background: var(--bad); }
    .status-label { font-size: 14px; font-weight: 650; }
    .status-good .status-label { color: var(--good); }
    .status-warn .status-label { color: var(--warn); }
    .status-bad .status-label { color: var(--bad); }
    .status-hint { color: var(--muted); font-size: 10px; }
    .message {
      margin-top: 14px;
      padding: 16px 20px;
      border: 1px solid var(--line);
      border-left: 3px solid var(--accent);
      border-radius: 8px;
      background: var(--panel);
    }
    .message-text { margin-top: 5px; font-size: 15px; font-weight: 550; }
    .block {
      margin-top: 14px;
      padding: 18px 20px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
      page-break-inside: avoid;
      break-inside: avoid;
    }
    .kpi-row {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .kpi {
      padding: 12px 14px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: var(--soft);
    }
    .kpi-label {
      display: block;
      color: var(--muted);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }
    .kpi-value { display: block; margin-top: 8px; font-size: 20px; font-weight: 650; line-height: 1.1; }
    .kpi-note { display: block; margin-top: 5px; color: var(--muted); font-size: 11px; }
    .status-list { list-style: none; margin: 14px 0 0; padding: 0; }
    .status-list li {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 7px 0;
      border-top: 1px solid var(--line-soft);
      font-weight: 550;
    }
    .status-list .count { margin-left: auto; font-weight: 650; }
    .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--muted); }
    .dot-good { background: var(--good); }
    .dot-warn { background: var(--warn); }
    .dot-bad { background: var(--bad); }
    .block-note { margin-top: 12px; color: var(--muted); font-size: 11px; }
    .chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
    .chip {
      padding: 4px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--soft);
      font-variant-numeric: tabular-nums;
      font-size: 11px;
    }
    table { width: 100%; border-collapse: collapse; }
    table.events { margin-top: 12px; }
    th, td {
      border-bottom: 1px solid var(--line-soft);
      padding: 7px 6px;
      text-align: left;
      font-size: 11px;
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    td.time, td.sev { white-space: nowrap; color: var(--muted); }
    td.value { text-align: right; font-weight: 600; white-space: nowrap; }
    .chart-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .chart-card {
      padding: 12px 14px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: var(--panel);
      page-break-inside: avoid;
      break-inside: avoid;
    }
    .chart-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 11px;
    }
    .chart {
      width: 100%;
      height: 130px;
      border: 1px solid var(--line-soft);
      background: var(--soft);
    }
    .empty {
      padding: 16px;
      border: 1px dashed var(--line);
      border-radius: 6px;
      color: var(--muted);
    }
    .appendix {
      margin-top: 20px;
      padding: 18px 20px;
      border: 1px solid var(--line-soft);
      border-radius: 10px;
      background: var(--soft);
      page-break-before: auto;
    }
    .appendix-label {
      display: block;
      color: var(--muted);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.09em;
      text-transform: uppercase;
    }
    .appendix-note { margin: 6px 0 4px; color: var(--muted); font-size: 11px; }
    .appendix-part { margin-top: 16px; page-break-inside: avoid; break-inside: avoid; }
    .cards {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    .card {
      padding: 12px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: var(--panel);
      page-break-inside: avoid;
      break-inside: avoid;
    }
    .card-group {
      display: block;
      color: var(--muted);
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .card-title { display: block; margin-top: 6px; font-weight: 650; }
    .card-metric { display: block; margin-top: 8px; font-size: 18px; font-weight: 650; line-height: 1; }
    .card-metric small { color: var(--muted); font-size: 11px; font-weight: 500; }
    .card-meta { margin-top: 7px; color: var(--muted); font-size: 10px; }
    table.data { margin-top: 6px; }
    .report-footer {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      margin-top: 22px;
      padding-top: 12px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 10px;
    }
    @page { size: A4; margin: 16mm 14mm; }
    @media print {
      body { background: #ffffff; }
      .report { width: 100%; padding: 0; }
      .cover, .block, .appendix, .message { break-inside: avoid; }
      .appendix { page-break-before: always; }
      .report-footer { page-break-inside: avoid; }
    }
    @media (max-width: 760px) {
      .cover { flex-direction: column; }
      .kpi-row, .chart-grid, .cards { grid-template-columns: 1fr; }
      .report-footer { flex-direction: column; gap: 4px; }
    }
"""


def _render_html(report: Dict[str, object], overview: Optional[Dict[str, object]] = None) -> str:
    overview = overview or {}
    cover = _render_report_cover(overview)
    message = _render_report_main_message(overview)
    summary_block = _render_report_operations_summary(overview)
    price_block = _render_report_price_block(overview)
    grid_block = _render_report_grid_block(overview)
    events_block = _render_report_events_block(overview)
    charts_block = _render_report_charts(report)
    appendix = "\n".join(_render_report_section_fallback(section) for section in report.get("sections", []))
    title = escape(str(overview.get("title") or report.get("title") or "Tagesbericht"))
    return """<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
{styles}
  </style>
</head>
<body>
  <main class="report">
    {cover}
    {message}
    {summary}
    {price}
    {grid}
    {events}
    {charts}
    <section class="appendix">
      <span class="appendix-label">Technischer Anhang</span>
      <p class="appendix-note">Dieser Abschnitt enthält die zugrunde liegenden Messwerte für die technische Nachvollziehbarkeit.</p>
      {appendix}
    </section>
    <footer class="report-footer">
      <span>Mini EMS Betriebsbericht</span>
      <span>Bei fehlendem PDF-Renderer kann diese Ansicht im Browser über Drucken / Als PDF speichern exportiert werden.</span>
    </footer>
  </main>
</body>
</html>
""".format(
        title=title,
        styles=_REPORT_STYLES,
        cover=cover,
        message=message,
        summary=summary_block,
        price=price_block,
        grid=grid_block,
        events=events_block,
        charts=charts_block,
        appendix=appendix or "<p class='muted'>Keine Detaildaten für diese Auswahl.</p>",
    )


def _render_report_cover(overview: Dict[str, object]) -> str:
    # Ampellogik nur funktional: aus den Zustandszeilen des Tages ableiten.
    status_lines = overview.get("status_lines", []) or []
    labels = {str(line.get("label")): int(line.get("count") or 0) for line in status_lines}
    if labels.get("Sicherer Modus"):
        tone = "bad"
    elif labels.get("Eingeschränkter Betrieb"):
        tone = "warn"
    else:
        tone = "good"
    tone_label = {"good": "Normalbetrieb", "warn": "Eingeschränkter Betrieb", "bad": "Sicherer Modus"}[tone]
    return (
        "<header class='cover'>"
        "<div class='cover-main'>"
        "<span class='eyebrow'>Mini EMS &middot; Betriebsbericht</span>"
        "<h1>{title}</h1>"
        "<p class='cover-sub'>{location}</p>"
        "<dl class='cover-meta'>"
        "<div><dt>Berichtstag</dt><dd>{date}</dd></div>"
        "<div><dt>Zeitraum</dt><dd>{period}</dd></div>"
        "<div><dt>Erstellt</dt><dd>{generated}</dd></div>"
        "</dl>"
        "</div>"
        "<div class='cover-status status-{tone}'>"
        "<span class='status-dot'></span>"
        "<span class='status-label'>{tone_label}</span>"
        "<span class='status-hint'>Betriebsstatus des Tages</span>"
        "</div>"
        "</header>"
    ).format(
        title=escape(str(overview.get("title") or "Tagesbericht")),
        location=escape(str(overview.get("location") or "")),
        date=escape(str(overview.get("date_label") or "kein Datum")),
        period=escape(str(overview.get("period_label") or "")),
        generated=escape(str(overview.get("generated_label") or "")),
        tone=tone,
        tone_label=escape(tone_label),
    )


def _render_report_main_message(overview: Dict[str, object]) -> str:
    message = overview.get("main_message")
    if not message:
        return ""
    return (
        "<section class='message'>"
        "<span class='eyebrow'>Hauptbotschaft</span>"
        "<p class='message-text'>{0}</p>"
        "</section>"
    ).format(escape(str(message)))


def _render_report_kpi(label: str, value: str, note: str) -> str:
    return (
        "<article class='kpi'>"
        "<span class='kpi-label'>{0}</span>"
        "<strong class='kpi-value'>{1}</strong>"
        "<span class='kpi-note'>{2}</span>"
        "</article>"
    ).format(escape(label), escape(value), escape(note))


def _render_report_operations_summary(overview: Dict[str, object]) -> str:
    cycle_count = int(overview.get("cycle_count") or 0)
    status_lines = overview.get("status_lines", []) or []
    if status_lines:
        rows = "".join(
            "<li><span class='dot dot-{tone}'></span>{label}<span class='count'>{count}</span></li>".format(
                tone=_status_line_tone(str(line.get("label"))),
                label=escape(str(line.get("label"))),
                count=int(line.get("count") or 0),
            )
            for line in status_lines
        )
        breakdown = "<ul class='status-list'>{0}</ul>".format(rows)
    else:
        breakdown = "<p class='muted'>Für diesen Tag liegen noch keine Läufe vor.</p>"
    return (
        "<section class='block'>"
        "<h2>Betriebszusammenfassung</h2>"
        "<div class='kpi-row'>{kpi}</div>"
        "{breakdown}"
        "</section>"
    ).format(
        kpi=_render_report_kpi("Läufe heute", str(cycle_count), "Ausgeführte Steuerungszyklen"),
        breakdown=breakdown,
    )


def _status_line_tone(label: str) -> str:
    if label == "Sicherer Modus":
        return "bad"
    if label == "Eingeschränkter Betrieb":
        return "warn"
    if label == "Normalbetrieb":
        return "good"
    return "warn"


def _render_report_price_block(overview: Dict[str, object]) -> str:
    price = overview.get("price", {}) or {}
    windows = overview.get("windows", []) or []
    kpis = (
        _render_report_kpi("Tagesmittel", _format_price(price.get("average")), "Mittlerer Börsenstrompreis")
        + _render_report_kpi("Günstigster Preis", _format_price(price.get("min")), "Niedrigster Viertelstundenpreis")
        + _render_report_kpi("Höchster Preis", _format_price(price.get("max")), "Höchster Viertelstundenpreis")
    )
    if windows:
        window_html = "<div class='chips'>{0}</div>".format(
            "".join("<span class='chip'>{0}</span>".format(escape(str(window))) for window in windows)
        )
        window_block = "<p class='block-note'>Geplante Preisfenster ({0}):</p>{1}".format(len(windows), window_html)
    else:
        window_block = "<p class='block-note'>Für diesen Tag wurden keine Preisfenster geplant.</p>"
    return (
        "<section class='block'>"
        "<h2>Strompreis</h2>"
        "<div class='kpi-row'>{kpis}</div>"
        "{windows}"
        "</section>"
    ).format(kpis=kpis, windows=window_block)


def _render_report_grid_block(overview: Dict[str, object]) -> str:
    grid = overview.get("grid", {}) or {}
    kpis = (
        _render_report_kpi("Mittlere Leistung", _format_power(grid.get("average")), "Durchschnitt am Netzanschluss")
        + _render_report_kpi("Niedrigste Leistung", _format_power(grid.get("min")), "Minimum des Tages")
        + _render_report_kpi("Höchste Leistung", _format_power(grid.get("max")), "Maximum des Tages")
    )
    return (
        "<section class='block'>"
        "<h2>Netzleistung</h2>"
        "<div class='kpi-row'>{kpis}</div>"
        "</section>"
    ).format(kpis=kpis)


def _render_report_events_block(overview: Dict[str, object]) -> str:
    count = int(overview.get("event_count") or 0)
    events = overview.get("events", []) or []
    if count == 0:
        body = "<p class='muted'>Keine Kommunikationshinweise an diesem Tag.</p>"
    else:
        rows = "".join(
            "<tr><td class='time'>{time}</td><td class='sev'>{sev}</td><td>{msg}</td></tr>".format(
                time=escape(str(event.get("time") or "--:--")),
                sev=escape(str(event.get("severity") or "Hinweis")),
                msg=escape(str(event.get("message") or "")),
            )
            for event in events
        )
        note = "" if count <= len(events) else "<p class='block-note'>Angezeigt werden die letzten {0} von {1} Meldungen.</p>".format(len(events), count)
        body = "<table class='events'><thead><tr><th>Zeit</th><th>Status</th><th>Meldung</th></tr></thead><tbody>{0}</tbody></table>{1}".format(rows, note)
    return (
        "<section class='block'>"
        "<h2>Kommunikationshinweise</h2>"
        "<p class='block-note'>Meldungen aus dem Datenaustausch mit der Anlage: {count}.</p>"
        "{body}"
        "</section>"
    ).format(count=count, body=body)


def _render_report_charts(report: Dict[str, object]) -> str:
    cards = []
    for section in report.get("sections", []):
        if section.get("component") != "line_chart":
            continue
        for serie in section.get("series", []):
            cards.append(_render_report_series_card(serie))
    if not cards:
        return ""
    return (
        "<section class='block charts'>"
        "<h2>Verlaufsdiagramme</h2>"
        "<div class='chart-grid'>{0}</div>"
        "</section>"
    ).format("".join(cards))


def _render_report_section_fallback(section: Dict[str, object]) -> str:
    title = escape(str(section.get("title", "")))
    component = section.get("component")
    if component == "summary":
        cards = "".join(
            "<article class='card {0}'><span class='card-group'>{1}</span><span class='card-title'>{2}</span><strong class='card-metric'>{3} <small>{4}</small></strong><p class='card-meta'>{5}; {6}</p><p class='card-meta'>{7} Messpunkte</p></article>".format(
                "energy" if card.get("kind") == "energy_counter" else "",
                escape(str(card.get("group") or "EMS")),
                escape(str(card["label"])),
                _format_report_number(card.get("display_value")),
                escape(str(card.get("unit") or "")),
                escape(str(card.get("display_label") or "")),
                escape(str(card.get("detail") or "")),
                escape(str(card.get("sample_count") or 0)),
            )
            for card in section.get("cards", [])
        )
        return "<div class='appendix-part'><h3>{0}</h3><div class='cards'>{1}</div></div>".format(title, cards)
    if component == "line_chart":
        charts = "".join(_render_report_series_card(serie) for serie in section.get("series", []))
        if not charts:
            charts = "<div class='empty'>Keine Diagrammdaten für diese Auswahl.</div>"
        return "<div class='appendix-part'><h3>{0}</h3><div class='chart-grid'>{1}</div></div>".format(title, charts)
    rows = section.get("rows", [])
    header = "<tr><th>Zeit</th><th>Datenpunkt</th><th>Wert</th><th>Details</th></tr>"
    body = "".join(
        "<tr><td>{0}</td><td>{1}</td><td class='value'>{2}</td><td>{3}</td></tr>".format(
            escape(str(row.get("timestamp", ""))),
            escape(str(row.get("label") or "Anlage")),
            escape(_format_report_number(row.get("value"))),
            escape(str(row.get("message") or row.get("event_type") or row.get("unit") or "")),
        )
        for row in rows
    )
    if not body:
        body = "<tr><td colspan='4' class='muted'>Keine Einträge im gewählten Zeitraum.</td></tr>"
    return "<div class='appendix-part'><h3>{0}</h3><table class='data'>{1}{2}</table></div>".format(title, header, body)


def _render_report_series_card(serie: Dict[str, object]) -> str:
    points = [point for point in serie.get("points", []) if point.get("value") is not None]
    label = escape(str(serie.get("label") or "Datenpunkt"))
    unit = escape(str(serie.get("unit") or ""))
    if not points:
        chart = "<div class='empty'>Kein Messwert im gewählten Zeitraum.</div>"
        meta = ""
    else:
        width = 520
        height = 150
        values = [float(point["value"]) for point in points]
        min_value = min(values)
        max_value = max(values)
        span = max(max_value - min_value, 1e-9)
        step = width / max(len(points) - 1, 1)
        polyline = " ".join(
            "{0:.1f},{1:.1f}".format(
                point_index * step,
                132 - (((float(point["value"]) - min_value) / span) * 112),
            )
            for point_index, point in enumerate(points)
        )
        stroke = "#3f7a5f" if str(serie.get("unit") or "") == "kWh" else "#3b6ea5"
        chart = "<svg class='chart' viewBox='0 0 {0} {1}' preserveAspectRatio='none' role='img'><line x1='0' y1='132' x2='{0}' y2='132' stroke='#d7ddE4'></line><polyline fill='none' stroke='{2}' stroke-width='2' points='{3}'></polyline></svg>".format(width, height, stroke, polyline)
        meta = "<p class='card-meta'>Min {0} / Max {1}</p>".format(_format_report_number(min_value), _format_report_number(max_value))
    return "<article class='chart-card'><div class='chart-head'><strong>{0}</strong><span>{1}</span></div>{2}{3}</article>".format(label, unit, chart, meta)


def _format_report_number(value: object) -> str:
    if value is None:
        return "-"
    try:
        return "{0:.2f}".format(float(value))
    except (TypeError, ValueError):
        return str(value)


_MONTHS_DE = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)


def _parse_report_timestamp(value: object) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return to_berlin(parsed)


def _format_date_de(date_iso: object) -> str:
    parsed = _parse_report_timestamp("{0}T00:00:00Z".format(str(date_iso)[:10]))
    if parsed is None:
        return str(date_iso or "kein Datum")
    return "{0}. {1} {2}".format(parsed.day, _MONTHS_DE[parsed.month - 1], parsed.year)


def _format_datetime_de(value: object) -> str:
    parsed = _parse_report_timestamp(value)
    if parsed is None:
        return "kein Zeitpunkt"
    return "{0}. {1} {2}, {3:02d}:{4:02d} Uhr".format(
        parsed.day, _MONTHS_DE[parsed.month - 1], parsed.year, parsed.hour, parsed.minute
    )


def _format_time_de(value: object) -> str:
    parsed = _parse_report_timestamp(value)
    if parsed is None:
        return "--:--"
    return "{0:02d}:{1:02d} Uhr".format(parsed.hour, parsed.minute)


def _format_period_de(start: object, end: object) -> str:
    start_parsed = _parse_report_timestamp(start)
    end_parsed = _parse_report_timestamp(end)
    if start_parsed is None or end_parsed is None:
        return "Zeitraum nicht bekannt"
    total_seconds = (end_parsed - start_parsed).total_seconds()
    # Ganztags-Bericht: rund ein Tag zwischen Tagesgrenzen -> ohne verwirrende Uhrzeit.
    spans_full_day = 23 * 3600 <= total_seconds <= 24 * 3600 + 3600
    same_clock = (start_parsed.hour, start_parsed.minute) == (end_parsed.hour, end_parsed.minute)
    if spans_full_day and same_clock:
        return "{0}, ganztägig".format(_format_date_de(start_parsed.date().isoformat()))
    if start_parsed.date() == end_parsed.date():
        return "{0}, {1:02d}:{2:02d}-{3:02d}:{4:02d} Uhr".format(
            _format_date_de(start_parsed.date().isoformat()),
            start_parsed.hour,
            start_parsed.minute,
            end_parsed.hour,
            end_parsed.minute,
        )
    return "{0} bis {1}".format(
        _format_datetime_de(start_parsed.isoformat()),
        _format_datetime_de(end_parsed.isoformat()),
    )


def _format_price(value: object) -> str:
    if value is None:
        return "kein Messwert"
    try:
        return "{0:.2f} ct/kWh".format(float(value))
    except (TypeError, ValueError):
        return "kein Messwert"


def _format_power(value: object) -> str:
    if value is None:
        return "kein Messwert"
    try:
        return "{0:.1f} kW".format(float(value))
    except (TypeError, ValueError):
        return "kein Messwert"


def _report_location_name(normalized: Dict[str, object]) -> str:
    location = str(normalized.get("location") or normalized.get("site") or "").strip()
    return location or "Standort Mini EMS"


def _report_main_message(cycle_count: int, status_counts: Dict[str, object], event_count: object) -> str:
    """Eine datengetriebene Hauptbotschaft in einem Satz (UX1, Prio 1)."""
    if cycle_count <= 0:
        return "Für diesen Tag liegen noch keine Betriebsdaten vor."
    healthy = int(status_counts.get("healthy", 0) or 0)
    degraded = int(status_counts.get("degraded", 0) or 0)
    safe_mode = int(status_counts.get("safe_mode", 0) or 0)
    try:
        events = int(event_count or 0)
    except (TypeError, ValueError):
        events = 0

    if safe_mode > 0:
        return (
            "Die Steuerung war heute zeitweise im sicheren Modus; bitte den Systemzustand prüfen."
        )
    if degraded > 0:
        return (
            "Die Anlage lief heute überwiegend im Normalbetrieb, zeitweise mit Einschränkungen "
            "bei der Datenübertragung."
        )
    if healthy == cycle_count:
        base = "Die Anlage lief heute durchgehend im Normalbetrieb."
    else:
        base = "Die Anlage lief heute im Normalbetrieb."
    if events > 0:
        return base + " Es gab einzelne Kommunikationshinweise."
    return base
