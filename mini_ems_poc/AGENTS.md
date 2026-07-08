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

**Use the scheduled task, not the legacy Windows service.**

> **Stand 2026-07-07 – Produktionspfad ist jetzt das Release-Paket (H2).** Die Pilot-IPC
> läuft `C:\Program Files\MiniEMS\mini_ems.exe --config C:\ProgramData\MiniEMS\config.json --loop`
> über den geplanten Task **`MiniEmsPoCRelease`** (SYSTEM, Boot-Trigger), nicht mehr über den
> Git-Checkout und `mini_ems.py`. Die konkurrierenden Alt-Autostarts sind entschärft: der alte
> Dev-Task `MiniEmsPoC` ist **deaktiviert**, der Legacy-Dienst `MiniEmsPoC` steht auf **Manual**,
> der Task `MiniEmsDashboardProxy` ist **deaktiviert**. Der Ablauf unten (mit `install_task.ps1`,
> `run_mini_ems.cmd`, `mini_ems.py`) beschreibt den älteren Checkout-Betrieb und bleibt als
> Referenz/Fallback stehen; die Release-Betriebsschritte stehen in `RELEASE_WORKFLOW.md` und
> `UPDATE_WARTUNG.md`.

- Do not use `sc.exe start MiniEmsPoC` as the normal runtime path. The `MiniEmsPoC` Windows service entry is legacy and can fail with `StartService FEHLER 1053` because `mini_ems.py` is a console process, not a native Windows service.
- The supported IPC production start path is `windows/install_task.ps1` plus `run_mini_ems.cmd`.
- The production runtime must use `config.json`, which binds the dashboard/API to `192.168.244.10:8090` and performs real BACnet writes.
- The local simulation uses `config.local.json`, binds to `127.0.0.1:8090`, and is not reachable through Secomea.

Install or repair the scheduled task from an elevated PowerShell:

```powershell
cd C:\dev\openems\mini_ems_poc
.\windows\install_task.ps1 `
  -TaskName MiniEmsPoC `
  -ProjectDir C:\dev\openems\mini_ems_poc `
  -PythonPath python `
  -StartNow:$false
```

`-PythonPath` accepts a bare command (resolved via `Get-Command`) or an absolute path;
`python` is the default, so the flag can usually be omitted. For the packaged release path
(H2) use `-Mode release`, which launches `mini_ems.exe` from `C:\Program Files\MiniEMS` with
`--config C:\ProgramData\MiniEMS\config.json` instead of the checkout. Do **not** use
`windows/install_service.ps1` — it is a deprecated legacy helper (see the banner in that file).

Start the IPC runtime:

```powershell
Start-ScheduledTask -TaskName MiniEmsPoC
```

Verify that Secomea can reach the dashboard:

```powershell
Get-NetTCPConnection -LocalPort 8090
Invoke-WebRequest -UseBasicParsing http://192.168.244.10:8090/dashboard
Get-Content C:\dev\openems\mini_ems_poc\runtime\health.json
```

Expected state:

- Exactly one listener on `192.168.244.10:8090`.
- The owning process command line contains `mini_ems.py --config C:\dev\openems\mini_ems_poc\config.json --loop`.
- `runtime/health.json` is current and reports `status: healthy`.
- The dashboard request returns HTTP `200`.

If the task view shows `Ready` but the dashboard works, trust the process and health checks first. The wrapper may leave the actual Python process running through `run_mini_ems.cmd`; verify by checking port `8090`, process command line, and `runtime/health.json`.

Stop the runtime only when needed:

```powershell
Get-NetTCPConnection -LocalPort 8090
taskkill /PID <OwningProcess> /T /F
```
