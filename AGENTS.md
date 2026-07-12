# Repository Guidelines

## Project Structure & Module Organization

OpenEMS is a multi-project repository. Java/OSGi bundles live in `io.openems.*` directories, grouped by domain such as `io.openems.edge.*`, `io.openems.backend.*`, and `io.openems.common.*`. The Angular/Ionic frontend is in `ui/`. Documentation sources are in `doc/`. The local Mini EMS prototype is in `mini_ems_poc/`, with runtime code under `mini_ems_poc/mini_ems_runtime/`, browser assets under `mini_ems_poc/dashboard/`, and Python tests under `mini_ems_poc/tests/`.

## Build, Test, and Development Commands

- `./gradlew buildEdge` builds the OpenEMS Edge fat jar into `build/openems-edge.jar`.
- `./gradlew buildBackend` builds the Backend fat jar into `build/openems-backend.jar`.
- `./gradlew testEdge` / `./gradlew testBackend` run Java tests for Edge or Backend bundles.
- `./gradlew checkstyleAll` runs Java Checkstyle with `cnf/checkstyle.xml`.
- `cd ui && npm test` runs Angular/Karma tests.
- `cd ui && npm run lint` runs Angular linting plus translation-key checks.
- `cd mini_ems_poc && python3.12 mini_ems.py --site-dir runtime/local/site --once` runs one safe simulated Mini EMS cycle.
- `python3.12 -m unittest discover -s mini_ems_poc/tests -v` runs Mini EMS Python tests.
- **Mini EMS requires Python >= 3.10** (PEP-604 syntax such as `X | None`). The default `python3` on this machine is 3.9 and fails deep inside the import with a `TypeError` instead of the intended check. Always use `python3.12` or the repo `.venv` (`/Users/gabriel/dev/openems/.venv/bin/python`) for `mini_ems_poc`. `mini_ems.py` itself now guards this at startup and exits with a clear German error message on Python < 3.10.

## Coding Style & Naming Conventions

Java code uses UTF-8, Gradle toolchains, and Checkstyle. Keep bundle naming aligned with existing `io.openems.<area>.<feature>` patterns. Angular code follows the local Angular/ESLint/Prettier setup; keep templates, translations, and component names consistent with existing UI conventions. For `mini_ems_poc`, prefer small Python modules, explicit configuration, and clear channel names such as `site.outdoor_temperature_c`.

## Testing Guidelines

Place Java tests in each bundle’s `test/` tree and use Gradle task groups for broader checks. UI specs should stay near the relevant Angular component. Mini EMS tests use `unittest`; name files `test_*.py` and isolate hardware/network behavior with fakes or simulation.

## Commit & Pull Request Guidelines

History uses concise imperative subjects, sometimes with prefixes such as `feat:` or scopes like `[Backend]`. Keep subjects specific: `feat: Implement price caching` or `[Backend] Docker: fix default ports`. PRs should describe behavior changes, list commands run, link issues, and include screenshots for UI changes.

## Security & Configuration Tips

Do not commit logs, runtime databases, secrets, or plant-specific credentials. The active IPC/UI configuration lives in the external site store `C:\ProgramData\MiniEMS\site.sqlite`; local work uses a separate `--site-dir runtime/local/site`. Legacy `config.json` is migration input only. Never add a local-development path that can send real BACnet writes.

For Mini EMS IPC restart and Secomea access, follow `mini_ems_poc/AGENTS.md` section "IPC Restart / Secomea Runbook". The supported production start path is the scheduled release task (`windows/install_task.ps1` + `run_mini_ems_release.cmd`), not the checkout launcher or legacy `MiniEmsPoC` Windows service.
