## 0. Python-Version

**Mini EMS braucht Python >= 3.10. Verwende `python3.12` bzw. die Projekt-`.venv`.**

- Der Code nutzt PEP-604-Syntax (`X | None`). Der Standard-`python3` vieler Laptops (z. B. macOS-System-Python)
  ist 3.9 und scheitert damit tief im Import mit einem kryptischen `TypeError`, nicht mit einer klaren Meldung.
- `mini_ems.py` prüft die Version deshalb selbst ganz am Anfang und bricht bei < 3.10 mit einer eindeutigen
  deutschen Fehlermeldung und Exit-Code `1` ab.
- Exakter Interpreter: `python3.12` oder `/Users/gabriel/dev/openems/.venv/bin/python`.
- Tests: `/Users/gabriel/dev/openems/.venv/bin/python -m unittest discover -s mini_ems_poc/tests -v`.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## 5. Mini EMS File Overview

**Keep technical roadmap, product UX, and runtime docs separate.**

- `README.md` is the short project entry point: purpose, MVP scope, core files, and documentation links.
- `MINI_EMS_ANLEITUNG.md` is the operational and technical runbook: configuration, runtime behavior, API, dashboard, IPC operation, and troubleshooting.
- `ROADMAP.md` is the technical roadmap: architecture, data quality, safety, deployment, protected customer hosting, and operational hardening.
- `PRODUCT_UX_ROADMAP.md` is the product and UX roadmap: reporting quality, easier user flows, modern minimal UI direction, wording, roles, and demo readiness.
- `EMS-Mapping.md` is the protocol and channel mapping reference: how external points become Mini EMS channels and how future protocol adapters should stay aligned.
- `config.json` is the real IPC/site configuration. Treat it as plant operation.
- `config.local.json` is the local simulation configuration. Use it for laptop development.
- `dashboard/` contains the browser UI. Customer-facing UI text must use clear German and hide internal IDs unless the view is explicitly technical diagnostics.
- `mini_ems_runtime/` contains runtime code. Keep business logic, protocol access, API, persistence, and reporting changes scoped to the relevant module.
- `windows/`, `run_mini_ems.cmd`, logs, data, and runtime state belong to deployment and operation, not product UX.

When a discussion surfaces a sensible future architecture or product idea, add it to `ROADMAP.md` or
`PRODUCT_UX_ROADMAP.md` if it is missing or too vague. Mark it as a future option with benefit, risks, and
scope; do not silently turn it into immediate implementation work.

## 6. German UI Language

**Use real German umlauts in user-facing German text.**

- Write `ä`, `ö`, `ü`, `Ä`, `Ö`, `Ü` and `ß` directly.
- Do not write `ae`, `oe`, `ue` or `ss` as replacements in German UI copy, documentation, or messages unless the target system technically requires ASCII.
- Customer-facing UI must use plain business language. Do not show internal IDs such as `ems.lockout_spotmarket`, BACnet object names, or protocol terms unless the screen is explicitly technical diagnostics.

## 7. Local vs IPC Safety

**The laptop is for simulation. The IPC is for real plant operation.**

- Keep `config.json` as the real IPC configuration unless the user explicitly asks to change plant operation.
- Use `config.local.json` for laptop work.
- Local development must use `runtime.bacnet_mode=simulated` and `runtime.real_writes_enabled=false`.
- Do not add a code path that sends real BACnet writes from `environment=local`.
- If you need test values, edit `sim/sample_values.json` or `sim/sample_prices.json` instead of changing real BACnet points.

## 8. IPC Restart / Secomea Runbook

**Use the packaged release task (production default), not the legacy Windows service. The Git-checkout task is a development/fallback path only.**

> **Stand 2026-07-08 – Produktionspfad ist das Release-Paket hinter Caddy.** Die Pilot-IPC läuft
> `C:\Program Files\MiniEMS\mini_ems.exe --config C:\ProgramData\MiniEMS\config.json --loop` über den
> geplanten Task **`MiniEmsPoCRelease`** (SYSTEM, Boot-Trigger). Mini EMS bindet lokal auf
> `127.0.0.1:8090`; ein Caddy-Reverse-Proxy (Task `MiniEmsDashboardCaddy`) lauscht auf
> `192.168.244.10:443` und leitet intern auf `127.0.0.1:8090` weiter; `api.read_only` ist aktiv.
> `C:\ProgramData\MiniEMS` ist per ACL auf Administratoren/SYSTEM gehärtet. Die konkurrierenden
> Alt-Autostarts sind entschärft: der alte Dev-Task `MiniEmsPoC` ist **deaktiviert**, der Legacy-Dienst
> `MiniEmsPoC` steht auf **Manual**, der Task `MiniEmsDashboardProxy` ist **deaktiviert**. Der
> Checkout-Ablauf unten (`install_task.ps1 -Mode checkout`, `run_mini_ems.cmd`, `mini_ems.py`) bleibt als
> Entwicklungs-/Rollback-Pfad verfügbar, ist aber **nicht** der aktuelle Produktionspfad. Details:
> `ROADMAP.md` ("Aktueller IPC-Stand"), `RELEASE_WORKFLOW.md`, `UPDATE_WARTUNG.md`,
> `HOSTING_SICHERHEIT.md` Teil 4.

