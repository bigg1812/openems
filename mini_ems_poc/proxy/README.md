# Mini EMS – Reverse Proxy (H4)

Dieses Verzeichnis liefert die **Vorstufe zu H4** aus `ROADMAP.md`: die
Mini-EMS-API wird intern an `127.0.0.1` gebunden und ausschließlich über einen
lokalen Reverse Proxy (Caddy) mit HTTPS erreichbar gemacht. Das Konzept, die
Bindungs-Matrix und die Sicherheits-Ehrlichkeit dazu stehen in
`HOSTING_SICHERHEIT.md`, **Teil 4**. Dieses README ist die praktische
Installationsanleitung.

> **Was diese Stufe leistet und was nicht.** H4 nimmt die technische API aus dem
> Netz (sie hört nur noch auf `127.0.0.1`), stellt TLS bereit und kanalisiert den
> Zugriff über genau einen Einstiegspunkt. H4 ist **kein Login**: Wer den Proxy im
> Kundennetz/VPN erreicht, sieht das Dashboard ohne Passwort. Login und Rollen
> (`viewer`/`operator`/`admin`) kommen mit **H6**. Der Schutz endet außerdem beim
> Kunden-Administrator der IPC (Grenze aus `HOSTING_SICHERHEIT.md`, Teil 1.3).

## Inhalt

| Datei | Zweck |
|---|---|
| `Caddyfile` | kommentierte Reverse-Proxy-Vorlage (HTTPS intern, reverse_proxy auf `127.0.0.1:8090`, auskommentierter Login-Block für H6) |
| `firewall_rules.ps1` | kopierbare Windows-Firewall-Regeln (Proxy-Port nur Kundennetz, 8090 nur lokal) |
| `README.md` | diese Datei |

Analog zu `packaging/` sind das **nur Vorlagen**. Sie ändern nichts an Mini EMS,
an `config.json` oder an `windows/*.ps1`. Zugangsdaten/Passwort-Hashes gehören
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
Integration als Windows-Dienst; das passt zur Release-Paket-Philosophie und hält
die Betriebsschritte minimal.

## Voraussetzungen auf der IPC

1. `caddy.exe` (Windows-Build von <https://caddyserver.com/download>) an einen
   festen Ort legen, z. B. `C:\Program Files\Caddy\caddy.exe`.
2. Diese `Caddyfile`-Vorlage kopieren, z. B. nach
   `C:\ProgramData\MiniEMS\proxy\Caddyfile`, und die `<...>`-Platzhalter anpassen
   (Hostname/IP, ggf. Port).
3. **Mini-EMS-API auf lokal umstellen** (Admin-Arbeit an `config.json`, gehört
   nicht in dieses Repo): im `api`-Block `host` auf `127.0.0.1` setzen und
   `read_only: true` ergänzen. Danach ist 8090 nur noch lokal erreichbar, und die
   read-only Grenze gilt zusätzlich serverseitig (siehe `HOSTING_SICHERHEIT.md`
   2.1/Teil 4). Anschließend Mini EMS neu starten.

   ```json
   "api": {
     "enabled": true,
     "host": "127.0.0.1",
     "port": 8090,
     "history_default_limit": 96,
     "read_only": true
   }
   ```

## Installation als Windows-Dienst

Caddy bringt keinen eigenen Windows-Dienst mit; empfohlen ist der native
`sc.exe`-Dienst. Als Administrator:

```powershell
# Dienst anlegen (Autostart), mit explizitem Config-Pfad
sc.exe create caddy start= auto binPath= "C:\Program Files\Caddy\caddy.exe run --config C:\ProgramData\MiniEMS\proxy\Caddyfile"

# Bei Absturz automatisch neu starten (nach 5 s, dauerhaft)
sc.exe failure caddy reset= 0 actions= restart/5000

# Starten
sc.exe start caddy
```

Nach einer Änderung an der `Caddyfile` lädt der Dienst die Konfiguration **nicht**
automatisch neu; explizit nachladen:

```powershell
& "C:\Program Files\Caddy\caddy.exe" reload --config C:\ProgramData\MiniEMS\proxy\Caddyfile
```

Alternativ – konsistent zum bestehenden `MiniEmsPoC`-Task – kann Caddy auch als
geplanter Windows-Task mit `-AtStartup` laufen (wie `windows/install_task.ps1` für
Mini EMS, hier nur als Muster genannt, nicht vorgegeben). Für einen dauerhaft
lauschenden Netzwerkdienst ist der `sc.exe`-Dienst mit Restart-Aktion aber die
robustere Wahl.

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

1. Lokal auf der IPC: `curl http://127.0.0.1:8090/api/status` → `200` (API lebt lokal).
2. Lokal über den Proxy: `curl -k https://<hostname>/api/status` → `200`.
3. Vom zweiten Rechner (Kundennetz/VPN): `curl -k https://<hostname>/api/status`
   → `200`; `curl http://192.168.244.10:8090/api/status` → Verbindung abgelehnt
   (API nicht mehr direkt im Netz).
4. Schreib-/Aktiv-Endpunkte über den Proxy: `curl -k -X POST
   https://<hostname>/api/config/spotmarket-lockout` → `403 read_only_mode`;
   `curl -k https://<hostname>/api/diagnostics/read` → `403`.

## Abgrenzung zum Secomea-Pfad

Der heutige Betrieb (`HOSTING_SICHERHEIT.md`, Teil 2, Pfad a) bindet die API an
die EMS-LAN-IP `192.168.244.10:8090` und erreicht sie über Secomea/VPN **direkt**,
ohne Proxy und ohne TLS. Dieser Proxy ist eine **optionale Stufe davor**, kein
Ersatz: Er kanalisiert denselben VPN-Zugriff über HTTPS und einen einzigen
Einstiegspunkt und macht 8090 im Netz unsichtbar. Solange der Proxy nicht
eingerichtet ist, bleibt Pfad a unverändert gültig.

## Beim Mini-EMS-Update

Der Proxy ist ein **eigener** Dienst und muss für ein Mini-EMS-Update (Ablauf in
`UPDATE_WARTUNG.md`, Abschnitt 2) **nicht** gestoppt werden. Während Mini EMS
neu startet, liefert der Proxy kurz `502` und erholt sich automatisch, sobald
`127.0.0.1:8090` wieder antwortet. Neu gestartet/nachgeladen werden muss der
Proxy nur, wenn sich die `Caddyfile` oder die `caddy.exe` selbst ändert.

## Ausblick H6

Der auskommentierte `basic_auth`-Block in der `Caddyfile` ist die vorbereitete
Andockstelle für den ersten Zugriffsschutz. Er bleibt inaktiv, bis H6 freigegeben
ist; Passwort-Hashes werden dann mit `caddy hash-password` erzeugt und **außerhalb
des Repos** gehalten. Die vollständige Rollenlogik (`viewer`/`operator`/`admin`)
ist Gegenstand von H6 und `PRODUCT_UX_KONZEPT.md`, Abschnitt 3.
