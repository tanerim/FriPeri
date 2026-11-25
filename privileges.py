"""Directory-scoped public/static privileges, isolated from CMS administrator accounts.

IMPORTANT: Reverse proxies must forward *all* /static/ requests to the FastAPI
application. An nginx 'alias' / 'root' shortcut bypasses this authorization.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import sqlite3
import secrets
import time
from pathlib import Path
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from login_security import blocked as login_blocked, failed as login_failed, succeeded as login_succeeded

COOKIE = "friperi_privilege_session"
CSRF_COOKIE = "friperi_privilege_csrf"
SESSION_AGE = 7 * 24 * 3600
HEADERS = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
           "X-Content-Type-Options": "nosniff"}
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
FOLDER_RE = re.compile(r"^[^/\\\\\x00-\x1f]{1,120}$")


def install_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS privilege_directories(
        folder TEXT PRIMARY KEY, is_private INTEGER NOT NULL DEFAULT 0
        CHECK(is_private IN (0,1)), updated_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS privilege_accounts(
        id INTEGER PRIMARY KEY, first_name TEXT NOT NULL,
        last_name TEXT NOT NULL, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password_salt TEXT NOT NULL, password_hash TEXT NOT NULL,
        session_version INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS privilege_requests(
        account_id INTEGER NOT NULL REFERENCES privilege_accounts(id) ON DELETE CASCADE,
        folder TEXT NOT NULL, status TEXT NOT NULL
          CHECK(status IN ('pending','approved','denied','revoked')),
        requested_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY(account_id,folder)
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS privilege_requests_folder ON privilege_requests(folder,status)")
    conn.execute("""CREATE TABLE IF NOT EXISTS privilege_audit(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        folder TEXT NOT NULL,
        account_id INTEGER,
        created_at TEXT NOT NULL
    )""")


def folders(static_dir: Path):
    """Top-level directories only; no symlinks or dot-prefixed system entries."""
    return sorted((p.name for p in static_dir.iterdir()
                   if p.is_dir() and not p.is_symlink() and not p.name.startswith(".")
                   and FOLDER_RE.fullmatch(p.name)), key=str.casefold)


def private_folder(conn, folder: str) -> bool:
    row = conn.execute("SELECT is_private FROM privilege_directories WHERE folder=?", (folder,)).fetchone()
    return bool(row and row["is_private"])


def hash_privilege_password(password: str):
    """New privilege accounts use PBKDF2-HMAC-SHA256 with 600k iterations.

    Separate versioned salt keeps compatibility with accounts created by
    earlier FriPeri builds without changing CMS password storage.
    """
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000).hex()
    return "pbkdf2-600k:" + salt, digest


def verify_privilege_password(password: str, salt: str, digest: str, legacy_verify):
    if salt.startswith("pbkdf2-600k:"):
        raw = salt.split(":", 1)[1]
        if not re.fullmatch(r"[0-9a-f]{32}", raw):
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), raw.encode(), 600_000).hex()
        return hmac.compare_digest(candidate, digest)
    return legacy_verify(password, salt, digest)


def sign_session(account, secret: str) -> str:
    expiry = int(time.time()) + SESSION_AGE
    payload = f"{account['id']}:{account['session_version']}:{expiry}:{secrets.token_hex(12)}"
    signature = hmac.new(secret.encode(), ("privilege:" + payload).encode(), hashlib.sha256).hexdigest()
    return payload + ":" + signature


def current_account(request: Request, conn, secret: str):
    value = request.cookies.get(COOKIE, "")
    parts = value.split(":")
    if len(parts) != 5:
        return None
    uid, version, expires, nonce, signature = parts
    if not (uid.isdecimal() and version.isdecimal() and expires.isdecimal()
            and re.fullmatch(r"[0-9a-f]{24}", nonce)
            and re.fullmatch(r"[0-9a-f]{64}", signature)):
        return None
    payload = ":".join(parts[:4])
    expected = hmac.new(secret.encode(), ("privilege:" + payload).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected) or int(expires) < time.time():
        return None
    row = conn.execute("SELECT * FROM privilege_accounts WHERE id=?", (int(uid),)).fetchone()
    return row if row and row["session_version"] == int(version) else None


def allowed(request: Request, conn, folder: str, secret: str, admin_check=None) -> bool:
    if admin_check and admin_check(request):
        return True
    account = current_account(request, conn, secret)
    if account is None:
        return False
    row = conn.execute(
        "SELECT status FROM privilege_requests WHERE account_id=? AND folder=?",
        (account["id"], folder)).fetchone()
    return bool(row and row["status"] == "approved")


def safe_target(value: str, folder: str):
    prefix = "/static/" + folder + "/"
    # Avoid protocol-relative URLs, backslashes, CRLF, traversal, and redirects.
    if (not value.startswith(prefix) or "\\" in value or any(c in value for c in "\r\n")
            or ".." in value.split("/") or "%" in value):
        return prefix + "index.html"
    return value


def access_url(folder: str, target: str | None = None):
    base = "/access/" + quote(folder, safe="")
    return base + ("?next=" + quote(target, safe="") if target else "")


class ProtectedStaticFiles(StaticFiles):
    """Gate every asset under a private top-level folder, including HTML/JS/CSS.

    StaticFiles continues to handle safe path resolution and symlink protection.
    """
    def __init__(self, *, directory, db, secret, admin_check=None, first_run=None):
        super().__init__(directory=directory, html=False, check_dir=True, follow_symlink=False)
        self._db, self._secret, self._admin = db, secret, admin_check
        self._first_run = first_run

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        relative = path.split("/static/", 1)[-1] if "/static/" in path else ""
        folder = relative.split("/", 1)[0]
        if scope["type"] == "http" and folder and FOLDER_RE.fullmatch(folder):
            try:
                with self._db() as conn:
                    gated = private_folder(conn, folder)
                    permitted = not gated or allowed(Request(scope), conn, folder, self._secret(), self._admin)
            except sqlite3.OperationalError:
                if self._first_run and self._first_run():
                    return await super().__call__(scope, receive, send)
                response = Response("Static access temporarily unavailable", status_code=503, headers=HEADERS)
                await response(scope, receive, send)
                return
            if gated and not permitted:
                wants_page = relative.endswith((".html", "/")) or "/" not in relative
                if wants_page and scope["method"] in ("GET", "HEAD"):
                    response = RedirectResponse(access_url(folder, path), status_code=303, headers=HEADERS)
                else:
                    response = Response("Forbidden", status_code=403, headers=HEADERS)
                await response(scope, receive, send)
                return
            if gated:
                async def private_send(message):
                    if message["type"] == "http.response.start":
                        entries = [(key, value) for key, value in message.get("headers", [])
                                   if key.lower() not in (b"cache-control", b"etag")]
                        entries += [(b"cache-control", b"private, no-store"),
                                    (b"vary", b"Cookie"),
                                    (b"x-content-type-options", b"nosniff")]
                        message["headers"] = entries
                    await send(message)
                return await super().__call__(scope, receive, private_send)
        return await super().__call__(scope, receive, send)


def create_router(*, db, static_dir: Path, secret, secure_cookie: bool,
                  password_hash, password_verify, admin_account, admin_token, now, render_admin):
    router = APIRouter()

    def csrf_page(request: Request, content: str, status=200):
        token = request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,64}", token):
            token = secrets.token_urlsafe(32)
        response = HTMLResponse(content.replace("{{CSRF}}", token), status_code=status, headers=HEADERS)
        response.set_cookie(CSRF_COOKIE, token, secure=secure_cookie,
                            httponly=True, samesite="lax", max_age=3600, path="/access")
        return response

    def valid_public_form(request, form):
        # Compare the submitted Origin to the actual forwarded Host. A TLS
        # terminator may create request.url from an internal HTTP upstream.
        origin = request.headers.get("origin", "")
        if origin:
            parsed = urlsplit(origin)
            host = request.headers.get("host", "").lower().rstrip(".")
            if (parsed.scheme not in ("http", "https")
                    or not host or parsed.netloc.lower().rstrip(".") != host):
                return False
        elif request.headers.get("sec-fetch-site", "") == "cross-site":
            return False
        supplied = str(form.get("csrf", ""))
        cookie = request.cookies.get(CSRF_COOKIE, "")
        return bool(supplied and cookie and hmac.compare_digest(supplied, cookie))

    def rejected_public_form(request, folder):
        # Keep the CSRF protection and show a recoverable error, not a blank 403.
        body = ('<p role="alert">Your form could not be verified. Please reload '
                'the access page and try again. Enable cookies for this site.</p>'
                f'<p><a href="{access_url(folder)}">Return to access page</a></p>')
        return csrf_page(request, shell("Form verification failed", folder, body), status=403)

    def shell(title, folder, body, next_path=""):
        from html import escape as e
        f = e(folder)
        return ("""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
        <meta name="robots" content="noindex,nofollow"><title>""" + e(title) + """ · FriPeri</title>
        <style>body{font:16px/1.6 system-ui;background:#f4f7fb;color:#17263b;min-height:100vh;display:grid;place-items:center;margin:0}
        main{box-sizing:border-box;width:min(500px,calc(100% - 32px));background:white;padding:36px;border:1px solid #dce5ed;border-radius:18px;box-shadow:0 16px 45px #10273a10}
        h1{margin:0 0 8px}p{color:#53647a}label{display:grid;gap:5px;margin:14px 0;font-weight:600;font-size:14px}
        input{padding:12px;border:1px solid #ccd8e5;border-radius:8px;font:inherit}button{background:#20435b;color:white;border:0;border-radius:9px;padding:12px 18px;cursor:pointer;font:inherit}
        a{color:#205b7a}nav{display:flex;gap:14px;flex-wrap:wrap;margin-top:20px}</style></head><body><main>
        <p>FriPeri · Controlled Access</p><h1>""" + e(title) + """</h1><p>Directory: <strong>""" + f + """</strong></p>""" +
        body + """<nav><a href="/access/""" + quote(folder, safe="") + """">Access</a><a href="/">Home</a></nav></main></body></html>""")

    def page(request, folder, error="", next_path=""):
        from html import escape as e
        if folder not in folders(static_dir):
            return Response(status_code=404)
        with db() as conn:
            if not private_folder(conn, folder):
                return RedirectResponse("/static/" + quote(folder, safe="") + "/index.html", status_code=303)
            account = current_account(request, conn, secret())
            if account:
                status = conn.execute("SELECT status FROM privilege_requests WHERE account_id=? AND folder=?",
                                      (account["id"], folder)).fetchone()
                if status and status["status"] == "approved":
                    return RedirectResponse(safe_target(next_path, folder), status_code=303)
                state = status["status"] if status else "No access request yet"
                form = (f'<p>Access status: <strong>{e(state)}</strong></p>'
                        f'<form method="post" action="/access/{quote(folder,safe="")}/request">'
                        '<input type="hidden" name="csrf" value="{{CSRF}}">'
                        '<button type="submit">Request access</button></form>' if not status else
                        f'<p>Your access status is <strong>{e(state)}</strong>. Contact the administrator if needed.</p>')
                form += ('<form method="post" action="/access/logout"><input type="hidden" name="csrf" value="{{CSRF}}">'
                         '<button type="submit">Sign out</button></form>')
                return csrf_page(request, shell("Access status", folder, form))
        next_input = f'<input type="hidden" name="next" value="{e(safe_target(next_path,folder))}">'
        login = (f'<form method="post" action="/access/{quote(folder,safe="")}/login">'
                 '<label>Email<input name="email" type="email" required autocomplete="username"></label>'
                 '<label>Password<input name="password" type="password" required autocomplete="current-password"></label>'
                 + next_input + '<input type="hidden" name="csrf" value="{{CSRF}}"><button type="submit">Sign in</button></form>')
        register = (f'<details><summary>New user? Register for access</summary><form method="post" action="/access/{quote(folder,safe="")}/register">'
                    '<label>First name<input name="first_name" required maxlength="80"></label>'
                    '<label>Last name<input name="last_name" required maxlength="80"></label>'
                    '<label>Email<input name="email" type="email" required autocomplete="email"></label>'
                    '<label>Password (12–128 characters)<input name="password" type="password" required minlength="12" maxlength="128" autocomplete="new-password"></label>'
                    '<input type="hidden" name="csrf" value="{{CSRF}}"><button type="submit">Register and request access</button></form></details>')
        msg = f'<p role="alert">{e(error)}</p>' if error else ""
        return csrf_page(request, shell("Restricted directory", folder, msg+login+register))

    @router.get("/access/{folder}", response_class=HTMLResponse)
    async def access_page(request: Request, folder: str):
        return page(request, folder, next_path=request.query_params.get("next", ""))

    @router.post("/access/{folder}/register")
    async def register(request: Request, folder: str):
        if folder not in folders(static_dir):
            return Response(status_code=404)
        form = await request.form()
        if not valid_public_form(request, form):
            return rejected_public_form(request, folder)
        ip = request.client.host if request.client else "unknown"
        registration_key = "privilege-registration:" + ip
        if login_blocked(ip, registration_key):
            return Response("Too many registration attempts", status_code=429,
                            headers={**HEADERS, "Retry-After": "900"})
        first, last = (str(form.get(key,"")).strip() for key in ("first_name", "last_name"))
        email, password = str(form.get("email","")).strip().lower(), str(form.get("password",""))
        if not (1<=len(first)<=80 and 1<=len(last)<=80 and EMAIL_RE.fullmatch(email)
                and 12<=len(password)<=128 and not any(ord(c)<32 for c in first+last)):
            return page(request, folder, "Please enter valid details and a password of at least 12 characters.")
        with db() as conn:
            if not private_folder(conn, folder):
                return Response(status_code=409)
            exists = conn.execute("SELECT id FROM privilege_accounts WHERE email=?", (email,)).fetchone()
            if exists:
                return page(request, folder, "If you have an existing account, please sign in.")
            login_failed(ip, registration_key)
            salt, digest = hash_privilege_password(password)
            cur = conn.execute(
                "INSERT INTO privilege_accounts(first_name,last_name,email,password_salt,password_hash,created_at) VALUES(?,?,?,?,?,?)",
                (first,last,email,salt,digest,now()))
            conn.execute("INSERT INTO privilege_requests(account_id,folder,status,requested_at,updated_at) VALUES(?,?,'pending',?,?)",
                         (cur.lastrowid,folder,now(),now()))
            account = conn.execute("SELECT * FROM privilege_accounts WHERE id=?", (cur.lastrowid,)).fetchone()
        response = RedirectResponse(access_url(folder), status_code=303, headers=HEADERS)
        response.set_cookie(COOKIE,sign_session(account,secret()),secure=secure_cookie,httponly=True,samesite="lax",
                            max_age=SESSION_AGE,path="/")
        return response

    @router.post("/access/{folder}/login")
    async def login(request: Request, folder: str):
        if folder not in folders(static_dir):
            return Response(status_code=404)
        form = await request.form()
        if not valid_public_form(request,form):
            return rejected_public_form(request, folder)
        email, password = str(form.get("email","")).strip().lower(),str(form.get("password",""))
        key="priv:"+email
        ip=request.client.host if request.client else "unknown"
        if login_blocked(ip,key):
            return Response("Too many attempts", status_code=429, headers={**HEADERS,"Retry-After":"900"})
        with db() as conn:
            account=conn.execute("SELECT * FROM privilege_accounts WHERE email=?", (email,)).fetchone()
        if not account or not verify_privilege_password(password, account["password_salt"], account["password_hash"], password_verify):
            login_failed(ip,key)
            return page(request,folder,"Invalid credentials.")
        login_succeeded(ip,key)
        response=RedirectResponse(access_url(folder,str(form.get("next",""))),status_code=303,headers=HEADERS)
        response.set_cookie(COOKIE,sign_session(account,secret()),secure=secure_cookie,httponly=True,samesite="lax",
                            max_age=SESSION_AGE,path="/")
        return response

    @router.post("/access/{folder}/request")
    async def request_access(request:Request,folder:str):
        if folder not in folders(static_dir):
            return Response(status_code=404)
        form=await request.form()
        if not valid_public_form(request,form):
            return rejected_public_form(request, folder)
        with db() as conn:
            account=current_account(request,conn,secret())
            if not account:return Response(status_code=401)
            if not private_folder(conn,folder):return Response(status_code=409)
            existing=conn.execute("SELECT status FROM privilege_requests WHERE account_id=? AND folder=?",
                                  (account["id"],folder)).fetchone()
            if not existing:
                conn.execute("INSERT INTO privilege_requests VALUES(?,?,'pending',?,?)",
                             (account["id"],folder,now(),now()))
        return RedirectResponse(access_url(folder),status_code=303,headers=HEADERS)

    @router.post("/access/logout")
    async def logout(request:Request):
        form=await request.form()
        if not valid_public_form(request,form):return Response(status_code=403)
        response=RedirectResponse("/",status_code=303,headers=HEADERS)
        response.delete_cookie(COOKIE,path="/")
        return response

    @router.get("/admin/privileges")
    async def admin_list(request:Request):
        admin=admin_account(request)
        if not admin or admin["role"]!="admin":return Response(status_code=403)
        # Dedicated template, data kept separate and escaped by Jinja.
        with db() as conn:
            modes={r["folder"]:bool(r["is_private"]) for r in conn.execute("SELECT * FROM privilege_directories")}
            rows=[dict(r) for r in conn.execute("""SELECT r.folder,r.status,r.account_id,a.first_name,a.last_name,a.email,r.updated_at
                  FROM privilege_requests r JOIN privilege_accounts a ON a.id=r.account_id ORDER BY r.updated_at DESC""")]
        return render_admin(request,"admin/privileges.html","Privileges",{
            "active_admin":"privileges","directories":[
                {"name":name,"private":modes.get(name,False),
                 "requests":[r for r in rows if r["folder"]==name]}
                for name in folders(static_dir)],
            "settings_token":admin_token(request,admin["username"]),
            "proxy_confirmed":os.getenv("PRIVILEGES_STATIC_PROXY_CONFIRMED","0")=="1",
        },admin["username"])

    def admin_action(request, token):
        admin=admin_account(request)
        if not admin or admin["role"]!="admin":return False
        return hmac.compare_digest(str(token),admin_token(request,admin["username"]))

    @router.post("/admin/privileges/{folder}/mode")
    async def toggle(request:Request,folder:str):
        if folder not in folders(static_dir):return Response(status_code=404)
        form=await request.form()
        if not admin_action(request,form.get("settings_token","")):return Response(status_code=403)
        mode=str(form.get("mode",""))
        if mode not in ("public","private"):return Response(status_code=400)
        if mode=="private" and os.getenv("PRIVILEGES_STATIC_PROXY_CONFIRMED","0")!="1":
            return Response("Private mode requires PRIVILEGES_STATIC_PROXY_CONFIRMED=1 after verifying the reverse proxy.",status_code=409)
        with db() as conn:
            previous=private_folder(conn, folder)
            conn.execute("""INSERT INTO privilege_directories(folder,is_private,updated_at) VALUES(?,?,?)
                 ON CONFLICT(folder) DO UPDATE SET is_private=excluded.is_private,updated_at=excluded.updated_at""",
                 (folder,int(mode=="private"),now()))
            # Switching Public -> Private never silently restores older grants.
            if mode=="private" and not previous:
                conn.execute("UPDATE privilege_requests SET status='pending',updated_at=? WHERE folder=? AND status='approved'",
                             (now(),folder))
            admin=admin_account(request)
            conn.execute("INSERT INTO privilege_audit(actor,action,folder,account_id,created_at) VALUES(?,?,?,NULL,?)",
                         (admin["username"],"mode:"+mode,folder,now()))
        return RedirectResponse("/admin/privileges",status_code=303)

    @router.post("/admin/privileges/{folder}/{account_id}/{action}")
    async def review(request:Request,folder:str,account_id:int,action:str):
        if folder not in folders(static_dir) or action not in ("approve","deny","revoke","reset"):
            return Response(status_code=404)
        form=await request.form()
        if not admin_action(request,form.get("settings_token","")):return Response(status_code=403)
        with db() as conn:
            row=conn.execute("SELECT 1 FROM privilege_requests WHERE folder=? AND account_id=?",
                             (folder,account_id)).fetchone()
            if not row:return Response(status_code=404)
            if action=="reset":
                password=str(form.get("password",""))
                if not 12<=len(password)<=128:return Response("Password must have 12–128 characters",status_code=400)
                salt,digest=password_hash(password)
                conn.execute("""UPDATE privilege_accounts SET password_salt=?,password_hash=?,
                  session_version=session_version+1 WHERE id=?""",(salt,digest,account_id))
            else:
                conn.execute("UPDATE privilege_requests SET status=?,updated_at=? WHERE folder=? AND account_id=?",
                             ({"approve":"approved","deny":"denied","revoke":"revoked"}[action],now(),folder,account_id))
                if action in ("deny","revoke"):
                    # Invalidate all previously issued signed privilege cookies.
                    conn.execute("UPDATE privilege_accounts SET session_version=session_version+1 WHERE id=?",(account_id,))
            admin=admin_account(request)
            conn.execute("INSERT INTO privilege_audit(actor,action,folder,account_id,created_at) VALUES(?,?,?,?,?)",
                         (admin["username"],action,folder,account_id,now()))
        return RedirectResponse("/admin/privileges",status_code=303)

    return router
