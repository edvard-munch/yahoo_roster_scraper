import sys

import pytest

from roster_scraper import cloud_server


def test_launcher_binds_cloud_run_port_with_one_worker():
    command = cloud_server.build_server_command(
        {"SCRAPER_API_SECRET": "test-secret", "PORT": "9090"}
    )

    assert command == [
        sys.executable,
        "-m",
        "uvicorn",
        "roster_scraper.web:app",
        "--host",
        "0.0.0.0",
        "--port",
        "9090",
        "--workers",
        "1",
    ]
    assert "test-secret" not in command


def test_launcher_defaults_to_port_8080():
    command = cloud_server.build_server_command({"SCRAPER_API_SECRET": "test-secret"})

    assert command[command.index("--port") + 1] == "8080"


@pytest.mark.parametrize("secret", [None, "", "   "])
def test_launcher_rejects_missing_secret_without_exposing_it(secret):
    with pytest.raises(ValueError, match="SCRAPER_API_SECRET must be configured"):
        cloud_server.build_server_command({"SCRAPER_API_SECRET": secret})


@pytest.mark.parametrize("port", ["", "invalid", "0", "65536", "-1"])
def test_launcher_rejects_invalid_port(port):
    with pytest.raises(ValueError, match="PORT must be an integer"):
        cloud_server.build_server_command({"SCRAPER_API_SECRET": "test-secret", "PORT": port})


def test_main_replaces_process_with_uvicorn(monkeypatch):
    calls = []
    monkeypatch.setenv("SCRAPER_API_SECRET", "test-secret")
    monkeypatch.setenv("PORT", "9090")
    monkeypatch.setattr(
        cloud_server.os, "execv", lambda executable, args: calls.append((executable, args))
    )

    cloud_server.main()

    assert calls == [(sys.executable, cloud_server.build_server_command(cloud_server.os.environ))]


def test_main_fails_before_starting_server_without_secret(monkeypatch):
    monkeypatch.delenv("SCRAPER_API_SECRET", raising=False)
    monkeypatch.setattr(
        cloud_server.os,
        "execv",
        lambda *args: (_ for _ in ()).throw(AssertionError("Server must not start")),
    )

    with pytest.raises(SystemExit, match="SCRAPER_API_SECRET must be configured"):
        cloud_server.main()
