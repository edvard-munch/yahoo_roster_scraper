import bs4

from roster_scraper import cli


def _build_soup(rows_html):
    html = f"<html><body><table><tbody></tbody><tbody>{rows_html}</tbody></table></body></html>"
    return bs4.BeautifulSoup(html, "lxml")


def test_get_body_uses_direct_team_schedule_match():
    soup = _build_soup(
        '<tr><td class="pos-label">C</td><td class="player"><a class="Nowrap name F-link playernote">Player One</a><span class="Fz-xxs">BOS - C</span></td><td class="stat">10</td></tr>'
    )
    schedule = {"BOS": {cli.schedule_scraper.GAMES_LEFT_THIS_WEEK_COLUMN: 3}}

    body = cli.get_body(soup, schedule)

    assert body[-1] == [3]


def test_get_body_uses_alias_schedule_match():
    soup = _build_soup(
        '<tr><td class="pos-label">C</td><td class="player"><a class="Nowrap name F-link playernote">Player Two</a><span class="Fz-xxs">MON - C</span></td><td class="stat">11</td></tr>'
    )
    schedule = {"MTL": {cli.schedule_scraper.GAMES_LEFT_THIS_WEEK_COLUMN: 2}}

    body = cli.get_body(soup, schedule)

    assert body[-1] == [2]


def test_get_body_records_missing_schedule_team_and_sets_zero():
    soup = _build_soup(
        '<tr><td class="pos-label">C</td><td class="player"><a class="Nowrap name F-link playernote">Player Three</a><span class="Fz-xxs">XYZ - C</span></td><td class="stat">12</td></tr>'
    )
    missing_schedule_teams = set()

    schedule = {"BOS": {cli.schedule_scraper.GAMES_LEFT_THIS_WEEK_COLUMN: 3}}

    body = cli.get_body(
        soup, schedule=schedule, missing_schedule_teams=missing_schedule_teams
    )

    assert body[-1] == [0]
    assert missing_schedule_teams == {"XYZ"}


def test_get_body_skips_not_playing_rows():
    soup = _build_soup(
        '<tr><td class="pos-label">C</td><td class="player"><a class="Nowrap name F-link playernote">Healthy Player</a><span class="Fz-xxs">BOS - C</span></td><td class="stat">10</td></tr>'
        '<tr><td class="pos-label">IR</td><td class="player"><a class="Nowrap name F-link playernote">Injured Player</a><span class="Fz-xxs">BOS - C</span></td><td class="stat">9</td></tr>'
    )
    schedule = {"BOS": {cli.schedule_scraper.GAMES_LEFT_THIS_WEEK_COLUMN: 3}}

    body = cli.get_body(soup, schedule)

    flattened = [item for column in body for item in column]
    assert "Healthy Player" in flattened
    assert "Injured Player" not in flattened
    assert body[-1] == [3]
