"""Directory privileges: whole-asset authorization, requests, revocation and reset.

Run: python -m pytest -q tests/test_privileges.py
"""
import sqlite3
import re
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from initialization import connect_database, hash_password, verify_password
from privileges import (ProtectedStaticFiles, create_router, current_account,
                        install_schema, safe_target)


@pytest.fixture
def app_site(tmp_path, monkeypatch):
    db_path = tmp_path / "site.db"
    static = tmp_path / "static"
    folder = static / "video_sorgu"
    public = static / "public_pages"
    folder.mkdir(parents=True)
    public.mkdir()
    (folder / "index.html").write_text("<h1>Private research</h1>")
    (folder / "app.js").write_text("console.log('protected');")
    (public / "index.html").write_text("<p>Public</p>")
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        install_schema(conn)
    def db():
        return connect_database(db_path)
    def is_admin(request):
        return request.cookies.get("priv_admin_test") == "yes"
    def account(request):
        return {"role":"admin","username":"admin"} if is_admin(request) else None
    def render_admin(request, template, title, context, username):
        return HTMLResponse(f"<h1>{title}</h1><p>{len(context['directories'])} folders</p>")
    app = FastAPI()
    app.mount("/static", ProtectedStaticFiles(
        directory=static, db=db, secret=lambda: "test-secret",
        admin_check=is_admin, first_run=lambda: False))
    app.include_router(create_router(
        db=db, static_dir=static, secret=lambda:"test-secret",
        secure_cookie=True, password_hash=hash_password,
        password_verify=verify_password,
        admin_account=account, admin_token=lambda r,u:"admin-csrf",
        site_name=lambda:"Research Portal",
        now=lambda:"2026-11-25T12:00:00+00:00", render_admin=render_admin))
    monkeypatch.setenv("PRIVILEGES_STATIC_PROXY_CONFIRMED", "1")
    with TestClient(app, base_url="https://testserver",follow_redirects=False) as client:
        yield client, db, folder


def csrf(client):
    page=client.get("/access/video_sorgu")
    assert page.status_code==200
    match=re.search(r'name="csrf" value="([^"]+)"',page.text)
    assert match, "Access form must contain a signed CSRF token"
    return match.group(1)


def set_private(client):
    client.cookies.set("priv_admin_test","yes")
    response=client.post("/admin/privileges/video_sorgu/mode",data={
        "mode":"private","settings_token":"admin-csrf"})
    assert response.status_code==303
    client.cookies.delete("priv_admin_test")


def register(client, email="person@example.org"):
    token=csrf(client)
    response=client.post("/access/video_sorgu/register",data={
        "csrf":token,"first_name":"First","last_name":"Last",
        "email":email,"password":"long-test-password-2026"})
    assert response.status_code==303
    assert client.cookies.get("friperi_privilege_session")


def admin_action(client, db, action, password=None):
    with db() as conn:
        uid=conn.execute("SELECT id FROM privilege_accounts").fetchone()["id"]
    client.cookies.set("priv_admin_test","yes")
    form={"settings_token":"admin-csrf"}
    if password is not None:form["password"]=password
    response=client.post(f"/admin/privileges/video_sorgu/{uid}/{action}",data=form)
    client.cookies.delete("priv_admin_test")
    assert response.status_code==303


def test_public_dirs_remain_public(app_site):
    client,db,_=app_site
    assert client.get("/static/public_pages/index.html").status_code==200
    assert client.get("/static/video_sorgu/index.html").status_code==200
    set_private(client)
    assert client.get("/static/public_pages/index.html").status_code==200


def test_private_root_html_js_and_direct_assets_protected(app_site):
    client,db,_=app_site
    set_private(client)
    page=client.get("/static/video_sorgu/index.html")
    assert page.status_code==303
    assert page.headers["location"].startswith("/access/video_sorgu")
    assert client.get("/static/video_sorgu/app.js").status_code==403
    register(client)
    assert client.get("/static/video_sorgu/app.js").status_code==403
    admin_action(client,db,"approve")
    allowed=client.get("/static/video_sorgu/index.html")
    assert allowed.status_code==200
    assert allowed.headers["cache-control"]=="private, no-store"
    assert client.get("/static/video_sorgu/app.js").status_code==200
    admin_action(client,db,"revoke")
    assert client.get("/static/video_sorgu/index.html").status_code==303
    assert client.get("/static/video_sorgu/app.js").status_code==403


def test_reset_revokes_session_and_new_password_works(app_site):
    client,db,_=app_site
    set_private(client)
    register(client)
    admin_action(client,db,"approve")
    assert client.get("/static/video_sorgu/app.js").status_code==200
    admin_action(client,db,"reset","different-long-password")
    assert client.get("/static/video_sorgu/app.js").status_code==403
    token=csrf(client)
    response=client.post("/access/video_sorgu/login",data={
        "csrf":token,"email":"person@example.org",
        "password":"different-long-password"})
    assert response.status_code==303
    assert client.get("/static/video_sorgu/app.js").status_code==200


def test_admin_actions_are_csrf_and_role_protected(app_site):
    client,db,_=app_site
    set_private(client)
    register(client)
    assert client.post("/admin/privileges/video_sorgu/mode",
          data={"settings_token":"admin-csrf","mode":"private"}).status_code==403
    client.cookies.set("priv_admin_test","yes")
    assert client.post("/admin/privileges/video_sorgu/mode",
          data={"mode":"private"}).status_code==403
    client.cookies.delete("priv_admin_test")


