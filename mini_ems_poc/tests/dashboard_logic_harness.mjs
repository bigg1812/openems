/* Node-Harness für die reinen Logikfunktionen der Inbetriebnahme-UI
   (UX14/UX15/UX16) in dashboard/dashboard.js.

   Lauf: node mini_ems_poc/tests/dashboard_logic_harness.mjs
   (kein Bestandteil der Python-Unittest-Suite; DOM wird gestubbt,
   getestet werden nur Zustandsableitung, Draft-Aufbau und die
   Übersetzung der Testergebnisse in Inbetriebnahme-Sprache). */

import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../dashboard/dashboard.js", import.meta.url), "utf8");
const context = vm.createContext({
  document: { addEventListener() {} },
  window: {},
  console,
});
vm.runInContext(source, context, { filename: "dashboard.js" });

let failures = 0;
let checks = 0;

function check(name, actual, expected) {
  checks += 1;
  const okValue = typeof expected === "function" ? expected(actual) : actual === expected;
  if (!okValue) {
    failures += 1;
    console.error(`FEHLER  ${name}`);
    console.error(`        erhalten: ${JSON.stringify(actual)}`);
    if (typeof expected !== "function") {
      console.error(`        erwartet: ${JSON.stringify(expected)}`);
    }
  }
}

/* ---------- Vorbelegung aus der aktiven Konfiguration ---------- */

const siteConfig = {
  network: { controller_ip: "192.168.1.100", controller_port: 47808 },
  points: {
    grid_active_power_kw: 300,
    current_price_av: 1000,
    grid_lockout_bv: 400,
    spotmarket_lockout_bv: 401,
  },
  additional_inputs: [
    {
      channel_id: "site.outdoor_temperature_c",
      object_type: "ai",
      instance: 1801,
      description: "Outdoor temperature",
      plausible_min: -30.0,
      plausible_max: 60.0,
      max_age_seconds: 120,
      read_interval_cycles: 1,
      include_in_health: true,
    },
  ],
  runtime: { environment: "local", bacnet_mode: "simulated" },
  api: { host: "127.0.0.1", port: 8090 },
};

const seeded = context.buildSetupFromSiteConfig(siteConfig);
check("Seed: ein Gerät aus network", seeded.devices.length, 1);
check("Seed: Gerätehost", seeded.devices[0].host, "192.168.1.100");
check("Seed: 4 Kern- + 1 Zusatzpunkt", seeded.rows.length, 5);
check("Seed: Netzleistung zugeordnet", seeded.rows[0].channelId, "grid.active_power_kw");
check("Seed: Netzleistung Instanz", seeded.rows[0].instance, 300);
check("Seed: Sperre ist Schreibpunkt", context.setupRowStatus(seeded.rows.find((r) => r.channelId === "ems.lockout_spotmarket")), "write");
check("Seed: Zusatzpunkt Plausibilität", seeded.rows[4].plausibleMin, -30);
check("Seed: Zusatzpunkt überwacht", seeded.rows[4].includeInHealth, true);

const emptySeed = context.buildSetupFromSiteConfig(null);
check("Seed(null): keine Zeilen", emptySeed.rows.length, 0);
check("Seed(null): Gerät ohne Adresse", emptySeed.devices[0].host, "");

const partialSeed = context.buildSetupFromSiteConfig({ points: { grid_active_power_kw: "kaputt" }, additional_inputs: [null, {}] });
check("Seed(kaputt): robuste Leere", partialSeed.rows.length, 0);

/* ---------- Import-Antwort -> Kandidaten ---------- */

const importPayload = {
  valid: true,
  errors: [],
  warnings: ["Zeile 6: AO wird als Kandidat importiert, ist aber noch kein aktivierbarer Mini-EMS-Rohpunkt"],
  devices: [{ id: "device_100", name: "EBCON", host: "", port: 47808 }],
  suggested_mappings: [
    { channel_id: "grid.active_power_kw", source_point_id: "bacnet:device_100:av:300" },
    { channel_id: "unbekannt.kanal", source_point_id: "bacnet:device_100:ai:1801" },
  ],
  candidates: [
    { id: "bacnet:device_100:av:300", device_id: "device_100", object_type: "av", instance: 300, name: "Netzleistung Hauptzähler", unit: "kW", access: "read", value: 42.3, source: { filename: "punkte.csv", row: 2 } },
    { id: "bacnet:device_100:ai:1801", device_id: "device_100", object_type: "ai", instance: 1801, name: "Außentemperatur", unit: "°C", access: "read", value: 8.4, source: { filename: "punkte.csv", row: 3 } },
    { id: "bacnet:device_100:bv:401", device_id: "device_100", object_type: "bv", instance: 401, name: "Preissteuerung Sperre", unit: "", access: "write", value: null, source: { filename: "punkte.csv", row: 4 } },
    { id: "bacnet:device_100:ao:5", device_id: "device_100", object_type: "ao", instance: 5, name: "Ventil Stellsignal", unit: "%", access: "write", value: null, source: { filename: "punkte.csv", row: 6 } },
    { id: "bacnet:device_100:av:300", device_id: "device_100", object_type: "av", instance: 300, name: "Duplikat", unit: "", access: "read", value: null, source: {} },
  ],
};

