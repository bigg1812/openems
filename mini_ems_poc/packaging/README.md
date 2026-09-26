# Mini EMS – Paketbau

Der Release-Betrieb verwendet ein One-Dir-Paket und einen externen Standortordner. Die einzige aktive
Konfigurationsquelle ist dessen `site.sqlite`. Installation und Erststart stehen in
[RELEASE_WORKFLOW.md](../RELEASE_WORKFLOW.md), Abnahme und Rollback in [UPDATE_WARTUNG.md](../UPDATE_WARTUNG.md).

## Festes Prüfprofil

Python 3.12; Build-Abhängigkeiten aus `requirements-build.txt`. Die Versionen sind festgeschrieben,
`BUILD_REQUIREMENTS.txt` dokumentiert zusätzlich die tatsächlich installierten Pakete. Das ist ein
wiederholbarer Build-Ablauf, keine Zusage bitidentischer Binärdateien auf unterschiedlichen Systemen.

Enthalten: Runtime, BACnet-/Modbus-Adapter, Dashboard, uPlot, Schriftdateien, Simulation und IANA-Zeitzonen.
Berichte verwenden den eingebauten HTML-Renderer und die Browser-Druckfunktion für PDF. Die optionalen
Quellcode-Erweiterungen Jinja2, WeasyPrint und BACpypes3 werden bewusst ausgeschlossen; ihre Installation auf
dem Build-Rechner verändert das Release-Profil nicht. Nicht benötigte Jinja-Vorlagen werden nicht mitgeliefert.

Unter `windows/` werden nur `install_task.ps1`, `update_release.ps1` und `smoketest_release.ps1` ausgeliefert.
Der veraltete Service-Installer und der Python-Dashboard-Proxy bleiben historische Quellcodehilfen.

## Lokal bauen und das Binary prüfen

Aus dem Repository-Stamm auf macOS/Linux:

```bash
python3.12 -m venv /tmp/mini-ems-build
/tmp/mini-ems-build/bin/python -m pip install -r mini_ems_poc/packaging/requirements-build.txt
MINI_EMS_VERSION=2026.09.1 PYTHON=/tmp/mini-ems-build/bin/python bash mini_ems_poc/packaging/build_release.sh
python3.12 mini_ems_poc/packaging/verify_release.py --package mini_ems_poc/packaging/dist/mini_ems
```

Unter Windows, ebenfalls aus dem Repository-Stamm:

```powershell
py -3.12 -m venv mini_ems_poc\.venv
mini_ems_poc\.venv\Scripts\python.exe -m pip install -r mini_ems_poc\packaging\requirements-build.txt
mini_ems_poc\packaging\build_release.ps1 -Version 2026.09.1 -Python mini_ems_poc\.venv\Scripts\python.exe
mini_ems_poc\.venv\Scripts\python.exe mini_ems_poc\packaging\verify_release.py --package mini_ems_poc\packaging\dist\mini_ems
```

Die Version ist ein expliziter Pflichtparameter im Format `JJJJ.MM.n`; für die nächste veröffentlichte Version
bewusst erhöhen. `.github/workflows/mini-ems.yml` führt Tests, Paketbau und Binary-Prüfung auf Linux/Windows aus
und bewahrt nur erfolgreiche Kandidaten als Artefakt auf. Ein angelegter Workflow ist kein bestandener CI-Lauf.

`verify_release.py` erzeugt ausschließlich temporäre simulierte Standorte. Es prüft alle Prüfsummen,
Erststart, Anmeldung, Viewer-Rechte, read-only Zugriff, Prozessabsturz/Wiederanlauf, Standortkopie/Restore,
SQLite-Integrität und die Unverändertheit des Programmpakets. Es registriert keinen Windows-Task und
verbindet sich mit keiner Anlage. Task/SYSTEM, VPN, Caddy und echte Geräte brauchen eigene Nachweise.

## Paket und Version

Ausgabe: `packaging/dist/mini_ems/`. `build/` und `dist/` unter `packaging/` sind ignorierte Build-Verzeichnisse.
Sie werden bei einem neuen Build ersetzt; Standortdaten dürfen dort nie abgelegt werden.

Das Paket enthält `VERSION` mit Version, Build-Zeit, Commit und Plattform, einen Changelog-Schnappschuss,
`SHA256SUMS`, `BUILD_REQUIREMENTS.txt` und `RELEASE_HINWEISE.md`. Der Launcher startet `--supervise`.
`+dirty` bezeichnet einen lokalen Prüfstand und ist keine Freigabe für den Produktiveinsatz.

Für eine Übergabe: Änderungen prüfen, bekannten Commit sichern, daraus auf Windows bauen und prüfen,
Paket unverändert transportieren und anhand der Prüfsummen vergleichen. Der Build schreibt keinen
Release-Eintrag in den Quellcode-Changelog; dieser wird bei der tatsächlichen Release-Freigabe nachgezogen.

Die Ressourcenauflösung in `resources.py` trennt Programmpaket und Standortdaten. Ein Wechsel des Packagers
ist nicht Teil dieses Arbeitsblocks; die bestehende PyInstaller-Spec ist der verbindliche Build-Einstieg.
