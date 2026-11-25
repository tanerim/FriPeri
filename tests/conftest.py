"""Keep process-local security state isolated between independent tests."""
import pytest

import login_security


@pytest.fixture(autouse=True)
def isolate_login_rate_limiter(monkeypatch):
    # Preserve real throttling within each test, without leaking attempts
    # across independent application fixtures.
    monkeypatch.setattr(login_security, "_attempts", {})
