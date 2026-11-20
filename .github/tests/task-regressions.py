#!/usr/bin/env python3
"""Offline task regressions. Requires Python 3 and uds; no CAT credentials."""

import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
UDS = shutil.which("uds")


def load_tasks(path):
    return json.loads(subprocess.check_output(
        [UDS, "zarf", "tools", "yq", "-o=json", ".", str(path)], text=True
    ))


STUB = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import sys

tool = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["TASK_CALLS"], "a") as out:
    out.write(json.dumps({"tool": tool, "args": args,
                         "cat": os.getenv("OLM_CAT_TOKEN", ""),
                         "identity": os.getenv("OLM_IDENTITY_TOKEN", "")}) + "\n")
if tool == "uds":
    if args[:3] == ["zarf", "package", "create"]:
        Path("zarf-package-example-amd64-1.0.0.tar.zst").touch()
    else:
        sys.exit(subprocess.call([os.environ["REAL_UDS"], *args]))
elif tool == "olm":
    if args == ["version"]:
        print("olm test fixture")
    elif os.getenv("OLM_FAIL"):
        print("CAT exchange rejected: fixture diagnostic", file=sys.stderr)
        sys.exit(42)
    elif args[:2] == ["tools", "generate-fulcio-token"]:
        print("fixture.fulcio.token")
elif tool == "witness":
    if os.getenv("WITNESS_FAIL"):
        print("failed to load signers: fixture Fulcio rejection", file=sys.stderr)
        sys.exit(23)
    command = args[args.index("--") + 1:]
    result = subprocess.call(command)
    if result:
        sys.exit(result)
    for arg in args:
        if arg.startswith("--outfile="):
            Path(arg.split("=", 1)[1]).write_text("{}")
elif tool in ("gitleaks", "opengrep"):
    flag = "--report-path" if tool == "gitleaks" else "--sarif-output"
    Path(args[args.index(flag) + 1]).write_text("{}")
