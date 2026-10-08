from dataclasses import dataclass

from roster_scraper import runtime


@dataclass
class Context:
    columns: object
    wide_column_width: int
    number_of_matchups_processed_message: str
    matchup_totals_parameter: str
    matchup_result_classes: str
    team_name_matchup_result_classes: str
    proxies_scraper: object
    parse_full_page: object
    scrape_from_page: object


@dataclass
class Dependencies:
    base_fantasy_url: str
    xlsx_format: str
    matchup_range_days_threshold: int
    playoffs_header: str
    research_stats_page: dict
    parse_full_page: object
    resolve_league_links: object
    get_matchup_date_range: object
    get_links_from_standings: object
    get_schedule: object
    build_roster_context: object
    build_avg_stats_page: object
    process_links: object
    today: object


def test_build_matchups_context_maps_runtime_values():
    callbacks = [object() for _ in range(3)]

    result = runtime.build_matchups_context(
        Context,
        columns={"first": (0, 0)},
        wide_column_width=20,
        processed_message="{} ready",
        totals_parameter="&date=total",
        result_classes="results",
        team_name_classes="team-name",
        proxies_scraper=callbacks[0],
        parse_full_page=callbacks[1],
        scrape_from_page=callbacks[2],
    )

    assert result.columns == {"first": (0, 0)}
    assert result.wide_column_width == 20
    assert result.number_of_matchups_processed_message == "{} ready"
    assert result.proxies_scraper is callbacks[0]
    assert result.parse_full_page is callbacks[1]
    assert result.scrape_from_page is callbacks[2]


def test_build_scrape_dependencies_maps_runtime_values():
    callbacks = [object() for _ in range(9)]

    result = runtime.build_scrape_dependencies(
        Dependencies,
        base_fantasy_url="https://example.com/",
        xlsx_format="1",
        matchup_range_days_threshold=7,
        playoffs_header="Championship Bracket",
        research_stats_page={"stat1": "R"},
        parse_full_page=callbacks[0],
        resolve_league_links=callbacks[1],
        get_matchup_date_range=callbacks[2],
        get_links_from_standings=callbacks[3],
        get_schedule=callbacks[4],
        build_roster_context=callbacks[5],
        build_avg_stats_page=callbacks[6],
        process_links=callbacks[7],
        today=callbacks[8],
    )

    assert result.base_fantasy_url == "https://example.com/"
    assert result.xlsx_format == "1"
    assert result.parse_full_page is callbacks[0]
    assert result.resolve_league_links is callbacks[1]
    assert result.process_links is callbacks[7]
    assert result.today is callbacks[8]


def test_default_sheet_runtime_builds_actual_contexts_without_interaction(monkeypatch):
    from roster_scraper import application, cli
    from roster_scraper.services import google_api_auth, matchups

    def forbidden(*args, **kwargs):
        raise AssertionError("Runtime construction must not prompt, scrape, or start OAuth")

    monkeypatch.setattr("builtins.input", forbidden)
    monkeypatch.setattr(google_api_auth, "get_credentials", forbidden)
    monkeypatch.setattr(cli.proxies_scraper, "get_response", forbidden)

    dependencies, context = runtime.build_default_sheet_runtime()

    assert isinstance(dependencies, application.ScrapeDependencies)
    assert isinstance(context, matchups.MatchupsContext)
    assert dependencies.parse_full_page is cli.parse_full_page
    assert dependencies.resolve_league_links is cli.resolve_league_links
    assert context.parse_full_page is dependencies.parse_full_page
