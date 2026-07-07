#!/usr/bin/env bash
# Build a Mini EMS release package on macOS/Linux (local verification of H2).
# Mirrors the Windows build_release.ps1 logic and uses the same PyInstaller spec.
#
# Output: packaging/dist/mini_ems/  (one-dir: executable + resources + VERSION +
# SHA256SUMS + RELEASE_HINWEISE.md). config.json / operational data are never
# part of the package.
#
# Prerequisites: a Python >= 3.10 interpreter with PyInstaller installed on PATH
# (or via the PYTHON env var). PyInstaller build/dist work dirs stay under
# packaging/ and are git-ignored.
set -euo pipefail

SEMVER="${MINI_EMS_VERSION:-2026.07.0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SPEC="${SCRIPT_DIR}/mini_ems.spec"
WORK_DIR="${SCRIPT_DIR}/build"
DIST_DIR="${SCRIPT_DIR}/dist"
RELEASE_DIR="${DIST_DIR}/mini_ems"

PYTHON="${PYTHON:-python3.12}"
if ! command -v "${PYTHON}" >/dev/null 2>&1; then
  PYTHON="python3"
fi

echo "[build] project : ${PROJECT_DIR}"
echo "[build] python  : $(command -v "${PYTHON}")"
echo "[build] version : ${SEMVER}"

# Fresh build, but only under packaging/ (never touch the repo build/ dir).
rm -rf "${WORK_DIR}" "${DIST_DIR}"

echo "[build] running PyInstaller ..."
"${PYTHON}" -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "${DIST_DIR}" \
  --workpath "${WORK_DIR}" \
  "${SPEC}"

if [ ! -d "${RELEASE_DIR}" ]; then
  echo "[build] ERROR: expected release dir not found: ${RELEASE_DIR}" >&2
  exit 1
fi

# --- VERSION file: semver + build date + git commit hash --------------------
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
GIT_COMMIT="$(cd "${PROJECT_DIR}" && git rev-parse --short=12 HEAD 2>/dev/null || echo unknown)"
GIT_DIRTY=""
if ! (cd "${PROJECT_DIR}" && git diff --quiet HEAD 2>/dev/null); then
  GIT_DIRTY="+dirty"
fi
{
  echo "version=${SEMVER}"
  echo "build_date=${BUILD_DATE}"
  echo "git_commit=${GIT_COMMIT}${GIT_DIRTY}"
  echo "platform=$(uname -s)-$(uname -m)"
} > "${RELEASE_DIR}/VERSION"
echo "[build] wrote VERSION (${SEMVER}, ${GIT_COMMIT}${GIT_DIRTY})"

# --- Release launcher + notes: package vs. site data ------------------------
cp "${PROJECT_DIR}/run_mini_ems_release.cmd" "${RELEASE_DIR}/run_mini_ems_release.cmd"
cp "${SCRIPT_DIR}/RELEASE_HINWEISE.md" "${RELEASE_DIR}/RELEASE_HINWEISE.md"

# --- SHA256SUMS over every release file (excluding the sums file itself) -----
(
  cd "${RELEASE_DIR}"
  if command -v sha256sum >/dev/null 2>&1; then
    find . -type f ! -name SHA256SUMS -print0 | sort -z \
      | xargs -0 sha256sum > SHA256SUMS
  else
    # macOS: emulate sha256sum output ("<hash>  <path>") using shasum -a 256.
    : > SHA256SUMS
    find . -type f ! -name SHA256SUMS -print0 | sort -z | while IFS= read -r -d '' f; do
      shasum -a 256 "$f" >> SHA256SUMS
    done
  fi
)
FILE_COUNT="$(wc -l < "${RELEASE_DIR}/SHA256SUMS" | tr -d ' ')"
echo "[build] wrote SHA256SUMS over ${FILE_COUNT} files"

echo "[build] done -> ${RELEASE_DIR}"
echo "[build] contents:"
ls -1 "${RELEASE_DIR}"
