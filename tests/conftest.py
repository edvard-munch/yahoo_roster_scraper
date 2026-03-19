from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
FIXTURES_PATH = Path(__file__).resolve().parent / "fixtures"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


@pytest.fixture
def fixtures_path() -> Path:
    return FIXTURES_PATH


@pytest.fixture
def frozenpool_schedule_html(fixtures_path: Path) -> str:
    return (fixtures_path / "frozenpool_schedule.html").read_text()


@pytest.fixture
def yahoo_team_page_html(fixtures_path: Path) -> str:
    return (fixtures_path / "yahoo_team_page.html").read_text()