const merged = context.importResultToSetup(importPayload, new Set(["bacnet:device_100:av:300"]), new Set());
check("Import: Duplikat + vorhandene Zeile übersprungen", merged.rows.length, 3);
check("Import: unbekannter Kanalvorschlag ignoriert", merged.rows.find((r) => r.id === "bacnet:device_100:ai:1801").channelId, "");
check("Import: AO nicht aktivierbar", merged.rows.find((r) => r.id === "bacnet:device_100:ao:5").supported, false);
check("Import: Schreibzugriff übernommen", merged.rows.find((r) => r.id === "bacnet:device_100:bv:401").access, "write");
check("Import: Quelle lesbar", merged.rows.find((r) => r.id === "bacnet:device_100:ai:1801").sourceLabel, "punkte.csv · Zeile 3");
check("Import: Gerät übernommen", merged.devices.length, 1);
check("Import: Warnungen durchgereicht", merged.warnings.length, 1);

const brokenImport = context.importResultToSetup({ valid: false, errors: ["Keine verwertbaren BACnet-Rohpunkte erkannt"] }, new Set(), new Set());
check("Import(fehlerhaft): keine Zeilen", brokenImport.rows.length, 0);
check("Import(fehlerhaft): Fehler durchgereicht", brokenImport.errors[0], "Keine verwertbaren BACnet-Rohpunkte erkannt");
check("Import(null): robust", context.importResultToSetup(null, new Set(), new Set()).rows.length, 0);

/* ---------- Statusableitung je Zeile (UX15) ---------- */

const mkRow = (fields) => context.makeSetupRow({ id: "t", deviceId: "d", protocol: "bacnet", objectType: "ai", instance: 1, name: "Punkt", ...fields });
check("Status: Kandidat ohne Zuordnung", context.setupRowStatus(mkRow({})), "review");
check("Status: zugeordnet", context.setupRowStatus(mkRow({ channelId: "site.outdoor_temperature_c" })), "assigned");
check("Status: Schreibpunkt (Kanal)", context.setupRowStatus(mkRow({ objectType: "bv", channelId: "ems.lockout_grid" })), "write");
check("Status: Schreibpunkt (Liste)", context.setupRowStatus(mkRow({ access: "write" })), "write");
const testedRow = mkRow({ channelId: "site.outdoor_temperature_c" });
testedRow.test = { tone: "ok", text: "Wert kommt an.", valueLabel: "8,4 °C" };
check("Status: geprüft", context.setupRowStatus(testedRow), "tested");
testedRow.test = { tone: "alert", text: "Keine Antwort von der Anlage.", valueLabel: "" };
check("Status: keine Antwort", context.setupRowStatus(testedRow), "failed");
const unsupportedRow = mkRow({ objectType: "ao" });
check("Status: nicht unterstützt -> prüfen", context.setupRowStatus(unsupportedRow), "review");

/* ---------- Mapping-Entwurf für Vorschau/Aktivierung ---------- */

const draftDevices = [{ id: "d", name: "EBCON", host: "192.168.1.20", port: 47808 }];
const draftRows = [
  mkRow({ id: "p1", channelId: "grid.active_power_kw", objectType: "av", instance: 300, plausibleMin: -1000, plausibleMax: 1000, maxAgeSeconds: 120 }),
  mkRow({ id: "p2", channelId: "site.outdoor_temperature_c", objectType: "ai", instance: 1801, includeInHealth: true }),
  mkRow({ id: "p3" }),
];
const { draft, problems } = context.buildSetupMappingDraft(draftDevices, draftRows);
check("Draft: keine Hürden", problems.length, 0);
check("Draft: nur zugeordnete Rohpunkte", draft.raw_points.length, 2);
check("Draft: Gerät im Entwurf", draft.devices[0].host, "192.168.1.20");
check("Draft: Kernkanal read", draft.mappings[0].access, "read");
check("Draft: Plausibilität übernommen", draft.mappings[0].plausible_min, -1000);
check("Draft: max_age übernommen", draft.mappings[0].max_age_seconds, 120);
check("Draft: include_in_health", draft.mappings[1].include_in_health, true);
check("Draft: Label fachlich", draft.mappings[0].label, "Netzleistung");

