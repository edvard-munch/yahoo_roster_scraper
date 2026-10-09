import datetime
from functools import partial

from . import application
from .core import output as core_output, parsing as core_parsing
from .services import matchups as matchups_service
from .services import proxies as proxies_scraper, schedule as schedule_scraper
from .services import roster_workflow, write_to_google_sheet, yahoo_scraper


def build_matchups_context(
    context_type,
    *,
    columns,
    wide_column_width,
    processed_message,
    totals_parameter,
    result_classes,
    team_name_classes,
    proxies_scraper,
    parse_full_page,
    scrape_from_page,
):
    return context_type(
        columns=columns,
        wide_column_width=wide_column_width,
        number_of_matchups_processed_message=processed_message,
        matchup_totals_parameter=totals_parameter,
        matchup_result_classes=result_classes,
        team_name_matchup_result_classes=team_name_classes,
        proxies_scraper=proxies_scraper,
        parse_full_page=parse_full_page,
        scrape_from_page=scrape_from_page,
    )


def build_scrape_dependencies(
    dependencies_type,
    *,
    base_fantasy_url,
    xlsx_format,
    matchup_range_days_threshold,
    playoffs_header,
    research_stats_page,
    parse_full_page,
    resolve_league_links,
    get_matchup_date_range,
    get_links_from_standings,
    get_schedule,
    build_roster_context,
    build_avg_stats_page,
    process_links,
    today,
):
    return dependencies_type(
        base_fantasy_url=base_fantasy_url,
        xlsx_format=xlsx_format,
        matchup_range_days_threshold=matchup_range_days_threshold,
        playoffs_header=playoffs_header,
        research_stats_page=research_stats_page,
        parse_full_page=parse_full_page,
        resolve_league_links=resolve_league_links,
        get_matchup_date_range=get_matchup_date_range,
        get_links_from_standings=get_links_from_standings,
        get_schedule=get_schedule,
        build_roster_context=build_roster_context,
        build_avg_stats_page=build_avg_stats_page,
        process_links=process_links,
        today=today,
    )


def build_default_matchups_context():
    return build_matchups_context(
        matchups_service.MatchupsContext,
        columns=yahoo_scraper.COLUMNS,
        wide_column_width=yahoo_scraper.WIDE_COLUMN_WIDTH,
        processed_message=yahoo_scraper.NUMBER_OF_MATCHUPS_PROCESSED_MESSAGE,
        totals_parameter=yahoo_scraper.MATCHUP_TOTALS_PARAMETER,
        result_classes=yahoo_scraper.MATCHUP_RESULT_CLASSES,
        team_name_classes=yahoo_scraper.TEAM_NAME_MATCHUP_RESULT_CLASSES,
        proxies_scraper=proxies_scraper,
        parse_full_page=yahoo_scraper.parse_full_page,
        scrape_from_page=yahoo_scraper.scrape_from_page,
    )


def build_roster_context(stats_sink, matchups_context, season_mode):
    return roster_workflow.RosterWorkflowContext(
        format_choices=yahoo_scraper.FORMAT_CHOICES,
        parser=yahoo_scraper.PARSER,
        proxies_scraper=proxies_scraper,
        schedule_scraper=schedule_scraper,
        core_parsing=core_parsing,
        core_output=core_output,
        write_to_google_sheet=write_to_google_sheet,
        stats_sink=stats_sink,
        scoring_columns=yahoo_scraper.SCORING_COLUMNS,
        empty_spot_string=yahoo_scraper.EMPTY_SPOT_STRING,
        number_of_teams_processed_message=yahoo_scraper.NUMBER_OF_TEAMS_PROCESSED_MESSAGE,
        positions_filename=yahoo_scraper.POSITIONS_FILENAME,
        get_team_name=yahoo_scraper.get_team_name,
        get_headers=partial(yahoo_scraper.get_headers, season_in_progress=season_mode.in_progress),
        get_body=partial(yahoo_scraper.get_body, season_in_progress=season_mode.in_progress),
        matchups_service=matchups_service,
        matchups_context=matchups_context,
    )


def build_default_scrape_dependencies():
    return build_scrape_dependencies(
        application.ScrapeDependencies,
        base_fantasy_url=yahoo_scraper.BASE_FANTASY_URL,
        xlsx_format=yahoo_scraper.FORMAT_CHOICES["xlsx"],
        matchup_range_days_threshold=yahoo_scraper.MATCHUP_RANGE_DAYS_THRESHOLD,
        playoffs_header=yahoo_scraper.PLAYOFFS_HEADER,
        research_stats_page=yahoo_scraper.RESEARCH_STATS_PAGE,
        parse_full_page=yahoo_scraper.parse_full_page,
        resolve_league_links=yahoo_scraper.resolve_league_links,
        get_matchup_date_range=yahoo_scraper.get_matchup_date_range,
        get_links_from_standings=yahoo_scraper.get_links_from_standings,
        get_schedule=schedule_scraper.get_schedule,
        build_roster_context=build_roster_context,
        build_avg_stats_page=yahoo_scraper.build_avg_stats_page,
        process_links=roster_workflow.process_links,
        today=datetime.date.today,
    )


def build_default_sheet_runtime():
    return build_default_scrape_dependencies(), build_default_matchups_context()
