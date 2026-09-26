# Lokale Validierung – Beobachtungsmodus und Messwertalter

Stand: 20.09.2026. Arbeitsblock R8a/R8b/R1b aus der technischen Roadmap.
Geprüft wurde der lokale Arbeitsstand; kein Windows-Release und keine Anlagenfreigabe.

## Ergebnis

- Vollständige Python-Suite: **196 Tests bestanden**, davon 18 neue Tests in `test_monitoring.py`.
- Dashboard-Harness: **116 Prüfungen bestanden**, jeweils mit Europe/Berlin und America/New_York.
- macOS-Paket mit Python 3.12 / PyInstaller 6.21.0 gebaut und als eigener Prozess geprüft.
- Browser: Login, Beobachtungszustand, Messpunktausfall, Wiederkehr, Technikansicht und HTML-Tagesbericht geprüft.
- Insgesamt 118 simulierte Paketzyklen gespeichert; abschließender Einzelzyklus mit erneut gebautem Paket bestanden.
- Neustart desselben Teststandorts erhält Historie und Zyklusfolge; ausgefallene Messpunkte erhalten keinen
  erfundenen neuen Wert oder Empfangszeitstempel. Keine Ausgangsmessungen oder simulierten Schreibereignisse.

## Reproduzierbare automatisierte Prüfungen

Vom Repository-Root:

```sh
python3.12 -m unittest discover -s mini_ems_poc/tests -q
TZ=Europe/Berlin node mini_ems_poc/tests/dashboard_logic_harness.mjs
TZ=America/New_York node mini_ems_poc/tests/dashboard_logic_harness.mjs
git diff --check
```

Die HTTP-Integration braucht lokale Loopback-Sockets; das Desktop-Sandboxprofil erforderte dafür eine
Ausführung außerhalb der Socket-Sperre. Tests verwenden temporäre Standortdaten, Fake-Geräte und lokale
Testserver. Keine realen BACnet-/Modbus-Ziele und keine SMARD-Abfragen waren Teil dieser Validierung.

| Fall | Erwartung und Nachweis |
| --- | --- |
| Preisquelle ohne Cache ausgefallen | Reads und SQLite-Historie laufen weiter; aktueller Preis `null`. Beobachtung bleibt bei gültigen Reads gesund, Steuerungsmodus blockiert preisabhängige Entscheidungen. |
| Preisabruf hängt | Zwei Erfassungszyklen laufen, während ein Fake-Provider blockiert ist. Höchstens ein Hintergrundabruf; keine Worker-Vermehrung. |
| Cache vorhanden, Quelle gestört | Aktuelles Intervall wird bei jeder Auswertung neu gewählt; fehlender aktueller Slot bleibt gesperrt. Cache-Nutzung verbirgt den Quellfehler nicht; erfolgreiche Aktualisierung hebt ihn auf. |
| Ein Controller/Messpunkt nicht erreichbar | Andere Punkte werden weiterhin gelesen; gestörter Punkt ist `bad` und nicht als gültiger Durchschnitt enthalten. |
| Leseintervall ausgelassen | Empfangszeit bleibt gleich, Alter steigt, Grenzüberschreitung wird `stale`; keine zusätzliche Rohmessung/Rollup aus altem Cache. |
| Gleicher Wert erneut empfangen | Neue Empfangszeit, aber Quellfrische ausdrücklich unbekannt. Keine automatische Erkennung eingefrorener Controllerwerte behauptet. |
| Manuelle Diagnose mit breiten Wertebereichen | Ersetzt weder den zyklischen Lesecache noch dessen Plausibilitäts-/Altersgrenzen; keine neue Historienzeile aus der Diagnose. |
| Neustart bei Kommunikationsausfall | Neue Reads, kein übernommener alter Wert als gültige Messung; historische Werte bleiben erhalten. |
| Health zwischen Zyklen | API bewertet Messwertalter neu; Beobachtungsstatus wird bei veralteten Messwerten eingeschränkt. Gespeicherte Health-Datei und historischer `cycle_status` bleiben unverändert. |
| Beobachtung mit aktiviert konfiguriertem Heartbeat | Keine regulären Preis-, Sperr-, Heartbeat- oder Testausgaben; direkte Write-/Relinquish-Aufrufe am Router verweigert. |
| Offene Lease bei Moduswechsel | Rückgabe bleibt offen und sichtbar. Recovery/Shutdown und manuelle Aktionen senden in Beobachtung kein Relinquish. Rückgabe im ausdrücklich freigegebenen Steuerungsmodus kann die ursprüngliche Verpflichtung abschließen. |
| Bestehende SQLite-Datei | Vier neue Metadatenspalten additiv angelegt; alte Werte erhalten keine erfundene Qualität/Quellzeit. Zweite Initialisierung ist ebenfalls erfolgreich. |
| Alte Preispläne nach Moduswechsel | Bleiben als Datei erhalten, erscheinen aber nicht als aktiver Plan im Beobachtungsstatus. |

