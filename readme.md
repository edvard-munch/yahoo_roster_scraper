League has to be publicly viewable to scrape data.

## UV workflow

Install dependencies from lockfile:

```bash
uv sync
```

Run tests:

```bash
uv run --group dev pytest
```

Run lint checks:

```bash
make lint
```

Format code:

```bash
make fmt
```

Install pre-commit hooks (runs format, lint, and tests before each commit):

```bash
uv run --group dev pre-commit install
```

Run scraper:

```bash
uv run yahoo-roster-scraper
```