const writeDraft = context.buildSetupMappingDraft(draftDevices, [mkRow({ id: "w1", channelId: "ems.lockout_spotmarket", objectType: "bv", instance: 401 })]);
check("Draft: Kern-Schreibkanal access=write", writeDraft.draft.mappings[0].access, "write");

const noHost = context.buildSetupMappingDraft([{ id: "d", name: "EBCON", host: "", port: 47808 }], [draftRows[0]]);
check("Draft: fehlende Geräteadresse gemeldet", noHost.problems.length >= 1 && noHost.problems[0].includes("Geräteadresse"), true);

const duplicate = context.buildSetupMappingDraft(draftDevices, [draftRows[0], mkRow({ id: "p9", channelId: "grid.active_power_kw", objectType: "av", instance: 301 })]);
check("Draft: Doppelzuordnung gemeldet", duplicate.problems.some((p) => p.includes("mehrfach zugeordnet")), true);

const nothing = context.buildSetupMappingDraft(draftDevices, [mkRow({ id: "p3" })]);
check("Draft: nichts zugeordnet gemeldet", nothing.problems.some((p) => p.includes("kein Datenpunkt zugeordnet")), true);

/* ---------- Übersetzung der Live-Reads (UX16) ---------- */

const rangeRow = mkRow({ channelId: "grid.active_power_kw", unit: "kW", plausibleMin: -1000, plausibleMax: 1000 });
const okDiag = context.translateSetupDiagnostic(rangeRow, { status: "ok", value: 42.3, plausible: true, quality: "good", error: null });
check("Test-Text: ok im Bereich", okDiag.text, "Wert kommt an und liegt im erwarteten Bereich.");
check("Test-Text: Ton ok", okDiag.tone, "ok");
check("Test-Text: Wert formatiert", okDiag.valueLabel.includes("kW"), true);

const plainRow = mkRow({ channelId: "site.outdoor_temperature_c", unit: "°C" });
check("Test-Text: ok ohne Bereich", context.translateSetupDiagnostic(plainRow, { status: "ok", value: 8.4, plausible: true }).text, "Wert kommt an.");
check(
  "Test-Text: außerhalb des Zeilenbereichs",
  context.translateSetupDiagnostic(rangeRow, { status: "ok", value: 5000, plausible: true }).text,
  "Wert kommt an, aber bitte Einheit und erwarteten Bereich prüfen.",
);
check(
  "Test-Text: Backend unplausibel",
  context.translateSetupDiagnostic(plainRow, { status: "warning", value: 8.4, plausible: false, error: "value_out_of_range" }).tone,
  "warn",
);
check(
  "Test-Text: veraltet",
  context.translateSetupDiagnostic(plainRow, { status: "warning", value: 8.4, plausible: true, quality: "stale", error: "value_stale" }).text,
  "Wert kommt an, ist aber veraltet. Bitte die Aktualität der Quelle prüfen.",
);
check(
  "Test-Text: Teilmessung",
  context.translateSetupDiagnostic(plainRow, { status: "warning", value: 8.4, plausible: true }).text,
  "Wert kommt an, aber nicht alle Einzelmessungen kamen an.",
);
check(
  "Test-Text: Fehler -> keine Antwort",
  context.translateSetupDiagnostic(plainRow, { status: "error", value: null, error: "timeout" }).text,
  "Keine Antwort von der Anlage. Bitte Adresse und Verbindung prüfen.",
);
check("Test-Text: kaputte Antwort robust", context.translateSetupDiagnostic(plainRow, null).tone, "alert");

check("Test-Text: read-only 403", context.translateSetupReadFailure(403, "read_only_mode").text.includes("Netzwerkzugriff"), true);
check("Test-Text: unbekannter Kanal", context.translateSetupReadFailure(500, "'Unknown channel_id: site.x'").text.includes("nach Aktivierung"), true);
check("Test-Text: Serverfehler", context.translateSetupReadFailure(500, "boom").text, "Keine Antwort von der Anlage. Bitte Adresse und Verbindung prüfen.");

/* ---------- Schrittzustände und Hauptbotschaft (UX14) ---------- */

