# Lokale Validierung – 22.09.2026

Ergebnis: Die lokale Vorbereitung für einen begrenzten Standortversuch ist abgeschlossen. Der nächste
Nachweis gehört auf Windows: natives Paket, Task/SYSTEM und Update/Rollback in separater Simulation.
Danach den freigegebenen VPN-Zugang zunächst lesend prüfen. Es gab in dieser Runde keine Verbindung zur
realen Anlage, keine Produktivinstallation und keine echten BACnet-Schreibzugriffe.

## Prüfstand und Umfang

- Repository: `openems`, Teilprojekt `mini_ems_poc`, Branch `codex/auth-bacnet-commissioning`.
- Basis-Commit: `53deb51899961cd78bcec5cbdb0f9c3ff27999e5`; Änderungen lokal/uncommittet.
- Vorgänger: [Validierung 20.09.2026](VALIDIERUNG_2026-09-20.md), 196 Python-Tests und 116 Dashboard-Prüfungen.
- macOS arm64, Python 3.12; temporäre Simulationsstandorte mit Loopback-HTTP. Reale Writes gesperrt.
- Bestehender unversionierter `design_prototype/` blieb unberührt; Laufzeitdaten/Testkonten sind keine Release-Dateien.

Geprüfte Ergänzungen: Speicherfehler und eindeutige Zyklus-IDs, separater Prozesswächter mit begrenzten
Neustarts, Logrotation, reduzierte Übersicht und Kanalwahl, optionales Standortwetter, Trennung von
Datenabfrage und Berichtdarstellung, Sommer-/Winterzeit-Aggregate und ein festes schlankes Paketprofil.

## Automatisierte Nachweise

Aus dem Repository-Stamm:

```bash
python3.12 -m unittest discover -s mini_ems_poc/tests -v
env TZ=UTC node mini_ems_poc/tests/dashboard_logic_harness.mjs
env TZ=Europe/Berlin node mini_ems_poc/tests/dashboard_logic_harness.mjs
```

**Ergebnis: 211 Python-Tests in 18,433 Sekunden, OK; jeweils 121 JavaScript-Prüfungen bestanden.**
Die HTTP-Tests verwenden kurzlebige Server auf `127.0.0.1`. Die Sandbox erlaubt solche Listener nicht;
die Suite wurde mit freigegebenem lokalen Netzwerkzugriff erfolgreich ausgeführt. Kein Anlagen-I/O.

Zusätzliche relevante Fälle:

- State-/Historien-Schreibfehler sichtbar; Wiederaufnahme erfindet keine fehlende Historie. Fehlgeschlagene
  Health-Schreibvorgänge können keinen neuen gesunden Nachweis erzeugen. Neustart ohne State erhält alte Zyklen.
- Prozessabbruch, Hänger und fortschreitende fachliche/Speicherstörung werden unterschieden. Alte Health einer
  fremden Run-ID gilt nicht als neuer Fortschritt. Neustartbudget überlebt den Supervisor-Neustart.
- Betriebssystem-Sperre verhindert parallele Instanzen; Prozessabbruch gibt die Sperre frei.
- API erkennt einen verlorenen Supervisor bei lebender Runtime, ohne historische Health umzuschreiben.
- Logs rotieren begrenzt. Watchdog-Werte müssen endlich und größer als die Zykluspause sein.
- Wetter ohne Koordinaten: kein externer Request, keine Paketdatei. Standortwechsel verwirft alte Wetterdaten;
  Cache liegt im SiteDir. Antworten des Wetterdienstes wurden simuliert, nicht live abgenommen.
- Doppelte Herbststunde hat getrennte UTC-Stundenaggregate; lokale Tage umfassen 23/24/25 Stunden.
  Vorhandene alte Aggregate werden nicht rückwirkend korrigiert.
- Bericht-Stylesheet wird durch seinen konkreten CSP-Hash freigegeben; keine allgemeine Inline-Skriptfreigabe.
  API-Rollen, read-only, Monitoring-Write-Sperren und frühere Rückgaberegressionen bleiben grün.

## Prüfung des gebauten Programms

Saubere Build-Umgebung aus `packaging/requirements-build.txt`, danach:

