"""Security regression checks; all tests run locally without GitHub Actions."""
import pytest
from starlette.requests import Request

import login_security as limiter
from main import _same_origin_admin_request


def request_for(host="example.org", origin=None, referer=None, fetch_site="same-origin"):
    headers = [(b"host", host.encode()), (b"sec-fetch-site", fetch_site.encode())]
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    if referer is not None:
        headers.append((b"referer", referer.encode()))
    scope = {"type": "http", "method": "POST", "path": "/admin/backup/create",
             "scheme": "https", "server": ("example.org", 443),
             "client": ("127.0.0.1", 1234), "headers": headers}
    return Request(scope)


def test_admin_origin_checks():
    assert _same_origin_admin_request(request_for(origin="https://example.org"))
    assert _same_origin_admin_request(request_for(referer="https://example.org/admin"))
    assert not _same_origin_admin_request(request_for(origin="https://bad.org"))
    assert not _same_origin_admin_request(request_for(fetch_site="cross-site"))
    assert not _same_origin_admin_request(request_for(fetch_site="same-site"))
    assert not _same_origin_admin_request(request_for(origin="https://example.org.evil.test"))


@pytest.fixture(autouse=True)
def reset_login_attempts():
    limiter._attempts.clear()
    yield
    limiter._attempts.clear()


def test_login_throttle_and_account_reset():
    for _ in range(limiter.MAX_FAILURES):
        limiter.failed("192.0.2.1", "admin")
    assert limiter.blocked("192.0.2.1", "admin")
    assert not limiter.blocked("192.0.2.2", "admin")
    for n in range(limiter.MAX_ACCOUNT_FAILURES - limiter.MAX_FAILURES):
        limiter.failed(f"198.51.100.{n}", "admin")
    assert limiter.blocked("192.0.2.2", "admin")
    assert limiter.blocked("192.0.2.1", "other")
    limiter.succeeded("192.0.2.1", "admin")
    assert not limiter.blocked("192.0.2.2", "admin")
    assert limiter.blocked("192.0.2.1", "other")
