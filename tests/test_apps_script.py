import json
from pathlib import Path
import shutil
import subprocess

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = PROJECT_ROOT / "google_apps_script"


def test_apps_script_manifest_has_bound_sheet_and_http_scopes():
    manifest = json.loads((SCRIPT_DIR / "appsscript.json").read_text())

    assert manifest["runtimeVersion"] == "V8"
    assert set(manifest["oauthScopes"]) == {
        "https://www.googleapis.com/auth/spreadsheets.currentonly",
        "https://www.googleapis.com/auth/script.container.ui",
        "https://www.googleapis.com/auth/script.external_request",
    }
    assert "webapp" not in manifest


def test_apps_script_logic_with_fake_google_services():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js 18+ is required to run the Apps Script mock tests")

    result = subprocess.run(
        [node, "--test", str(PROJECT_ROOT / "tests" / "apps_script.test.cjs")],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
