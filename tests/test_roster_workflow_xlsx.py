from types import SimpleNamespace

from roster_scraper.services import roster_workflow


class DummyResponse:
    def __init__(self, text):
        self.text = text


class WorkbookSpy:
    def __init__(self):
        self.added = []

    def add_worksheet(self, name):
        worksheet = SimpleNamespace(name=name)
        self.added.append(worksheet)
        return worksheet


def _build_xlsx_context(proxy_enabled, get_body_impl):
    map_calls = []
    write_calls = []
    matchup_calls = []
    get_proxy_calls = []
    get_response_calls = []

    workbook = WorkbookSpy()

    if proxy_enabled:
        proxies_scraper = SimpleNamespace(
            get_proxy=lambda proxies: (
                get_proxy_calls.append(list(proxies))
                or {"http": "1.1.1.1:80", "https": "1.1.1.1:80"}
            ),
            get_response=lambda link, stats_page, proxies, proxy: (
                get_response_calls.append(
                    {
                        "link": link,
                        "stats_page": stats_page,
                        "proxies": list(proxies),
                        "proxy": proxy,
                    }
                )
                or DummyResponse("<html><body></body></html>")
            ),
        )
    else:
        proxies_scraper = SimpleNamespace(
            get_proxy=lambda proxies: (_ for _ in ()).throw(
                AssertionError("get_proxy should not be called")
            ),
            get_response=lambda link, stats_page: (
                get_response_calls.append({"link": link, "stats_page": stats_page})
                or DummyResponse("<html><body></body></html>")
            ),
        )

    context = roster_workflow.RosterWorkflowContext(
        format_choices={"xlsx": "1", "txt": "2", "json": "3", "google_sheets": "4"},
        parser="lxml",
        proxies_scraper=proxies_scraper,
        schedule_scraper=SimpleNamespace(
            TEAM_CODE_ALIASES={"XYZ": "XYZ"},
            apply_team_aliases=lambda schedule: schedule,
        ),
        core_parsing=SimpleNamespace(
            map_headers_to_body=lambda headers, body, season_in_progress: (
                map_calls.append(
                    {
                        "headers": dict(headers),
                        "body": body,
                        "season_in_progress": season_in_progress,
                    }
                )
                or {"G": [1, 2, 3.0], "Other": ["x"]}
            )
        ),
        core_output=SimpleNamespace(
            verify_sheet_name=lambda team_name: team_name.replace("/", ""),
            write_to_xlsx=lambda table, worksheet: write_calls.append(
                {"table": table, "worksheet": worksheet}
            ),
        ),
        write_to_google_sheet=SimpleNamespace(google=lambda *_: None),
        workbook=workbook,
        scoring_columns=["G", "A"],
        empty_spot_string="Empty",
        number_of_teams_processed_message="{}/{} teams ready",
        positions_filename="reports/positions.json",
        get_team_name=lambda soup, fallback_name: " Team/One ",
        get_headers=lambda soup: {"G": [], "Other": []},
        get_body=get_body_impl,
        matchups_service=SimpleNamespace(process_matchups=lambda *args: matchup_calls.append(args)),
        matchups_context=SimpleNamespace(tag="ctx"),
    )

    return (
        context,
        workbook,
        map_calls,
        write_calls,
        matchup_calls,
        get_proxy_calls,
        get_response_calls,
    )


def test_process_links_xlsx_builds_totals_and_dispatches_matchups_without_proxies():
    context, workbook, map_calls, write_calls, matchup_calls, _, get_response_calls = (
        _build_xlsx_context(
            proxy_enabled=False,
            get_body_impl=lambda soup, schedule, missing_schedule_teams: [["row"], [0]],
        )
    )

    roster_workflow.process_links(
        context,
        links=["https://example.com/team/1"],
        proxies=[],
        choice="1",
        stats_page={"stat": "AS"},
        matchup_links=["https://example.com/m1"],
        schedule={"BOS": {"GL": 3}},
        matchups_worksheet=SimpleNamespace(name="matchups"),
    )

    assert workbook.added[0].name == " TeamOne "
    assert len(map_calls) == 1
    assert map_calls[0]["season_in_progress"] is True
    assert len(write_calls) == 1
    assert len(get_response_calls) == 1

    assert len(matchup_calls) == 1
    args = matchup_calls[0]
    assert args[0].tag == "ctx"
    assert args[1] == ["https://example.com/m1"]
    assert args[2] == {"Team/One": {"G": 3.0}}
    assert args[3] == []
    assert args[4].name == "matchups"


def test_process_links_xlsx_uses_proxy_path_and_reports_missing_schedule_teams(
    monkeypatch,
):
    printed = []
    monkeypatch.setattr(
        "builtins.print",
        lambda *args, **kwargs: printed.append(" ".join(str(arg) for arg in args)),
    )

    context, _, _, _, matchup_calls, get_proxy_calls, get_response_calls = _build_xlsx_context(
        proxy_enabled=True,
        get_body_impl=lambda soup, schedule, missing_schedule_teams: (
            missing_schedule_teams.add("XYZ") or [["row"], [0]]
        ),
    )

    roster_workflow.process_links(
        context,
        links=["https://example.com/team/1"],
        proxies=[{"http": "proxy", "https": "proxy"}],
        choice="1",
        stats_page={"stat": "AS"},
        matchup_links=[],
        schedule={"BOS": {"GL": 3}},
        matchups_worksheet=SimpleNamespace(name="matchups"),
    )

    assert len(get_proxy_calls) == 1
    assert len(get_response_calls) == 1
    assert len(matchup_calls) == 1
    assert any("Schedule teams not found" in message for message in printed)
