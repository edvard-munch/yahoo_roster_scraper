import ast
import os
from pathlib import Path
import re
import subprocess
import sys

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "scrape-google-sheet.yml"


def load_workflow():
    # BaseLoader keeps YAML's `on` key and boolean-looking values as strings.
    return yaml.load(WORKFLOW_PATH.read_text(), Loader=yaml.BaseLoader)


def test_workflow_is_manual_only_and_uses_standard_runner():
    workflow = load_workflow()

    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["on"]["workflow_dispatch"]["inputs"] == {
        "spreadsheet_id": {
            "description": "Google spreadsheet ID (not its URL)",
            "required": "true",
            "type": "string",
        }
    }
    job = workflow["jobs"]["scrape"]
    assert job["runs-on"] == "ubuntu-latest"
    assert job["if"] == "github.ref == 'refs/heads/master'"
    assert job["environment"] == "google-sheets"
    assert job["timeout-minutes"] == "15"


def test_workflow_serializes_each_sheet_without_cancelling_active_runs():
    assert load_workflow()["concurrency"] == {
        "group": "sheet-scrape-${{ inputs.spreadsheet_id }}",
        "cancel-in-progress": "false",
    }


def test_workflow_uses_minimal_permissions_and_pinned_actions():
    workflow = load_workflow()
    job = workflow["jobs"]["scrape"]

    assert workflow["permissions"] == {"contents": "read"}
    assert job["permissions"] == {"contents": "read", "id-token": "write"}
    for step in job["steps"]:
        if "uses" in step:
            assert re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+@[0-9a-f]{40}", step["uses"])
            assert "upload-artifact" not in step["uses"]
    checkout = next(
        step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@")
    )
    assert checkout["with"]["persist-credentials"] == "false"


def test_workflow_validates_before_auth_and_uses_wif_not_json_keys():
    steps = load_workflow()["jobs"]["scrape"]["steps"]
    validate_index = next(i for i, step in enumerate(steps) if step["name"].startswith("Validate"))
    auth_index = next(
        i
        for i, step in enumerate(steps)
        if step.get("uses", "").startswith("google-github-actions/auth@")
    )
    auth = steps[auth_index]["with"]

    assert validate_index < auth_index
    assert auth == {
        "workload_identity_provider": "${{ vars.GCP_WORKLOAD_IDENTITY_PROVIDER }}",
        "service_account": "${{ vars.GCP_SERVICE_ACCOUNT }}",
        "create_credentials_file": "true",
        "export_environment_variables": "true",
    }
    assert "credentials_json" not in WORKFLOW_PATH.read_text()


def test_workflow_passes_spreadsheet_id_as_quoted_env_argument():
    job = load_workflow()["jobs"]["scrape"]

    assert job["env"]["SPREADSHEET_ID"] == "${{ inputs.spreadsheet_id }}"
    for step in job["steps"]:
        assert "${{ inputs." not in step.get("run", "")
    assert job["steps"][-1]["run"] == (
        'uv run --no-sync yahoo-roster-scraper-actions --spreadsheet-id "$SPREADSHEET_ID"'
    )
    assert any(step.get("run") == "uv sync --frozen --no-dev" for step in job["steps"])


def validation_source():
    step = next(
        step
        for step in load_workflow()["jobs"]["scrape"]["steps"]
        if step["name"].startswith("Validate")
    )
    source = step["run"].split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    ast.parse(source)
    return source


def run_validation(
    spreadsheet_id,
    provider="projects/123/locations/global/workloadIdentityPools/pool/providers/github",
):
    return subprocess.run(
        [sys.executable, "-c", validation_source()],
        cwd=PROJECT_ROOT,
        env={
            **os.environ,
            "SPREADSHEET_ID": spreadsheet_id,
            "GCP_WORKLOAD_IDENTITY_PROVIDER": provider,
            "GCP_SERVICE_ACCOUNT": "scraper@project.iam.gserviceaccount.com",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_inline_validation_accepts_id_without_network_calls():
    result = run_validation("sheet-123_A")

    assert result.returncode == 0, result.stderr


def test_inline_validation_rejects_shell_input_as_data():
    result = run_validation("$(echo must-not-be-executed)")

    assert result.returncode != 0
    assert "Supply a spreadsheet ID" in result.stderr
    assert result.stdout == ""


def test_inline_validation_rejects_missing_federation_settings():
    result = run_validation("sheet-123", provider="")

    assert result.returncode != 0
    assert "Missing GitHub environment variable: GCP_WORKLOAD_IDENTITY_PROVIDER" in result.stderr


def test_ephemeral_google_credentials_are_gitignored():
    assert "/gha-creds-*.json" in (PROJECT_ROOT / ".gitignore").read_text()
