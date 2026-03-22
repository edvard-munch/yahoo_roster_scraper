from types import SimpleNamespace

import pytest
import requests

from roster_scraper.services import proxies


def test_get_response_without_proxy_calls_requests_directly(monkeypatch):
    captured = {}

    def fake_get(link, params):
        captured["link"] = link
        captured["params"] = params
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(proxies.requests, "get", fake_get)

    response = proxies.get_response("https://example.com", {"a": "1"})

    assert response.status_code == 200
    assert captured == {"link": "https://example.com", "params": {"a": "1"}}


def test_get_response_with_proxy_timeout_removes_proxy_and_returns_none(monkeypatch):
    def fake_get(*args, **kwargs):
        raise requests.ConnectTimeout

    monkeypatch.setattr(proxies.requests, "get", fake_get)

    proxy = {"http": "1.1.1.1:80", "https": "1.1.1.1:80"}
    proxies_list = [proxy]

    response = proxies.get_response("https://example.com", {}, proxies=proxies_list, proxy=proxy)

    assert response is None
    assert proxies_list == []


def test_get_response_with_retries_returns_first_success(monkeypatch):
    response = SimpleNamespace(status_code=200)

    monkeypatch.setattr(proxies, "get_proxy", lambda proxies_list: proxies_list[0])
    monkeypatch.setattr(proxies, "get_response", lambda *args, **kwargs: response)

    web, proxy = proxies.get_response_with_retries(
        "https://example.com",
        {},
        proxies=[{"http": "1.1.1.1:80", "https": "1.1.1.1:80"}],
    )

    assert web is response
    assert proxy["http"] == "1.1.1.1:80"


def test_get_response_with_retries_retries_then_succeeds(monkeypatch):
    response = SimpleNamespace(status_code=200)
    calls = {"count": 0}

    monkeypatch.setattr(proxies, "get_proxy", lambda proxies_list: proxies_list[0])

    def fake_get_response(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            return None
        return response

    monkeypatch.setattr(proxies, "get_response", fake_get_response)

    web, _ = proxies.get_response_with_retries(
        "https://example.com",
        {},
        proxies=[{"http": "1.1.1.1:80", "https": "1.1.1.1:80"}],
    )

    assert web is response
    assert calls["count"] == 3


def test_get_response_with_retries_raises_when_proxy_pool_exhausted(monkeypatch):
    calls = {"count": 0}

    def fake_get_proxy(proxies_list):
        calls["count"] += 1
        if calls["count"] < 3:
            return {"http": "1.1.1.1:80", "https": "1.1.1.1:80"}
        raise RuntimeError(proxies.NO_FREE_PROXIES_MESSAGE)

    monkeypatch.setattr(proxies, "get_proxy", fake_get_proxy)
    monkeypatch.setattr(proxies, "get_response", lambda *args, **kwargs: None)

    with pytest.raises(
        RuntimeError,
        match="Failed to load schedule: no free proxies available: https://example.com",
    ):
        proxies.get_response_with_retries(
            "https://example.com",
            {},
            proxies=[{"http": "1.1.1.1:80", "https": "1.1.1.1:80"}],
            failure_target=proxies.PROXY_FAILURE_TARGET_SCHEDULE,
        )
