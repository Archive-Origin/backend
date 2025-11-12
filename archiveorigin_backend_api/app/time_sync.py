from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from time import time
from typing import Optional

import ntplib

from config import settings

class TrustedTime:
    """Best-effort NTP backed clock with cached offset."""

    def __init__(self, refresh_interval: int = 60):
        self.refresh_interval = refresh_interval
        self._lock = Lock()
        self._last_fetch: float = 0.0
        self._offset: float = 0.0

    def now(self) -> datetime:
        with self._lock:
            current = time()
            if current - self._last_fetch > self.refresh_interval:
                self._refresh()
                self._last_fetch = current
            adjusted = current + self._offset
        return datetime.fromtimestamp(adjusted, tz=timezone.utc)

    def _refresh(self):
        client = ntplib.NTPClient()
        for host in settings.ntp_servers:
            try:
                response = client.request(host, version=3, timeout=1.5)
            except Exception:
                continue
            self._offset = response.tx_time - time()
            return
        # No servers reachable; fall back to system clock
        self._offset = 0.0

trusted_time = TrustedTime()
