from __future__ import annotations
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def check_url(url: str, *, timeout: int = 5, retries: int = 12, interval: int = 5) -> bool:
    last_error: Exception | str | None = None
    for _ in range(retries):
        try:
            req = Request(url, headers={"User-Agent": "odooctl/0.1"})
            with urlopen(req, timeout=timeout) as response:
                if 200 <= response.status < 400:
                    return True
                last_error = f"unexpected HTTP status {response.status}"
        except (URLError, HTTPError, TimeoutError) as exc:
            last_error = exc
        time.sleep(interval)
    if last_error:
        raise RuntimeError(f"Health check failed for {url}: {last_error}")
    return False
