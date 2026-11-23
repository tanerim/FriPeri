"""Navbar design, Contact presentation, and Messages moderation regressions."""
import sqlite3
from pathlib import Path

import main
from test_integration_flows import site, sign_in  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def test_design_navbar_controls_and_save(site):
    client, db = site
    sign_in(client)
    page = client.get("/admin/design")
    assert page.status_code == 200
    for field in ("navbar_style", "navbar_position", "navbar_alignment",
                  "navbar_logo_mode", "navbar_font_size", "navbar_logo_url"):
        assert 'name="' + field + '"' in page.text
    saved = client.post("/admin/design", data={
        "navbar_style": "glass", "navbar_position": "static",
        "navbar_alignment": "center", "navbar_width": "full",
        "navbar_font": "serif", "navbar_font_size": "17",
        "navbar_font_weight": "700", "navbar_height": "86",
        "navbar_logo_mode": "initials", "navbar_logo_size": "48",
        "navbar_show_tagline": "1",
    })
    assert saved.status_code == 303
    response = client.get("/contact")
    assert response.status_code == 200
    assert 'data-navbar-style="glass"' in response.text
    assert 'data-navbar-position="static"' in response.text
    assert 'data-navbar-alignment="center"' in response.text


def test_invalid_navbar_is_rejected(site):
    client, db = site
    sign_in(client)
    assert client.post("/admin/design", data={
        "navbar_style": "unknown", "navbar_height": "8000",
    }).status_code == 400


def test_contact_is_styled_and_form_is_preserved(site):
    client, _ = site
    page = client.get("/contact")
    assert page.status_code == 200
    assert 'class="contact-hero"' in page.text
    assert 'class="contact-layout"' in page.text
    assert 'name="contact_token"' in page.text
    assert 'name="website"' in page.text


def test_delete_message_requires_token(site):
    client, db = site
    sign_in(client)
    with sqlite3.connect(db) as conn:
        msg = conn.execute(
            "INSERT INTO contact_messages(name,email,message,created_at) "
            "VALUES('Visitor','visitor@example.org','Hello','2026-01-01')"
        )
        message_id = msg.lastrowid
    assert client.post(f"/admin/messages/{message_id}/delete").status_code == 403
    assert client.post(f"/admin/messages/{message_id}/delete", data={
        "editor_token": main.custom_home_token("admin"),
    }).status_code == 303
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM contact_messages").fetchone()[0] == 0


def test_spam_blocks_future_messages_and_can_unblock(site):
    client, db = site
    sign_in(client)
    with sqlite3.connect(db) as conn:
        msg = conn.execute(
            "INSERT INTO contact_messages(name,email,message,created_at) "
            "VALUES('Visitor','Spammer@Example.org','First','2026-01-01')"
        )
        message_id = msg.lastrowid
        conn.execute(
            "INSERT INTO contact_messages(name,email,message,created_at) "
            "VALUES('Visitor','SPAMMER@example.org','Second','2026-01-01')"
        )
    token = main.custom_home_token("admin")
    assert client.post(f"/admin/messages/{message_id}/spam",
                       data={"editor_token": token}).status_code == 303
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM contact_messages").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM blocked_contact_emails").fetchone()[0] == 1
    ignored = client.post("/contact", data={
        "name": "Visitor", "email": "spammer@example.org",
        "message": "Again", "contact_token": main.contact_token()
    })
    assert ignored.status_code == 303
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM contact_messages").fetchone()[0] == 0
    assert client.post("/admin/messages/unblock", data={
        "editor_token": token, "email": "spammer@example.org",
    }).status_code == 303
    allowed = client.post("/contact", data={
        "name": "Visitor", "email": "spammer@example.org",
        "message": "Again", "contact_token": main.contact_token()
    })
    assert allowed.status_code == 303
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM contact_messages").fetchone()[0] == 1
