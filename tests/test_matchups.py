from types import SimpleNamespace

import bs4

from roster_scraper.services import matchups


class WorksheetSpy:
    def __init__(self):
        self.columns = []
        self.rows = []

    def set_column(self, *args):
        self.columns.append(args)

    def write_row(self, index, col, row):
        self.rows.append((index, col, list(row)))


def _build_soup(value_g="1", value_a="2"):
    html = f"""
    <html>
      <body>
        <table class="Table-plain Table Table-px-sm Table-mid Datatable Ta-center Tz-xxs Bdr">
          <thead>
            <tr><th>Team</th><th>G</th><th>A</th></tr>
          </thead>
          <tbody>
            <tr>
              <td><span class="Grid-u Nowrap">Team A</span></td>
              <td>{value_g}</td>
              <td>{value_a}</td>
            </tr>
          </tbody>
        </table>
      </body>
    </html>
    """
    return bs4.BeautifulSoup(html, "lxml")


def _build_context(parse_full_page):
    return matchups.MatchupsContext(
        columns={"first": (0, 0), "second": (1, 1)},
        wide_column_width=20,
        number_of_matchups_processed_message="{}/{} matchups ready",
        matchup_totals_parameter="?stat1=ML",
        matchup_result_classes="Table-plain Table Table-px-sm Table-mid Datatable Ta-center Tz-xxs Bdr",
        team_name_matchup_result_classes="Grid-u Nowrap",
        proxies_scraper=SimpleNamespace(get_proxy=lambda proxies: proxies[0] if proxies else None),
        parse_full_page=parse_full_page,
        scrape_from_page=lambda soup, *args: soup.find_all("table"),
    )


def test_process_matchups_writes_headers_once_and_aggregates_totals():
    worksheet = WorksheetSpy()
    soups = [_build_soup("1", "2"), _build_soup("2", "3")]

    def parse_full_page(*args, **kwargs):
        return soups.pop(0), None

    context = _build_context(parse_full_page)

    matchups.process_matchups(
        context,
        matchup_links=["https://example.com/m1", "https://example.com/m2"],
        team_totals_dict={"Team A": {"G": 10.0, "A": 20.0}},
        proxies=[],
        worksheet=worksheet,
    )

    assert worksheet.columns == [(1, 1, 20), (0, 0, 20)]

    header_rows = [row for _, _, row in worksheet.rows if row[:3] == ["Team", "G", "A"]]
    assert len(header_rows) == 1

    data_rows = [row for _, _, row in worksheet.rows if row and row[0] == "Team A"]
    assert data_rows[0][:3] == ["Team A", 11.0, 22.0]
    assert data_rows[1][:3] == ["Team A", 12.0, 23.0]


def test_process_matchups_treats_non_numeric_values_as_zero_before_prognosis():
    worksheet = WorksheetSpy()

    context = _build_context(lambda *args, **kwargs: (_build_soup("N/A", "-"), None))

    matchups.process_matchups(
        context,
        matchup_links=["https://example.com/m1"],
        team_totals_dict={"Team A": {"G": 5.0, "A": 7.0}},
        proxies=[],
        worksheet=worksheet,
    )

    data_rows = [row for _, _, row in worksheet.rows if row and row[0] == "Team A"]
    assert data_rows[0][:3] == ["Team A", 5.0, 7.0]


def test_process_matchups_uses_initial_proxy_when_proxies_enabled():
    worksheet = WorksheetSpy()
    proxy_calls = []
    parse_calls = []

    def parse_full_page(link, proxies, proxy):
        parse_calls.append({"link": link, "proxies": proxies, "proxy": proxy})
        return _build_soup("1", "2"), proxy

    context = matchups.MatchupsContext(
        columns={"first": (0, 0), "second": (1, 1)},
        wide_column_width=20,
        number_of_matchups_processed_message="{}/{} matchups ready",
        matchup_totals_parameter="?stat1=ML",
        matchup_result_classes="Table-plain Table Table-px-sm Table-mid Datatable Ta-center Tz-xxs Bdr",
        team_name_matchup_result_classes="Grid-u Nowrap",
        proxies_scraper=SimpleNamespace(
            get_proxy=lambda proxies: (
                proxy_calls.append(list(proxies)) or {"http": "4.4.4.4:80", "https": "4.4.4.4:80"}
            )
        ),
        parse_full_page=parse_full_page,
        scrape_from_page=lambda soup, *args: soup.find_all("table"),
    )

    proxies_list = [{"http": "4.4.4.4:80", "https": "4.4.4.4:80"}]
    matchups.process_matchups(
        context,
        matchup_links=["https://example.com/m1"],
        team_totals_dict={"Team A": {"G": 1.0, "A": 1.0}},
        proxies=proxies_list,
        worksheet=worksheet,
    )

    assert len(proxy_calls) == 1
    assert parse_calls[0]["proxy"] == {"http": "4.4.4.4:80", "https": "4.4.4.4:80"}


def test_process_matchups_handles_missing_team_span_and_writes_spacer_rows():
    worksheet = WorksheetSpy()
    html = """
    <html>
      <body>
        <table class="Table-plain Table Table-px-sm Table-mid Datatable Ta-center Tz-xxs Bdr">
          <thead>
            <tr><th>Team</th><th>G</th><th>A</th></tr>
          </thead>
          <tbody>
            <tr><td>Fallback Team</td><td>1</td><td>2</td></tr>
            <tr><td><span class="Grid-u Nowrap">Team A</span></td><td>2</td><td>3</td></tr>
          </tbody>
        </table>
      </body>
    </html>
    """
    soup = bs4.BeautifulSoup(html, "lxml")

    context = _build_context(lambda *args, **kwargs: (soup, None))

    matchups.process_matchups(
        context,
        matchup_links=["https://example.com/m1"],
        team_totals_dict={"Team A": {"G": 5.0, "A": 7.0}},
        proxies=[],
        worksheet=worksheet,
    )

    data_rows = [
        row for _, _, row in worksheet.rows if row and row[0] in {"Fallback Team", "Team A"}
    ]
    assert data_rows[0][:3] == ["Fallback Team", "1", "2"]
    assert data_rows[1][:3] == ["Team A", 7.0, 10.0]

    spacer_rows = [row for _, _, row in worksheet.rows if row == [None, None, None]]
    assert len(spacer_rows) == 1


def test_process_matchups_skips_missing_table_and_continues(monkeypatch):
    worksheet = WorksheetSpy()
    printed = []
    soups = [
        bs4.BeautifulSoup("<html><body><p>no table</p></body></html>", "lxml"),
        _build_soup("3", "4"),
    ]

    monkeypatch.setattr(
        "builtins.print",
        lambda *args, **kwargs: printed.append(" ".join(str(arg) for arg in args)),
    )

    def parse_full_page(*args, **kwargs):
        return soups.pop(0), None

    context = _build_context(parse_full_page)

    matchups.process_matchups(
        context,
        matchup_links=["https://example.com/m1", "https://example.com/m2"],
        team_totals_dict={"Team A": {"G": 10.0, "A": 20.0}},
        proxies=[],
        worksheet=worksheet,
    )

    assert any(
        "Skipping matchup: result table not found (https://example.com/m1)" in m for m in printed
    )
    data_rows = [row for _, _, row in worksheet.rows if row and row[0] == "Team A"]
    assert data_rows[0][:3] == ["Team A", 13.0, 24.0]
