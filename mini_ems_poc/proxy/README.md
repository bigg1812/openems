# Mini EMS – Reverse Proxy (H4)

Dieses Verzeichnis liefert den **H4-Reverse-Proxy** aus `ROADMAP.md`: die
Mini-EMS-API wird intern an `127.0.0.1` gebunden und ausschließlich über einen
lokalen Reverse Proxy (Caddy) mit HTTPS erreichbar gemacht. Das Konzept, die
Bindungs-Matrix und die Sicherheits-Ehrlichkeit dazu stehen in
`HOSTING_SICHERHEIT.md`, **Teil 4**. Dieses README ist die praktische
Installationsanleitung.

> **Was Caddy leistet und was nicht.** Caddy nimmt die technische API aus dem
> Netz (sie hört nur noch auf `127.0.0.1`), stellt TLS bereit und kanalisiert den
> Zugriff über genau einen Einstiegspunkt. Login und Rollen liegen seit H6 in
> Mini EMS selbst: Ohne Sitzung sind nur die Anmeldeseite und `/api/health`
> erreichbar; Viewer lesen, Admins verwalten. Caddy ersetzt diese Rollenprüfung
> nicht. Der Schutz endet außerdem beim Kunden-Administrator der IPC (Grenze aus
> `HOSTING_SICHERHEIT.md`, Teil 1.3).

## Inhalt

| Datei | Zweck |
|---|---|
| `Caddyfile` | kommentierte Reverse-Proxy-Vorlage (HTTPS intern, `reverse_proxy` auf `127.0.0.1:8090`) |
| `firewall_rules.ps1` | kopierbare Windows-Firewall-Regeln (Proxy-Port nur Kundennetz, 8090 nur lokal) |
| `README.md` | diese Datei |

Analog zu `packaging/` sind das **nur Vorlagen**. Sie ändern nichts an Mini EMS,
am Standort-Speicher oder an `windows/*.ps1`. Zugangsdaten/Passwort-Hashes gehören
**nie** in dieses Verzeichnis oder ins Git.

## Warum Caddy

Kurzvergleich der drei naheliegenden Optionen für die Windows-IPC:

- **Caddy (Empfehlung).** Eine einzige Binary (`caddy.exe`), kein Installer, kein
  Runtime-Unterbau. Automatisches, intern vertrauenswürdiges HTTPS über die
  eingebaute lokale CA (`tls internal`) – ohne Internet-CA, was für eine IPC ohne
  öffentliche Erreichbarkeit genau passt. Die "eine Binary neben einer Konfig"-
  Philosophie deckt sich mit dem Release-Paket-Ansatz aus `packaging/`.
- **nginx für Windows.** Funktioniert, aber HTTPS-Zertifikate müssen manuell
  erzeugt und erneuert werden, und der Windows-Build gilt als zweitrangig
  gepflegt. Mehr Handarbeit für denselben Zweck.
- **IIS mit URL-Rewrite/ARR.** Bereits im Windows-Ökosystem, aber schwergewichtig:
  Rollen/Features aktivieren, ARR- und URL-Rewrite-Module nachinstallieren,
  Zertifikate über den Windows-Zertifikatspeicher verwalten. Deutlich mehr
  bewegliche Teile als eine einzelne Binary.

**Empfehlung: Caddy** – eine Binary, automatisches internes HTTPS, einfache
Integration als geplanter Windows-Task; das passt zur Release-Paket-Philosophie und hält
die Betriebsschritte minimal.

## Voraussetzungen auf der IPC

1. `caddy.exe` (Windows-Build von <https://caddyserver.com/download>) an einen
   festen Ort legen, z. B. `C:\Program Files\Caddy\caddy.exe`.
2. Diese `Caddyfile`-Vorlage kopieren, z. B. nach
   `C:\ProgramData\MiniEMS\proxy\Caddyfile`, und die `<...>`-Platzhalter anpassen
   (Hostname/IP, ggf. Port).
3. **Mini-EMS-API auf lokal umstellen:** als Admin unter **Standort einrichten →
   Technische Einstellungen** `api.host` auf `127.0.0.1` und `api.read_only` auf
   `true` setzen, speichern und Mini EMS neu starten. Die Änderung landet als
   Revision in `C:\ProgramData\MiniEMS\site.sqlite`; `config.json` ist nur noch
   ein einmaliger Migrationseingang. Danach ist 8090 nur lokal erreichbar, und
   die read-only Grenze gilt zusätzlich serverseitig (siehe
   `HOSTING_SICHERHEIT.md` 2.1/Teil 4).

   ```json
   "api": {
     "enabled": true,
     "host": "127.0.0.1",
     "port": 8090,
     "history_default_limit": 96,
     "read_only": true
   }
   ```

## Installation als geplanter Windows-Task (empfohlen)

> **Wichtig – auf der Pilot-IPC (2026-07-07) verifiziert:** Ein nativer
> `sc.exe`-Dienst mit `caddy run` funktioniert auf Windows **nicht** zuverlässig.
> `caddy run` ist ein Konsolenprozess ohne Windows-Service-Handler; der SCM
> beendet ihn nach ~30 s `START_PENDING` (dieselbe Ursache wie beim
> Legacy-`MiniEmsPoC`-Dienst, Fehler 1053, siehe `AGENTS.md` Abschnitt 8).
> Deshalb läuft Caddy hier als **geplanter Task** – konsistent zu
> `MiniEmsPoCRelease`.

Als Administrator (PowerShell):

```powershell
$caddy = 'C:\Program Files\Caddy\caddy.exe'
$cfg   = 'C:\ProgramData\MiniEMS\proxy\Caddyfile'
$action    = New-ScheduledTaskAction -Execute $caddy -Argument "run --config `"$cfg`""
$trigger   = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) `
               -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'MiniEmsDashboardCaddy' -Action $action `
  -Trigger $trigger -Principal $principal -Settings $settings -Force
