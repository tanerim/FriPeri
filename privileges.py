"""Directory-scoped public/static privileges, isolated from CMS administrator accounts.

IMPORTANT: Reverse proxies must forward *all* /static/ requests to the FastAPI
application. An nginx 'alias' / 'root' shortcut bypasses this authorization.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import stat
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

logger = logging.getLogger("friperi.privileges")
COOKIE = "friperi_privilege_session"
CSRF_COOKIE = "friperi_privilege_csrf"
SESSION_AGE = 7 * 24 * 3600
HEADERS = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
           "X-Content-Type-Options": "nosniff"}
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
EXCLUDED_FOLDERS = frozenset({"images", "uploads"})
FOLDER_RE = re.compile(r"^[^/\\\\\x00-\x1f]{1,120}$")


def install_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS privilege_directories(
        folder TEXT PRIMARY KEY, is_private INTEGER NOT NULL DEFAULT 0
        CHECK(is_private IN (0,1)), updated_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS privilege_external_mappings(
        id INTEGER PRIMARY KEY, folder TEXT NOT NULL, relative_path TEXT NOT NULL,
        target_path TEXT NOT NULL, allowed_extensions TEXT NOT NULL DEFAULT '',
        enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(folder,relative_path)
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
                   and p.name.casefold() not in EXCLUDED_FOLDERS
                   and FOLDER_RE.fullmatch(p.name)), key=str.casefold)


def private_folder(conn, folder: str) -> bool:
    if folder.casefold() in EXCLUDED_FOLDERS:
        return False
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

    def lookup_path(self, path: str):
        parts = Path(path).parts
        if (len(parts) < 2 or Path(path).is_absolute() or "\\" in path
                or any(x in ("", ".", "..") for x in parts)):
            return super().lookup_path(path)
        try:
            with self._db() as conn:
                mappings = [dict(r) for r in conn.execute(
                    "SELECT * FROM privilege_external_mappings WHERE folder=?", (parts[0],))]
        except sqlite3.OperationalError:
            return super().lookup_path(path)
        for mapping in sorted(mappings, key=lambda r: len(r["relative_path"]), reverse=True):
            prefix = (mapping["folder"], *mapping["relative_path"].split("/"))
            if parts[:len(prefix)] != prefix:
                continue
            if not mapping["enabled"] or len(parts) <= len(prefix):
                return "", None
            try:
                trusted = Path(mapping["target_path"])
                if not trusted.is_absolute() or trusted.resolve() != trusted or not trusted.is_dir():
                    return "", None
                link = Path(self.directory).joinpath(*prefix)
                if any(Path(self.directory).joinpath(*prefix[:i]).is_symlink()
                       for i in range(1, len(prefix))):
                    return "", None
                if not link.is_symlink() or link.resolve() != trusted:
                    return "", None
                relative = parts[len(prefix):]
                if any(trusted.joinpath(*relative[:i]).is_symlink()
                       for i in range(1, len(relative)+1)):
                    return "", None
                resolved = trusted.joinpath(*relative).resolve()
                if not resolved.is_relative_to(trusted):
                    return "", None
                extensions = mapping["allowed_extensions"].split(",")
                if mapping["allowed_extensions"] and resolved.suffix.lower().lstrip(".") not in extensions:
                    return "", None
                info = resolved.stat()
                if stat.S_ISREG(info.st_mode):
                    return str(resolved), info
            except (OSError, RuntimeError, ValueError):
                pass
            return "", None
        return super().lookup_path(path)

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
                  password_hash, password_verify, admin_account, admin_token, now, render_admin, site_name=None):
    router = APIRouter()

    def csrf_token():
        # Stateless, tamper-evident form token: no dependency on the browser
        # returning a cookie through a reverse proxy or privacy extension.
        expiry = int(time.time()) + 3600
        nonce = secrets.token_hex(16)
        payload = f"{expiry}:{nonce}"
        signature = hmac.new(secret().encode(),
                             ("privilege-csrf:" + payload).encode(),
                             hashlib.sha256).hexdigest()
        return f"{payload}:{signature}"

    def csrf_page(request: Request, content: str, status=200):
        token = csrf_token()
        # A fresh token is embedded directly in the HTML form. Private pages
        # are no-store. An old double-submit cookie is not required.
        return HTMLResponse(content.replace("{{CSRF}}", token),
                            status_code=status, headers=HEADERS)

    def valid_public_form(request, form):
        # Never log passwords, session cookies, or CSRF tokens.
        def reject(reason):
            logger.warning("Privilege form rejected: reason=%s path=%s host=%r origin=%r fetch_site=%r",
                           reason, request.url.path,
                           request.headers.get("host", ""),
                           request.headers.get("origin", ""),
                           request.headers.get("sec-fetch-site", ""))
            return False

        if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
            return reject("cross_site")
        origin = request.headers.get("origin", "")
        fetch_site = request.headers.get("sec-fetch-site", "").lower()
        # Privacy-focused browsers may send Origin: null even for a
        # same-origin form submission. Accept this only when Fetch Metadata
        # explicitly confirms same-origin; the signed CSRF token below is
        # still mandatory. Never accept null for cross-site or unknown context.
        if origin == "null":
            if fetch_site != "same-origin":
                return reject("opaque_origin_not_same_origin")
        elif origin:
            parsed = urlsplit(origin)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                return reject("invalid_origin")
            host = request.headers.get("host", "").lower().rstrip(".")
            configured = os.getenv("FRIPERI_PUBLIC_ORIGIN", "").strip()
            allowed_hosts = {host} if host else set()
            if configured:
                configured_url = urlsplit(configured)
                if configured_url.scheme not in ("http", "https") or not configured_url.netloc:
                    return reject("invalid_public_origin_config")
                # Explicitly configured public origin is trusted. Do not trust
                # client-controlled X-Forwarded-Host without proxy validation.
                allowed_hosts.add(configured_url.netloc.lower().rstrip("."))
            if parsed.netloc.lower().rstrip(".") not in allowed_hosts:
                return reject("origin_host_mismatch")
        supplied = str(form.get("csrf", ""))
        parts = supplied.split(":")
        if len(parts) != 3:
            return reject("missing_or_malformed_csrf")
        expiry, nonce, signature = parts
        if (not expiry.isdecimal() or not re.fullmatch(r"[0-9a-f]{32}", nonce)
                or not re.fullmatch(r"[0-9a-f]{64}", signature)):
            return reject("invalid_csrf_format")
        now_time = int(time.time())
        if not now_time <= int(expiry) <= now_time + 3600:
            return reject("expired_or_future_csrf")
        payload = f"{expiry}:{nonce}"
        expected = hmac.new(secret().encode(),
                            ("privilege-csrf:" + payload).encode(),
                            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return reject("csrf_signature_mismatch")
        return True

    def rejected_public_form(request, folder):
        # Keep CSRF protection while explaining the recovery action.
        body = ('<p role="alert">Your form could not be verified. Please '
                'reload the access page and submit it again.</p>'
                f'<p><a href="{access_url(folder)}">Return to access page</a></p>')
        return csrf_page(request, shell("Form verification failed", folder, body), status=403)

    def shell(title, folder, body, next_path=""):
        from html import escape as e
        # The brand comes from the CMS settings, not a separate access label.
        brand = str(site_name() if site_name else "FriPeri").strip() or "FriPeri"
        return ("""<!doctype html><html lang="en"><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <meta name="robots" content="noindex,nofollow"><title>""" + e(title) + " · " + e(brand) + """</title>
        <style>
        :root{color-scheme:light;--navy:#182749;--blue:#2449bf;--sky:#e7f2fc;--line:#dbe4f1}
        *{box-sizing:border-box}
        body{margin:0;min-height:100vh;display:grid;place-items:center;padding:26px;
             background:#eaf2fa;font:15px/1.5 system-ui,-apple-system,sans-serif;color:var(--navy)}
        main{width:min(920px,100%);display:grid;grid-template-columns:minmax(0,.86fr) minmax(0,1fr);
             min-height:550px;background:#fff;border-radius:22px;overflow:hidden;
             box-shadow:0 24px 70px rgba(19,41,76,.12);border:1px solid #d6e1ef}
        .visual{background:linear-gradient(150deg,#203d9e,#2d64d5 65%,#77b4ee);color:#fff;
                padding:45px 38px;display:flex;flex-direction:column;position:relative;overflow:hidden}
        .visual:before,.visual:after{content:"";position:absolute;border:1px solid #ffffff35;
                border-radius:50%;width:430px;height:430px;right:-210px;top:90px;pointer-events:none}
        .visual:after{width:310px;height:310px;right:-130px;top:165px;background:#ffffff0d}
        .visual-brand{position:relative;z-index:1;font-weight:800;font-size:20px;letter-spacing:-.03em}
        .visual-content{position:relative;z-index:1;margin:auto 0}
        .visual-content h2{font-size:clamp(30px,3.5vw,46px);line-height:1.1;letter-spacing:-.045em;
                           margin:0 0 18px;font-weight:800}
        .visual-content p{margin:0;color:#e3edff;max-width:290px;line-height:1.7}
        .visual-bottom{position:relative;z-index:1;font-size:12px;color:#dae6ff}
        .auth{padding:clamp(26px,4vw,58px);display:flex;flex-direction:column;justify-content:center;min-width:0}
        .eyebrow{font-size:11px;letter-spacing:.13em;text-transform:uppercase;font-weight:800;color:#3156ba;margin:0 0 12px}
        h1{font-size:clamp(26px,3vw,34px);line-height:1.18;letter-spacing:-.035em;margin:0 0 9px}
        .subtitle{color:#697991;font-size:14px;line-height:1.6;margin:0 0 26px}
        label{display:grid;gap:7px;font-size:13px;font-weight:650;color:#324360;margin:0 0 17px}
        input{min-height:47px;padding:11px 13px;width:100%;border:1px solid #cbd7e7;border-radius:9px;
              font:inherit;background:#fbfdff;color:#162746}
        input:focus-visible,button:focus-visible,summary:focus-visible{outline:3px solid #9abafb;outline-offset:2px}
        input:focus{border-color:#4c74d4}
        button{border:0;background:var(--blue);color:#fff;width:100%;min-height:48px;border-radius:9px;
               padding:12px;font:inherit;font-weight:700;cursor:pointer;transition:background .15s}
        button:hover{background:#183b9f}
        .register{margin-top:22px;padding-top:20px;border-top:1px solid var(--line)}
        .register summary{list-style:none;cursor:pointer;color:#3154b5;font-weight:700;text-align:center;font-size:13px}
        .register summary::-webkit-details-marker{display:none}
        .register .register-open{display:none}
        .register[open] .register-closed{display:none}
        .register[open] .register-open{display:inline}
        .register[open]{border-top:0;margin-top:0;padding-top:0}
        .register[open] summary{margin-top:16px;order:2}
        .register[open]{display:flex;flex-direction:column}
        .register[open] form{order:1}
        .login-panel:has(+.register[open]){display:none}
        .auth:has(.register[open])>.auth-heading{display:none}
        .register[open]:before{content:"Create an account";font-size:30px;letter-spacing:-.035em;
                              font-weight:800;line-height:1.25;margin-bottom:22px}
        .name-fields{display:grid;grid-template-columns:1fr 1fr;gap:12px}
        .helper{color:#6b7b92;font-size:12px;margin:0 0 16px}
        [role=alert]{background:#fff1f2;border-left:3px solid #c84152;color:#8d3041;
                     border-radius:6px;padding:12px 14px;font-size:13px}
        .auth-status{color:#536785;line-height:1.65}
        @media(max-width:690px){
          body{padding:14px}main{grid-template-columns:1fr;min-height:0;border-radius:16px}
          .visual{padding:25px 26px;min-height:150px}
          .visual-content{margin:22px 0 0}.visual-content h2{font-size:25px;margin-bottom:6px}
          .visual-content p{font-size:12px}.visual-bottom{display:none}
          .auth{padding:30px 25px 35px}.name-fields{grid-template-columns:1fr}
        }
        @media(prefers-reduced-motion:reduce){button{transition:none}}
        </style></head><body><main>
        <aside class="visual" aria-label="Site access">
          <div class="visual-brand">""" + e(brand) + """</div>
          <div class="visual-content"><h2>Private access.<br>Simply managed.</h2>
          <p>Sign in to access protected content, or request an account for administrator review.</p></div>
          <div class="visual-bottom">Secure access portal</div>
        </aside>
        <section class="auth"><div class="auth-heading"><p class="eyebrow">""" +
        e(brand) + """ · Controlled Access</p><h1>""" + e(title) +
        """</h1><p class="subtitle">Use your account to continue securely.</p></div>""" +
        body + """</section></main></body></html>""")

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
                form = (f'<p class="auth-status">Access status: <strong>{e(state)}</strong></p>'
                        f'<form method="post" action="/access/{quote(folder,safe="")}/request">'
                        '<input type="hidden" name="csrf" value="{{CSRF}}">'
                        '<button type="submit">Request access</button></form>' if not status else
                        f'<p>Your access status is <strong>{e(state)}</strong>. Contact the administrator if needed.</p>')
                form += ('<form method="post" action="/access/logout"><input type="hidden" name="csrf" value="{{CSRF}}">'
                         '<button type="submit">Sign out</button></form>')
                return csrf_page(request, shell("Access status", folder, form))
        next_input = f'<input type="hidden" name="next" value="{e(safe_target(next_path,folder))}">'
        login = (f'<div class="login-panel"><form method="post" action="/access/{quote(folder,safe="")}/login">'
                 '<label>Email<input name="email" type="email" required autocomplete="username"></label>'
                 '<label>Password<input name="password" type="password" required autocomplete="current-password"></label>'
                 + next_input + '<input type="hidden" name="csrf" value="{{CSRF}}"><button type="submit">Sign in</button></form></div>')
        register = (f'<details class="register"><summary><span class="register-closed">New user? Request access</span><span class="register-open">Already registered? Back to sign in</span></summary>'
                    f'<form method="post" action="/access/{quote(folder,safe="")}/register">'
                    '<div class="name-fields">'
                    '<label>First name<input name="first_name" required maxlength="80" autocomplete="given-name"></label>'
                    '<label>Last name<input name="last_name" required maxlength="80" autocomplete="family-name"></label>'
                    '</div>'
                    '<label>Email address<input name="email" type="email" required autocomplete="email"></label>'
                    '<label>Create password<input name="password" type="password" required minlength="12" maxlength="128" autocomplete="new-password"></label>'
                    '<p class="helper">Use 12–128 characters. Access is granted only after administrator approval.</p>'
                    '<input type="hidden" name="csrf" value="{{CSRF}}">'
                    '<button type="submit">Register and request access</button></form></details>')
        msg = f'<p role="alert">{e(error)}</p>' if error else ""
        return csrf_page(request, shell("Welcome back", folder, msg+login+register))

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
            mappings=[dict(r) for r in conn.execute("SELECT * FROM privilege_external_mappings ORDER BY relative_path")]
            modes={r["folder"]:bool(r["is_private"]) for r in conn.execute("SELECT * FROM privilege_directories")}
            rows=[dict(r) for r in conn.execute("""SELECT r.folder,r.status,r.account_id,a.first_name,a.last_name,a.email,r.updated_at
                  FROM privilege_requests r JOIN privilege_accounts a ON a.id=r.account_id ORDER BY r.updated_at DESC""")]
        return render_admin(request,"admin/privileges.html","Privileges",{
            "active_admin":"privileges","directories":[
                {"name":name,"private":modes.get(name,False),
                 "requests":[r for r in rows if r["folder"]==name],
                 "mappings":[r for r in mappings if r["folder"]==name]}
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

    @router.post("/admin/privileges/{folder}/mapping")
    async def mapping_action(request: Request, folder: str):
        if folder not in folders(static_dir):
            return Response(status_code=404)
        form = await request.form()
        if not admin_action(request, form.get("settings_token", "")):
            return Response(status_code=403)
        action = str(form.get("action", "save"))
        raw_id = str(form.get("mapping_id", ""))
        if raw_id and (not raw_id.isdecimal() or len(raw_id) > 18):
            return Response(status_code=400)
        mid = int(raw_id) if raw_id else None
        with db() as conn:
            old = conn.execute("SELECT * FROM privilege_external_mappings WHERE id=? AND folder=?",
                               (mid, folder)).fetchone() if mid is not None else None
            if mid is not None and old is None:
                return Response(status_code=404)
            if action in ("delete", "disable"):
                if old is None:
                    return Response(status_code=400)
                if action == "delete":
                    conn.execute("DELETE FROM privilege_external_mappings WHERE id=?", (mid,))
                else:
                    conn.execute("UPDATE privilege_external_mappings SET enabled=0,updated_at=? WHERE id=?", (now(),mid))
            elif action == "save":
                relative = str(form.get("relative_path", "")).strip()
                target = str(form.get("target_path", "")).strip()
                extensions = sorted(set(x.strip().lower().lstrip(".") for x in
                                        str(form.get("allowed_extensions", "")).split(",") if x.strip()))
                parts = relative.split("/")
                if (len(relative)>512 or not all(re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", x) for x in parts)
                        or not all(re.fullmatch(r"[a-z0-9]{1,16}", x) for x in extensions)
                        or len(target)>4096):
                    return Response("Invalid mapping path or extensions", status_code=400)
                try:
                    root = Path(target)
                    static_root = static_dir.resolve()
                    link = static_dir.joinpath(folder, *parts)
                    prefix = (folder, *parts)
                    if (not root.is_absolute() or root.resolve()!=root or not root.is_dir()
                            or root.is_relative_to(static_root) or static_root.is_relative_to(root)
                            or any(static_dir.joinpath(*prefix[:i]).is_symlink() for i in range(1,len(prefix)))
                            or not link.is_symlink() or link.resolve()!=root):
                        return Response("Mapping requires an existing symlink to the exact external directory", status_code=400)
                except (OSError, RuntimeError, ValueError):
                    return Response("Invalid external directory", status_code=400)
                for row in conn.execute("SELECT id,relative_path FROM privilege_external_mappings WHERE folder=?", (folder,)):
                    other = row["relative_path"]
                    if row["id"] != mid and (other==relative or other.startswith(relative+"/") or relative.startswith(other+"/")):
                        return Response("Overlapping mapping", status_code=409)
                values = (relative, str(root), ",".join(extensions), now())
                if old is None:
                    conn.execute("""INSERT INTO privilege_external_mappings
                        (folder,relative_path,target_path,allowed_extensions,created_at,updated_at)
                        VALUES(?,?,?,?,?,?)""", (folder,*values,now()))
                else:
                    conn.execute("""UPDATE privilege_external_mappings SET relative_path=?,target_path=?,
                        allowed_extensions=?,updated_at=?,enabled=1 WHERE id=?""", (*values,mid))
            else:
                return Response(status_code=400)
            conn.execute("INSERT INTO privilege_audit(actor,action,folder,account_id,created_at) VALUES(?,?,?,NULL,?)",
                         (admin_account(request)["username"],"mapping:"+action,folder,now()))
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
