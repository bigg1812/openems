# Mini EMS – UI-Styleguide (UX7)

Verbindliche Design-Referenz für das Dashboard (`dashboard/dashboard.css`) und kommende
UI-Arbeiten (UX3, UX5, UX6, UX8 sowie das Report-Styling aus UX2). Der Styleguide dokumentiert
die **tatsächlich vorhandenen** CSS-Variablen und Muster – wer neue UI baut, verwendet diese
Tokens und erfindet keine neuen Farben, Abstände oder Schriftgrößen.

Sprache der Oberfläche: klares Deutsch mit echten Umlauten, Wording aus
`PRODUCT_UX_KONZEPT.md`, Abschnitt 2. Keine internen IDs oder Protokollbegriffe außerhalb
der technischen Diagnose.

## 1. Leitprinzipien

1. **Ruhig:** Eine Tiefenebene. Karten sind flach (Border statt Schatten); Schatten gibt es nur
   für schwebende Ebenen (Tooltip, Modal). Keine Verläufe, keine Dekoration.
2. **Minimalistisch:** Farbe ist Bedeutung. Bunt ist nur, was einen Zustand oder eine Datenreihe
   codiert; alles andere bleibt neutral (`--ink`, `--muted`, `--line`).
3. **Scannbar:** Wichtiges zuerst und größer. Eine Hauptbotschaft pro Seite, Kennzahlen in
   priorisierter Reihenfolge, Statusfarbe als schmaler linker Balken statt großflächiger Fläche.
4. **Ehrlich:** Warnungen weder dramatisieren noch verharmlosen. Jeder kritische Zustand nennt
   den nächsten sinnvollen Schritt.

## 2. Themes und Farb-Tokens

Light/Dark wird über `data-theme` am `<html>`-Element geschaltet (persistiert in
`localStorage`, Schlüssel `miniEmsTheme`). **Alle** Farben kommen aus Tokens – nie Hexwerte
direkt in Komponenten oder JS-generiertem Markup verwenden. Diagramme lesen die Tokens zur
Laufzeit über `getComputedStyle` (siehe Abschnitt 7).

### 2.1 Flächen und Text

| Token | Light | Dark | Verwendung |
| --- | --- | --- | --- |
| `--bg` | `#eef2f6` | `#0a101b` | Seitenhintergrund |
| `--surface` | `#ffffff` | `#131c2b` | Karten, Panels, Eingabefelder |
| `--surface-soft` | `#f5f8fb` | `#0f1827` | eingebettete Flächen (Diagrammrahmen, Kacheln) |
| `--surface-strong` | `#eef3f8` | `#1b2638` | Hover-Flächen, Tabellenköpfe-Nähe |
| `--ink` | `#0f1b2d` | `#e9f0f8` | Primärtext |
| `--muted` | `#5b6b7e` | `#8a99ac` | Sekundärtext, Achsen, Untertitel |
| `--subtle` | `#8595a6` | `#6b7c90` | Micro-Labels, Kicker |
| `--line` | `#e4eaf1` | `rgba(255,255,255,0.09)` | Standard-Rahmen, Diagrammgitter |
| `--line-strong` | `#d2dbe6` | `rgba(255,255,255,0.16)` | Rahmen von Bedienelementen |

### 2.2 Akzent und Statusfarben

Statusfarben sind semantisch und an das Wording-Set gebunden – nicht dekorativ einsetzen.

