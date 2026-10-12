# Tests for scraper/fetcher.py. A fake session stands in for the network and a fake
# clock stands in for time, so these never hit the UMD site and never actually sleep.

from datetime import date
from typing import List, Optional

import pytest
import requests

from scraper.fetcher import (
    Fetcher,
    FetchError,
    build_label_url,
    build_menu_url,
)


class FakeResponse:
    """Pretends to be a requests.Response with a given status code and body."""

    def __init__(self, status_code: int = 200, text: str = "") -> None:
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        """Mimic requests: raise HTTPError for 4xx/5xx status codes."""
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


class FakeSession:
    """Pretends to be a requests.Session. Returns a canned response (or raises a
    canned error) and records which URLs were requested."""

    def __init__(self, response: Optional[FakeResponse] = None, error: Optional[Exception] = None) -> None:
        self.headers = {}
        self.response = response or FakeResponse()
        self.error = error
        self.requested_urls: List[str] = []

    def get(self, url: str, timeout: float) -> FakeResponse:
        self.requested_urls.append(url)
        if self.error is not None:
            raise self.error
        return self.response


class FakeClock:
    """A clock that only moves when we tell it to. Its sleep() records how long
    it was asked to wait and moves time forward by that much, without real waiting."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: List[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_fetcher(session: FakeSession, clock: Optional[FakeClock] = None) -> Fetcher:
    """Build a Fetcher wired to fakes, with a 2-second delay."""
    clock = clock or FakeClock()
    return Fetcher(session=session, delay_seconds=2.0, clock=clock.time, sleep=clock.sleep)


# --- URL building ---

def test_menu_url_uses_umd_date_format():
    assert build_menu_url(19, date(2026, 10, 13)) == "https://nutrition.umd.edu/?locationNum=19&dtdate=10/13/2026"


def test_label_url_keeps_recipe_id_as_is():
    assert build_label_url("080603*4") == "https://nutrition.umd.edu/label.aspx?RecNumAndPort=080603*4"


# --- Downloading ---

def test_successful_request_returns_html():
    session = FakeSession(FakeResponse(200, "<html>menu</html>"))
    html = make_fetcher(session).fetch_menu_html(19, date(2026, 10, 13))
    assert html == "<html>menu</html>"
    assert session.requested_urls == [build_menu_url(19, date(2026, 10, 13))]


def test_sends_identifying_user_agent():
    session = FakeSession()
    make_fetcher(session)
    assert "umd-macros-tracker" in session.headers["User-Agent"]


def test_server_error_raises_fetch_error():
    session = FakeSession(FakeResponse(500))
    with pytest.raises(FetchError, match="500"):
        make_fetcher(session).fetch_label_html("080603*4")


def test_timeout_raises_fetch_error():
    session = FakeSession(error=requests.Timeout())
    with pytest.raises(FetchError, match="longer than"):
        make_fetcher(session).get_html("https://nutrition.umd.edu/")


def test_connection_failure_raises_fetch_error():
    session = FakeSession(error=requests.ConnectionError())
    with pytest.raises(FetchError, match="site down"):
        make_fetcher(session).get_html("https://nutrition.umd.edu/")


# --- Politeness delay ---

def test_first_request_does_not_wait():
    clock = FakeClock()
    make_fetcher(FakeSession(), clock).get_html("https://nutrition.umd.edu/")
    assert clock.sleeps == []


def test_back_to_back_requests_wait_full_delay():
    clock = FakeClock()
    fetcher = make_fetcher(FakeSession(), clock)
    fetcher.get_html("https://nutrition.umd.edu/a")
    fetcher.get_html("https://nutrition.umd.edu/b")
    assert clock.sleeps == [2.0]


def test_waits_only_the_remaining_time():
    clock = FakeClock()
    fetcher = make_fetcher(FakeSession(), clock)
    fetcher.get_html("https://nutrition.umd.edu/a")
    clock.now += 1.5  # pretend 1.5s passed (e.g. parsing the page)
    fetcher.get_html("https://nutrition.umd.edu/b")
    assert clock.sleeps == [pytest.approx(0.5)]


def test_no_wait_if_delay_already_passed():
    clock = FakeClock()
    fetcher = make_fetcher(FakeSession(), clock)
    fetcher.get_html("https://nutrition.umd.edu/a")
    clock.now += 5
    fetcher.get_html("https://nutrition.umd.edu/b")
    assert clock.sleeps == []


def test_failed_request_still_counts_for_delay():
    clock = FakeClock()
    session = FakeSession(error=requests.ConnectionError())
    fetcher = make_fetcher(session, clock)
    with pytest.raises(FetchError):
        fetcher.get_html("https://nutrition.umd.edu/a")
    session.error = None
    fetcher.get_html("https://nutrition.umd.edu/b")
    assert clock.sleeps == [2.0]
