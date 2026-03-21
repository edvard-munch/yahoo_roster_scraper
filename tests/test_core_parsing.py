import bs4

from roster_scraper.core import parsing


def test_string_to_num_handles_none_dash_and_percent_values():
    assert parsing.string_to_num(None, None) == 0.0
    assert parsing.string_to_num("-", None) == 0.0
    assert parsing.string_to_num("88%", "%") == 88.0


def test_map_headers_to_body_adds_scoring_totals_and_removes_action_column():
    headers = {
        "Action": [],
        "G": [],
        "A": [],
        "GL": [],
    }
    body = [
        ["+", "+"],
        ["1", "2"],
        ["3", "4"],
        [2, 3],
    ]

    result = parsing.map_headers_to_body(headers, body, season_in_progress=True)

    assert "Action" not in result
    assert result["G"] == ["1", "2", 8.0]
    assert result["A"] == ["3", "4", 18.0]
    assert result["GL"] == [2, 3]


def test_parse_clean_names_sorts_by_percent_and_defaults_missing_percent_to_zero():
    html = (
        "<tbody>"
        '<tr><td class="player"><a class="Nowrap name F-link playernote">Low</a>20%</td></tr>'
        '<tr><td class="player"><a class="Nowrap name F-link playernote">High</a>80%</td></tr>'
        '<tr><td class="player"><a class="Nowrap name F-link playernote">NoPercent</a>n/a</td></tr>'
        "</tbody>"
    )
    body = bs4.BeautifulSoup(html, "lxml").find("tbody")

    result = parsing.parse_clean_names([body])

    assert list(result[0]) == ["High", "Low", "NoPercent"]


def test_parse_for_json_skips_defensemen(monkeypatch):
    html = (
        "<tbody>"
        '<tr><td class="player"><a class="Nowrap name F-link playernote">Defenseman</a><span class="Fz-xxs">BOS - D</span></td></tr>'
        '<tr><td class="player"><a class="Nowrap name F-link playernote">Center</a><span class="Fz-xxs">BOS - C</span></td></tr>'
        "</tbody>"
    )
    skaters = bs4.BeautifulSoup(html, "lxml").find("tbody")

    monkeypatch.setattr(
        parsing.positions_scraper,
        "get_positional_data",
        lambda roster, name: {"name": name},
    )

    result = parsing.parse_for_json(skaters)

    assert result == [{"name": "Center"}]
