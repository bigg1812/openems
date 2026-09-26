"""Single-flight SMARD refresh; the control cycle only reads the local cache."""

import threading
import time

from .price_cache import SpotmarketPriceCacheService, PublishedPriceSnapshot


class BackgroundPriceService:
    def __init__(self, service: SpotmarketPriceCacheService, *, refresh_seconds: float = 60):
        self.service = service
        self.refresh_seconds = refresh_seconds
        self._lock = threading.Lock()
        self._worker = None
        self._closed = False
        self._next_refresh = 0.0
        self._last_error = "Preisaktualisierung läuft."

    def refresh(self) -> PublishedPriceSnapshot:
        with self._lock:
            if not self._closed and (self._worker is None or not self._worker.is_alive()) and time.monotonic() >= self._next_refresh:
                self._worker = threading.Thread(target=self._update, name="mini-ems-prices", daemon=True)
                self._worker.start()
            error = self._last_error
            refreshing = self._worker is not None and self._worker.is_alive()
        # Atomic cache replacement makes concurrent reads see old or new complete data.
        # Re-slice the current interval on every call; never reuse an old current price.
        return self.service.read_cached_snapshot(error=error, refreshing=refreshing)

    def _update(self) -> None:
        try:
            snapshot = self.service.refresh()
            # The underlying service may return a usable cache after a failed
            # request. Preserve that source failure instead of claiming recovery.
            error = snapshot.price_source_status.get("error") or None
        except Exception as exc:
            # Preserve collection even if the provider returns malformed data.
            error = str(exc) or type(exc).__name__
        with self._lock:
            self._last_error = error
            self._next_refresh = time.monotonic() + self.refresh_seconds

    def close(self) -> None:
        with self._lock:
            self._closed = True
            worker = self._worker
        if worker is not None:
            worker.join(timeout=1)
