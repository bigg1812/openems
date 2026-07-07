# Mini EMS – Firewall-Regeln fuer den Reverse Proxy (H4)
# =====================================================================
# KOPIERVORLAGE fuer die Windows-IPC. Als Administrator ausfuehren.
# Aendert nichts an Mini EMS oder an windows/*.ps1; setzt nur
# Windows-Firewall-Regeln fuer die H4-Bindungsstufe.
#
# Zielbild (HOSTING_SICHERHEIT.md, Teil 4):
#   - Mini-EMS-API (8090) ist NUR lokal gebunden (api.host=127.0.0.1)
#     und damit ohnehin nicht im Netz. Die Block-Regel ist Redundanz
#     (defense in depth), falls die Bindung je auf eine LAN-IP zurueckfaellt.
#   - Der Proxy-Port (HTTPS, hier 443) ist NUR aus dem Kundennetz/VPN
#     erreichbar, nie aus dem Internet.
#
# Platzhalter anpassen:
#   $ProxyPort      -> HTTPS-Port des Proxys (443 oder z. B. 8443)
#   $Kundennetz     -> Subnetz(e), aus denen der Zugriff erlaubt ist
#                      (Kundennetz und/oder VPN-Adressbereich)
# =====================================================================

$ProxyPort  = 443
$ApiPort    = 8090
$Kundennetz = "192.168.244.0/24"   # <-- an das reale Kundennetz/VPN anpassen

# --- 1. Proxy-Port nur aus dem Kundennetz/VPN zulassen ----------------
New-NetFirewallRule `
	-DisplayName "MiniEMS Proxy HTTPS (nur Kundennetz)" `
	-Direction Inbound -Action Allow -Protocol TCP `
	-LocalPort $ProxyPort `
	-RemoteAddress $Kundennetz `
	-Profile Domain,Private

# --- 2. API-Port 8090 eingehend aus dem Netz blockieren ---------------
# Hinweis: Windows-Firewall filtert Loopback (127.0.0.1) NICHT. Diese
# Regel unterbindet daher NUR Netzzugriffe von aussen; der Proxy erreicht
# 127.0.0.1:8090 weiterhin. Bei api.host=127.0.0.1 ist 8090 ohnehin nicht
# im Netz – die Regel ist bewusst Redundanz.
New-NetFirewallRule `
	-DisplayName "MiniEMS API 8090 (nur lokal, Netz blockiert)" `
	-Direction Inbound -Action Block -Protocol TCP `
	-LocalPort $ApiPort `
	-RemoteAddress Any

# --- Pruefen ----------------------------------------------------------
# Get-NetFirewallRule -DisplayName "MiniEMS*" |
#   Format-Table DisplayName, Direction, Action, Enabled
#
# Erwartet: die Allow-Regel fuer den Proxy-Port und die Block-Regel fuer 8090.

# --- Zuruecknehmen (bei Bedarf) ---------------------------------------
# Remove-NetFirewallRule -DisplayName "MiniEMS Proxy HTTPS (nur Kundennetz)"
# Remove-NetFirewallRule -DisplayName "MiniEMS API 8090 (nur lokal, Netz blockiert)"
