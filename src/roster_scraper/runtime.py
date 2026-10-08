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


def build_default_sheet_runtime():
    """Reuse current Yahoo callbacks without invoking CLI prompts or OAuth.

    The parsing helpers still reside in cli.py; importing it does not run main().
    Keep this adapter here so the HTTP entrypoint need not depend on that layout.
    """
    from . import cli

    return cli.build_scrape_dependencies(), cli.build_matchups_context()