```bash
MINI_EMS_VERSION=2026.09.1 PYTHON=/tmp/mini-ems-build-20260921/bin/python bash mini_ems_poc/packaging/build_release.sh
python3.12 mini_ems_poc/packaging/verify_release.py --package mini_ems_poc/packaging/dist/mini_ems
```

**Ergebnis: `passed`.** Das tatsächlich gebaute Programm wurde geprüft, nicht nur der Quellcode.

| Merkmal | Nachweis |
|---|---|
| Version | `2026.09.1` |
| Build-Zeit | `2026-09-22T16:01:35Z` |
| Codekennung | `53deb5189996+dirty` |
| Plattform | `Darwin-arm64` |
| Manifest | 687 reguläre Dateien geprüft; nach Lauf unverändert |
| Größe | 24,05 MiB reguläre Paketdateien |
| SHA-256 von SHA256SUMS | `767615470ee1d9fdec50411e8dc5356f6e9130aa4c0c9879c48655d0e84279c7` |
| Sichere Ersteinrichtung | Frischer temporärer SiteDir, lokale Simulation, keine realen Writes |
| Zugriff | Login, Viewer-Rechte, gesperrte Admin-/read-only-Aktion |
| Bericht | HTML erreichbar; Stylesheet-Hash im Security-Header |
| Wiederanlauf | Eigenen Kindprozess gezielt beendet; neue Run-ID und zweiter Start erkannt |
| Restore | Gestoppten Standort vollständig kopiert; Revision/Konten erhalten; Zyklen von 4 auf 6 fortgesetzt |
| Datenbank | `PRAGMA integrity_check = ok` vor und nach Restore |

Das macOS-Paket ist kein Windows-Installationspaket. `+dirty` kennzeichnet einen lokalen Prüfstand; vor
Übergabe einen geprüften Commit sichern und den nativen Windows-Kandidaten daraus bauen. CI für Linux/Windows
mit PowerShell-Syntaxprüfung und Binary-Test ist vorbereitet, aber noch nicht auf GitHub ausgeführt.

## Historienlast und Wiederherstellung

Beschleunigter Speicherlasttest: sieben Tage im 30-Sekunden-Takt, zehn Messpunkte, **20.160 Zyklen und
201.600 Messwerte**. SQLite-Datei: **144.031.744 Byte (rund 137 MiB)**. Schreiben dauerte lokal 281,61 Sekunden;
Abfrage eines Tagesberichts mit 2.880 Zyklen 0,343 Sekunden. SQLite-Backup, Wiederherstellung, Zeilenzahlen
und Integrität waren korrekt. Die temporäre Lastdatenbank wurde nach dem Versuch entfernt.

Dies ist kein siebentägiger Echtzeit-Dauerlauf und kein Anlagenmodell. Größen und Zeiten gelten nur für
dieses Profil auf diesem Mac. Historie wird nicht automatisch gelöscht; begrenzte Laufzeit, Speicherkontrolle
und vollständiges ruhendes Standortbackup sind im [Wartungsablauf](../UPDATE_WARTUNG.md) festgelegt.

## Bedienprüfung und Grenzen

Reale Browserinteraktion gegen lokale Simulation; Testkonten und Änderungen nur im temporären Standort.

