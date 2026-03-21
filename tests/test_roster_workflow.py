from types import SimpleNamespace

from roster_scraper.services import roster_workflow


class DummyResponse:
    def __init__(self, text):
        self.text = text


def test_process_links_skips_team_when_headers_missing(monkeypatch):
    html_missing_headers = """
    <html>
      <head><title>Broken Team | Yahoo Fantasy Sports</title></head>
      <body>
        <table><tr><th>Team</th><th>GP</th></tr></table>
      </body>
    </html>
    """

    proxies_scraper = SimpleNamespace(
        get_response=lambda *args, **kwargs: DummyResponse(html_missing_headers),
        get_proxy=lambda proxies: None,
    )

    workbook = SimpleNamespace(
        add_worksheet=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("worksheet should not be created")
        )
    )

    matchups_calls = []
    matchups_service = SimpleNamespace(
        process_matchups=lambda *args, **kwargs: matchups_calls.append((args, kwargs))
    )

    context = roster_workflow.RosterWorkflowContext(
        format_choices={"xlsx": "1", "txt": "2", "json": "3", "google_sheets": "4"},
        parser="lxml",
        proxies_scraper=proxies_scraper,
        schedule_scraper=SimpleNamespace(
            TEAM_CODE_ALIASES={},
            apply_team_aliases=lambda schedule: schedule,
        ),
        core_parsing=SimpleNamespace(
            map_headers_to_body=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("map_headers_to_body should not be called")
            )
        ),
        core_output=SimpleNamespace(
            verify_sheet_name=lambda name: name,
            write_to_xlsx=lambda *args, **kwargs: None,
        ),
        write_to_google_sheet=SimpleNamespace(google=lambda *_: None),
        workbook=workbook,
        scoring_columns=[],
        empty_spot_string="Empty",
        number_of_teams_processed_message="{}/{} teams ready",
        positions_filename="reports/positions.json",
        get_team_name=lambda soup, fallback_name: "Broken Team",
        get_headers=lambda soup: (_ for _ in ()).throw(
            RuntimeError("Roster header row not found")
        ),
        get_body=lambda *args, **kwargs: [],
        matchups_service=matchups_service,
        matchups_context=SimpleNamespace(),
    )

    printed = []
    monkeypatch.setattr(
        "builtins.print",
        lambda *args, **kwargs: printed.append(" ".join(str(arg) for arg in args)),
    )

    roster_workflow.process_links(
        context,
        links=["https://example.com/team/1"],
        proxies=[],
        choice="1",
        stats_page={},
        matchup_links=[],
        schedule={},
        matchups_worksheet=SimpleNamespace(),
    )

    assert any(
        "Skipping team due to header parse error: Broken Team" in message
        for message in printed
    )
    assert any("Roster header row not found" in message for message in printed)
    assert len(matchups_calls) == 1