- Do not use `sc.exe start MiniEmsPoC` as a runtime path. The `MiniEmsPoC` Windows service entry is legacy and can fail with `StartService FEHLER 1053` because `mini_ems.py` is a console process, not a native Windows service.
- **Production start path (default): the release task.** `windows/install_task.ps1 -Mode release` plus `run_mini_ems_release.cmd` start `mini_ems.exe` from `C:\Program Files\MiniEMS` against the external `C:\ProgramData\MiniEMS\config.json`. Production binds the API to `127.0.0.1:8090` with `api.read_only: true`; the Caddy proxy exposes the dashboard/API on `https://192.168.244.10`. See `RELEASE_WORKFLOW.md` for a full new-install walkthrough and `UPDATE_WARTUNG.md` for updates.
- **Development/fallback start path: the checkout task.** `windows/install_task.ps1` (`-Mode checkout`) plus `run_mini_ems.cmd` start `mini_ems.py` directly from the Git checkout against the checkout's `config.json`, binding to `192.168.244.10:8090` directly (no proxy, no `api.read_only`). This path stays available for development/rollback but is **not** the current production path on the pilot IPC.
- The local simulation uses `config.local.json`, binds to `127.0.0.1:8090`, and is not reachable through Secomea.

Install or repair the release task from an elevated PowerShell (production path):

```powershell
cd C:\dev\openems\mini_ems_poc
.\windows\install_task.ps1 `
  -Mode release `
  -TaskName MiniEmsPoCRelease `
  -AppDir "C:\Program Files\MiniEMS" `
  -ConfigPath "C:\ProgramData\MiniEMS\config.json" `
  -StartNow:$false
```

For the older checkout/development path:

```powershell
cd C:\dev\openems\mini_ems_poc
.\windows\install_task.ps1 `
  -Mode checkout `
  -TaskName MiniEmsPoC `
  -ProjectDir C:\dev\openems\mini_ems_poc `
  -PythonPath python `
  -StartNow:$false
```

`-PythonPath` accepts a bare command (resolved via `Get-Command`) or an absolute path;
`python` is the default, so the flag can usually be omitted. Do **not** use
`windows/install_service.ps1` — it is a deprecated legacy helper (see the banner in that file).

Start the IPC runtime (production):

```powershell
Start-ScheduledTask -TaskName MiniEmsPoCRelease
```

Verify that Secomea/the customer network can reach the dashboard (production, release path):

```powershell
Get-NetTCPConnection -LocalPort 8090
Get-NetTCPConnection -LocalPort 443
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8090/api/status
Invoke-WebRequest -UseBasicParsing -SkipCertificateCheck https://192.168.244.10/dashboard
Get-Content C:\ProgramData\MiniEMS\runtime\health.json
```

Expected state (production, release path):

- `8090` listens only on `127.0.0.1` (not on `192.168.244.10`); a direct `http://192.168.244.10:8090/dashboard` request must **not** succeed anymore.
- Exactly one listener on `192.168.244.10:443`, owned by `caddy.exe` (task `MiniEmsDashboardCaddy`).
- The owning process command line contains `mini_ems.exe --config C:\ProgramData\MiniEMS\config.json --loop`, started by task `MiniEmsPoCRelease` — not `mini_ems.py` from the Git checkout.
- `C:\ProgramData\MiniEMS\runtime\health.json` is current and reports `status: healthy`.
- `https://192.168.244.10/dashboard` and `/api/status` return HTTP `200`; `/api/status` reports `api_read_only: true`.

If the task view shows `Ready` but the dashboard works, trust the process and health checks first. The wrapper may leave the actual `mini_ems.exe` process running through `run_mini_ems_release.cmd`; verify by checking port `8090`/`443`, process command line, and `health.json`.

Stop the runtime only when needed:

```powershell
Get-NetTCPConnection -LocalPort 8090
taskkill /PID <OwningProcess> /T /F
```

For the older checkout/development path, the equivalent checks use `192.168.244.10:8090` directly (no proxy) and `C:\dev\openems\mini_ems_poc\runtime\health.json`; the owning process command line contains `mini_ems.py --config C:\dev\openems\mini_ems_poc\config.json --loop`.
