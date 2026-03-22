.PHONY: fmt lint test

fmt:
	uv run --group dev ruff format src tests

lint:
	uv run --group dev ruff check src tests
	uv run --group dev pytest

test:
	uv run --group dev pytest
