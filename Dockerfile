FROM ghcr.io/astral-sh/uv:0.10.10 AS uv

FROM python:3.12-slim AS builder
COPY --from=uv /uv /uvx /bin/
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock readme.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ ./src/
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/scraper
RUN groupadd --gid 10001 scraper \
    && useradd --uid 10001 --gid scraper --create-home scraper
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
USER scraper
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/health', timeout=3)"
CMD ["python", "-m", "roster_scraper.cloud_server"]
