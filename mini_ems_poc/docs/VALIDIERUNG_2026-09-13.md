# Lokale Validierung – 13.09.2026

Dieser Nachweis dokumentiert die Stabilisierungsrunde R3b/R4 und die lokale Paketprüfung aus R7.
Aufgabenstatus: [ROADMAP](../ROADMAP.md). Gemeinsame Zielabnahme: [Update und Wartung](../UPDATE_WARTUNG.md).
Es handelt sich um einen Entwicklungsstand, keine Produktionsfreigabe und keinen Windows-/DDC-Nachweis.

## Stand und Umgebung

- Basis-Commit: `1bd2d3986f39`; Arbeitskopie enthält die Änderungen dieser und der vorangehenden Runde.
- Endgültiges macOS-Prüfpaket: Version `2026.09.0`, Build `2026-09-13T08:22:01Z`,
  Commitkennzeichen `1bd2d3986f39+dirty`, Plattform `Darwin-arm64`.
- Python 3.12.13, PyInstaller 6.21.0; bestehende lokale Build-Umgebung, kein neu festgeschriebenes Dependency-Lock.
- Standort ausschließlich in einem temporären Ordner; API auf `127.0.0.1:18091`.
  `environment=local`, `bacnet_mode=simulated`, `real_writes_enabled=false`.
- Test-Admin als lokale Fixture angelegt; Anmelden danach durch die Browseroberfläche.
  Keine IPC-Datenbank verwendet, kein Git-Push und kein Windows-Update durchgeführt.
- Vorheriger Nachweis vom 12.09.: 160 Python-Tests und 92 Dashboard-Prüfungen.
  Die erste breite Prüfung dieser Fortsetzung scheiterte am Sandbox-Verbot für lokale Testports;
  mit erlaubten Loopback-Testservern bestanden alle Tests. Kein verbleibender Funktionsfehler daraus.

## Automatisierte Nachweise

| Prüfung | Ergebnis | Aussage / Grenze |
|---|---|---|
| `.venv/bin/python -m unittest discover -s mini_ems_poc/tests -q` | Pass: 178 Tests, 16,098 s | Runtime, HTTP/Auth, Schutzgrenzen, Mapping, Migrationen und neue Regressionen; Fake-Geräte |
| Dashboard-Harness mit `TZ=Europe/Berlin` und `TZ=America/New_York` | Pass: je 101 Prüfungen | UTC-Diagrammzeiten hängen nicht von der Prozesszeitzone ab; kein Ersatz für Browserlayout |
| `node --check mini_ems_poc/dashboard/dashboard.js` | Pass | JavaScript-Syntax |
| `bash -n mini_ems_poc/packaging/build_release.sh` | Pass | Shell-Syntax; PowerShell-Ausführung nicht nachgewiesen |
| `git diff --check` | Pass | Keine Whitespace-Befunde |
| `packaging/build_release.sh` mit expliziter Version und Projekt-Python | Pass | Eigenständiges macOS-Paket gebaut |
| SHA256SUMS gegen alle Paketdateien | Pass: 78 Dateien | Keine Standort-SQLite-Datei im Paket |
| Laufende `/api/health` gegen Paket-VERSION | Pass | `healthy`, Version/Commit/Buildzeit stimmen |

Neue Fehlerfälle: fehlendes Write-ACK, Write-Ausnahme mit unklarem Ausgang, fehlgeschlagene Rückgabe,
Neustart, unterbrochene Rückgabe ohne Ergebnis, gesperrter Folgetest, ursprüngliche Zielpriorität trotz
geänderter Freigabe und Migration historischer Fehlversuche. Bereits vergangene I/O-Zeit wird nicht
nochmals als zehn Sekunden Testzeit angehängt.

Preisfälle: 92/96/100 UTC-Viertelstunden, beide Herbststunden, Zeitzonen-Fallback ohne System-Zonendaten,
Stundenquelle, korrigierte gleiche Datenmenge, neuester Quellblock, fehlender aktueller Preis,
Offline-Cache nach Tageswechsel, normale Cachemigration, Zurückweisen mehrdeutiger alter Cachetage,
Planfenster über Zeitumstellung, historische Daten neben neuen UTC-Daten und manuelle UTC-Fenster.
Mehrdeutige manuelle Ortszeiten führen vor regulären Ausgaben in den bestehenden `safe_mode`-Pfad.

