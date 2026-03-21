import bs4
import pytest

from roster_scraper import cli


def test_get_headers_uses_action_fallback_row():
    html = """
    <html>
      <body>
        <table>
          <tr><th>Ignore</th></tr>
          <tr>
            <th>Action</th>
            <th>Forwards/Defensemen</th>
            <th>Team</th>
            <th>Pos</th>
            <th>G</th>
          </tr>
        </table>
      </body>
    </html>
    """
    soup = bs4.BeautifulSoup(html, "lxml")

    headers = cli.get_headers(soup)

    assert "Action" in headers
    assert "G" in headers
    assert cli.schedule_scraper.GAMES_LEFT_THIS_WEEK_COLUMN in headers


def test_get_headers_raises_when_no_header_row_found():
    html = """
    <html>
      <body>
        <table>
          <tr><th>Team</th><th>GP</th></tr>
          <tr><td>BOS</td><td>3</td></tr>
        </table>
      </body>
    </html>
    """
    soup = bs4.BeautifulSoup(html, "lxml")

    with pytest.raises(RuntimeError, match="Roster header row not found"):
        cli.get_headers(soup)
