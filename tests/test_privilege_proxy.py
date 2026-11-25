"""Additional regression checks for proxy-aware privilege registration."""
from test_privileges import app_site, csrf, set_private


def test_register_behind_proxy_with_configured_origin(app_site, monkeypatch):
    client, db, _ = app_site
    set_private(client)
    monkeypatch.setenv("FRIPERI_PUBLIC_ORIGIN", "https://public.example.org")
    token = csrf(client)
    response = client.post(
        "/access/video_sorgu/register",
        headers={"Origin": "https://public.example.org",
                 "Host": "internal-app:8000",
                 "X-Forwarded-Host": "public.example.org",
                 "Sec-Fetch-Site": "same-origin"},
        data={"csrf": token, "first_name": "Proxy",
              "last_name": "User", "email": "proxy@example.org",
              "password": "strong-long-password-2026"},
    )
    assert response.status_code == 303


def test_cross_site_rejected_even_if_forwarded_host_matches(app_site):
    client, db, _ = app_site
    set_private(client)
    token = csrf(client)
    response = client.post(
        "/access/video_sorgu/register",
        headers={"Origin": "https://attacker.example",
                 "Host": "internal-app:8000",
                 "X-Forwarded-Host": "attacker.example",
                 "Sec-Fetch-Site": "cross-site"},
        data={"csrf": token, "first_name": "Proxy",
              "last_name": "User", "email": "blocked@example.org",
              "password": "strong-long-password-2026"},
    )
    assert response.status_code == 403


def test_opaque_origin_same_origin_with_signed_token(app_site):
    client, db, _ = app_site
    set_private(client)
    token = csrf(client)
    response = client.post(
        "/access/video_sorgu/register",
        headers={"Origin": "null", "Sec-Fetch-Site": "same-origin"},
        data={"csrf": token, "first_name": "Private", "last_name": "Browser",
              "email": "opaque@example.org", "password": "strong-long-password-2026"},
    )
    assert response.status_code == 303
    with db() as conn:
        row = conn.execute("SELECT status FROM privilege_requests WHERE folder='video_sorgu'").fetchone()
        assert row["status"] == "pending"


def test_opaque_origin_without_same_origin_is_rejected(app_site):
    client, db, _ = app_site
    set_private(client)
    token = csrf(client)
    for headers in (
        {"Origin": "null"},
        {"Origin": "null", "Sec-Fetch-Site": "cross-site"},
        {"Origin": "null", "Sec-Fetch-Site": "same-site"},
    ):
        response = client.post(
            "/access/video_sorgu/register", headers=headers,
            data={"csrf": token, "first_name": "Unsafe", "last_name": "Browser",
                  "email": "unsafe@example.org", "password": "strong-long-password-2026"},
        )
        assert response.status_code == 403


def test_register_displays_mutually_exclusive_panels(app_site):
    client, db, _ = app_site
    set_private(client)
    response = client.get("/access/video_sorgu")
    assert response.status_code == 200
    assert 'class="login-panel"' in response.text
    assert 'class="register"' in response.text
    assert "main:has(.register[open]) .login-panel{display:none}" in response.text
