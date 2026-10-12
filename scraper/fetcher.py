# Downloads raw HTML pages from nutrition.umd.edu. This is the only part of the scraper
# that touches the network: it hands the HTML to menu_parser.py / label_parser.py,
# which turn it into Python objects. Keeping the two apart means the parsers can be
# tested on saved pages, and this file can be tested with a fake network.

import time
from datetime import date
from typing import Callable, Optional

import requests

BASE_URL = "https://nutrition.umd.edu"

# Identify ourselves honestly so UMD can see who is making requests.
USER_AGENT = "umd-macros-tracker (student project; scrapes at most twice a day)"

# Seconds to wait between requests, so we never hammer UMD's server.
DEFAULT_DELAY_SECONDS = 2.0

# Give up on a request after this many seconds instead of hanging forever.
DEFAULT_TIMEOUT_SECONDS = 10.0


class FetchError(Exception):
    """Raised when a page can't be downloaded (site down, timeout, error status).

    Wraps the several different `requests` exceptions into one, so callers
    only have to catch this.
    """


def build_menu_url(location_num: int, day: date) -> str:
    """Build the URL of one dining hall's menu page for one day.

    Args:
        location_num: UMD's ID for the dining hall (e.g. 19 = Yahentamitsi).
        day: which day's menu to get.

    Returns:
        The full URL. UMD expects the date as MM/DD/YYYY.

    Example:
        build_menu_url(19, date(2026, 10, 13))
        -> "https://nutrition.umd.edu/?locationNum=19&dtdate=10/13/2026"
    """
    # Built by hand rather than with urlencode, which would turn "/" into "%2F";
    # this way the URL looks exactly like the links on UMD's own site.
    return f"{BASE_URL}/?locationNum={location_num}&dtdate={day.strftime('%m/%d/%Y')}"


def build_label_url(recipe_id: str) -> str:
    """Build the URL of one item's nutrition label page.

    Args:
        recipe_id: UMD's RecNumAndPort ID, as found by menu_parser.

    Returns:
        The full label URL.

    Example:
        build_label_url("080603*4")
        -> "https://nutrition.umd.edu/label.aspx?RecNumAndPort=080603*4"
    """
    return f"{BASE_URL}/label.aspx?RecNumAndPort={recipe_id}"


class Fetcher:
    """Downloads pages politely: one at a time, with a pause between requests.

    It's a class (not plain functions) because it has to remember things between
    calls: the HTTP session (which reuses one connection) and when the last request
    happened (so it knows how long to wait).

    Example:
        fetcher = Fetcher()
        html = fetcher.fetch_menu_html(19, date(2026, 10, 13))
    """

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        delay_seconds: float = DEFAULT_DELAY_SECONDS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Set up the fetcher.

        Args:
            session: the HTTP session to use. Tests pass a fake one; normally leave it out.
            delay_seconds: minimum gap between two requests.
            timeout_seconds: how long to wait for UMD to respond.
            clock / sleep: how to read the time and how to wait. Tests pass fakes
                so they don't actually pause.
        """
        self.session = session if session is not None else requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self._clock = clock
        self._sleep = sleep
        self._last_request_time: Optional[float] = None

    def get_html(self, url: str) -> str:
        """Download one page and return its HTML, waiting first if needed.

        Args:
            url: the page to download.

        Returns:
            The page's HTML as a string.

        Raises:
            FetchError: if the site is unreachable, times out, or returns an error status.

        Example:
            fetcher.get_html("https://nutrition.umd.edu/label.aspx?RecNumAndPort=080603*4")
            -> "<html>...Nutrition Facts..."
        """
        self._wait_for_turn()
        try:
            response = self.session.get(url, timeout=self.timeout_seconds)
            response.raise_for_status()
        except requests.Timeout as error:
            raise FetchError(f"UMD Dining took longer than {self.timeout_seconds}s to respond: {url}") from error
        except requests.HTTPError as error:
            raise FetchError(f"UMD Dining returned an error ({response.status_code}) for {url}") from error
        except requests.RequestException as error:
            raise FetchError(f"Could not reach UMD Dining (is the site down?): {url}") from error
        finally:
            # Count failed requests too, so a retry loop elsewhere still waits.
            self._last_request_time = self._clock()
        return response.text

    def fetch_menu_html(self, location_num: int, day: date) -> str:
        """Download one dining hall's menu page for one day. See build_menu_url."""
        return self.get_html(build_menu_url(location_num, day))

    def fetch_label_html(self, recipe_id: str) -> str:
        """Download one item's nutrition label page. See build_label_url."""
        return self.get_html(build_label_url(recipe_id))

    def _wait_for_turn(self) -> None:
        """Sleep just long enough that requests are at least delay_seconds apart."""
        if self._last_request_time is None:
            return  # first request: no need to wait
        elapsed = self._clock() - self._last_request_time
        if elapsed < self.delay_seconds:
            self._sleep(self.delay_seconds - elapsed)