Bestehende Regressionen für Rollen/API-Schutz, BACnet-Rückgaben, Modbus und UTC-Preise einschließlich
Zeitumstellung bleiben Teil der vollständigen Suite.

## Paket- und Browserprüfung

Das vorhandene Spec wurde mit getrennten temporären Build-/Dist-Verzeichnissen verwendet:

```sh
.venv/bin/python -m PyInstaller --noconfirm \
  --distpath /tmp/mini-ems-monitoring-build/dist \
  --workpath /tmp/mini-ems-monitoring-build/work \
  mini_ems_poc/packaging/mini_ems.spec
```

Teststandort: neu angelegte `site.sqlite` und `identity.sqlite` in einem temporären Verzeichnis,
unterhalb `runtime/local/site`. Betriebsgrenzen: `environment=local`, `bacnet_mode=simulated`,
`real_writes_enabled=false`, `operation_mode=monitoring`; API nur `127.0.0.1:18092`.
Zwei synthetische Werte (Netzleistung 12,5 kW, Außentemperatur 18 °C), Zyklus 5 Sekunden,
Temperatur-Altersgrenze 15 Sekunden, absichtlich fehlende Preisdatei. Eigenes lokales Testkonto.

Beobachtungen:

1. Ohne Preise laufen Erfassung und Historie weiter. Anzeige: „Beobachtungsmodus aktiv“, Preissteuerung
   „deaktiviert“, fehlender Preis als Strich; keine behauptete Preisübergabe.
2. Entfernen des simulierten Netzzählers ergibt „eingeschränkt“/„Netzleistung gestört“ und `value=null`.
   Temperatur bleibt verfügbar. Im HTML-Bericht erscheinen gestörte Reads und Läufe ohne aktuellen Preis.
3. Nach geordnetem Stop/Neustart geht die Folge von `cycle-000069` zu `cycle-000070` weiter. Alte Zyklen
   bleiben erhalten. Solange der Zähler fehlt, bleiben Wert und neuer Empfangszeitstempel unbekannt.
4. Nach Wiederherstellung des Simulationswerts kehrt die Erfassung zu „in Ordnung“ zurück; Preise fehlen weiter.
5. Der HTML-Bericht benennt ausdrücklich Beobachtung ohne Anlagenaktionen und unbekannte Quellfrische;
   keine behauptete Wirkung von Eingriffen. Fehler bleiben historisch erkennbar.

Das Testpaket ist ein macOS-Entwicklungsbuild ohne versionierte `VERSION`/Release-Checksumme, kein
verteilbares Windows-Release. Laufzeitdaten, Testkonto und Builddateien wurden nicht ins Repository aufgenommen. Der temporäre
Testserver ist beendet; die abschließend gebündelten Browserdateien entsprechen dem geprüften Arbeitsstand.

## Verbleibende Grenzen und nächste Aufgaben

- R2b: unabhängige Prozessüberwachung, Alarmierung und kontrollierter Wiederanlauf bei Hänger/Abbruch fehlen.
  Ein manueller macOS-Neustart ersetzt diesen Nachweis nicht.
- R7: GitHub-CI auf Linux/Windows bestätigen, Abhängigkeiten festschreiben, Windows-Paket sowie Update/Restore
  prüfen. Datenbankwachstum, Aufbewahrung und Speicherfehler in einem separaten Dauertest behandeln.
  Insbesondere meldet der bisherige Runtime-Pfad SQLite-Schreibfehler bislang nur im Log; ein gesunder
  Erfassungsstatus ist deshalb kein alleiniger Nachweis lückenloser Speicherung.
- Keine Controller-Quellzeit verfügbar; `source_freshness=unknown`. Frischer Empfang beweist keine neue Messung.
- Protokoll-Reads bleiben sequenziell mit Timeouts/Retry-Grenzen; keine harte maximale Zyklusdauer garantiert.
- R5/R8c: tatsächlichen IPC-Stand und Zugriff abnehmen, danach begrenzter Standort-Beobachtungslauf.
- R3c/R6: Write-/Rückgabe-Feldprüfung und DDC-Fallback bleiben Voraussetzungen vor Steuerungsbetrieb.
