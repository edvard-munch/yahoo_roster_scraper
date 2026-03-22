import json
from types import SimpleNamespace

from roster_scraper.services import roster_workflow


class DummyResponse:
    def __init__(self, text):
        self.text = text


def _build_context(tmp_path, choice, parse_clean_names_result=None, parse_for_json_result=None):
    html = "<html><body><tbody></tbody><tbody><tr><td>player</td></tr></tbody></body></html>"
    calls = {
        "txt": [],
        "google": [],
        "json_parse": [],
        "clean_parse": [],
    }

    core_parsing = SimpleNamespace(
        map_headers_to_body=lambda *args, **kwargs: {},
        parse_clean_names=lambda bodies: (
            calls["clean_parse"].append(bodies) or parse_clean_names_result
        ),
        parse_for_json=lambda body: calls["json_parse"].append(body) or parse_for_json_result,
    )
    core_output = SimpleNamespace(
        verify_sheet_name=lambda name: name,
        write_to_xlsx=lambda *args, **kwargs: None,
        write_roster_to_txt=lambda data, mode, team_name, empty_spot: calls["txt"].append(
            {
                "data": data,
                "mode": mode,
                "team_name": team_name,
                "empty_spot": empty_spot,
            }
        ),
    )
    write_to_google_sheet = SimpleNamespace(
        google=lambda filename: calls["google"].append(filename)
    )

    context = roster_workflow.RosterWorkflowContext(
        format_choices={"xlsx": "1", "txt": "2", "json": "3", "google_sheets": "4"},
        parser="lxml",
        proxies_scraper=SimpleNamespace(
            get_response=lambda *args, **kwargs: DummyResponse(html),
            get_proxy=lambda proxies: None,
        ),
        schedule_scraper=SimpleNamespace(
            TEAM_CODE_ALIASES={},
            apply_team_aliases=lambda schedule: schedule,
        ),
        core_parsing=core_parsing,
        core_output=core_output,
        write_to_google_sheet=write_to_google_sheet,
        workbook=SimpleNamespace(add_worksheet=lambda **kwargs: SimpleNamespace()),
        scoring_columns=[],
        empty_spot_string="Empty",
        number_of_teams_processed_message="{}/{} teams ready",
        positions_filename=str(tmp_path / "positions.json"),
        get_team_name=lambda soup, fallback_name: "Team One",
        get_headers=lambda soup: {},
        get_body=lambda *args, **kwargs: [],
        matchups_service=SimpleNamespace(process_matchups=lambda *args, **kwargs: None),
        matchups_context=SimpleNamespace(),
    )

    roster_workflow.process_links(
        context,
        links=["https://example.com/team/1"],
        proxies=[],
        choice=choice,
        stats_page={},
        matchup_links=[],
        schedule={},
        matchups_worksheet=SimpleNamespace(),
    )

    return calls, context


def test_process_links_txt_branch_writes_clean_roster(tmp_path):
    calls, _ = _build_context(tmp_path, choice="2", parse_clean_names_result=[["P1", "P2"]])

    assert len(calls["txt"]) == 1
    assert calls["txt"][0]["data"] == [["P1", "P2"]]
    assert calls["txt"][0]["mode"] == "w"
    assert calls["txt"][0]["team_name"] == "Team One"
    assert calls["txt"][0]["empty_spot"] == "Empty"


def test_process_links_json_branch_writes_positions_file(tmp_path):
    calls, context = _build_context(
        tmp_path,
        choice="3",
        parse_for_json_result=[{"name": "Player Json"}],
    )

    with open(context.positions_filename) as text_file:
        payload = json.load(text_file)

    assert payload == {"Team One": [{"name": "Player Json"}]}
    assert len(calls["json_parse"]) == 1
    assert calls["google"] == []


def test_process_links_google_sheets_branch_writes_json_and_calls_google(tmp_path):
    calls, context = _build_context(
        tmp_path,
        choice="4",
        parse_for_json_result=[{"name": "Player Sheet"}],
    )

    with open(context.positions_filename) as text_file:
        payload = json.load(text_file)

    assert payload == {"Team One": [{"name": "Player Sheet"}]}
    assert calls["google"] == [context.positions_filename]
