import datetime
import re
from dataclasses import dataclass
from typing import Any, Callable


MATCHUP_RANGE_DETECTED_MESSAGE = "Detected matchup range: {} -> {} ({} days)"
MATCHUP_RANGE_MODE_MESSAGE = "Using matchup range for schedule scraping"
MATCHUP_RANGE_EFFECTIVE_MESSAGE = "Effective remaining matchup range: {} -> {}"
MATCHUP_WEEKLY_MODE_MESSAGE = "Using default weekly schedule scraping"
MATCHUP_RANGE_NOT_FOUND_MESSAGE = (
    "Could not detect matchup date range; using default weekly schedule ({})"
)


@dataclass(frozen=True)
class SeasonMode:
    in_progress: bool
    just_started: bool


SEASON_MODES_BY_NAME = {
    "preseason": SeasonMode(in_progress=False, just_started=False),
    "just_started": SeasonMode(in_progress=True, just_started=True),
    "in_season": SeasonMode(in_progress=True, just_started=False),
}


@dataclass(frozen=True)
class ScrapeConfig:
    league_id: str
    season_mode: SeasonMode
    output_format: str
    start_date_override: datetime.date | None = None


@dataclass
class PreparedLeague:
    soup: Any
    links: tuple[list[str], list[str]]
    proxies: list
    current_proxy: Any = None


@dataclass(frozen=True)
class ScrapeDependencies:
    base_fantasy_url: str
    xlsx_format: str
    matchup_range_days_threshold: int
    playoffs_header: str
    research_stats_page: dict
    parse_full_page: Callable
    resolve_league_links: Callable
    get_matchup_date_range: Callable
    get_links_from_standings: Callable
    get_schedule: Callable
    build_roster_context: Callable
    build_avg_stats_page: Callable
    process_links: Callable
    today: Callable[[], datetime.date]


def prepare_league(league_id, season_mode, proxies, dependencies, current_proxy=None):
    league_link = dependencies.base_fantasy_url + league_id
    soup, current_proxy = dependencies.parse_full_page(
        league_link,
        proxies,
        current_proxy,
    )
    league_links, current_proxy = dependencies.resolve_league_links(
        soup,
        league_link,
        league_id,
        season_mode,
        proxies,
        current_proxy,
    )

    if not league_links or not league_links[1]:
        return None

    return PreparedLeague(
        soup=soup,
        links=league_links,
        proxies=proxies,
        current_proxy=current_proxy,
    )


def run_scrape(config, prepared_league, matchups_context, dependencies, stats_sink=None):
    matchup_links, team_links = prepared_league.links
    current_proxy = prepared_league.current_proxy

    if config.output_format == dependencies.xlsx_format:
        if stats_sink is None:
            raise ValueError("Full stats output requires a stats sink")

        start_date = None
        end_date = None
        if matchup_links:
            matchup_date_range, current_proxy = dependencies.get_matchup_date_range(
                matchup_links[0],
                prepared_league.proxies,
                current_proxy,
                league_soup=prepared_league.soup,
            )
            if matchup_date_range:
                parsed_start_date, parsed_end_date = matchup_date_range
                duration_days = (parsed_end_date - parsed_start_date).days + 1
                print(
                    MATCHUP_RANGE_DETECTED_MESSAGE.format(
                        parsed_start_date,
                        parsed_end_date,
                        duration_days,
                    )
                )
                if duration_days > dependencies.matchup_range_days_threshold:
                    today = dependencies.today()
                    start_date = max(today, parsed_start_date)
                    end_date = parsed_end_date
                    print(MATCHUP_RANGE_MODE_MESSAGE)
                    print(MATCHUP_RANGE_EFFECTIVE_MESSAGE.format(start_date, end_date))
                else:
                    print(MATCHUP_WEEKLY_MODE_MESSAGE)
            else:
                print(MATCHUP_RANGE_NOT_FOUND_MESSAGE.format(matchup_links[0]))

        schedule, _ = dependencies.get_schedule(
            start_date=start_date,
            end_date=end_date,
            start_date_override=config.start_date_override,
        )
        roster_context = dependencies.build_roster_context(
            stats_sink,
            matchups_context,
            config.season_mode,
        )
        current_proxy = dependencies.process_links(
            roster_context,
            team_links,
            prepared_league.proxies,
            config.output_format,
            dependencies.build_avg_stats_page(config.season_mode.just_started),
            matchup_links,
            schedule,
            proxy=current_proxy,
        )
        stats_sink.close()
        return current_proxy

    if prepared_league.soup.find(string=re.compile(dependencies.playoffs_header)):
        team_links, current_proxy = dependencies.get_links_from_standings(
            config.league_id,
            prepared_league.proxies,
            current_proxy,
        )

    roster_context = dependencies.build_roster_context(
        None,
        matchups_context,
        config.season_mode,
    )
    return dependencies.process_links(
        roster_context,
        team_links,
        prepared_league.proxies,
        config.output_format,
        dependencies.research_stats_page,
        proxy=current_proxy,
    )