## Durchlauf im echten Browser mit gebautem Paket

| Ablauf | Ergebnis | Beobachtung |
|---|---|---|
| Anmeldung am vorbereiteten Simulationsstandort | Pass | Admin-Menüs erreichbar, aktuelle Daten geladen |
| Übersicht mit Preisen und geplanten Fenstern | Pass | Preis und Fenster heute/morgen sichtbar |
| Standort → Schreibzugriffe → `EMS_LOKAL_PRUEFUNG` freigeben | Pass | BV 200, Loopback-Ziel, Priorität 14 gespeichert; Modus ausdrücklich Simulation |
| Ein testen → Timer-Rückgabe | Pass | Readback, ausstehende Rückgabe, gesperrter Folgetest, danach dauerhafte Rückgabebestätigung |
| Reload → Schreibzugriffe wieder öffnen | Pass | Freigabe und Ergebnis erhalten |
| Finales Paket neu starten → erneut anmelden | Pass | Konto, Freigabe und altes Ergebnis erhalten; korrigierte Hinweistexte sichtbar |
| Aus testen → Jetzt zurückgeben | Pass | Manuelle Rückgabe bestätigt und dauerhaft angezeigt |
| Browserergebnis mit temporärer SQLite vergleichen | Pass | Zwei Leases `released`, Rückgabeauslöser `timer` und `manual`; 192 UTC-Preisintervalle gespeichert |
| Fehlendes ACK, Kommunikationsausfall, Prozessabbruch | Automatisiert Pass; im Browser nicht als echter Fehler provoziert | Adapter-/HTTP-Regressionen und Darstellungs-Harness; keine physische Anlage |
| Windows-Paket, Caddy, Rollen auf Zweitrechner, DDC-Prioritäten und Fallback | Nicht durchgeführt | Gemeinsame Zielabnahme R3c/R5/R6/R7 offen |

Die Simulation meldet einen bestätigten simulierten Vorgang, aber kein echtes BACnet-ACK.
Die UI zeigt deshalb korrekt „BACnet-ACK: nicht bestätigt“. Der Readback ist ebenfalls ein Simulationswert.
Die mobile Browserdarstellung wurde visuell angesehen; eine umfassende Geräte-/Browsermatrix wurde nicht geprüft.

## Vereinfachungen und beibehaltene Grenzen

- Entfernt: ungenutzter zweiter SMARD-Snapshot-/Stundenaggregationsweg, nach Referenzprüfung ohne Runtime-Aufrufer.
  Preiszugriff und Zeitrechnung laufen über den bestehenden Scan und ein gemeinsames UTC-Intervallmodul.
- Ersetzt: stiller Best-effort-Relinquish durch den gespeicherten Rückgabeablauf. Der Beginn eines Versuchs
  wird vor dem I/O persistiert; ein unbekanntes Ergebnis bleibt `null`.
- Erhalten: historische Preiszeilen und alte Schreibnachweise. Mehrdeutige Vergangenheit wird nicht umgedeutet.
- Erhalten: lokaler Simulationsschutz und eigenständige Standortdaten; keine Containerumstellung.
- Nicht bereinigt: Legacy-Controller, alte Proxy-/Service-Helfer und Report-Renderer. Ihre Entfernung ist R10;
  diese Runde liefert dafür keine vollständige Kompatibilitätsprüfung.
- Bestehender fremder Arbeitsstand `design_prototype/` wurde nicht verändert.

`+dirty` bedeutet: Dieser Build ist keinem sauberen Commit vollständig zuordenbar. Für die nächste
Auslieferung zuerst den geprüften Quellstand versionieren, CI bestätigen und daraus ein Windows-Paket bauen.
Die hier protokollierte Paketprüfung ersetzt weder diesen Schritt noch eine physische Rückgabe-/Fallback-Abnahme.
