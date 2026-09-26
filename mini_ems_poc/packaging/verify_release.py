"""Exercise the built binary on a disposable, simulated site. No plant access.

Run with Python 3.12: packaging/verify_release.py --package packaging/dist/mini_ems
"""
import argparse
import base64
import hashlib
import http.cookiejar
import json
import os
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mini_ems_poc.mini_ems_runtime.config import validate_raw_config
from mini_ems_poc.mini_ems_runtime.site_store import SiteConfigStore
from mini_ems_poc.mini_ems_runtime.supervisor import stop_child


def wait_for(check, *, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for packaged runtime")


def verify_checksums(package):
    covered = set()
    for line in (package / "SHA256SUMS").read_text(encoding="utf-8-sig").splitlines():
        digest, relative = line.split(None, 1)
        target = package / relative.strip()
        if not target.resolve().is_relative_to(package.resolve()):
            raise AssertionError("Manifest path leaves package")
        assert hashlib.sha256(target.read_bytes()).hexdigest() == digest, relative
        covered.add(target.relative_to(package).as_posix())
    actual = {path.relative_to(package).as_posix() for path in package.rglob("*")
              if path.is_file() and not path.is_symlink() and path.name != "SHA256SUMS"}
    assert covered == actual, (covered ^ actual)
    assert not list(package.rglob("*.sqlite")), "Operational database in package"
    assert not (package / "windows/install_service.ps1").exists(), "Legacy service installer in package"
    return len(covered)


def verify(package, directory):
    files = verify_checksums(package)
    binary = package / ("mini_ems.exe" if os.name == "nt" else "mini_ems")
    version = dict(line.split("=", 1) for line in (package / "VERSION").read_text().splitlines() if "=" in line)
    site = directory / "site"
    output = (directory / "process.log").open("w")
    with output:
        subprocess.run([str(binary), "--site-dir", str(site), "--once"], check=True,
                       stdout=output, stderr=output, timeout=30)
        store = SiteConfigStore(site)
        raw = store.active_config()
        assert raw["runtime"]["environment"] == "local"
        assert raw["runtime"]["bacnet_mode"] == "simulated"
        assert raw["runtime"]["real_writes_enabled"] is False
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        raw["runtime"]["operation_mode"] = "monitoring"
        raw["api"].update(host="127.0.0.1", port=port, read_only=False)
        raw["timing"]["cycle_seconds"] = 1
        raw["watchdog"]["max_cycle_age_seconds"] = 5
        config = validate_raw_config(raw, base_dir=site)
        revision = store.save_revision(raw, action="release.simulation", actor="local_verification")
        base = "http://127.0.0.1:{0}".format(port)
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

        def request(path, body=None, *, expected=200):
            data = json.dumps(body).encode() if body is not None else None
            req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json", "Origin": base})
            try:
                response = client.open(req, timeout=3)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                content = response.read().decode()
                assert response.status == expected, (path, response.status, content)
                if path == "/api/report/html":
                    styles = re.findall(r"<style>(.*?)</style>", content, re.DOTALL)
                    assert styles, "Report stylesheet missing"
                    for css in styles:
                        digest = base64.b64encode(hashlib.sha256(css.encode("utf-8")).digest()).decode("ascii")
                        assert "'sha256-{0}'".format(digest) in response.headers["Content-Security-Policy"]
                return json.loads(content) if "application/json" in response.headers.get("Content-Type", "") else content

        def launch(current_site):
            options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
            return subprocess.Popen([str(binary), "--site-dir", str(current_site), "--supervise"],
                                    stdout=output, stderr=output, **options)

        def running(current_site):
            path = current_site / "runtime/supervisor.json"
            status = json.loads(path.read_text())
            return status if status["status"] == "running" else None

        parent = launch(site)
        try:
            first = wait_for(lambda: running(site))
            public = request("/api/health")
            assert public["app_version"]["version"] == version["version"]
            assert public["status"] == "healthy"
            assert "Strompreise und Planung" in request("/dashboard")
            request("/api/status", expected=401)
            password = "Local-package-test-" + os.urandom(12).hex()
            request("/api/auth/bootstrap", {"bootstrap_code": raw["api"]["config_admin_token"],
                                          "username": "testadmin", "password": password})
            request("/api/auth/users/create", {"username": "testviewer", "display_name": "Test Viewer",
                                             "role": "viewer", "password": password})
            request("/api/auth/logout", {})
            request("/api/auth/login", {"username": "testviewer", "password": password})
            assert request("/api/status")["health"]["operation_mode"] == "monitoring"
            assert "Tagesbericht" in request("/api/report/html")
            request("/api/config/save", {}, expected=403)
            # Kill only the child PID returned by our own disposable supervisor.
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(first["process_id"]), "/F"], check=True, stdout=output, stderr=output)
            else:
                os.kill(first["process_id"], signal.SIGKILL)
            def recovered():
                status = running(site)
                return status if status and status["run_id"] != first["run_id"] else None
            second = wait_for(recovered)
            assert len(second["start_timestamps"]) == 2
            assert request("/api/status")["health"]["storage_status"] == "ok"
        finally:
            stop_child(parent, grace_seconds=15)
        assert parent.returncode == 0, parent.returncode
        with closing(sqlite3.connect(config.database_path)) as db:
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            before = db.execute("SELECT COUNT(*) FROM cycle_runs").fetchone()[0]
            assert before >= 3
        # A stopped, complete site copy includes identity, revisions, history and recovery evidence.
        restored = directory / "restored"
        shutil.copytree(site, restored)
        restored_store = SiteConfigStore(restored)
        assert restored_store.active_revision() == revision
        raw["api"]["read_only"] = True
        restored_store.save_revision(raw, action="release.read_only", actor="local_verification")
        parent = launch(restored)
        try:
            wait_for(lambda: running(restored))
            assert request("/api/health")["api_read_only"] is True
            request("/api/auth/login", {"username": "testadmin", "password": password})
            request("/api/config/save", {}, expected=403)
            status = request("/api/status")
            assert status["health"]["status"] == "healthy"
            assert status["health"]["pending_release_count"] == 0
        finally:
            stop_child(parent, grace_seconds=15)
        restored_config = validate_raw_config(raw, base_dir=restored)
        with closing(sqlite3.connect(restored_config.database_path)) as db:
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            after = db.execute("SELECT COUNT(*) FROM cycle_runs").fetchone()[0]
            assert after > before
        assert verify_checksums(package) == files, "Runtime modified release files"
        return {"result": "passed", "version": version, "manifest_files": files,
                "cycles_before_restore": before, "cycles_after_restore": after,
                "checks": ["manifest", "safe_bootstrap", "login", "viewer_permissions", "read_only", "report_html_csp",
                           "supervised_crash_recovery", "site_restore", "database_integrity", "immutable_package"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="mini-ems-release-") as temporary:
        try:
            result = verify(args.package.resolve(), Path(temporary))
        except Exception:
            log = Path(temporary) / "process.log"
            if log.exists():
                print(log.read_text()[-6000:], file=sys.stderr)
            raise
        print(json.dumps(result, indent=2))
