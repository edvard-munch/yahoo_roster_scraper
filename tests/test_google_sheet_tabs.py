from unittest.mock import MagicMock

from roster_scraper.services import google_sheet_tabs


def make_service(sheets):
    service = MagicMock()
    service.get.return_value.execute.return_value = {"sheets": sheets}
    return service


def sheet(sheet_id, title, hidden=False):
    return {"properties": {"sheetId": sheet_id, "title": title, "hidden": hidden}}


def test_sanitize_tab_title_removes_forbidden_characters_and_limits_length():
    assert google_sheet_tabs.sanitize_tab_title(" BOS/[Stats]*? ") == "BOSStats"
    assert google_sheet_tabs.sanitize_tab_title("") == "Team"
    assert len(google_sheet_tabs.sanitize_tab_title("A" * 120)) == 100


def test_build_team_tabs_deduplicates_names_and_reserved_titles():
    team_tabs = google_sheet_tabs.build_team_tabs(
        ["Team/A", "TeamA", "MATCHUPS", "_config", "TeamA"]
    )

    assert [tab.title for tab in team_tabs] == [
        "TeamA",
        "TeamA (2)",
        "MATCHUPS (2)",
        "_config (2)",
        "TeamA (3)",
    ]


def test_build_team_tabs_reserves_suffix_space_with_long_names():
    team_tabs = google_sheet_tabs.build_team_tabs(["A" * 100, "A" * 100])

    assert len(team_tabs[1].title) == 100
    assert team_tabs[1].title.endswith(" (2)")


def test_quote_tab_range_escapes_apostrophes():
    assert google_sheet_tabs.quote_tab_range("Shawn's team") == "'Shawn''s team'"


def test_sync_stats_tabs_creates_missing_deletes_departed_and_clears_values():
    service = make_service(
        [
            sheet(1, "MATCHUPS"),
            sheet(2, "_config", hidden=True),
            sheet(3, "Existing Team"),
            sheet(4, "Departed Team"),
        ]
    )

    tabs = google_sheet_tabs.sync_stats_tabs(
        service,
        "sheet-123",
        ["Existing Team", "New Team"],
    )

    assert [tab.title for tab in tabs] == ["Existing Team", "New Team"]
    requests = service.batchUpdate.call_args.kwargs["body"]["requests"]
    assert requests == [
        {"addSheet": {"properties": {"title": "New Team"}}},
        {"deleteSheet": {"sheetId": 4}},
    ]
    service.values.return_value.batchClear.assert_called_once_with(
        spreadsheetId="sheet-123",
        body={"ranges": ["'MATCHUPS'", "'Existing Team'", "'New Team'"]},
    )


def test_sync_stats_tabs_adds_reserved_tabs_before_deleting_last_old_tab():
    service = make_service([sheet(9, "Old Team")])

    google_sheet_tabs.sync_stats_tabs(service, "sheet-123", [])

    requests = service.batchUpdate.call_args.kwargs["body"]["requests"]
    assert requests == [
        {"addSheet": {"properties": {"title": "MATCHUPS"}}},
        {"addSheet": {"properties": {"title": "_config", "hidden": True}}},
        {"deleteSheet": {"sheetId": 9}},
    ]


def test_sync_stats_tabs_preserves_existing_title_case_and_reserved_tabs():
    service = make_service(
        [
            sheet(1, "MATCHUPS"),
            sheet(2, "_config", hidden=True),
            sheet(3, "team one"),
        ]
    )

    tabs = google_sheet_tabs.sync_stats_tabs(service, "sheet-123", ["Team One"])

    assert tabs == [google_sheet_tabs.TeamTab("Team One", "team one")]
    service.batchUpdate.assert_not_called()


def test_sync_stats_tabs_hides_existing_config_tab():
    service = make_service([sheet(1, "MATCHUPS"), sheet(2, "_config"), sheet(3, "Team")])

    google_sheet_tabs.sync_stats_tabs(service, "sheet-123", ["Team"])

    requests = service.batchUpdate.call_args.kwargs["body"]["requests"]
    assert requests == [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": 2, "hidden": True},
                "fields": "hidden",
            }
        }
    ]