| Token | Light | Dark | Bedeutung (UI-Text) |
| --- | --- | --- | --- |
| `--accent` / `--accent-ink` / `--accent-soft` | `#1769d6` / `#ffffff` / `#e7f0fd` | `#4f9bff` / `#06101f` / `rgba(79,155,255,0.16)` | Primäraktion, aktive Navigation, Fokus |
| `--ok` / `--ok-soft` | `#0f8a5f` / `#e7f6ef` | `#37d99a` / `rgba(55,217,154,0.15)` | Normalbetrieb, in Ordnung, Preisfenster |
| `--warn` / `--warn-soft` | `#a9700d` / `#fbf1da` | `#f0b13b` / `rgba(240,177,59,0.15)` | eingeschränkter Betrieb, Wert veraltet, wartet |
| `--alert` / `--alert-soft` | `#c23a32` / `#fdeceb` | `#f06d63` / `rgba(240,109,99,0.16)` | sicherer Modus, Messwert gestört, Übergabe gestört |
| `--neutral` | `#51647a` | `#9aabbd` | unbestimmt/informativ, "Jetzt"-Linie |

Regel: `*-soft` als Hintergrund immer mit der Vollfarbe als Text/Balken kombinieren
(z. B. Badge `background: var(--warn-soft); color: var(--warn);`).

### 2.3 Navigation (eigene, immer dunkle Fläche)

`--nav-bg` (`#0f1b2d` / `#070c14`), `--nav-ink` (`#b7c5d6` / `#8a99ac`),
`--nav-ink-strong` (`#ffffff`), `--nav-active` und `--nav-line`
(`rgba(255,255,255,0.10)` bzw. `0.08` im Dark-Theme).

### 2.4 Datenreihen (Diagramme)

`--series-1` … `--series-8`: Blau, Grün, Amber, Rot, Slate, Violett, Petrol, Magenta –
in dieser Reihenfolge vergeben (Light: `#1769d6 #0f8a5f #a9700d #c23a32 #51647a #7c3aed #0e7c8b #b83280`;
Dark: `#4f9bff #37d99a #f0b13b #f06d63 #9aabbd #a78bfa #2dd4bf #f472b6`).

## 3. Typografie

Schrift: `--font` = Inter (400/500/600, lokal aus `/vendor`, offline-fähig am IPC),
`--mono` für Rohdaten in der Diagnose. Basisgröße 14 px, Zeilenhöhe 1.5.
Negative Letter-Spacing (−0.01/−0.02 em) nur bei Überschriften und großen Zahlen.

