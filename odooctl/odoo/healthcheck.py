from __future__ import annotations
import time
from http.client import HTTPException
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def with_db_selector(url: str, db_name: str | None = None) -> str:
    if not db_name:
        return url
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["db"] = db_name
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def check_url(url: str, *, timeout: int = 5, retries: int = 12, interval: int = 5) -> bool:
    last_error: Exception | str | None = None
    for _ in range(retries):
        try:
            req = Request(url, headers={"User-Agent": "odooctl/0.1"})
            with urlopen(req, timeout=timeout) as response:
                if 200 <= response.status < 400:
                    return True
                last_error = f"unexpected HTTP status {response.status}"
        except HTTPError as exc:
            if 300 <= exc.code < 400:
                return True
            last_error = exc
        except (URLError, TimeoutError, ConnectionError, OSError, HTTPException) as exc:
            last_error = exc
        time.sleep(interval)
    if last_error:
        raise RuntimeError(f"Health check failed for {url}: {last_error}")
    return False