| Ablauf | Status | Beobachtung |
|---|---|---|
| Übersicht | Pass | Zustand und zwei Kennzahlen sichtbar; Preise und weitere Anzeigen geschlossen; keine leere Hinweiskarte |
| Preisansicht | Pass | Aufklappen erzeugt das Diagramm; Schließen funktioniert |
| Analyse | Pass | Nur Netzleistung und Außentemperatur des Teststandorts angeboten; Kurven mit Messwerten |
| Wetter ohne Standort | Pass | Verständlicher leerer Zustand; kein vorgetäuschter Stuttgart-Standort |
| Anmeldung/Viewer | Pass | Testkonten angemeldet; Viewer hat keine Standort-/Kontenverwaltung; reduzierte Ansicht auch bei schmalem Fenster sichtbar |
| Konfiguration | Pass | Bedienhinweis geprüft, gespeichert und nach Neuladen im Formular wiedergefunden; Standortrevision gespeichert |
| Berichte-Übersicht | Pass | Tagesauswertung sichtbar; erweiterte Einstellungen eingeklappt |
| Eigenständiges Berichtsfenster/Drucken | Blocked | In-App-Browser öffnete den Link nicht; ein direkter Öffnungsversuch endete mit `net::ERR_BLOCKED_BY_CLIENT`. Danach keine weiteren Umgehungsversuche. HTML/CSP durch HTTP- und Pakettest geprüft; sichtbares Drucklayout bleibt auf Windows zu prüfen |
| Speicher-/Supervisorstörung | Pass (automatisiert) | API-/Zyklusregressionen und JavaScript-Meldungslogik; Fehler wurden nicht zusätzlich im Browser provoziert |
| Mapping/Import/Schreibtest-Rückgabe | Pass (automatisiert) | Bestehende Regressionen grün; in dieser Runde keine erneute vollständige manuelle Inbetriebnahme |
| Windows-Task/Update/Rollback/Caddy | Offen | Kein nativer Windows-/IPC-Lauf dieser Änderungen |
| Reale Anlage/DDC-Fallback | Nicht ausgeführt | Benötigt vereinbarten Standortzugriff und separate Betreiberabnahme |

## Bereinigung mit Begründung

| Entscheidung | Umfang und Begründung |
|---|---|
| Remove | Ungenutzter `SpotMarketLockoutController` und drei ausschließlich für ihn vorhandene Tests; aktiver UTC-Planer und dessen Regressionen bleiben erhalten |
| Remove | Vier wirkungslose Parameter aus der UI; ihre gespeicherten Altwerte bleiben beim Speichern erhalten |
| Simplify | Berichtdarstellung nach `reporting.py` verschoben; `RuntimeDatabase` behält seine öffentliche Schnittstelle |
| Simplify | Standardansicht, Kanalauswahl und bedarfsweiser Wetterabruf; keine zusätzliche Frontend-Bibliothek |
| Simplify | Betriebsanleitung deutlich gekürzt; Paketbau zentral dokumentiert, historische Startpfade aus aktuellen Anweisungen entfernt |
| Keep | Alte Zustands-/Konfigurationsfelder für Kompatibilität, bewährte Testfälle, Audit, Rückgabeverpflichtungen und Site-Migration |
| Keep | Legacy-Service-/Proxy-Helfer als historische Quellen; im Release nicht enthalten. Optionale Quellcode-Renderer bleiben verfügbar, sind im festen Paketprofil ausgeschlossen und wurden nicht mit installierten optionalen Bibliotheken geprüft |
| Unresolved | Allgemeiner Metadatenkatalog für beliebige neue Kanäle und weitere Modulteilung benötigen einen konkreten Folgefall; kein spekulativer Umbau |

Abschlussprüfungen: `git diff --check`, Python-Kompilierung und Bash-Syntaxprüfung ohne Fehler;
relative Links der neun aktiven Anleitungen geprüft. Der lokale Testsupervisor wurde geordnet beendet,
sein Status ist `stopped`; temporäre Browserfenster geschlossen.

## Nächste Abnahme

1. Geprüften Quellstand versionieren; native Windows-/Linux-CI und Windows-Paketprüfung durchführen.
2. Auf Windows Task/SYSTEM, Update/Rollback und Berichtdruck mit separaten Simulationsordnern prüfen.
3. VPN einrichten und bestehenden IPC-Stand zunächst lesend aufnehmen: Version, Task/Prozess, SiteDir,
   Revision, offene Rückgaben, Zugriffsschutz und Backup.
4. Wenige vorab vereinbarte Punkte zeitlich begrenzt beobachten. Datenlücken, Datenalter, Wiederanlauf,
   Speicherwachstum und Bedienbarkeit bewerten. Noch kein Nachweis von Einsparungen oder Steuerungswirkung.

Ein externer Alarmweg, automatische Langzeitaufbewahrung, DDC-Fallback und die Freigabe aktiver Eingriffe
sind hier nicht abgeschlossen. Die maßgebliche Aufgabenfolge steht in [ROADMAP.md](../ROADMAP.md).
