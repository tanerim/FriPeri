"""End-to-end ASGI regression scenarios against an isolated ephemeral SQLite installation.

Run locally with: python -m pip install -r requirements-dev.txt
                  python -m pytest -q tests/test_integration_flows.py
"""
import sqlite3

import pytest
from fastapi.testclient import TestClient

import main
from initialization import initialize_database, is_initialized, setup_defaults


@pytest.fixture
def site(tmp_path, monkeypatch):
    db = tmp_path / "database" / "test-site.db"
    uploads = tmp_path / "uploads"
    config = setup_defaults()
    config["site_name"] = "FriPeri Test Site"
    initialize_database(db, config, "admin", "correct-horse-2026", "correct-horse-2026")
    assert is_initialized(db)
    monkeypatch.setattr(main, "DB_PATH", db)
    monkeypatch.setattr(main, "UPLOAD_DIR", uploads)
    monkeypatch.setattr(main, "BACKUP_DIR", tmp_path / "backups")
    main.BACKUP_DIR.mkdir(exist_ok=True)
    monkeypatch.setattr(main.app.state, "database_identity", None, raising=False)
    with TestClient(main.app, base_url="https://testserver", follow_redirects=False) as client:
        yield client, db


def sign_in(client):
    response = client.post("/login", data={"username": "admin", "password": "correct-horse-2026"})
    assert response.status_code == 303
    assert "site_session" in client.cookies
    return response


def test_authentication_permissions_and_logout(site):
    client, _ = site
    assert client.get("/admin").status_code == 303
    assert client.get("/admin/documentation").status_code == 303
    assert client.post("/login", data={"username": "admin", "password": "wrong"}).status_code == 401
    sign_in(client)
    assert client.get("/admin").status_code == 200
    assert client.get("/admin/documentation").status_code == 200
    assert client.post("/admin/backup/create").status_code == 403
    assert client.post("/admin/backup/create", headers={"origin": "https://attacker.test"}).status_code == 403
    assert client.get("/logout").status_code == 303
    assert client.get("/admin").status_code == 303


def test_create_edit_and_delete_post(site):
    client, db = site
    sign_in(client)
    create = client.post("/admin/posts/new", data={
        "title_en": "An integration test post",
        "excerpt_en": "A description of the content",
        "body_html_en": "<p>Document body</p>",
        "status": "published",
    })
    assert create.status_code == 303
    with sqlite3.connect(db) as conn:
        post = conn.execute("SELECT id, slug, title FROM posts WHERE title=?", ("An integration test post",)).fetchone()
    assert post is not None
    assert client.get("/posts/" + post[1]).status_code == 200
    assert client.get("/admin/posts/" + str(post[0]) + "/edit").status_code == 200

    edited = client.post("/admin/posts/" + str(post[0]) + "/edit", data={
        "title_en": "Revised integration test post",
        "excerpt_en": "Updated excerpt",
        "body_html_en": "<p>Updated body</p>",
        "status": "published",
    })
    assert edited.status_code == 303
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT title FROM posts WHERE id=?", (post[0],)).fetchone()[0] == "Revised integration test post"
    deleted = client.post("/admin/posts/" + str(post[0]) + "/delete")
    assert deleted.status_code == 303
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM posts WHERE id=?", (post[0],)).fetchone()[0] == 0


def test_contact_validation_and_persistence(site):
    client, db = site
    import main as runtime
    bad = client.post("/contact", data={"name": "Visitor", "email": "invalid", "message": "Hello"})
    assert bad.status_code == 400
    good = client.post("/contact", data={
        "name": "Visitor", "email": "visitor@example.org", "message": "Hello!",
        "contact_token": runtime.contact_token(),
    })
    assert good.status_code == 303
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM contact_messages WHERE email=?", ("visitor@example.org",)).fetchone()[0] == 1


def test_first_run_rejected_after_initialization(site):
    client, _ = site
    assert client.get("/first-run").status_code == 303
    assert client.post("/first-run", data={}).status_code == 409


def test_runtime_health_exposes_no_filesystem_paths(site):
    client, _ = site
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_first_run_creates_isolated_installation(tmp_path, monkeypatch):
    fresh_db = tmp_path / "fresh" / "new.sqlite3"
    assert not fresh_db.exists()
    monkeypatch.setattr(main, "DB_PATH", fresh_db)
    monkeypatch.setattr(main.app.state, "database_identity", None, raising=False)
    with TestClient(main.app, base_url="https://testserver", follow_redirects=False) as client:
        page = client.get("/first-run")
        assert page.status_code == 200
        token = client.cookies.get("friperi_setup")
        assert token
        created = client.post("/first-run", data={
            "site_name": "New Test Installation",
            "site_description": "A fresh FriPeri installation",
            "admin_username": "admin",
            "admin_password": "a-strong-password-2026",
            "password_confirmation": "a-strong-password-2026",
            "setup_token": token,
        })
        assert created.status_code == 303
        assert is_initialized(fresh_db)
        assert client.get("/first-run").status_code == 303
