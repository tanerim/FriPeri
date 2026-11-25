"""Additional regression checks for proxy-aware privilege registration."""
from test_privileges import csrf, set_private


def test_register_behind_proxy_with_forwarded_host(app_site):
    client, db, _ = app_site
    set_private(client)
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