'''


class TaskRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {"root": load_tasks(ROOT / "tasks.yaml")}
        for path in (ROOT / "tasks").glob("*.yaml"):
            cls.sources[path.stem] = load_tasks(path)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="udm-task-test-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.bin = self.work / "home/.local/bin"
        self.bin.mkdir(parents=True)
        self.calls_file = self.work / "calls.jsonl"
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("OLM_", "ACTIONS_", "WITNESS_"))}
        self.env.update(HOME=str(self.work / "home"),
                        TMPDIR=str(self.work),
                        PATH=f"{self.bin}:{os.environ['PATH']}",
                        TASK_CALLS=str(self.calls_file), REAL_UDS=UDS)
        for name in ("uds", "witness", "gitleaks", "opengrep"):
            path = self.bin / name
            path.write_text(STUB)
            path.chmod(0o755)
        (self.work / "olm").write_text(STUB)
        (self.work / "olm").chmod(0o755)
        for name, source in self.sources.items():
            data = json.loads(json.dumps(source))
            if name == "root":
                data["includes"] = [
                    {f"udm-{n}": f"./{n}.yaml"}
                    for n in self.sources if n != "root"
                ]
                # Consumer lint is independent of the library's lint tooling.
                next(t for t in data["tasks"] if t["name"] == "lint")["actions"] = [{"cmd": "true"}]
            if name == "setup":
                for task in data["tasks"]:
                    task["actions"] = [{"cmd": "true"}]
            if name == "olm":
                next(t for t in data["tasks"] if t["name"] == "setup")["actions"] = [{"cmd": "true"}]
            if name == "scan":
                for task in data["tasks"]:
                    if task["name"].startswith("install-"):
                        task["actions"] = [{"cmd": "true"}]
            path = self.work / ("tasks.yaml" if name == "root" else f"{name}.yaml")
            path.write_text(json.dumps(data))
        self.git("init", "-q")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.com",
                 "commit", "--allow-empty", "-qm", "fixture")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.work, env=self.env,
                       check=True, capture_output=True)

    def run_task(self, task, **inputs):
        args = [UDS, "run", task, "--no-progress"]
        for key, value in inputs.items():
            args.extend(["--with", f"{key}={value}"])
        return subprocess.run(args, cwd=self.work, env=self.env,
                              capture_output=True, text=True, timeout=30)

    def calls(self, tool):
        if not self.calls_file.exists():
            return []
        return [c for c in map(json.loads, self.calls_file.read_text().splitlines())
                if c["tool"] == tool]

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cat_token_reaches_fulcio_exchange(self):
        result = self.run_task("udm-olm:generate-fulcio-token", olm_cat="cat.example.com",
                               olm_org="example", olm_project="app", olm_cat_token="cat_fixture")
        self.assert_success(result)
        call = self.calls("olm")[-1]
        self.assertEqual(call["cat"], "cat_fixture")
        self.assertEqual(call["identity"], "")
        self.assertEqual((self.work / ".fulcio-token").read_text().strip(), "fixture.fulcio.token")
        self.assertEqual((self.work / ".fulcio-token").stat().st_mode & 0o777, 0o600)
        self.assertNotIn("cat_fixture", result.stdout + result.stderr)

    def test_exchange_failure_is_visible_and_discards_stale_token(self):
        (self.work / ".fulcio-token").write_text("stale-token")
        self.env["OLM_FAIL"] = "1"
        result = self.run_task("udm-olm:generate-fulcio-token", olm_cat="cat.example.com", olm_org="example")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CAT exchange rejected: fixture diagnostic", result.stdout + result.stderr)
        self.assertIn("exit 42", result.stdout + result.stderr)
        self.assertFalse((self.work / ".fulcio-token").exists())

    def test_conflicting_credentials_fail_before_olm(self):
        self.env["OLM_IDENTITY_TOKEN"] = "identity_fixture"
        result = self.run_task("udm-olm:generate-fulcio-token", olm_cat="cat.example.com",
                               olm_org="example", olm_cat_token="cat_fixture")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("mutually exclusive", result.stdout + result.stderr)
        self.assertEqual(self.calls("olm"), [])

    def test_cat_token_reaches_vouch(self):
        (self.work / "package.tar.zst").touch()
        result = self.run_task("udm-vouch:package", zarf_package="package.tar.zst",
                               olm_cat="cat.example.com", olm_org="example", olm_project="app",
                               olm_cat_token="cat_fixture")
        self.assert_success(result)
        call = self.calls("olm")[-1]
        self.assertEqual(call["cat"], "cat_fixture")
        self.assertEqual(call["args"][call["args"].index("--project") + 1], "app")

    def test_environment_cat_token_overrides_ambient_github_oidc(self):
        self.env.update(OLM_CAT_TOKEN="cat_fixture", ACTIONS_ID_TOKEN_REQUEST_TOKEN="github_fixture",
                        ACTIONS_ID_TOKEN_REQUEST_URL="https://unused.example.com")
        result = self.run_task("scan-and-vouch", olm_cat="cat.example.com", olm_org="example",
                               run_opengrep="false")
        self.assert_success(result)
        for call in self.calls("olm"):
            self.assertEqual(call["cat"], "cat_fixture")
            self.assertEqual(call["identity"], "")

    def test_orchestrators_preserve_cat_and_oidc_auth(self):
        for task in ("scan-and-vouch", "pipeline"):
            for mode in ("cat", "identity"):
                with self.subTest(task=task, mode=mode):
                    self.calls_file.unlink(missing_ok=True)
                    inputs = {f"olm_{mode}_token": f"{mode}_fixture"}
                    result = self.run_task(task, olm_cat="cat.example.com", olm_org="example",
                                           olm_project="app", run_opengrep="false", **inputs)
                    self.assert_success(result)
                    auth_calls = [c for c in self.calls("olm") if c["args"] != ["version"]]
                    self.assertGreaterEqual(len(auth_calls), 2)
                    for call in auth_calls:
                        self.assertEqual(call[mode], f"{mode}_fixture")
                        self.assertEqual(call["identity" if mode == "cat" else "cat"], "")
                        self.assertEqual(call["args"][call["args"].index("--project") + 1], "app")
                    for call in self.calls("witness"):
                        self.assertIn("--signer-fulcio-token", call["args"])
                        self.assertNotIn("--signer-file-key-path", call["args"])

    def test_witness_failure_has_step_and_exit_code(self):
        self.env["WITNESS_FAIL"] = "1"
        (self.work / ".fulcio-token").write_text("fixture.fulcio.token")
        for task in ("udm-attest:lint", "udm-scan:gitleaks", "udm-scan:opengrep", "udm-build:zarf-package"):
            with self.subTest(task=task):
                result = self.run_task(task)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("fixture Fulcio rejection", result.stdout + result.stderr)
                self.assertIn("exit 23", result.stdout + result.stderr)
                self.assertIn(task, result.stdout + result.stderr)

    def test_local_key_and_unsigned_scans_remain_available(self):
        (self.work / "key.pem").touch()
        result = self.run_task("udm-scan:security", witness_key_path="key.pem")
        self.assert_success(result)
        for call in self.calls("witness"):
            self.assertIn("--signer-file-key-path", call["args"])
            self.assertNotIn("--signer-fulcio-token", call["args"])
        self.calls_file.unlink()
        result = self.run_task("udm-scan:security", enable_sigstore="false")
        self.assert_success(result)
        self.assertEqual(self.calls("witness"), [])
        self.assertEqual(len(self.calls("gitleaks")), 1)
        self.assertEqual(len(self.calls("opengrep")), 1)

    def test_vouch_failure_preserves_diagnostic_and_exit_code(self):
        (self.work / "package.tar.zst").touch()
        self.env["OLM_FAIL"] = "1"
        result = self.run_task("udm-vouch:package", zarf_package="package.tar.zst",
                               olm_cat="cat.example.com", olm_org="example")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CAT exchange rejected: fixture diagnostic", result.stdout + result.stderr)
        self.assertIn("udm-vouch:package failed (exit 42", result.stdout + result.stderr)

    def test_installers_stop_after_download_failure(self):
        # Real installer actions, isolated PATH; never download or touch user tools.
        for name in ("setup", "scan"):
            (self.work / f"{name}.yaml").write_text(json.dumps(self.sources[name]))
        (self.bin / "uds").unlink()
        self.env["PATH"] = str(self.bin)
        for name in ("bash", "uname", "awk", "tr", "mkdir", "mktemp", "rm", "tar", "gzip", "grep"):
            (self.bin / name).symlink_to(shutil.which(name))
        (self.bin / "python3").symlink_to(sys.executable)
        curl = self.bin / "curl"
        curl.write_text('#!/bin/bash\necho "fixture download failed" >&2\nexit 22\n')
        curl.chmod(0o755)
        for task in ("udm-scan:install-gitleaks", "udm-scan:install-opengrep",
                     "udm-setup:uds-cli", "udm-setup:cosign", "udm-setup:witness"):
            with self.subTest(task=task):
                result = self.run_task(task)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("fixture download failed", result.stdout + result.stderr)
                self.assertIn(f"ERROR: {task} failed (exit ", result.stdout + result.stderr)
                self.assertNotIn("installed to", result.stdout + result.stderr)
                self.assertNotIn("Sigstore verification passed", result.stdout + result.stderr)

    def test_witness_install_stops_after_signature_rejection(self):
        (self.work / "setup.yaml").write_text(json.dumps(self.sources["setup"]))
        archive = self.work / "fixture.tar.gz"
        with tarfile.open(archive, "w:gz") as out:
            content = b"#!/bin/sh\nexit 0\n"
            member = tarfile.TarInfo("witness")
            member.size = len(content)
            member.mode = 0o755
            out.addfile(member, io.BytesIO(content))
        # curl returns local fixtures; the real task must honor cosign's failure.
        curl = self.bin / "curl"
        curl.write_text('#!/bin/bash\ncp "$FIXTURE_ARCHIVE" "${@: -1}"\n')
        curl.chmod(0o755)
        cosign = self.bin / "cosign"
        cosign.write_text('#!/bin/bash\necho "fixture signature rejected" >&2\nexit 25\n')
        cosign.chmod(0o755)
        self.env["FIXTURE_ARCHIVE"] = str(archive)
        (self.bin / "witness").unlink()
        result = self.run_task("udm-setup:witness")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fixture signature rejected", result.stdout + result.stderr)
        self.assertIn("udm-setup:witness failed (exit 25", result.stdout + result.stderr)
        self.assertNotIn("Sigstore verification passed", result.stdout + result.stderr)
        self.assertFalse((self.bin / "witness").exists())
        self.assertEqual(list((self.work / "home/.cache").glob("**/witness.sha256")), [])


if __name__ == "__main__":
    unittest.main()
