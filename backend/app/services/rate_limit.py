"""Limits per network address for sign-in and password-reset requests (review 22-11-2026, package 2).

The per-account lockout (5 wrong passwords, 15 minutes) stops guessing one account; this stops one address from
trying a password across many accounts, or locking staff out on purpose, and from flooding reset emails. Kept in
memory: the CRM runs as one server process. A restart clears it, which only gives an attacker a fresh window.
"""
import threading
import time
from collections import defaultdict, deque
from typing import Optional


class AddressLimit:
    def __init__(self, max_events: int, window_seconds: int):
        self.max_events, self.window = max_events, window_seconds
        self._events: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, q: deque, now: float) -> None:
        while q and now - q[0] > self.window:
            q.popleft()

    def blocked(self, address: Optional[str]) -> bool:
        if not address:
            return False
        with self._lock:
            q = self._events[address]
            self._prune(q, time.monotonic())
            return len(q) >= self.max_events

    def record(self, address: Optional[str]) -> None:
        if not address:
            return
        with self._lock:
            q = self._events[address]
            now = time.monotonic()
            self._prune(q, now)
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


# 20 failed sign-ins per address in 15 minutes; 5 password-reset requests per address in 15 minutes.
login_failures = AddressLimit(max_events=20, window_seconds=15 * 60)
reset_requests = AddressLimit(max_events=5, window_seconds=15 * 60)
# Browser error reports: 20 per address in 15 minutes (review 22-11-2026, package 6).
error_reports = AddressLimit(max_events=20, window_seconds=15 * 60)


def reset_all() -> None:
    login_failures.reset()
    reset_requests.reset()
    error_reports.reset()
