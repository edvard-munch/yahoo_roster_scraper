"""Container launcher; validates settings before replacing itself with Uvicorn."""

import os
import sys


SECRET_ENV = "SCRAPER_API_SECRET"
PORT_ENV = "PORT"
DEFAULT_PORT = 8080
MIN_PORT = 1
MAX_PORT = 65535
BIND_HOST = "0.0.0.0"
APPLICATION_IMPORT = "roster_scraper.web:app"
WORKER_COUNT = 1


def build_server_command(environ):
    secret = environ.get(SECRET_ENV)
    if not secret or not secret.strip():
        raise ValueError(f"{SECRET_ENV} must be configured before starting the service")

    raw_port = environ.get(PORT_ENV, str(DEFAULT_PORT))
    try:
        port = int(raw_port)
    except (TypeError, ValueError) as error:
        raise ValueError("PORT must be an integer between 1 and 65535") from error
    if not MIN_PORT <= port <= MAX_PORT:
        raise ValueError("PORT must be an integer between 1 and 65535")

    return [
        sys.executable,
        "-m",
        "uvicorn",
        APPLICATION_IMPORT,
        "--host",
        BIND_HOST,
        "--port",
        str(port),
        "--workers",
        str(WORKER_COUNT),
    ]


def main():
    try:
        command = build_server_command(os.environ)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    os.execv(sys.executable, command)


if __name__ == "__main__":
    main()