def test_disabled_proxy_confirmation_rejects_private_setting(app_site,monkeypatch):
    client,db,_=app_site
    monkeypatch.delenv("PRIVILEGES_STATIC_PROXY_CONFIRMED")
    client.cookies.set("priv_admin_test","yes")
    response=client.post("/admin/privileges/video_sorgu/mode",data={
        "settings_token":"admin-csrf","mode":"private"})
    assert response.status_code==409


def test_registration_csrf_required(app_site):
    client,db,_=app_site
    set_private(client)
    response=client.post("/access/video_sorgu/register",data={
        "first_name":"A","last_name":"B","email":"p@example.org",
        "password":"long-test-password-2026"})
    assert response.status_code==403


def test_target_rejects_open_redirects():
    assert safe_target("https://evil.test/", "video_sorgu")=="/static/video_sorgu/index.html"
    assert safe_target("/static/video_sorgu/../secret", "video_sorgu")=="/static/video_sorgu/index.html"
    assert safe_target("/static/other/secret", "video_sorgu")=="/static/video_sorgu/index.html"


def test_privilege_password_hashes_are_salted_and_versioned():
    from privileges import hash_privilege_password, verify_privilege_password
    salt, digest=hash_privilege_password("long-test-password-2026")
    assert salt.startswith("pbkdf2-600k:")
    assert len(digest)==64
    assert verify_privilege_password("long-test-password-2026",salt,digest,verify_password)
    assert not verify_privilege_password("wrong-password",salt,digest,verify_password)


def test_registration_with_https_origin_behind_http_upstream(app_site):
    client, db, _ = app_site
    set_private(client)
    token = csrf(client)
    result = client.post("/access/video_sorgu/register", headers={
        "Origin": "https://testserver", "Host": "testserver"
    }, data={
        "csrf": token, "first_name": "Test", "last_name": "Person",
        "email": "origin-check@example.org", "password": "strong-long-password-2026",
    })
    assert result.status_code == 303
    with db() as conn:
        request = conn.execute("SELECT status FROM privilege_requests WHERE folder='video_sorgu'").fetchone()
    assert request is not None and request["status"] == "pending"


def test_csrf_failure_displays_recovery_page_without_creating_account(app_site):
    client, db, _ = app_site
    set_private(client)
    response = client.post("/access/video_sorgu/register", data={
        "csrf": "invalid", "first_name": "Test", "last_name": "Person",
        "email": "should-not-register@example.org", "password": "strong-long-password-2026",
    })
    assert response.status_code == 403
    assert "Form verification failed" in response.text
    assert "Return to access page" in response.text
    with db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM privilege_accounts").fetchone()[0] == 0


def test_cross_site_registration_rejected_even_with_csrf_cookie(app_site):
    client, db, _ = app_site
    set_private(client)
    token = csrf(client)
    response = client.post("/access/video_sorgu/register",
       headers={"Origin": "https://attacker.example"},
       data={"csrf": token, "first_name": "Test", "last_name": "Person",
             "email": "forbidden@example.org", "password": "strong-long-password-2026"})
    assert response.status_code == 403
    with db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM privilege_accounts").fetchone()[0] == 0


def test_registration_without_csrf_cookie(app_site):
    client, db, _ = app_site
    set_private(client)
    token = csrf(client)
    # Privacy-sensitive browsers may suppress cookies entirely on this form.
    client.cookies.clear()
    result=client.post("/access/video_sorgu/register",
        headers={"Origin":"https://testserver","Host":"testserver"},
        data={"csrf":token,"first_name":"Una","last_name":"Researcher",
              "email":"no-cookie@example.org","password":"long-test-password-2026"})
    assert result.status_code==303
    with db() as conn:
        assert conn.execute("SELECT status FROM privilege_requests").fetchone()["status"]=="pending"


def test_tampered_and_expired_tokens_are_rejected(app_site):
    import time
    client, db, _ = app_site
    set_private(client)
    token = csrf(client)
    pieces=token.split(":")
    tampered=":".join([pieces[0],pieces[1],"0"*64])
    for invalid in (tampered,"0:aaaa:"+pieces[-1], ""):
        response=client.post("/access/video_sorgu/register",data={
           "csrf":invalid,"first_name":"Una","last_name":"Researcher",
           "email":"bad-token@example.org","password":"long-test-password-2026"})
        assert response.status_code==403
    with db() as conn:
        assert conn.execute("SELECT count(*) FROM privilege_accounts").fetchone()[0]==0


def test_access_screen_uses_site_brand_and_hides_internal_paths(app_site):
    client, _, _ = app_site
    set_private(client)
    response = client.get("/access/video_sorgu")
    assert response.status_code == 200
    assert "Research Portal · Controlled Access" in response.text
    assert "FriPeri · Controlled Access" not in response.text
    assert "Directory:" not in response.text
    assert ">Access page</a>" not in response.text
    assert ">Home</a>" not in response.text
    assert 'name="csrf"' in response.text
    assert '/access/video_sorgu/register' in response.text
    assert '/access/video_sorgu/login' in response.text