function makeState(overrides) {
  return {
    loaded: true,
    loadFailed: false,
    siteConfig,
    saveEnabled: true,
    readOnly: false,
    devices: seeded.devices,
    rows: seeded.rows.map((row) => ({ ...row })),
    preview: { valid: null, message: null, tone: "neutral", patch: null },
    activation: { done: true, restartRequired: false, revision: "r1", activatedAt: "2026-07-11T10:00:00Z" },
    dirty: false,
    ...overrides,
  };
}

const steps = context.computeSetupSteps(makeState({}));
check("Schritte: fünf Stück", steps.length, 5);
check("Schritte: Standort erledigt", steps[0].state, "done");
check("Schritte: Geräte erledigt", steps[1].state, "done");
check("Schritte: Datenpunkte erledigt (aktive Zuordnung)", steps[2].state, "done");
check("Schritte: Testen offen", steps[3].state, "open");
check("Schritte: Abschluss aktiv", steps[4].state, "done");
check("Schritte: Abschluss verständlich benannt", steps[4].label, "Abschließen");

const readOnlySteps = context.computeSetupSteps(makeState({ readOnly: true }));
check("Schritte: read-only sperrt Testen", readOnlySteps[3].state, "locked");
check("Schritte: read-only sperrt Aktivieren", readOnlySteps[4].state, "locked");

const noTokenSteps = context.computeSetupSteps(makeState({
  saveEnabled: false,
  activation: { done: false, restartRequired: false, revision: null, activatedAt: null },
}));
check("Schritte: ohne Token gesperrt erklärt", noTokenSteps[4].state, "locked");
check("Schritte: Sperrgrund benannt", noTokenSteps[4].detail.includes("Freigabecode"), true);

const noTokenDirtySteps = context.computeSetupSteps(makeState({ saveEnabled: false, dirty: true }));
check("Schritte: offener Entwurf bleibt ohne Freigabecode gesperrt", noTokenDirtySteps[4].state, "locked");

const dirtySteps = context.computeSetupSteps(makeState({ dirty: true }));
check("Schritte: offener Entwurf ist nicht abgeschlossen", dirtySteps[4].state, "open");
check("Schritte: offener Entwurf verständlich erklärt", dirtySteps[4].detail.includes("noch nicht übernommen"), true);

const restartSteps = context.computeSetupSteps(makeState({
  activation: { done: true, restartRequired: true, revision: "r2", activatedAt: "2026-07-11T10:00:00Z" },
}));
check("Schritte: Neustart bleibt sichtbar", restartSteps[4].detail.includes("Neustart erforderlich"), true);

const failedState = makeState({});
failedState.rows[0].test = { tone: "alert", text: "Keine Antwort von der Anlage.", valueLabel: "" };
check("Schritte: Fehlversuch markiert Testen", context.computeSetupSteps(failedState)[3].state, "error");

const heroReadOnly = context.buildSetupHeroMessage(readOnlySteps, context.setupCounts(seeded.rows), makeState({ readOnly: true }));
check("Hero: read-only Warnung", heroReadOnly.level, "warn");
const heroActive = context.buildSetupHeroMessage(steps, context.setupCounts(seeded.rows), makeState({}));
check("Hero: aktiver Stand verständlich", heroActive.headline, "Der Standort ist eingerichtet.");
const heroNeutral = context.buildSetupHeroMessage(dirtySteps, context.setupCounts(seeded.rows), makeState({ dirty: true }));
check("Hero: Zählerzeile enthalten", heroNeutral.detail.includes("Datenpunkte gefunden"), true);
check("Hero: nächster Schritt benannt", heroNeutral.detail.includes("Nächster Schritt"), true);

/* ---------- Live testbare Kanäle ---------- */

const activeInfo = context.setupActiveChannelInfo(siteConfig);
check("Aktiv lesbar: Netzleistung", activeInfo.has("grid.active_power_kw"), true);
check("Aktiv lesbar: Zusatzpunkt", activeInfo.get("site.outdoor_temperature_c").instance, 1801);
check("Aktiv lesbar: Schreibkanäle nicht dabei", activeInfo.has("ems.lockout_grid"), false);
check("Aktiv lesbar: leere Konfiguration robust", context.setupActiveChannelInfo(null).size, 0);

/* ---------- Ergebnis ---------- */

if (failures) {
  console.error(`\n${failures} von ${checks} Prüfungen fehlgeschlagen.`);
  process.exit(1);
}
console.log(`Alle ${checks} Prüfungen bestanden.`);
