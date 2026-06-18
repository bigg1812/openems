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

## 5. German UI Language

**Use real German umlauts in user-facing German text.**

- Write `ä`, `ö`, `ü`, `Ä`, `Ö`, `Ü` and `ß` directly.
- Do not write `ae`, `oe`, `ue` or `ss` as replacements in German UI copy, documentation, or messages unless the target system technically requires ASCII.
- Customer-facing UI must use plain business language. Do not show internal IDs such as `ems.lockout_spotmarket`, BACnet object names, or protocol terms unless the screen is explicitly technical diagnostics.

## 6. Local vs IPC Safety

**The laptop is for simulation. The IPC is for real plant operation.**

- Keep `config.json` as the real IPC configuration unless the user explicitly asks to change plant operation.
- Use `config.local.json` for laptop work.
- Local development must use `runtime.bacnet_mode=simulated` and `runtime.real_writes_enabled=false`.
- Do not add a code path that sends real BACnet writes from `environment=local`.
- If you need test values, edit `sim/sample_values.json` or `sim/sample_prices.json` instead of changing real BACnet points.

## 7. IPC Restart / Secomea Runbook

**Use the scheduled task, not the legacy Windows service.**

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
  -PythonPath C:\Users\ENGIE_NL_STUTTGART\AppData\Local\Programs\Python\Python312\python.exe `
  -StartNow:$false
```

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
