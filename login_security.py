"""Conservative, bounded, per-process login attempt throttling.

For multi-worker installations, enforce a shared rate limit in the reverse proxy.
"""
from collections import deque
from threading import Lock
from time import monotonic

WINDOW_SECONDS = 15 * 60
MAX_FAILURES = 8
MAX_ACCOUNT_FAILURES = 30
MAX_TRACKED_KEYS = 10000
_attempts: dict[str, deque[float]] = {}
_lock = Lock()


def _keys(address: str, username: str) -> tuple[str, str]:
    # We deliberately do not trust client-supplied Forwarded/X-Forwarded-For.
    return "ip:" + address[:150], "account:" + username.casefold()[:150]


def _prune(key: str, now: float) -> deque[float]:
    events = _attempts.setdefault(key, deque())
    while events and now - events[0] >= WINDOW_SECONDS:
        events.popleft()
    return events


def blocked(address: str, username: str) -> bool:
    now = monotonic()
    with _lock:
        ip_key, account_key = _keys(address, username)
        return len(_prune(ip_key, now)) >= MAX_FAILURES or len(_prune(account_key, now)) >= MAX_ACCOUNT_FAILURES


def failed(address: str, username: str) -> None:
    now = monotonic()
    with _lock:
        if len(_attempts) > MAX_TRACKED_KEYS:
            # Keeps memory bounded if a client attempts many unique user names.
            for key in list(_attempts):
                if not _prune(key, now):
                    _attempts.pop(key, None)
            if len(_attempts) > MAX_TRACKED_KEYS:
                _attempts.clear()
        for key in _keys(address, username):
            _prune(key, now).append(now)


def succeeded(address: str, username: str) -> None:
    with _lock:
        _attempts.pop("account:" + username.casefold()[:150], None)
        # Deliberately preserve per-IP failures to slow credential stuffing.