| Größe | Gewicht | Verwendung |
| --- | --- | --- |
| 28 px | 600 | größter Messwert (Wetter „jetzt") |
| 24 px | 600 | KPI-Wert (`.metric-card strong`) |
| 20 px | 600 | Seitenüberschrift `h2` |
| 18–19 px | 600 | Topbar-Titel `h1` (19), Hauptbotschaft (18), Marke (18) |
| 15–17 px | 600 | Panel-Titel `h3` (15), Modal-/Berichtstitel (17) |
| 13–14 px | 400/500 | Fließtext, Tabellen, Buttons, Hinweise (13); Body-Basis (14) |
| 12 px | 400/500 | Untertitel, Meta, Achsenbeschriftung, Badges |
| 11 px | 500/600 | Micro-Labels/Kicker (Versalien, `letter-spacing: 0.06–0.07em`), Quality-Badges |

Zahlen im UI immer über die JS-Formatter (`formatNumber`, de-DE, Einheit mit schmalem Abstand).

## 4. Abstände, Radien, Schatten

| Token | Wert | Verwendung |
| --- | --- | --- |
| `--sp-1` … `--sp-6` | 4 / 8 / 12 / 16 / 24 / 32 px | einzige erlaubte Abstände (4/8-Raster) |
| `--radius-sm` | 8 px | Buttons, Inputs, Chips |
| `--radius-md` | 10 px | eingebettete Karten, Diagrammrahmen |
| `--radius-lg` | 12 px | Panels, KPI-Karten, Modal |
| `--radius-pill` | 999 px | Badges, Pills, Status-Punkt |
| `--shadow-raised` | Tooltip-Ebene | nur schwebende Elemente (`.ems-tooltip`) |
| `--shadow-overlay` | Modal-Ebene | nur Overlays (`.modal`) |

Vertikaler Rhythmus der Startseite: Abschnitte im Abstand `--sp-3` (Hauptbotschaft → KPIs →
Hinweise → Panels), Seiten-Padding `--sp-5`/`--sp-6`, Abstand unter Seitenkopf `--sp-5`.

## 5. Karten und Statusmuster

Grundkarte: `background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-lg); padding: var(--sp-4);`

- **`.metric-card` (KPI):** 3 px farbige Akzentleiste links (`accent-blue/green/amber/slate`),
  Label 12 px muted, Wert 24 px, Unterzeile 12 px muted. Quality-Badges unter dem Wert.
- **`.status-hero` (Hauptbotschaft, Startseite):** 4 px Statusbalken links
  (Level-Klassen `ok`/`warn`/`alert`, sonst `--neutral`), Headline 18 px,
  Erklärsatz mit nächstem Schritt in `--muted`, rechts „Stand …".
  Es gibt genau **eine** Hauptbotschaft pro Seite.
- **`.hint-item` / `.signal-card` (Hinweis-/Signalzeile):** 3 px Statusbalken links auf
  `--surface-soft`, ein kurzer Satz in Betreiber-Sprache. Levels: `ok`, `warn`, `alert`,
  neutral als Standard.
- **`.window-card`, `.report-tile`, `.stat-cell`:** neutrale Informationskacheln auf
  `--surface-soft`, Label klein/muted, Wert fett.

Leere Zustände: `.empty-state` (gestrichelter Rahmen, muted, zentriert) mit einem hilfreichen
Satz – nie leere Flächen oder rohe Fehlertexte.

## 6. Tabellen

`.table-wrap` (Rahmen + Radius + Scroll) um eine randlose Tabelle: Kopf 11 px Versalien auf
`--surface-soft`, Zellen 13 px mit `--line`-Trennlinien, letzte Zeile ohne Linie, Zellen-Padding
`--sp-3`, `white-space: nowrap`. Status in Tabellen als `.badge` (siehe Abschnitt 8), nie als
farbiger Zellenhintergrund.

## 7. Diagramm-Grundsätze (uPlot + SVG-Sparklines)

1. Farben zur Laufzeit aus Tokens lesen (`getComputedStyle`): Gitter `--line`, Achsen `--muted`
   (12 px `--font`), Reihen aus `--series-*`; nach Theme-Wechsel Charts neu aufbauen.
2. Flächen unter Linien maximal ~10–12 % Deckung; Preisfenster als `--ok` mit 16 % Deckung;
   „Jetzt"-Linie gestrichelt in `--neutral`.
3. Keine Legende im Chart – Titel und Einheit stehen im Panel-Kopf; Tooltip (`.ems-tooltip`)
   zeigt Zeitpunkt und formatierten Wert.
4. Achsenwerte über `formatAxis`/`Intl` (de-DE), Zeit als `HH:mm` bzw. `dd.MM`.
5. Höhen: Hauptdiagramm ~290 px, Kachel-/Berichtsdiagramme 200–220 px, Sparklines 150 px;
   Breite über `ResizeObserver` nachführen.

## 8. Badges

- **`.badge`** (Zustände, Tabellen): Pill, 12 px, `--surface-strong`/`--neutral`; Varianten
  `healthy`/`ok` (ok-soft/ok), `degraded`/`warn` (warn-soft/warn), `safe_mode`/`error`
  (alert-soft/alert). Text über `friendlyState()` – nie rohe Statuswörter.
- **`.quality-badge`** (Datenqualität an Kacheln): Pill, 11 px; `stale` = „Wert veraltet
  (seit …)" in warn, `bad` = „Messwert gestört" in alert; `good` bekommt **kein** Badge.
  Dieses Muster wird fortgeführt (Startseiten-Hinweise, Analyse, Berichte) und nicht ersetzt.
- **`.status-dot`** (Navigation): 9 px Punkt mit weichem Glow (`color-mix`, 22 %);
  Standard ok, Varianten `degraded` (warn) und `safe_mode`/`error` (alert).

## 9. Interaktionszustände

| Zustand | Regel |
| --- | --- |
| Hover | Flächenwechsel auf `--surface-strong` (Buttons, Optionen) bzw. `--nav-active`; Primärbutton dunkelt über `color-mix` ab; Transition 0.12 s ease |
| Fokus | `:focus-visible` mit `--ring` (3 px Akzent-Ring) auf Buttons, Links, Chips, Checkboxen; Eingabefelder zusätzlich `border-color: var(--accent)`; im Theme-Toggle Innenring `inset 0 0 0 2px var(--accent)` |
| Aktiv (Navigation) | `--nav-active`-Fläche + 2 px Akzentleiste (`inset box-shadow`) |
| Disabled | `opacity: 0.6; cursor: wait` (während Ladevorgängen); Aktionen, die eine Rolle nicht hat, werden ausgeblendet, nicht deaktiviert (Rollenmodell, `PRODUCT_UX_KONZEPT.md` 3.1) |
| Seitenwechsel | einzige Animation: `page-fade` 0.18 s (Opacity + 4 px Versatz) – keine weiteren Animationen |

## 10. Do / Don't

- **Do:** neue Komponenten aus vorhandenen Mustern zusammensetzen (Karte + Statusbalken +
  Badge); erst prüfen, ob ein Muster existiert.
- **Don't:** neue Hexfarben, Schatten auf Karten, mehr als eine Hauptbotschaft, farbige
  Großflächen für Warnungen, englische Zustandswörter oder interne Kanal-IDs in normalen
  Ansichten, zusätzliche Schriftgrößen außerhalb der Skala.

## 11. Responsive Verhalten (UX9)

Leitprinzip: Mobile-Optimierung darf die Desktop-Bedienung nicht verschlechtern.
Ab Desktop (>= 1280px) bleibt das Layout unverändert; die Regeln greifen erst darunter.

**Zwei bewusste Breakpoints** (mehr gibt es nicht):

| Breakpoint | Verhalten |
| --- | --- |
| **Tablet/Schmal** (`max-width: 1180px`) | Sidebar wird zur horizontalen Kopfnavigation (sticky), die einzeilig bleibt und bei Bedarf horizontal scrollt (kein zweizeiliger Umbruch). Seitenlayouts (`dashboard-layout`, `system-layout`, `report-layout`, `channel-layout`, `admin-config-layout`) werden einspaltig; feste 4er-/3er-Raster fallen auf 2 Spalten bzw. auto-fit. Deckt Tablet quer (1024) und schmale Desktop-Fenster (~800–1100px) ab. Touch-Ziele der Hauptaktionen (Button, Theme-Toggle, Segmented) mindestens 40px hoch. |
| **Kompakt** (`max-width: 760px`) | Kopfzeile, Aktionsleisten und Raster werden einspaltig; das Sidebar-Band bricht in zwei geordnete Reihen um (Marke + Status, Navigation darunter). Hauptaktionen dürfen volle Breite einnehmen. |

**Grid-Prinzip:** Wo eine feste Spaltenzahl nur zufällig passt, `repeat(auto-fit, minmax(<min>, 1fr))`
verwenden (Muster `.chart-stats`), damit Karten selbstständig umbrechen statt abgeschnitten zu werden.
Desktop-Spaltenzahlen, die bewusst gesetzt sind (KPI 4, Analyse-Karten 3, Preisfenster 2), bleiben als
feste Basis erhalten und werden erst unter 1180px aufgelöst — keine stille Desktop-Regression.

**Tabellen-Regel:** Tabellen stehen immer in `.table-wrap` (Rahmen + Radius + `overflow: auto`) und
scrollen bei Platzmangel horizontal innerhalb dieses Containers, statt das Seitenlayout zu sprengen
(`white-space: nowrap` an den Zellen bleibt erhalten).
