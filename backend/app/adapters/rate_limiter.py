import time


class RateLimiter:
    """Enforces a minimum gap between calls: a small, single-threaded stand-in for a token
    bucket, enough to stay under a broker API's published per-second cap."""

    def __init__(self, min_interval_seconds: float):
        self.min_interval = min_interval_seconds
        self._last_call = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()