Start-ScheduledTask -TaskName 'MiniEmsDashboardCaddy'
```

Nach einer Änderung an der `Caddyfile` lädt der Task die Konfiguration **nicht**
automatisch neu; explizit nachladen:

```powershell
& "C:\Program Files\Caddy\caddy.exe" reload --config C:\ProgramData\MiniEMS\proxy\Caddyfile
```

Die `Caddyfile` in diesem Verzeichnis enthält bereits die beiden dafür nötigen
globalen Optionen: `skip_install_trust` (kein blockierender Zertifikatspeicher-
Dialog im Task-Betrieb) und `auto_https disable_redirects` (kein Port-80-Redirect-
Listener – Port 80 ist auf einer IPC oft durch `http.sys`/IIS belegt und würde
sonst den gesamten Caddy-Start scheitern lassen).

## Firewall

Die Regeln stehen in `firewall_rules.ps1` (als Administrator ausführen). Kurz:

- **Proxy-Port (HTTPS, z. B. 443)** nur aus dem Kundennetz/VPN-Bereich zulassen –
  nie aus dem Internet, keine WAN-Portweiterleitung.
- **API-Port 8090** eingehend aus dem Netz blockieren. Bei `api.host=127.0.0.1`
  ist 8090 ohnehin nicht im Netz; die Block-Regel ist bewusst Redundanz. Windows
  filtert Loopback nicht, daher erreicht der Proxy `127.0.0.1:8090` weiterhin.

Das Subnetz (`$Kundennetz`) und den Proxy-Port an die reale Umgebung anpassen.

## Zertifikat auf dem Client

`tls internal` erzeugt Zertifikate aus Caddys **lokaler** CA. Der zweite Rechner
(Betreiber/Gast) kennt diese CA zunächst nicht und zeigt ohne Vorbereitung eine
Zertifikatswarnung. Zwei saubere Wege:

- Caddys Root-CA einmalig auf den Client exportieren und dort als
  vertrauenswürdige Stammzertifizierungsstelle importieren (Datei liegt auf der
  IPC unter Caddys Datenordner, `pki/authorities/local/root.crt`).
- Oder: die Warnung im Kundennetz/VPN bewusst akzeptieren, solange kein Root-CA-
  Rollout gewünscht ist. Für `curl`-Prüfungen im internen Netz reicht `-k`.

Wird ein **Hostname** in der `Caddyfile` verwendet, braucht der Client zusätzlich
einen DNS- oder `hosts`-Eintrag `<hostname> -> 192.168.244.10`.

## Prüfschritte nach der Installation

Ausführlich (curl von innen/außen, erwartete Ergebnisse) in
`HOSTING_SICHERHEIT.md`, **Teil 4, Verifikations-Checkliste**. Kurzform:

1. Lokal auf der IPC: `curl http://127.0.0.1:8090/api/health` → `200` (API lebt lokal).
2. Lokal über den Proxy: `curl -k https://<hostname>/api/health` → `200`.
3. Vom zweiten Rechner (Kundennetz/VPN): `curl -k https://<hostname>/api/health`
   → `200`; Dashboard öffnen und anmelden; `curl http://192.168.244.10:8090/api/health` → Verbindung abgelehnt
   (API nicht mehr direkt im Netz).
4. Schreib-/Aktiv-Endpunkte über den Proxy: `curl -k -X POST
   https://<hostname>/api/config/spotmarket-lockout` → `403 read_only_mode`;
   `curl -k https://<hostname>/api/diagnostics/read` → `403`.

## Abgrenzung zum direkten Secomea-Pfad

Der frühere Direktpfad bindet die API an die EMS-LAN-IP
`192.168.244.10:8090` und erreicht sie über Secomea/VPN ohne Proxy und ohne TLS.
Die App-Anmeldung gilt auch dort, aber der Transport ist schwächer. Der
empfohlene Produktivpfad führt Secomea/VPN deshalb über Caddy/HTTPS und hält 8090
im Netz unsichtbar.

## Beim Mini-EMS-Update

Der Proxy ist ein **eigener** Dienst und muss für ein Mini-EMS-Update (Ablauf in
`UPDATE_WARTUNG.md`, Abschnitt 2) **nicht** gestoppt werden. Während Mini EMS
neu startet, liefert der Proxy kurz `502` und erholt sich automatisch, sobald
`127.0.0.1:8090` wieder antwortet. Neu gestartet/nachgeladen werden muss der
Proxy nur, wenn sich die `Caddyfile` oder die `caddy.exe` selbst ändert.

## Login und Rollen

H6 ist in Mini EMS umgesetzt. Persönliche Viewer-/Admin-Konten, Passworthashes,
serverseitige Sitzungen und Rollenprüfungen liegen in
`C:\ProgramData\MiniEMS\identity.sqlite`. Ein zusätzlicher Caddy-`basic_auth`-
Block ist für den normalen Betrieb nicht nötig und würde nur eine zweite,
getrennte Passwortschicht erzeugen.
