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

Run scraper:

```bash
uv run yahoo-roster-scraper
```
