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
        proxies_scraper=SimpleNamespace(
            get_proxy=lambda proxies: proxies[0] if proxies else None
        ),
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
