from __future__ import annotations

import hashlib
import hmac
import html
import io
import json
import logging
import os
import re
import secrets
import shutil
import zipfile
import sqlite3
import tempfile
import time
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from PIL import Image
from image_uploads import ImageUploadError, store_image_upload
from localization import (LANGUAGES, TRANSLATIONS, LOCALIZED_SETTINGS, content_languages,
                          primary_language, secondary_language, localized_value, translate, detect_locale)
from language_migration import (backup_before_language_migration, migrate_languages,
                                insert_custom_menu, switch_secondary_content)

from dotenv import load_dotenv
from fastapi import FastAPI, Request, UploadFile, Form
from starlette.datastructures import UploadFile as StarletteUploadFile
from root_files import install_schema as install_root_file_schema, root_filename, safe_root_file, ROOT_FILE_TYPES
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse, FileResponse
from section_svg_design import render_svg
from custom_home import (validate_document, read_document, render_blocks, clean_html,
                         validate_appearance, SECTION_SVG_FIELDS, SECTION_SVG_FILENAME)
from navigation import menu_mapping, validate_parents, menu_tree
from category_design import parse_archive_design, validate_archive_design, archive_inline_styles
from color_templates import list_templates
from backup_security import (BackupError, MAX_UPLOAD_BYTES, create_backup as write_secure_backup,
                             restore_backup as restore_secure_backup, validate_backup, safe_backup_path)
from login_security import blocked as login_blocked, failed as login_failed, succeeded as login_succeeded
from documentation import list_documents, render_document
from privileges import (ProtectedStaticFiles, create_router, private_folder, allowed as privilege_allowed,
                        migrate_user_folders)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be set in environment or .env")
    return value


def project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


DB_PATH = project_path(os.getenv("SITE_DB_PATH", "db/site.db"))
STATIC_DIR = project_path(os.getenv("SITE_STATIC_DIR", "static"))
USER_FILES_DIR = project_path(os.getenv("SITE_USER_FILES_DIR", "user_files"))
ROOT_FILES_DIR = project_path(os.getenv("SITE_ROOT_FILES_DIR", "root_files"))
SITEMAP_PATH = STATIC_DIR / "sitemap.xml"
TEMPLATES_DIR = project_path(os.getenv("SITE_TEMPLATES_DIR", "templates"))
UPLOAD_DIR = project_path(os.getenv("SITE_UPLOAD_DIR", "static/uploads"))
SESSION_COOKIE = os.getenv("SESSION_COOKIE_NAME", "site_session")
LANG_COOKIE = os.getenv("LANG_COOKIE_NAME", "site_lang")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() in {"1", "true", "yes"}
SECRET_KEY = os.getenv("SITE_SECRET_KEY") or secrets.token_urlsafe(48)
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize an existing installation and load the persistent signing key."""
    init_db()
    if is_initialized(DB_PATH):
        with get_db() as conn:
            moved = migrate_user_folders(STATIC_DIR, USER_FILES_DIR, conn)
        if moved:
            logging.getLogger(__name__).info("Migrated Privileges directories to user_files: %s", moved)
    USER_FILES_DIR.mkdir(parents=True, exist_ok=True)
    ROOT_FILES_DIR.mkdir(parents=True, exist_ok=True)
    if is_initialized(DB_PATH):
        with get_db() as conn:
            install_root_file_schema(conn)
            # Legacy app-ads.txt is deliberately NOT auto-published.
    application.state.initialized = is_initialized(DB_PATH)
    refresh_secret()
    yield


app = FastAPI(
    title=os.getenv("SITE_NAME", "Personal Site"),
    description=os.getenv("SITE_DESCRIPTION", "Personal publishing system"),
    version="2.0.0",
    lifespan=lifespan,
)
@app.api_route("/static/images/friperi-section-{digest}.svg", methods=["GET", "HEAD"], include_in_schema=False)
async def section_svg(digest: str, request: Request) -> Response:
    # This special SVG route precedes the /static mount: enforce the same
    # folder-level permissions so /static/images never bypasses Privileges.
    private_images = False
    if DB_PATH.exists():
        try:
            with get_db() as conn:
                private_images = private_folder(conn, "images")
                if private_images and not privilege_allowed(
                    request, conn, "images", SECRET_KEY,
                    admin_check=lambda req: bool((actor(req) or {}).get("role") == "admin"),
                ):
                    return Response(status_code=403, headers={"Cache-Control": "no-store"})
        except sqlite3.Error:
            return Response(status_code=503, headers={"Cache-Control": "no-store"})
    filename = f"friperi-section-{digest}.svg"
    if not re.fullmatch(SECTION_SVG_FILENAME, filename):
        return Response(status_code=404)
    asset = STATIC_DIR / "images" / filename
    headers = {"Cache-Control": "private, no-store" if private_images else "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"}
    if asset.is_file():
        return FileResponse(asset, media_type="image/svg+xml", headers=headers)
    if not request.app.state.initialized:
        return Response(status_code=404)
    with get_db() as conn:
        row = conn.execute("SELECT value FROM site_settings WHERE key = ?", (f"section_svg:{filename}",)).fetchone()
    if row is None:
        return Response(status_code=404)
    svg = row["value"].encode("utf-8")
    headers["Content-Length"] = str(len(svg))
    return Response(svg if request.method == "GET" else b"", media_type="image/svg+xml", headers=headers)


@app.middleware("http")
async def branded_public_not_found(request: Request, call_next):
    """Replace browser-facing public 404 responses without changing their status."""
    response = await call_next(request)
    path = request.url.path
    accepts_html = "text/html" in request.headers.get("accept", "")
    if (response.status_code == 404 and request.method in {"GET", "HEAD"}
            and accepts_html
            and not path.startswith(("/admin", "/static", "/user_files", "/api", "/docs", "/redoc", "/openapi.json"))
            and path not in {"/sitemap.xml", "/app-ads.txt", "/robots.txt"}
            and response.headers.get("content-type", "").split(";")[0] != "application/json"):
        return FileResponse(TEMPLATES_DIR / "404.html", status_code=404,
                            media_type="text/html", headers={"Cache-Control": "no-store"})
    return response


# Serve system JS/CSS and media only; user application folders are never
# allowed through this mount, including before startup migration.
class SystemStaticFiles(StaticFiles):
    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        relative = path.split("/static/", 1)[-1] if path.startswith("/static/") else ""
        folder = relative.split("/", 1)[0]
        # Only CMS-owned public assets may reside under /static.
        # Privileges applications must be under /user_files, never served
        # through a stray folder accidentally left in static.
        if ("/" in relative and folder not in {"images", "uploads"}):
            response = Response(status_code=404)
            await response(scope, receive, send)
            return
        if ("/" not in relative and not relative.endswith((".js", ".css", ".xml"))):
            response = Response(status_code=404)
            await response(scope, receive, send)
            return
        if folder and DB_PATH.exists():
            try:
                with get_db() as conn:
                    controlled = (
                        conn.execute("SELECT 1 FROM privilege_directories WHERE folder=?", (folder,)).fetchone()
                        or conn.execute("SELECT 1 FROM privilege_requests WHERE folder=? LIMIT 1", (folder,)).fetchone()
                        or conn.execute("SELECT 1 FROM privilege_external_mappings WHERE folder=? LIMIT 1", (folder,)).fetchone()
                    )
            except sqlite3.Error:
                response = Response(status_code=503)
                await response(scope, receive, send)
                return
            if controlled:
                response = Response(status_code=404)
                await response(scope, receive, send)
                return
        return await super().__call__(scope, receive, send)


app.mount("/static", SystemStaticFiles(directory=STATIC_DIR), name="static")
app.mount("/user_files", ProtectedStaticFiles(
    directory=USER_FILES_DIR, db=lambda: get_db(), secret=lambda: SECRET_KEY,
    admin_check=lambda request: bool((actor(request) or {}).get("role") == "admin"),
    first_run=lambda: not DB_PATH.exists(), mount_prefix="/user_files",
), name="user_files")

@app.middleware("http")
async def legacy_privilege_urls(request: Request, call_next):
    path = request.url.path
    if path.startswith("/static/"):
        parts = path[len("/static/"):].split("/", 1)
        # Only migrate registered Privileges names. Otherwise the public
        # static assets (and their URL space) remain owned by the CMS.
        try:
            with get_db() as conn:
                old_folders = {r[0] for r in conn.execute("SELECT folder FROM privilege_directories")}
                old_folders.update(r[0] for r in conn.execute("SELECT DISTINCT folder FROM privilege_requests"))
                old_folders.update(r[0] for r in conn.execute("SELECT DISTINCT folder FROM privilege_external_mappings"))
        except sqlite3.Error:
            old_folders = set()
        if len(parts) == 2 and parts[0] in old_folders:
            url = "/user_files/" + parts[0] + "/" + parts[1]
            if request.url.query:
                url += "?" + request.url.query
            return RedirectResponse(url, status_code=307, headers={"Cache-Control": "no-store"})
    return await call_next(request)


@app.api_route("/sitemap.xml", methods=["GET", "HEAD"], include_in_schema=False)
async def sitemap(request: Request) -> Response:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM site_settings WHERE key = 'sitemap_xml'").fetchone()
    if row is not None:
        xml = row["value"].encode("utf-8")
        return Response(
            xml if request.method == "GET" else b"",
            media_type="application/xml",
            headers={"Content-Length": str(len(xml))},
        )
    if not SITEMAP_PATH.is_file():
        return Response(status_code=404)
    return FileResponse(SITEMAP_PATH, media_type="application/xml")

templates = Jinja2Templates(directory=TEMPLATES_DIR)


def static_url(path: str) -> str:
    target = STATIC_DIR / path.lstrip("/")
    try:
        mtime = int(target.stat().st_mtime)
        return f"/static/{path.lstrip('/')}?v={mtime}"
    except OSError:
        return f"/static/{path.lstrip('/')}"


from site_defaults import DEFAULT_SITE_SETTINGS, SOCIAL_PLATFORMS


def valid_url(value: str, relative: bool = False) -> bool:
    if not value or re.search(r"[\s\x00-\x1f\x7f\\]", value):
        return False
    if relative and value.startswith("/"):
        return not value.startswith("//")
    try:
        parsed = urlsplit(value)
        return parsed.scheme.lower() in {"http", "https"} and bool(parsed.hostname) and parsed.port != 0
    except ValueError:
        return False


def t(lang: str, key: str) -> str:
    custom = {}
    if lang not in LANGUAGES:
        with get_db() as conn:
            custom = dict(conn.execute("SELECT translation_key, translation_value FROM ui_translations WHERE language_code=?", (lang,)).fetchall())
    return translate(lang, key, custom)


def get_site_settings(conn: sqlite3.Connection) -> dict[str, str]:
    settings = dict(DEFAULT_SITE_SETTINGS)
    try:
        rows = conn.execute("SELECT key, value FROM site_settings WHERE key != 'sitemap_xml' AND key NOT GLOB 'section_svg:*'").fetchall()
    except sqlite3.OperationalError:
        return settings
    settings.update({row["key"]: row["value"] for row in rows})
    return settings


def brand_initials(site_name: str) -> str:
    words = re.findall(r"[A-Za-z0-9ÇĞİÖŞÜçğıöşü]+", site_name)
    if not words:
        return "S"
    return "".join(word[0] for word in words[:2]).upper()


# ── CSRF helpers ──────────────────────────────────────────────────────────────
# Per-user secret derived from the session secret and username.
# The token is ``hmac(secret, rand)`` with a 4096-byte random nonce;
# this gives ~256 bits of entropy in the secret and 320 bits in the token —
# enough to prevent cross-site request forgery without storing state.

def _csrf_secret(username: str) -> str:
    """Derive a per-user HMAC key from the global secret and the session username.

    The user cannot guess another user's secret because they do not know the
    global ``SECRET_KEY``.  An attacker who controls the user's machine but not
    their network can forge a request, so the secret *must* be protected by the
    SameSite attribute on the session cookie — which we already set.
    """
    base = f"FriPeri-CSRF:{SECRET_KEY}:{username}"
    return hashlib.sha256(base.encode()).hexdigest()


def csrf_token(username: str) -> tuple[str, str]:
    """Generate a new CSRF token for *username* and return ``(raw, secret)``.

    *raw*  — ``<hex>:<signature>`` to put in a hidden form field; never
             sent as a cookie so it is safe to log/inspect in dev.
    *secret* — ``<hex>`` to set as a SameSite=strict cookie.  It is the
                HMAC key for this user and is never expected to be sent
                back by the client.
    """
    rand = secrets.token_bytes(32)
    secret = _csrf_secret(username).encode()
    signature = hmac.new(secret, rand, hashlib.sha256).hexdigest()
    return rand.hex() + ":" + signature, hashlib.sha256(rand).hexdigest()


def valid_csrf_token(raw: str, expected: str, username: str) -> bool:
    """Constant-time comparison of two CSRF tokens.

    *``raw``* is the ``csrf_token`` form field (or ``X-Request-Id`` header).
    *``expected``* is the ``csrf_secret`` cookie value set earlier.
    """
    if not raw or not expected or ":" not in raw:
        return False
    try:
        rand_hex, sig = raw.rsplit(":", 1)
    except ValueError:
        return False
    try:
        rand = bytes.fromhex(rand_hex)
    except ValueError:
        return False
    computed = hmac.new(_csrf_secret(username).encode(), rand, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, sig) and hmac.compare_digest(expected, _csrf_secret(username).encode())


def contact_token() -> str:
    timestamp = str(int(datetime.now(timezone.utc).timestamp()))
    signature = hmac.new(SECRET_KEY.encode(), timestamp.encode(), hashlib.sha256).hexdigest()
    return f"{timestamp}:{signature}"


def valid_contact_token(raw: str) -> bool:
    if not raw or ":" not in raw:
        return False
    timestamp, signature = raw.split(":", 1)
    if not timestamp.isdigit():
        return False
    expected = hmac.new(SECRET_KEY.encode(), timestamp.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False
    age = int(datetime.now(timezone.utc).timestamp()) - int(timestamp)
    return 0 <= age <= 60 * 60 * 2


def valid_email(value: str) -> bool:
    if "\n" in value or "\r" in value:
        return False
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value))


def slugify(value: str) -> str:
    mapping = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    normalized = value.translate(mapping).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return slug[:80] or secrets.token_hex(4)


def unique_slug(conn: sqlite3.Connection, table: str, title: str) -> str:
    base = slugify(title)
    slug = base
    index = 2
    while conn.execute(f"SELECT 1 FROM {table} WHERE slug = ?", (slug,)).fetchone():
        slug = f"{base}-{index}"
        index += 1
    return slug


from initialization import (connect_database, set_site_settings, hash_password, verify_password,
                            now_iso, migrate_database, is_initialized, initialize_database,
                            setup_defaults, validate_setup, SetupError)


def get_db():
    return connect_database(DB_PATH)


def init_db():
    """Upgrade an existing installation without creating a database or changing credentials."""
    if is_initialized(DB_PATH):
        migrate_database(DB_PATH)


def refresh_secret():
    global SECRET_KEY
    if is_initialized(DB_PATH):
        with get_db() as conn:
            row = conn.execute("SELECT value FROM site_settings WHERE key='session_secret'").fetchone()
        if row:
            SECRET_KEY = row[0]



SESSION_TOKEN_VERSION = "v2"
SESSION_TOKEN_VERSION_V3 = "v3"


def sign_session(username: str) -> str:
    now = str(int(datetime.now(timezone.utc).timestamp()))
    token = secrets.token_hex(32)  # 32 random bytes, 64-char hex
    payload = f"{username}:{now}"
    signature = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{SESSION_TOKEN_VERSION}:{payload}:{signature}:{token}"


def sign_session_v3(username: str, user_id: int) -> str:
    """Sign a session cookie, with nanosecond issuance time for revocation.

    Previous v3 cookies with second timestamps remain supported until invalidated.
    """
    now = str(time.time_ns())
    token = secrets.token_hex(32)
    payload = f"{user_id}:{username}:{now}"
    signature = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{SESSION_TOKEN_VERSION_V3}:{payload}:{signature}:{token}"


def _load_revoked_tokens(conn: sqlite3.Connection, limit: int = 100_000) -> set[str]:
    """Load revoked session tokens from the database. Falls back to empty set."""
    try:
        rows = list(conn.execute("SELECT token FROM revoked_session_tokens LIMIT ?", (limit,)).fetchall())
        return {row[0] for row in rows}
    except sqlite3.OperationalError:
        # Table doesn't exist yet (migration hasn't run); don't bypass validation.
        # Any session without a revocation record is considered valid by default
        # (no tokens have been revoked yet).
        return set()


def _is_token_revoked(conn: sqlite3.Connection, token: str) -> bool:
    """Check if a session token has been revoked."""
    revoked = _load_revoked_tokens(conn)
    if not revoked:
        return False
    return token in revoked


def verify_session_v3(raw: str) -> str | None:
    """Verify a v3 session cookie and check that the associated user still exists.

    Format (v3): ``v3:user_id:username:timestamp:signature:token``
    Rejects the session if (a) the signature/timestamp is invalid,
    (b) the user_id is no longer in the users table, or
    (c) the session token has been revoked.
    """
    if not raw or ":" not in raw:
        return None

    after_version = raw[len(SESSION_TOKEN_VERSION_V3) + 1:]
    parts = after_version.rsplit(":", 4)
    if len(parts) != 5:
        return None

    user_id_str, username, ts_str, signature, token = parts
    if not user_id_str or not username or not ts_str or not signature or not token:
        return None

    try:
        user_id = int(user_id_str)
    except ValueError:
        return None

    try:
        ts = int(ts_str)
    except ValueError:
        return None

    # Old v3 tokens used Unix seconds; new tokens use nanoseconds.
    issued_ns = ts if ts >= 10**15 else ts * 1_000_000_000
    max_age = 7 * 24 * 60 * 60
    age_seconds = datetime.now(timezone.utc).timestamp() - issued_ns / 1_000_000_000
    if age_seconds > max_age or age_seconds < -60:
        return None

    # Verify HMAC signature over <user_id>:<username>:<timestamp>
    expected_signature = hmac.new(SECRET_KEY.encode(), f"{user_id}:{username}:{ts_str}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    # --- Check that the user still exists (catches deletion) ---
    with get_db() as conn:
        exists = conn.execute("SELECT username, session_epoch FROM users WHERE id = ?", (user_id,)).fetchone()
        if not exists or exists["username"] != username or issued_ns <= exists["session_epoch"]:
            return None

        # --- Check token revocation ---
        if _is_token_revoked(conn, token):
            return None

    return username


def verify_session(raw: str) -> str | None:
    """Verify a signed session cookie.

    Accepted format (v3): ``v3:user_id:username:timestamp:signature:token``
    Accepted format (v2): ``v2:username:timestamp:signature:token``
    Accepted format (v1): ``username:timestamp:signature`` (legacy, still verified)
    Rejects malformed values and sessions older than 7 days.
    Sessions checked against the revocation table.
    """
    if not raw or ":" not in raw:
        return None

    # --- v3 format (preferred): v3:user_id:username:timestamp:signature:token ---
    if raw.startswith(SESSION_TOKEN_VERSION_V3 + ":"):
        return verify_session_v3(raw)

    # --- v2 format: v2:username:timestamp:signature:token ---
    if raw.startswith(SESSION_TOKEN_VERSION + ":"):
        after_version = raw[len(SESSION_TOKEN_VERSION) + 1:]
        parts = after_version.rsplit(":", 3)
        if len(parts) != 4:
            return None
        username, ts_str, signature, token = parts
        if not username or not ts_str or not signature or not token:
            return None
        try:
            ts = int(ts_str)
        except ValueError:
            return None
        max_age = 7 * 24 * 60 * 60
        if datetime.now(timezone.utc).timestamp() - ts > max_age:
            return None
        expected_signature = hmac.new(SECRET_KEY.encode(), f"{username}:{ts_str}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return None
        # Check revocation
        with get_db() as conn:
            if _is_token_revoked(conn, token):
                return None
            account = conn.execute("SELECT session_epoch FROM users WHERE username=?", (username,)).fetchone()
            if account is None or ts * 1_000_000_000 <= account["session_epoch"]:
                return None
        return username

    # --- v1 format: username:timestamp:signature (legacy, no token) ---
    parts = raw.rsplit(":", 2)
    if len(parts) != 3:
        return None
    username, ts_str, signature = parts
    if not username or not ts_str or not signature:
        return None
    try:
        ts = int(ts_str)
    except ValueError:
        return None
    max_age = 7 * 24 * 60 * 60
    if datetime.now(timezone.utc).timestamp() - ts > max_age:
        return None
    expected_signature = hmac.new(SECRET_KEY.encode(), f"{username}:{ts_str}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None
    with get_db() as conn:
        account = conn.execute("SELECT session_epoch FROM users WHERE username=?", (username,)).fetchone()
        if account is None or ts * 1_000_000_000 <= account["session_epoch"]:
            return None
    return username


def current_user(request: Request) -> str | None:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    return verify_session(raw)


def stale_language_form(request, form):
    if 'content_language_code' not in form:
        return None
    with get_db() as conn:
        current = secondary_language(get_site_settings(conn))
    if str(form['content_language_code']) != (current or {}).get('code', ''):
        return HTMLResponse(t(pick_lang(request), 'language.stale'), status_code=409)
    return None


def allowed_languages(settings):
    return {item['code'] for item in content_languages(settings)}


def pick_lang(request: Request) -> str:
    with get_db() as conn:
        allowed = allowed_languages(get_site_settings(conn))
    selected = request.query_params.get("lang", request.cookies.get(LANG_COOKIE, "en"))
    return selected if selected in allowed else "en"


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def format_date(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y")
    except ValueError:
        return value


def category_label(category, lang: str) -> str:
    return localized_value(category, "menu_label", lang) or category["name"]


def localize_post(post, lang):
    result = dict(post)
    for field in ("title", "excerpt", "body_html"):
        result[field] = localized_value(post, field, lang)
    if 'category_label_en' in result:
        result['category_name'] = ((result.get('category_label_secondary') if lang != 'en' else '')
                                   or result.get('category_label_en') or result.get('category_name'))
    return result


def fetch_categories(conn: sqlite3.Connection, menu_only: bool = False) -> list[sqlite3.Row]:
    where = "WHERE show_in_menu = 1" if menu_only else ""
    return conn.execute(
        f"SELECT * FROM categories {where} ORDER BY sort_order ASC, name ASC"
    ).fetchall()


def fetch_posts(conn: sqlite3.Connection, category_slug: str | None = None, limit: int | None = None) -> list[sqlite3.Row]:
    params: tuple[Any, ...] = ()
    where = "WHERE p.status = 'published'"
    if category_slug:
        where += " AND c.slug = ?"
        params = (category_slug,)
    return conn.execute(
        f"""
        SELECT p.*, c.name AS category_name, c.slug AS category_slug, c.menu_label_en AS category_label_en, c.menu_label_secondary AS category_label_secondary, u.username AS author_username
        FROM posts p
        LEFT JOIN categories c ON c.id = p.category_id
        LEFT JOIN users u ON u.id = p.author_id
        {where}
        ORDER BY datetime(p.created_at) DESC, p.id DESC
        LIMIT ?
        """,
        (*params, limit if limit is not None else -1),
    ).fetchall()


def category_card_settings(settings):
    try:
        raw = json.loads(settings.get('category_cards_json', '{}'))
    except (ValueError, TypeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    result = {}
    for slug, values in raw.items():
        if not isinstance(values, dict):
            continue
        clean = {key: values.get(key) is not False for key in ('show_date', 'show_title', 'show_excerpt')}
        for key in ('background', 'text_color'):
            value = values.get(key, '')
            clean[key] = value if isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', value) else ''
        result[slug] = clean
    return result


def prepare_custom_blocks(blocks, lang):
    result = render_blocks(blocks)
    with get_db() as conn:
        cards = category_card_settings(get_site_settings(conn))
        def prepare_categories(items):
            for index, block in enumerate(items):
                if block['type'] == 'section':
                    prepare_categories(block['children'])
                elif block['type'] == 'category':
                    rows = fetch_posts(conn, block['category'], block['count']) if block['category'] else []
                    items[index] = dict(block, posts=[localize_post(post, lang) for post in rows],
                                        post_tags=tags_by_post_ids(conn, [post['id'] for post in rows]),
                                        card_options=cards.get(block['category'], {}))
        prepare_categories(result)
    return result


def tags_for_post(conn: sqlite3.Connection, post_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT t.name FROM tags t
        JOIN post_tags pt ON pt.tag_id = t.id
        WHERE pt.post_id = ?
        ORDER BY t.name
        """,
        (post_id,),
    ).fetchall()
    return [row["name"] for row in rows]


def set_post_tags(conn: sqlite3.Connection, post_id: int, raw_tags: str) -> None:
    conn.execute("DELETE FROM post_tags WHERE post_id = ?", (post_id,))
    names = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
    for name in dict.fromkeys(names):
        slug = slugify(name)
        existing = conn.execute("SELECT id FROM tags WHERE slug = ?", (slug,)).fetchone()
        if existing:
            tag_id = existing["id"]
        else:
            cursor = conn.execute("INSERT INTO tags (name, slug) VALUES (?, ?)", (name, slug))
            tag_id = cursor.lastrowid
        conn.execute("INSERT OR IGNORE INTO post_tags (post_id, tag_id) VALUES (?, ?)", (post_id, tag_id))


async def save_upload(file: Any) -> str:
    """Return empty for an absent image; raise a typed error for invalid uploads."""
    return await store_image_upload(file, UPLOAD_DIR, prefix="post-")


def tags_by_post_ids(conn: sqlite3.Connection, post_ids: list[int]) -> dict[int, list[str]]:
    if not post_ids:
        return {}
    placeholders = ",".join("?" for _ in post_ids)
    rows = conn.execute(
        f"""
        SELECT pt.post_id, t.name
        FROM tags t
        JOIN post_tags pt ON pt.tag_id = t.id
        WHERE pt.post_id IN ({placeholders})
        ORDER BY t.name
        """,
        post_ids,
    ).fetchall()
    tags: dict[int, list[str]] = {post_id: [] for post_id in post_ids}
    for row in rows:
        tags.setdefault(row["post_id"], []).append(row["name"])
    return tags


def template_context(request: Request, title: str, user: str | None = None) -> dict[str, Any]:
    lang = pick_lang(request)
    with get_db() as conn:
        menu_categories = fetch_categories(conn, menu_only=True)
        site_settings = get_site_settings(conn)
        custom_ui = dict(conn.execute('SELECT translation_key, translation_value FROM ui_translations WHERE language_code=?', (lang,)).fetchall())
        menu_items = [dict(url=f"/category/{cat['slug']}", label=category_label(cat, lang),
                           sort_order=cat["sort_order"], new_tab=False, key=f"category-{cat['id']}")
                      for cat in menu_categories]
        for item in conn.execute("SELECT * FROM custom_menu_items WHERE show_in_menu = 1"):
            if not item["url"] or valid_url(item["url"], relative=True):
                menu_items.append(dict(url=item["url"], label=localized_value(item, "label", lang),
                                       sort_order=item["sort_order"], new_tab=item["new_tab"], key=f"custom-{item['id']}"))
        page_orders = menu_mapping(site_settings, 'menu_page_orders_json')
        for page in conn.execute('SELECT id, title, slug FROM custom_pages WHERE published=1 AND show_in_menu=1 ORDER BY id'):
            menu_items.append(dict(url=f"/pages/{page['slug']}", label=page['title'],
                                   sort_order=int(page_orders.get(str(page['id']), 100)), new_tab=False, key=f"page-{page['id']}"))
        for key, url, setting in [('about', '/about', 'show_about_link'), ('contact', '/contact', 'show_contact_link'),
                                  ('login', '/login', 'show_login_link')]:
            if site_settings.get(setting) == '1' and (key != 'login' or not user):
                menu_items.append(dict(url=url, label=translate(lang, 'nav.' + key, custom_ui),
                                       sort_order=1000, new_tab=False, key='builtin-' + key))
        groups = {f"custom-{row['id']}" for row in conn.execute('SELECT id FROM custom_menu_items')}
        menu_items = menu_tree(menu_items, menu_mapping(site_settings, 'menu_parents_json'), groups)
    site_name = site_settings["site_name"]
    design_vars = {key: site_settings[key] if re.fullmatch(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?", site_settings[key])
                   else DEFAULT_SITE_SETTINGS[key] for key in DESIGN_SETTING_KEYS}
    return {
        "request": request,
        "t": lambda language, key: translate(language, key, custom_ui if language == lang else None),
        "title": site_name if title == "Home" else f"{title} · {site_name}",
        "lang": lang,
        "languages": content_languages(site_settings),
        "primary_language": primary_language(site_settings),
        "secondary_language": secondary_language(site_settings),
        "localized": lambda values, field: localized_value(values, field, lang),
        "user": user,
        "account_role": (account["role"] if (account := actor(request)) else None),
        "menu_categories": menu_categories,
        "menu_items": menu_items,
        "social_platforms": SOCIAL_PLATFORMS,
        "site_settings": site_settings,
        "site_name": site_name,
        "site_initials": brand_initials(site_name),
        "site_description": site_settings["site_description"],
        "contact_email": site_settings["contact_email"],
        "design_vars": design_vars,
        "social_links": [dict(key=key, name=name, url=site_settings[f"social_{key}_url"])
                         for key, name in SOCIAL_PLATFORMS
                         if site_settings[f"social_{key}_visible"] == "1"
                         and valid_url(site_settings[f"social_{key}_url"])],
        "year_now": str(datetime.now(timezone.utc).year),
    }


def render_template(
    request: Request,
    template_name: str,
    title: str,
    context: dict[str, Any] | None = None,
    user: str | None = None,
    status_code: int = 200,
) -> Response:
    data = template_context(request, title, user)
    if context:
        data.update(context)
    if not request.url.path.startswith('/admin'):
        for key in ('posts', 'blog_posts', 'note_posts'):
            if key in data:
                data[key] = [localize_post(post, data['lang']) for post in data[key]]
    return templates.TemplateResponse(request, template_name, data, status_code=status_code)


def format_size(byte_count: int) -> str:
    """Return a human-readable file size string."""
    if byte_count < 0:
        return "0 B"
    if byte_count == 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    i = 0
    size = float(byte_count)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    # round to clean number
    if i == 0:
        return f"{int(size)} B"
    if size == int(size):
        return f"{int(size)} {units[i]}"
    return f"{size:.1f} {units[i]}"


templates.env.globals["t"] = t
templates.env.globals["static_url"] = static_url
templates.env.globals["format_size"] = format_size
templates.env.filters["format_date"] = format_date
templates.env.filters["category_label"] = category_label


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> Response:
    user = current_user(request)
    lang = pick_lang(request)
    with get_db() as conn:
        settings = get_site_settings(conn)
        custom_blocks = read_document(localized_value(settings, 'custom_home', lang))
        if settings.get('homepage_mode') == 'custom' and custom_blocks:
            return render_template(request, 'custom_home.html', 'Home', {
                'custom_blocks': prepare_custom_blocks(custom_blocks, lang),
            }, user)

        # 1. Featured content
        featured_post = None
        if settings.get("show_featured_post") == "1" and settings.get("featured_post_id"):
            try:
                featured_id = int(settings.get("featured_post_id", "0"))
                featured_row = conn.execute(
                    """
                    SELECT p.*, c.name AS category_name, c.slug AS category_slug,
                           c.menu_label_en AS category_label_en, c.menu_label_secondary AS category_label_secondary
                    FROM posts p
                    LEFT JOIN categories c ON c.id = p.category_id
                    WHERE p.id = ? AND p.status = 'published'
                    """,
                    (featured_id,),
                ).fetchone()
                if featured_row:
                    featured_post = localize_post(featured_row, lang)
            except Exception:
                featured_post = None

        # 2. Latest Writing (Blog)
        latest_writing_posts = []
        writing_cat_slug = settings.get("latest_writing_category", "blog").strip() or "blog"
        if settings.get("show_latest_writing", "1") == "1":
            try:
                count = int(settings.get("latest_writing_count", "4"))
            except ValueError:
                count = 4
            all_writing = fetch_posts(conn, writing_cat_slug)
            latest_writing_posts = [localize_post(p, lang) for p in all_writing[:count]]

        # 3. Latest Notes
        latest_notes_posts = []
        notes_cat_slug = settings.get("latest_notes_category", "notlar").strip() or "notlar"
        if settings.get("show_latest_notes", "1") == "1":
            try:
                count = int(settings.get("latest_notes_count", "5"))
            except ValueError:
                count = 5
            all_notes = fetch_posts(conn, notes_cat_slug)
            latest_notes_posts = [localize_post(p, lang) for p in all_notes[:count]]

        # 4. Optional Category Modules
        homepage_category_modules = []
        try:
            hp_cat_configs = json.loads(settings.get("homepage_categories_json", "[]"))
            if not isinstance(hp_cat_configs, list):
                hp_cat_configs = []
        except Exception:
            hp_cat_configs = []

        for conf in hp_cat_configs:
            if not isinstance(conf, dict) or conf.get("enabled") != "1":
                continue
            cat_id = conf.get("id")
            cat_row = conn.execute("SELECT * FROM categories WHERE id = ?", (cat_id,)).fetchone()
            if not cat_row:
                continue
            try:
                cat_count = int(conf.get("count", 3))
            except ValueError:
                cat_count = 3
            cat_posts = fetch_posts(conn, cat_row["slug"])
            if cat_posts or settings.get("show_empty_placeholders") == "1":
                homepage_category_modules.append({
                    "category": cat_row,
                    "title": category_label(cat_row, lang),
                    "slug": cat_row["slug"],
                    "posts": [localize_post(p, lang) for p in cat_posts[:cat_count]],
                })

        # Collect post IDs for tags
        all_post_ids = []
        if featured_post:
            all_post_ids.append(featured_post["id"])
        all_post_ids.extend(p["id"] for p in latest_writing_posts)
        all_post_ids.extend(p["id"] for p in latest_notes_posts)
        for mod in homepage_category_modules:
            all_post_ids.extend(p["id"] for p in mod["posts"])
        
        post_tags = tags_by_post_ids(conn, list(set(all_post_ids)))
        home_categories = fetch_categories(conn)

    return render_template(
        request,
        "home.html",
        "Home",
        {
            "settings": settings,
            "featured_post": featured_post,
            "latest_writing_posts": latest_writing_posts,
            "latest_writing_slug": writing_cat_slug,
            "latest_writing_title": next((category_label(c, lang) for c in home_categories if c['slug'] == writing_cat_slug), t(lang, 'home.latest_writing')),
            "latest_notes_posts": latest_notes_posts,
            "latest_notes_slug": notes_cat_slug,
            "latest_notes_title": next((category_label(c, lang) for c in home_categories if c['slug'] == notes_cat_slug), t(lang, 'home.latest_notes')),
            "show_latest_writing": settings.get('show_latest_writing') == '1',
            "show_latest_notes": settings.get('show_latest_notes') == '1',
            "homepage_category_modules": homepage_category_modules,
            "post_tags": post_tags,
            "show_feature_strip": settings.get("show_feature_strip", "1") == "1",
            "show_feature_blog": settings.get("show_feature_blog", "1") == "1",
            "show_feature_notes": settings.get("show_feature_notes", "1") == "1",
            "show_feature_contact": settings.get("show_feature_contact", "1") == "1",
            "feature_blog_desc": localized_value(settings, "feature_blog_desc", lang) or "Essays, articles, and long-form thoughts.",
            "feature_notes_desc": localized_value(settings, "feature_notes_desc", lang) or "Short observations, links, and ideas.",
            "feature_contact_desc": localized_value(settings, "feature_contact_desc", lang) or "Get in touch or start a conversation.",
            "homepage_layout": settings.get("homepage_layout", "editorial_split"),
            "show_empty_placeholders": settings.get("show_empty_placeholders", "0") == "1",
        },
        user,
    )


@app.head("/")
async def home_head() -> Response:
    return Response(status_code=200, media_type="text/html")


@app.get("/category/{slug}", response_class=HTMLResponse)
async def category_page(slug: str, request: Request) -> Response:
    with get_db() as conn:
        category = conn.execute("SELECT * FROM categories WHERE slug = ?", (slug,)).fetchone()
        card_options = category_card_settings(get_site_settings(conn)).get(slug, {})
        archive_design = parse_archive_design(category["archive_design_json"]) if category else parse_archive_design(None)
        posts = fetch_posts(conn, slug)
        post_tags = tags_by_post_ids(conn, [post["id"] for post in posts])
    if not category:
        return HTMLResponse(t(pick_lang(request), "common.not_found"), status_code=404)
    return render_template(
        request,
        "category.html",
        category_label(category, pick_lang(request)),
        {"category": category, "posts": posts, "post_tags": post_tags, "card_options": card_options,
         "archive_design": archive_design, "archive_style": archive_inline_styles(archive_design)},
        current_user(request),
    )


@app.get("/posts/{slug}", response_class=HTMLResponse)
async def post_detail(slug: str, request: Request) -> Response:
    with get_db() as conn:
        post = conn.execute(
            """
            SELECT p.*, c.name AS category_name, c.menu_label_en AS category_label_en, c.menu_label_secondary AS category_label_secondary
            FROM posts p LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.slug = ?
            """,
            (slug,),
        ).fetchone()
        tags = tags_for_post(conn, post["id"]) if post else []
    if not post:
        return HTMLResponse(t(pick_lang(request), "common.not_found"), status_code=404)
    user = current_user(request)
    if post["status"] != "published":
        account = actor(request)
        if not account or (account["role"] == "cc" and post["author_id"] != account["id"]):
            return HTMLResponse(t(pick_lang(request), "common.not_found"), status_code=404)
    with get_db() as conn:
        settings = get_site_settings(conn)
    docs = post_documents(dict(post), settings)
    languages = content_languages(settings)
    suffix = next((item['suffix'] for item in languages if item['code'] == pick_lang(request)), languages[0]['suffix'])
    stored = json.loads(post['post_blocks_json'] or '{}')
    blocks = docs[suffix]
    if not blocks and suffix != languages[0]['suffix']:
        blocks = docs[languages[0]['suffix']]
    custom_blocks = prepare_custom_blocks(blocks, pick_lang(request)) if stored else None
    post = localize_post(post, pick_lang(request))
    return render_template(
        request,
        "post_detail.html",
        post["title"],
        {"post": post, "tags": tags, "custom_blocks": custom_blocks, "body_html": clean_html(post["body_html"] or post["body"])},
        user,
    )


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request) -> Response:
    lang = pick_lang(request)
    with get_db() as conn:
        settings = get_site_settings(conn)
    blocks = read_document(localized_value(settings, 'about_page', lang))
    if settings.get('enable_about_page') == '1' or blocks:
        return render_template(request, 'custom_home.html', t(lang, 'nav.about'), {
            'custom_blocks': prepare_custom_blocks(blocks, lang),
        }, user=current_user(request))
    return render_template(request, "about.html", t(lang, "nav.about"), user=current_user(request))


def render_contact(request: Request, *, error="", values=None, status_code=200):
    lang = pick_lang(request)
    with get_db() as conn:
        settings = get_site_settings(conn)
    return render_template(request, "contact.html", t(lang, "nav.contact"), {
        "contact_intro": localized_value(settings, "contact_intro", lang),
        "contact_details": localized_value(settings, "contact_details", lang),
        "contact_form_token": contact_token(),
        "success": not error and request.query_params.get("sent") == "1",
        "error": error or request.query_params.get("error", ""),
        "values": values or {},
    }, user=current_user(request), status_code=status_code)


@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request) -> Response:
    return render_contact(request)


@app.post("/contact", response_class=HTMLResponse)
async def send_contact(request: Request) -> Response:
    form = await request.form()
    values = {key: str(form.get(key, "")).strip() for key in ("name", "email", "message")}
    if str(form.get("website", "")).strip():
        return RedirectResponse("/contact?sent=1", status_code=303)
    error = ""
    if not all(values.values()):
        error = "required"
    elif any(len(values[key]) > limit for key, limit in (("name", 120), ("email", 160), ("message", 4000))):
        error = "too_long"
    elif "\n" in values['name'] or "\r" in values['name'] or not valid_email(values['email']):
        error = "email"
    elif not valid_contact_token(str(form.get("contact_token", ""))):
        error = "token"
    if error:
        return render_contact(request, error=error, values=values, status_code=400)
    try:
        with get_db() as conn:
            # Silently discard submissions from blocked addresses. Do not expose
            # blocklist membership through the public contact endpoint.
            blocked = conn.execute(
                "SELECT 1 FROM blocked_contact_emails WHERE email = ?",
                (values['email'].casefold(),)
            ).fetchone()
            if blocked:
                return RedirectResponse("/contact?sent=1", status_code=303)
            conn.execute("INSERT INTO contact_messages (name, email, message, created_at) VALUES (?, ?, ?, ?)",
                         (values['name'], values['email'], values['message'], now_iso()))
    except sqlite3.Error:
        return render_contact(request, error="send", values=values, status_code=503)
    return RedirectResponse("/contact?sent=1", status_code=303)


@app.get('/admin/messages', response_class=HTMLResponse)
async def admin_messages(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse('/login', status_code=303)
    try:
        page = max(1, int(request.query_params.get('page', '1')))
    except ValueError:
        page = 1
    with get_db() as conn:
        total = conn.execute('SELECT COUNT(*) FROM contact_messages').fetchone()[0]
        pages = max(1, (total + 24) // 25)
        page = min(page, pages)
        messages = conn.execute('SELECT * FROM contact_messages ORDER BY id DESC LIMIT 25 OFFSET ?',
                                ((page - 1) * 25,)).fetchall()
        blocked_senders = conn.execute(
            'SELECT email, blocked_at FROM blocked_contact_emails ORDER BY blocked_at DESC'
        ).fetchall()
    response = render_template(request, 'admin/messages.html', t(pick_lang(request), 'admin.messages'), {
        'active_admin': 'messages', 'messages': messages, 'total': total, 'page': page, 'pages': pages,
        'blocked_senders': blocked_senders, 'message_token': custom_home_token(user),
        'can_manage_messages': (actor(request) or {}).get('role') == 'admin',
    }, user)
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.post('/admin/messages/{message_id}/delete', response_class=HTMLResponse)
async def delete_message(request: Request, message_id: int) -> Response:
    account = actor(request)
    if not account:
        return RedirectResponse('/login', status_code=303)
    if account['role'] != 'admin':
        return Response('Forbidden', status_code=403)
    form = await request.form()
    if not hmac.compare_digest(str(form.get('editor_token', '')), custom_home_token(account['username'])):
        return Response('Invalid token', status_code=403)
    with get_db() as conn:
        deleted = conn.execute('DELETE FROM contact_messages WHERE id=?', (message_id,))
        if not deleted.rowcount:
            return Response('Message not found', status_code=404)
    return RedirectResponse('/admin/messages?deleted=1', status_code=303)


@app.post('/admin/messages/{message_id}/spam', response_class=HTMLResponse)
async def spam_message(request: Request, message_id: int) -> Response:
    account = actor(request)
    if not account:
        return RedirectResponse('/login', status_code=303)
    if account['role'] != 'admin':
        return Response('Forbidden', status_code=403)
    form = await request.form()
    if not hmac.compare_digest(str(form.get('editor_token', '')), custom_home_token(account['username'])):
        return Response('Invalid token', status_code=403)
    with get_db() as conn:
        row = conn.execute('SELECT email FROM contact_messages WHERE id=?', (message_id,)).fetchone()
        if not row:
            return Response('Message not found', status_code=404)
        email = row['email'].strip().casefold()
        conn.execute('INSERT OR IGNORE INTO blocked_contact_emails(email, blocked_at) VALUES(?, ?)',
                     (email, now_iso()))
        conn.execute('DELETE FROM contact_messages WHERE lower(email)=?', (email,))
    return RedirectResponse('/admin/messages?spam=1', status_code=303)


@app.post('/admin/messages/unblock', response_class=HTMLResponse)
async def unblock_contact_sender(request: Request) -> Response:
    account = actor(request)
    if not account:
        return RedirectResponse('/login', status_code=303)
    if account['role'] != 'admin':
        return Response('Forbidden', status_code=403)
    form = await request.form()
    if not hmac.compare_digest(str(form.get('editor_token', '')), custom_home_token(account['username'])):
        return Response('Invalid token', status_code=403)
    email = str(form.get('email', '')).strip().casefold()
    if not valid_email(email):
        return Response('Invalid email', status_code=400)
    with get_db() as conn:
        conn.execute('DELETE FROM blocked_contact_emails WHERE email=?', (email,))
    return RedirectResponse('/admin/messages?unblocked=1', status_code=303)


# ===========================
# Backup & Restore
# ===========================

BACKUP_DIR = BASE_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)
PROJECT_ROOT = BASE_DIR


def _get_backups() -> list[dict]:
    """List regular archives (never follow symlinks)."""
    items = []
    for file in BACKUP_DIR.iterdir():
        if not file.is_file() or file.is_symlink() or file.suffix.lower() != ".zip":
            continue
        try:
            safe_backup_path(BACKUP_DIR, file.name)
            stat = file.stat()
            items.append({
                "name": file.name, "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
                "_ts": stat.st_mtime,
            })
        except (OSError, BackupError):
            continue
    items.sort(key=lambda item: item["_ts"], reverse=True)
    for item in items:
        item.pop("_ts", None)
    return items


def _backup_csrf_valid(request: Request, user: str, form: Any) -> bool:
    expected = settings_form_token(request, user)
    return hmac.compare_digest(str(form.get("backup_csrf", "")).encode(), expected.encode())


def _backup_redirect(message: str, successful: bool = False) -> Response:
    response = RedirectResponse("/admin/backup", status_code=303)
    response.set_cookie("flash", ("success:" if successful else "error:") + message,
                        max_age=5, httponly=True, samesite="lax", secure=SESSION_COOKIE_SECURE)
    return response


@app.get("/admin/backup", response_class=HTMLResponse)
async def admin_backup(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return render_template(request, "admin/backup.html", t(pick_lang(request), "admin.backup"), {
        "active_admin": "backup", "backups": _get_backups(),
        "backup_csrf": settings_form_token(request, user),
    }, user)


@app.post("/admin/backup/create")
async def backup_create(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    if not _backup_csrf_valid(request, user, form):
        return Response(status_code=403)
    lang = pick_lang(request)
    filename = "backup-" + datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S") + "-" + secrets.token_hex(4) + ".zip"
    path = safe_backup_path(BACKUP_DIR, filename)
    try:
        write_secure_backup(path, DB_PATH, STATIC_DIR, UPLOAD_DIR, BASE_DIR / ".env", ROOT_FILES_DIR)
        validate_backup(path)
    except (BackupError, OSError, sqlite3.Error, zipfile.BadZipFile):
        path.unlink(missing_ok=True)
        logging.getLogger(__name__).exception("Backup creation failed")
        return _backup_redirect(t(lang, "admin.backup_error"))
    return _backup_redirect(t(lang, "admin.backup_created"), True)


@app.post("/admin/backup/upload")
async def backup_upload(request: Request, file: UploadFile = Form(...)) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    if not _backup_csrf_valid(request, user, form):
        return Response(status_code=403)
    lang = pick_lang(request)
    if not (file.filename or "").lower().endswith(".zip"):
        return _backup_redirect(t(lang, "admin.backup_upload_error"))
    if file.content_type and file.content_type not in ("application/zip", "application/x-zip-compressed", "application/octet-stream"):
        return _backup_redirect(t(lang, "admin.backup_upload_error"))
    name = "upload-" + datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S") + "-" + secrets.token_hex(4) + ".zip"
    dest = safe_backup_path(BACKUP_DIR, name)
    try:
        size = 0
        fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise BackupError("Uploaded archive exceeds limit")
                output.write(chunk)
        validate_backup(dest)
    except (BackupError, OSError, zipfile.BadZipFile):
        dest.unlink(missing_ok=True)
        logging.getLogger(__name__).warning("Rejected backup upload", exc_info=True)
        return _backup_redirect(t(lang, "admin.backup_upload_error"))
    finally:
        await file.close()
    return _backup_redirect(t(lang, "admin.backup_upload_success"), True)


@app.post("/admin/backup/restore/{backup_name}")
async def backup_restore(request: Request, backup_name: str) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    if not _backup_csrf_valid(request, user, form):
        return Response(status_code=403)
    lang = pick_lang(request)
    try:
        path = safe_backup_path(BACKUP_DIR, backup_name)
        if not path.is_file():
            return _backup_redirect(t(lang, "admin.backup_not_found"))
        restore_secure_backup(path, DB_PATH, STATIC_DIR, UPLOAD_DIR, BASE_DIR / ".env", ROOT_FILES_DIR)
        refresh_secret()
    except (BackupError, OSError, sqlite3.Error, zipfile.BadZipFile):
        logging.getLogger(__name__).exception("Backup restore failed")
        return _backup_redirect(t(lang, "admin.backup_restore_error"))
    return _backup_redirect(t(lang, "admin.backup_restored"), True)


@app.get("/admin/backup/download/{backup_name}")
async def backup_download(request: Request, backup_name: str) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    try:
        path = safe_backup_path(BACKUP_DIR, backup_name)
    except BackupError:
        return Response(status_code=404)
    if not path.is_file():
        return Response(status_code=404)
    return FileResponse(path, media_type="application/zip", filename=backup_name,
                        headers={"Cache-Control": "no-store"})


@app.get("/set-language/{lang}")
async def set_language(lang: str, request: Request) -> Response:
    target = request.query_params.get("next", "/")
    response = RedirectResponse(target if target.startswith("/") and valid_url(target, relative=True) else "/", status_code=303)
    with get_db() as conn:
        allowed = allowed_languages(get_site_settings(conn))
    response.set_cookie(LANG_COOKIE, lang if lang in allowed else "en", max_age=60 * 60 * 24 * 365, samesite="lax")
    return response


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> Response:
    lang = pick_lang(request)
    return render_template(request, "login.html", t(lang, "nav.login"), {"error": ""})


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request) -> Response:
    lang = pick_lang(request)
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    client_address = request.client.host if request.client else "unknown"
    if login_blocked(client_address, username):
        return Response("Too many sign-in attempts. Try again later.", status_code=429,
                        headers={"Retry-After": "900", "Cache-Control": "no-store"})
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user or not verify_password(password, user["password_salt"], user["password_hash"]):
        login_failed(client_address, username)
        return render_template(
            request,
            "login.html",
            t(lang, "nav.login"),
            {"error": t(lang, "auth.bad_login")},
            status_code=401,
        )
    login_succeeded(client_address, username)
    # Send content-only accounts directly to their permitted workspace.
    destination = "/admin" if user["role"] == "admin" else "/admin/posts"
    response = RedirectResponse(destination, status_code=303)
    # Use v3 format: ties session to immutable user_id so deletion invalidates the session
    response.set_cookie(
        SESSION_COOKIE,
        sign_session_v3(username, user["id"]),
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )
    return response


@app.get("/logout")
async def logout(request: Request) -> Response:
    # Revoke the current session token (if present) before deleting.
    # Handles both v2 and v3 cookie formats.
    raw = request.cookies.get(SESSION_COOKIE)
    if raw and raw.startswith(SESSION_TOKEN_VERSION_V3 + ":"):
        # v3: v3:user_id:username:timestamp:signature:token
        after_version = raw[len(SESSION_TOKEN_VERSION_V3) + 1:]
        parts = after_version.rsplit(":", 4)
        if len(parts) == 5:
            _, _, _, _, token = parts
            if token:
                try:
                    with get_db() as conn:
                        conn.execute(
                            "INSERT OR IGNORE INTO revoked_session_tokens (token, revoked_at) VALUES (?, ?)",
                            (token, now_iso()),
                        )
                        conn.commit()
                except sqlite3.OperationalError:
                    # Migration hasn't created the table yet — cookie deletion is still safe.
                    pass
    elif raw and raw.startswith(SESSION_TOKEN_VERSION + ":"):
        # v2: v2:username:timestamp:signature:token
        after_version = raw[len(SESSION_TOKEN_VERSION) + 1:]
        parts = after_version.rsplit(":", 3)
        if len(parts) == 4:
            _, _, _, token = parts
            if token:
                try:
                    with get_db() as conn:
                        conn.execute(
                            "INSERT OR IGNORE INTO revoked_session_tokens (token, revoked_at) VALUES (?, ?)",
                            (token, now_iso()),
                        )
                        conn.commit()
                except sqlite3.OperationalError:
                    # Migration hasn't created the table yet — cookie deletion is still safe.
                    pass

    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/", secure=SESSION_COOKIE_SECURE)
    return response


def require_user(request: Request) -> str | None:
    return current_user(request)


def actor(request: Request) -> dict[str, Any] | None:
    username = current_user(request)
    if not username:
        return None
    with get_db() as conn:
        row = conn.execute("SELECT id, username, role FROM users WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None


def can_write_post(conn: sqlite3.Connection, account: dict, post_id: int) -> bool:
    if account["role"] in ("admin", "editor"):
        return True
    post = conn.execute("SELECT author_id FROM posts WHERE id=?", (post_id,)).fetchone()
    return bool(post and post["author_id"] == account["id"])


def allowed_category(conn: sqlite3.Connection, account: dict, raw: str) -> bool:
    category_id_valid = bool(re.fullmatch(r"[0-9]{1,18}", raw))
    if account["role"] != "cc":
        return not raw or (category_id_valid and conn.execute(
            "SELECT 1 FROM categories WHERE id=?", (int(raw),)).fetchone() is not None)
    return bool(category_id_valid and conn.execute(
        "SELECT 1 FROM user_categories WHERE user_id=? AND category_id=?",
        (account["id"], int(raw))).fetchone())


@app.middleware("http")
async def enforce_roles(request: Request, call_next):
    """Apply authorization to every admin route, including upload/preview APIs."""
    # Treat /admin/ and /admin/documentation/ like their canonical routes.
    path = request.url.path.rstrip("/") or "/"
    if not (path == "/admin" or path.startswith("/admin/")):
        return await call_next(request)
    account = actor(request)
    if account is None:
        return await call_next(request)  # Existing handlers redirect unauthenticated users.
    role = account["role"]
    if role == "admin":
        return await call_next(request)
    method = request.method
    allowed = path in ("/admin", "/admin/documentation") and method in ("GET", "HEAD")
    if path.startswith("/admin/posts"):
        allowed = method in ("GET", "HEAD", "POST") and not (
            role == "cc" and path.endswith("/delete"))
        match = re.fullmatch(r"/admin/posts/([0-9]{1,18})/(?:edit(?:/preview|/upload)?|delete)", path)
        if allowed and match and role == "cc":
            with get_db() as conn:
                allowed = can_write_post(conn, account, int(match.group(1)))
    elif path == "/admin/users" and role == "editor":
        allowed = method in ("GET", "HEAD")
    elif role == "editor" and re.fullmatch(r"/admin/users/[0-9]{1,18}/categories", path):
        allowed = method == "POST"
    elif path == "/admin/categories":
        allowed = method in ("GET", "HEAD", "POST")
    elif path.startswith("/admin/categories/"):
        allowed = role == "editor" and bool(
            re.fullmatch(r"/admin/categories/[0-9]{1,18}/(?:edit|delete)", path))
    elif role == "editor":
        # Preserve the dashboard/documentation permission granted above.
        allowed = allowed or (path == "/admin/pages" or path.startswith("/admin/pages/")
                   or path == "/admin/about" or path.startswith("/admin/about/")
                   or path == "/admin/custom-home" or path.startswith("/admin/custom-home/")
                   or path == "/admin/section-svg"
                   or (path == "/admin/homepage" and method in ("GET", "HEAD")))
    if not allowed:
        return Response("Forbidden: insufficient permissions", status_code=403)
    return await call_next(request)


@app.get("/admin/documentation", response_class=HTMLResponse)
async def admin_documentation(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    root = BASE_DIR / "docs"
    documents = list_documents(root)
    allowed = {document["name"] for document in documents}
    selected = request.query_params.get("file") or ("index.md" if "index.md" in allowed else next(iter(sorted(allowed)), ""))
    if selected and selected not in allowed:
        return Response(status_code=404)
    rendered = render_document(root, selected, allowed) if selected else ""
    title = next((item["title"] for item in documents if item["name"] == selected), "Documentation")
    return render_template(request, "admin/documentation.html", title, {
        "active_admin": "documentation",
        "documents": documents,
        "selected_document": selected,
        "document_html": rendered,
        "document_title": title,
    }, user=user)


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    lang = pick_lang(request)
    account = actor(request)
    with get_db() as conn:
        if account and account["role"] == "cc":
            counts = dict(conn.execute("""
                SELECT COUNT(*) AS total,
                       COUNT(CASE WHEN status = 'published' THEN 1 END) AS published,
                       COUNT(CASE WHEN status = 'draft' THEN 1 END) AS drafts
                FROM posts WHERE author_id=?
            """, (account["id"],)).fetchone())
            recent_posts = [localize_post(row, lang) for row in conn.execute("""
                SELECT p.*, c.name AS category_name, c.menu_label_en AS category_label_en,
                       c.menu_label_secondary AS category_label_secondary
                FROM posts p LEFT JOIN categories c ON c.id=p.category_id
                WHERE p.author_id=? ORDER BY datetime(p.created_at) DESC, p.id DESC LIMIT 6
            """, (account["id"],)).fetchall()]
            category_counts = [dict(row, label=category_label(row, lang)) for row in conn.execute("""
                SELECT c.*, COUNT(p.id) AS post_count
                FROM categories c
                JOIN user_categories uc ON uc.category_id=c.id AND uc.user_id=?
                LEFT JOIN posts p ON p.category_id=c.id AND p.author_id=?
                GROUP BY c.id ORDER BY post_count DESC, c.sort_order, c.name
            """, (account["id"], account["id"])).fetchall()]
            uncategorized_count = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE author_id=? AND category_id IS NULL",
                (account["id"],)).fetchone()[0]
        else:
            counts = dict(conn.execute("""
                SELECT COUNT(*) AS total,
                       COUNT(CASE WHEN status = 'published' THEN 1 END) AS published,
                       COUNT(CASE WHEN status = 'draft' THEN 1 END) AS drafts
                FROM posts
            """).fetchone())
            recent_posts = [localize_post(row, lang) for row in conn.execute("""
                SELECT p.*, c.name AS category_name, c.menu_label_en AS category_label_en,
                       c.menu_label_secondary AS category_label_secondary
                FROM posts p LEFT JOIN categories c ON c.id = p.category_id
                ORDER BY datetime(p.created_at) DESC, p.id DESC LIMIT 6
            """).fetchall()]
            category_counts = [dict(row, label=category_label(row, lang)) for row in conn.execute("""
                SELECT c.*, COUNT(p.id) AS post_count
                FROM categories c LEFT JOIN posts p ON p.category_id = c.id
                GROUP BY c.id ORDER BY post_count DESC, c.sort_order, c.name
            """).fetchall()]
            uncategorized_count = conn.execute("""
                SELECT COUNT(*) FROM posts p LEFT JOIN categories c ON c.id = p.category_id
                WHERE c.id IS NULL
            """).fetchone()[0]
    dashboard_extra = None
    if account and account["role"] == "admin":
        with get_db() as conn:
            dashboard_extra = {
                "published_pages": conn.execute("SELECT COUNT(*) FROM custom_pages WHERE published=1").fetchone()[0],
                "total_pages": conn.execute("SELECT COUNT(*) FROM custom_pages").fetchone()[0],
                "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
                "private_directories": conn.execute(
                    "SELECT COUNT(*) FROM privilege_directories WHERE is_private=1 AND lower(folder) NOT IN ('images','uploads')").fetchone()[0],
                "access_accounts": conn.execute("SELECT COUNT(*) FROM privilege_accounts").fetchone()[0],
                "pending_requests": conn.execute(
                    "SELECT COUNT(*) FROM privilege_requests WHERE status='pending'").fetchone()[0],
            }
    is_first_run = not counts.get('total') and not category_counts
    return render_template(request, "admin/index.html", t(lang, "dashboard.title"), {
        "active_admin": "admin", "counts": counts, "recent_posts": recent_posts,
        "category_counts": category_counts, "uncategorized_count": uncategorized_count,
        "dashboard_extra": dashboard_extra,
        "is_first_run": is_first_run,
    }, user=user)


def post_documents(post, settings):
    """Language-code keyed blocks; absence alone triggers lossless legacy wrapping.

    Reading an old post never writes it. First explicit save stores the wrapper
    alongside (not instead of) its original body columns.
    """
    stored = json.loads(post.get('post_blocks_json') or '{}')
    result = {}
    for index, language in enumerate(content_languages(settings)):
        code = language['code']
        if code in stored:
            result[language['suffix']] = validate_document(json.dumps(stored[code]))
        else:
            source = (post.get('body_html') or post.get('body', '')) if index == 0 else post.get('body_html_secondary', '')
            result[language['suffix']] = [{'type': 'legacy_html', 'html': source}] if source else []
    return result


async def save_block_post(request, form, post_id=None):
    lang = pick_lang(request)
    def error(message, code=400):
        return JSONResponse({'error': message}, status_code=code)
    if not custom_home_authorized(request, form):
        return error(t(lang, 'builder.session_error'), 403)
    if stale_language_form(request, form) is not None:
        return error(t(lang, 'language.stale'), 409)
    title = str(form.get('title_en', '')).strip()
    excerpt = str(form.get('excerpt_en', '')).strip()
    status = str(form.get('status', 'draft'))
    category = str(form.get('category_id', ''))
    creation_key = str(form.get('creation_key', ''))
    if not title or len(title) > 160 or len(excerpt) > 260 or status not in {'draft', 'published'}:
        return error(t(lang, 'builder.invalid'))
    if post_id is None and not re.fullmatch(r'[a-f0-9]{32}', creation_key):
        return error(t(lang, 'builder.invalid'))
    with get_db() as conn:
        account = actor(request)
        if account is None:
            return error("Sign in required", 401)
        # Serializes retries of a new editor session, including a lost response.
        conn.execute('BEGIN IMMEDIATE')
        if post_id is None:
            existing = conn.execute('SELECT id FROM posts WHERE editor_creation_key=?', (creation_key,)).fetchone()
            post_id = existing['id'] if existing else None
        post = conn.execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone() if post_id else None
        if post_id and post is None:
            return error(t(lang, 'common.not_found'), 404)
        if post and not can_write_post(conn, account, post['id']):
            return error("Forbidden", 403)
        if not allowed_category(conn, account, category):
            return error(t(lang, 'admin.category_invalid'), 403)
        settings = get_site_settings(conn)
        documents = json.loads(post['post_blocks_json'] or '{}') if post else {}
        try:
            for language in content_languages(settings):
                documents[language['code']] = validate_document(str(form['post_' + language['suffix']]))
            secondary = {key: str(form[key]).strip() for key in ('title_secondary', 'excerpt_secondary')
                         if key in form} if secondary_language(settings) else {}
            if any(len(value) > (160 if key.startswith('title') else 260) for key, value in secondary.items()):
                raise ValueError('Invalid metadata')
        except (ValueError, KeyError):
            return error(t(lang, 'builder.invalid'))
        image = form.get('image')
        try:
            image_path = await save_upload(image)
        except ImageUploadError as exc:
            return error(exc.message, exc.status_code)
        image_path = image_path or (post['image_path'] if post else '')
        if post:
            conn.execute('UPDATE posts SET title=?, excerpt=?, category_id=?, status=?, image_path=?, post_blocks_json=?, updated_at=? WHERE id=?',
                         (title, excerpt, int(category) if category else None, status, image_path, json.dumps(documents, ensure_ascii=False), now_iso(), post_id))
            slug = post['slug']
        else:
            slug = unique_slug(conn, 'posts', title)
            cursor = conn.execute("""INSERT INTO posts (title, slug, excerpt, body, body_html, category_id, status, image_path,
                                   post_blocks_json, editor_creation_key, created_at, updated_at, author_id)
                                   VALUES (?, ?, ?, '', '', ?, ?, ?, ?, ?, ?, ?, ?)""",
                                  (title, slug, excerpt, int(category) if category else None, status, image_path,
                                   json.dumps(documents, ensure_ascii=False), creation_key, now_iso(), now_iso(), account['id']))
            post_id = cursor.lastrowid
        save_secondary_post(conn, post_id, secondary)
        set_post_tags(conn, post_id, str(form.get('tags', '')))
    return JSONResponse({'message': t(lang, 'builder.ready'), 'url': '/posts/' + slug,
                         'endpoint': f'/admin/posts/{post_id}/edit', 'image_path': image_path})


def post_form_response(
    request: Request,
    user: str,
    values: dict[str, Any] | None = None,
    error: str = "",
    action: str = "/admin/posts/new",
    heading: str | None = None,
    status_code: int = 200,
) -> Response:
    lang = pick_lang(request)
    values = values or {}
    with get_db() as conn:
        account = actor(request)
        categories = fetch_categories(conn)
        if account and account["role"] == "cc":
            categories = [cat for cat in categories if conn.execute(
                "SELECT 1 FROM user_categories WHERE user_id=? AND category_id=?",
                (account["id"], cat["id"])).fetchone()]
        settings = get_site_settings(conn)
    return render_template(
        request,
        "admin/post_form.html",
        heading or t(lang, "admin.new_content"),
        {
            "values": values,
            "builder_page": "post", "builder_endpoint": action, "settings": settings,
            "documents": post_documents(values, settings),
            "builder_categories": [dict(category) for category in categories],
            "editor_token": custom_home_token(user),
            "creation_key": secrets.token_hex(16),
            "error": error,
            "action": action,
            "heading": heading or t(lang, "admin.new_content"),
            "categories": categories,
            "active_admin": "posts",
        },
        user,
        status_code=status_code,
    )


@app.get("/admin/posts", response_class=HTMLResponse)
async def admin_posts(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    lang = pick_lang(request)
    with get_db() as conn:
        account = actor(request)
        if account and account["role"] == "cc":
            posts = conn.execute(
                "SELECT p.*, c.name AS category_name FROM posts p LEFT JOIN categories c ON c.id=p.category_id WHERE p.author_id=? ORDER BY p.id DESC",
                (account["id"],)).fetchall()
        else:
            posts = conn.execute(
                "SELECT p.*, c.name AS category_name FROM posts p LEFT JOIN categories c ON c.id = p.category_id ORDER BY p.id DESC"
            ).fetchall()
    return render_template(request, "admin/posts.html", t(lang, "admin.new_content"), {"posts": posts, "active_admin": "posts"}, user)


@app.get("/admin/posts/new", response_class=HTMLResponse)
async def new_post_page(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return post_form_response(request, user)


def read_secondary_post(form):
    with get_db() as conn:
        enabled = secondary_language(get_site_settings(conn))
    if not enabled:
        return {}
    values = {field: str(form[field]).strip() for field in ('title_secondary', 'excerpt_secondary', 'body_html_secondary') if field in form}
    if 'body_html_secondary' in values:
        cleaned = clean_html(values['body_html_secondary'])
        values['body_html_secondary'] = cleaned if html.unescape(re.sub('<[^>]+>', '', cleaned)).strip() else ''
    return values


def save_secondary_post(conn, post_id, values):
    if values:
        conn.execute('UPDATE posts SET ' + ','.join(f'{field}=?' for field in values) + ' WHERE id=?', (*values.values(), post_id))


@app.post("/admin/posts/new", response_class=HTMLResponse)
async def create_post(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    lang = pick_lang(request)
    form = await request.form()
    if 'editor_token' in form:
        return await save_block_post(request, form)
    stale = stale_language_form(request, form)
    if stale is not None:
        return stale
    title = str(form.get("title_en", form.get("title", ""))).strip()
    excerpt = str(form.get("excerpt_en", form.get("excerpt", ""))).strip()
    category_id = str(form.get("category_id", "")).strip()
    if category_id:
        with get_db() as conn:
            if not category_id.isdigit() or not conn.execute("SELECT 1 FROM categories WHERE id = ?", (category_id,)).fetchone():
                return HTMLResponse(t(lang, "admin.category_invalid"), status_code=400)
    tags = str(form.get("tags", "")).strip()
    status = str(form.get("status", "draft")).strip()
    status = status if status in {"draft", "published"} else "draft"
    body_html = clean_html(str(form.get("body_html_en", form.get("body_html", ""))).strip())
    secondary_values = read_secondary_post(form)
    image = form.get("image")
    if not title or not excerpt or body_html == "<p></p>":
        values = {"title": title, "excerpt": excerpt, "category_id": category_id, "tags": tags, "body_html": body_html, "status": status, **secondary_values}
        return post_form_response(request, user, values, t(lang, "common.required"), status_code=400)
    with get_db() as conn:
        if not allowed_category(conn, actor(request), category_id):
            return Response("Forbidden: category not assigned", status_code=403)
    try:
        image_path = await save_upload(image)
    except ImageUploadError as exc:
        values = {"title": title, "excerpt": excerpt, "category_id": category_id,
                  "tags": tags, "body_html": body_html, "status": status, **secondary_values}
        return post_form_response(request, user, values, exc.message, status_code=exc.status_code)
    with get_db() as conn:
        slug = unique_slug(conn, "posts", title)
        cursor = conn.execute(
            """
            INSERT INTO posts (title, slug, excerpt, body, body_html, image_path, category_id, created_at, updated_at, status, author_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title, slug, excerpt, html.unescape(re.sub("<[^>]+>", " ", body_html)), body_html, image_path, int(category_id) if category_id else None, now_iso(), now_iso(), status, actor(request)['id']),
        )
        save_secondary_post(conn, cursor.lastrowid, secondary_values)
        set_post_tags(conn, cursor.lastrowid, tags)
    return RedirectResponse(f"/posts/{slug}", status_code=303)


@app.get("/admin/posts/{post_id}/edit", response_class=HTMLResponse)
async def edit_post_page(post_id: int, request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    with get_db() as conn:
        post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not post:
            return HTMLResponse(t(pick_lang(request), "common.not_found"), status_code=404)
        values = dict(post)
        values["tags"] = ", ".join(tags_for_post(conn, post_id))
    return post_form_response(
        request,
        user,
        values,
        action=f"/admin/posts/{post_id}/edit",
        heading=values["title"],
    )


@app.post("/admin/posts/{post_id}/edit", response_class=HTMLResponse)
async def update_post(post_id: int, request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    lang = pick_lang(request)
    form = await request.form()
    if 'editor_token' in form:
        return await save_block_post(request, form, post_id)
    stale = stale_language_form(request, form)
    if stale is not None:
        return stale
    title = str(form.get("title_en", form.get("title", ""))).strip()
    excerpt = str(form.get("excerpt_en", form.get("excerpt", ""))).strip()
    category_id = str(form.get("category_id", "")).strip()
    if category_id:
        with get_db() as conn:
            if not category_id.isdigit() or not conn.execute("SELECT 1 FROM categories WHERE id = ?", (category_id,)).fetchone():
                return HTMLResponse("Invalid category. Reload the editor and select an existing category or Uncategorized.", status_code=400)
    tags = str(form.get("tags", "")).strip()
    status = str(form.get("status", "draft")).strip()
    status = status if status in {"draft", "published"} else "draft"
    body_html = clean_html(str(form.get("body_html_en", form.get("body_html", ""))).strip())
    secondary_values = read_secondary_post(form)
    image = form.get("image")
    if not title or not excerpt or body_html == "<p></p>":
        values = {
            **secondary_values,
            "title": title,
            "excerpt": excerpt,
            "category_id": category_id,
            "tags": tags,
            "body_html": body_html,
            "status": status,
        }
        return post_form_response(
            request,
            user,
            values,
            t(lang, "common.required"),
            action=f"/admin/posts/{post_id}/edit",
            heading=title or t(lang, "common.edit"),
            status_code=400,
        )

    with get_db() as conn:
        post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not post:
            return HTMLResponse(t(pick_lang(request), "common.not_found"), status_code=404)
        if not can_write_post(conn, actor(request), post_id) or not allowed_category(conn, actor(request), category_id):
            return Response("Forbidden", status_code=403)
        try:
            image_path = await save_upload(image)
        except ImageUploadError as exc:
            values = {**dict(post), "title": title, "excerpt": excerpt,
                      "category_id": category_id, "tags": tags, "body_html": body_html,
                      "status": status, **secondary_values}
            return post_form_response(request, user, values, exc.message,
                                      action=f"/admin/posts/{post_id}/edit",
                                      heading=title or t(lang, "common.edit"),
                                      status_code=exc.status_code)
        if not image_path:
            image_path = post["image_path"]
        conn.execute(
            """
            UPDATE posts
            SET title = ?, excerpt = ?, body = ?, body_html = ?, image_path = ?,
                category_id = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                title,
                excerpt,
                html.unescape(re.sub("<[^>]+>", " ", body_html)),
                body_html,
                image_path,
                int(category_id) if category_id else None,
                status,
                now_iso(),
                post_id,
            ),
        )
        save_secondary_post(conn, post_id, secondary_values)
        set_post_tags(conn, post_id, tags)
    return RedirectResponse(f"/posts/{post['slug']}", status_code=303)


@app.post("/admin/posts/{post_id}/delete")
async def delete_post(post_id: int, request: Request) -> Response:
    if not require_user(request):
        return RedirectResponse("/login", status_code=303)
    with get_db() as conn:
        conn.execute("DELETE FROM post_tags WHERE post_id = ?", (post_id,))
        conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    return RedirectResponse("/admin/posts", status_code=303)


@app.get("/admin/categories", response_class=HTMLResponse)
async def admin_categories(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    lang = pick_lang(request)
    with get_db() as conn:
        categories = fetch_categories(conn)
        account = actor(request)
    return render_template(
        request,
        "admin/categories.html",
        t(lang, "admin.categories"),
        {"categories": categories, "active_admin": "categories", "can_delete_categories": account and account["role"] != "cc"},
        user,
    )


@app.post("/admin/categories")
async def create_category(request: Request) -> Response:
    if not require_user(request):
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    stale = stale_language_form(request, form)
    if stale is not None:
        return stale
    name = str(form.get("name", "")).strip()
    desc = str(form.get("description", "")).strip()
    if name:
        with get_db() as conn:
            inserted = conn.execute(
                """
                INSERT OR IGNORE INTO categories
                (name, slug, description, menu_label_secondary, menu_label_en, description_secondary, show_in_menu, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, 100, ?)
                """,
                (name, unique_slug(conn, "categories", name), desc, str(form.get("menu_label_secondary", "")).strip(), name, str(form.get("description_secondary", "")).strip(), now_iso()),
            )
            account = actor(request)
            if account and account["role"] == "cc" and inserted.rowcount == 1:
                created = conn.execute("SELECT id FROM categories WHERE name=?", (name,)).fetchone()
                if created:
                    conn.execute("INSERT OR IGNORE INTO user_categories (user_id, category_id) VALUES (?, ?)",
                                 (account["id"], created["id"]))
    return RedirectResponse("/admin/categories", status_code=303)


@app.get("/admin/categories/{category_id:int}/edit", response_class=HTMLResponse)
async def edit_category_page(category_id: int, request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    with get_db() as conn:
        category = conn.execute("SELECT * FROM categories WHERE id=?", (category_id,)).fetchone()
    if not category:
        return Response(status_code=404)
    return render_template(request, "admin/category_edit.html", "Edit category", {
        "active_admin": "categories", "category": category,
        "editor_token": custom_home_token(user),
    }, user)


@app.post("/admin/categories/{category_id:int}/edit")
async def update_category_details(category_id: int, request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    if not custom_home_authorized(request, form):
        return Response("Forbidden", status_code=403)
    stale = stale_language_form(request, form)
    if stale is not None:
        return stale
    name = str(form.get("name", "")).strip()
    description = str(form.get("description", "")).strip()
    secondary_label = str(form.get("menu_label_secondary", "")).strip()
    secondary_desc = str(form.get("description_secondary", "")).strip()
    if not name or len(name) > 120 or len(description) > 4000 or len(secondary_label) > 160 or len(secondary_desc) > 4000:
        return Response("Invalid category metadata", status_code=400)
    with get_db() as conn:
        try:
            changed = conn.execute("""UPDATE categories SET name=?, description=?, menu_label_en=?,
                menu_label_secondary=?, description_secondary=? WHERE id=?""",
                (name, description, name, secondary_label, secondary_desc, category_id))
        except sqlite3.IntegrityError:
            return Response("Category name is already in use", status_code=409)
        if not changed.rowcount:
            return Response(status_code=404)
    return RedirectResponse("/admin/categories", status_code=303)


@app.post("/admin/categories/{category_id}/delete")
async def delete_category(category_id: int, request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    if form.get("confirmed") != "1":
        return HTMLResponse(t(pick_lang(request), "admin.delete_confirmation"), status_code=400)
    try:
        with get_db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            before = {row[0] for row in conn.execute("SELECT id FROM posts")}
            conn.execute("UPDATE posts SET category_id = NULL WHERE category_id = ?", (category_id,))
            conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            if before != {row[0] for row in conn.execute("SELECT id FROM posts")}:
                raise sqlite3.IntegrityError("Content preservation check failed")
    except sqlite3.DatabaseError:
        with get_db() as conn:
            categories = fetch_categories(conn)
        lang = pick_lang(request)
        return render_template(request, "admin/categories.html", t(lang, "admin.categories"),
            {"categories": categories, "active_admin": "categories",
             "error": t(lang, "admin.category_delete_error")}, user, status_code=409)
    return RedirectResponse("/admin/categories", status_code=303)


@app.get("/admin/menu", response_class=HTMLResponse)
async def admin_menu(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    lang = pick_lang(request)
    with get_db() as conn:
        categories = fetch_categories(conn)
        custom_items = conn.execute("SELECT * FROM custom_menu_items ORDER BY sort_order, id").fetchall()
    with get_db() as conn:
        site_settings = get_site_settings(conn)
        hierarchy_context = menu_hierarchy_context(conn)
    # Support ?edit_category={id} — highlights the target row
    target_id = None
    try:
        target_id = int(str(request.query_params.get("edit_category", "") or "").strip())
    except (ValueError, TypeError):
        pass
    return render_template(request, "admin/menu.html", t(lang, "admin.menu"), {"categories": categories, "custom_items": custom_items, "site_settings": site_settings, "active_admin": "menu", "editing_category_id": target_id, **hierarchy_context}, user)


def menu_hierarchy_context(conn):
    settings = get_site_settings(conn)
    return {'menu_pages': [dict(row) for row in conn.execute('SELECT * FROM custom_pages ORDER BY title, id')],
            'menu_parents': menu_mapping(settings, 'menu_parents_json'),
            'page_orders': menu_mapping(settings, 'menu_page_orders_json')}


@app.post("/admin/menu")
async def save_menu(request: Request) -> Response:
    if not require_user(request):
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    stale = stale_language_form(request, form)
    if stale is not None:
        return stale
    custom_items = []
    parents, page_orders = {}, {}
    try:
        ids = [int(value) for value in form.getlist("category_id")]
        for category_id in ids:
            int(str(form.get(f"sort_{category_id}", "100")) or 100)
        for item_id in form.getlist("custom_id"):
            item = dict(id=str(item_id), label_secondary=str(form.get(f"custom_secondary_{item_id}", "")).strip(),
                        label_en=str(form.get(f"custom_en_{item_id}", "")).strip(),
                        url=str(form.get(f"custom_url_{item_id}", "")).strip(),
                        sort_order=str(form.get(f"custom_sort_{item_id}", "100")),
                        show_in_menu=1 if form.get(f"custom_show_{item_id}") else 0,
                        new_tab=1 if form.get(f"custom_tab_{item_id}") else 0)
            custom_items.append(item)
        for item in custom_items:
            if not item["label_en"] or (item["url"] and not valid_url(item["url"], relative=True)):
                raise ValueError("Invalid menu item")
            item["sort_order"] = int(item["sort_order"])
        if form.get('menu_hierarchy') == '1':
            with get_db() as conn:
                page_ids = {str(row['id']) for row in conn.execute('SELECT id FROM custom_pages')}
                category_ids = {str(row['id']) for row in conn.execute('SELECT id FROM categories')}
                existing_custom_ids = {str(row['id']) for row in conn.execute('SELECT id FROM custom_menu_items')}
            submitted_ids = [item['id'] for item in custom_items]
            if len(submitted_ids) != len(set(submitted_ids)):
                raise ValueError('Duplicate menu item')
            if any(item_id.isdigit() and item_id not in existing_custom_ids for item_id in submitted_ids):
                raise ValueError('Unknown menu item')
            groups = {'custom-' + item_id for item_id in submitted_ids}
            nodes = groups | {'category-' + value for value in category_ids} | {'page-' + value for value in page_ids}
            nodes |= {'builtin-about', 'builtin-contact', 'builtin-login'}
            parents = {key: str(form.get('parent_' + key, '')) for key in nodes}
            # Removing a group moves its children back to the top level.
            removed = {'custom-' + value for value in existing_custom_ids} - groups
            parents = {key: '' if parent in removed else parent for key, parent in parents.items()}
            validate_parents(parents, nodes, groups)
            page_orders = {value: int(str(form.get('page_sort_' + value, '100')) or '100') for value in page_ids}
    except ValueError:
        lang = pick_lang(request)
        with get_db() as conn:
            categories = fetch_categories(conn)
            hierarchy_context = menu_hierarchy_context(conn)
        if form.get('menu_hierarchy') == '1':
            hierarchy_context['menu_parents'] = parents
            hierarchy_context['page_orders'].update(page_orders)
            for page in hierarchy_context['menu_pages']:
                page['show_in_menu'] = bool(form.get(f"page_show_{page['id']}"))
        return render_template(request, "admin/menu.html", t(lang, "admin.menu"),
            {"categories": categories, "custom_items": custom_items, "active_admin": "menu",
             **hierarchy_context, "error": t(lang, "menu.hierarchy_error")}, require_user(request), status_code=400)
    with get_db() as conn:
        for category_id in ids:
            existing_category = conn.execute("SELECT * FROM categories WHERE id=?", (category_id,)).fetchone()
            if not existing_category:
                continue
            conn.execute(
                """
                UPDATE categories
                SET menu_label_secondary = ?, menu_label_en = ?, sort_order = ?, show_in_menu = ?
                WHERE id = ?
                """,
                (
                    str(form.get(f"label_secondary_{category_id}", existing_category["menu_label_secondary"])).strip(),
                    str(form.get(f"label_en_{category_id}", existing_category["menu_label_en"])).strip() or existing_category["menu_label_en"] or existing_category["name"],
                    int(str(form.get(f"sort_{category_id}", "100")) or 100),
                    1 if form.get(f"show_{category_id}") else 0,
                    category_id,
                ),
            )
        retained, resolved_keys = [], {}
        for item in custom_items:
            if item['id'].isdigit() and f"custom_secondary_{item['id']}" not in form:
                existing = conn.execute("SELECT label_secondary FROM custom_menu_items WHERE id=?", (item['id'],)).fetchone()
                if existing:
                    item['label_secondary'] = existing[0]
            values = (item["label_secondary"], item["label_en"], item["url"], item["sort_order"], item["show_in_menu"], item["new_tab"])
            if item["id"].isdigit():
                conn.execute("UPDATE custom_menu_items SET label_secondary=?, label_en=?, url=?, sort_order=?, show_in_menu=?, new_tab=? WHERE id=?", (*values, int(item["id"])))
                retained.append(int(item["id"]))
                resolved_keys['custom-' + item['id']] = 'custom-' + item['id']
            else:
                cursor = insert_custom_menu(conn, values)
                retained.append(cursor.lastrowid)
                resolved_keys['custom-' + item['id']] = f'custom-{cursor.lastrowid}'
        holders = ",".join("?" for _ in retained) or "NULL"
        conn.execute(f"DELETE FROM custom_menu_items WHERE id NOT IN ({holders})" if retained else "DELETE FROM custom_menu_items", retained)
        # Save page visibility settings
        show_about = "1" if form.get("show_about_link") else "0"
        show_contact = "1" if form.get("show_contact_link_page") else "0"
        show_login = "1" if form.get("show_login_link") else "0"
        settings = get_site_settings(conn)
        if form.get('menu_hierarchy') == '1':
            settings['menu_parents_json'] = json.dumps({resolved_keys.get(key, key): resolved_keys.get(parent, parent)
                                                       for key, parent in parents.items() if parent})
            settings['menu_page_orders_json'] = json.dumps(page_orders)
            for page_id in page_orders:
                conn.execute('UPDATE custom_pages SET show_in_menu=? WHERE id=?',
                             (int(bool(form.get('page_show_' + page_id))), int(page_id)))
        settings["show_about_link"] = show_about
        settings["show_contact_link"] = show_contact
        settings["show_login_link"] = show_login
        set_site_settings(conn, settings)
    return RedirectResponse("/admin/menu?saved=1", status_code=303)


SITE_SETTING_KEYS = (
    "site_name",
    "site_description",
    "head_snippet",
    "hero_kicker_secondary",
    "hero_kicker_en",
    "hero_title_secondary",
    "hero_title_en",
    "hero_copy_secondary",
    "hero_copy_en",
    "social_linkedin_url",
    "social_twitter_url",
    "contact_email",
    "show_login_link",
    "show_contact_link",
    "show_about_link",
    "contact_intro_secondary",
    "contact_intro_en",
    "contact_details_secondary",
    "contact_details_en",
    "color_nav",
    "color_nav_hover",
    "color_nav_active",
    "color_feature_bg",
    "color_feature_text",
    "color_feature_border",
    "color_accent_primary",
    "color_accent_secondary",
    "color_separator_1",
    "color_separator_2",
    "color_separator_3",
)


def fetch_settings_categories():
    with get_db() as conn:
        return fetch_categories(conn)


def settings_form_token(request: Request, user: str) -> str:
    session = request.cookies.get(SESSION_COOKIE, "")
    return hmac.new(_csrf_secret(user).encode(), f"settings:{session}".encode(), hashlib.sha256).hexdigest()


def settings_response(request, user, settings, *, error="", status_code=200,
                      sitemap_origin=None, sitemap_error=""):
    lang = pick_lang(request)
    with get_db() as conn:
        sitemap_saved = conn.execute("SELECT 1 FROM site_settings WHERE key = 'sitemap_xml'").fetchone() is not None
    return render_template(
        request,
        "admin/settings.html",
        t(lang, "admin.settings"),
        {
            "settings": settings,
            "saved": request.query_params.get("saved") == "1",
            "error": error,
            "active_admin": "settings",
            "card_categories": fetch_settings_categories(),
            "category_cards": category_card_settings(settings),
            "settings_token": settings_form_token(request, user),
            "sitemap_origin": str(request.base_url).rstrip("/") if sitemap_origin is None else sitemap_origin,
            "sitemap_exists": sitemap_saved or SITEMAP_PATH.is_file(),
            "sitemap_generated": request.query_params.get("sitemap") == "generated",
            "sitemap_error": sitemap_error,
        },
        user,
        status_code=status_code,
    )


@app.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    with get_db() as conn:
        settings = get_site_settings(conn)
    return settings_response(request, user, settings)


@app.post("/admin/settings", response_class=HTMLResponse)
async def save_settings(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    lang = pick_lang(request)
    form = await request.form()
    if "head_snippet" in form and not hmac.compare_digest(
        str(form.get("settings_token", "")).encode(), settings_form_token(request, user).encode()
    ):
        return Response(status_code=403)
    stale = stale_language_form(request, form)
    if stale is not None:
        return stale
    with get_db() as conn:
        current_settings = get_site_settings(conn)
    settings = dict(current_settings)
    for key in SITE_SETTING_KEYS:
        if key in form:
            settings[key] = str(form.get(key, "")).strip()
    if "show_login_link" in form:
        settings["show_login_link"] = "1" if form.get("show_login_link") else "0"
    if form.get('category_cards_present'):
        cards = {}
        for cat in fetch_settings_categories():
            prefix = f"card_{cat['id']}_"
            values = {key: bool(form.get(prefix + key)) for key in ('show_date', 'show_title', 'show_excerpt')}
            for key in ('background', 'text_color'):
                value = str(form.get(prefix + key, ''))
                values[key] = value.lower() if re.fullmatch(r'#[0-9a-fA-F]{6}', value) else ''
            cards[cat['slug']] = values
        settings['category_cards_json'] = json.dumps(cards)
    required = [
        "site_name",
        "site_description",
        "hero_kicker_en",
        "hero_title_en",
        "hero_copy_en",
    ]
    if any(not settings[key] for key in required):
        return settings_response(request, user, settings, error=t(lang, "common.required"), status_code=400)
    with get_db() as conn:
        set_site_settings(conn, settings)
    return RedirectResponse("/admin/settings?saved=1", status_code=303)


@app.post("/admin/settings/sitemap")
async def generate_sitemap(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    if not hmac.compare_digest(
        str(form.get("settings_token", "")).encode(), settings_form_token(request, user).encode()
    ):
        return Response(status_code=403)
    origin = str(form.get("sitemap_origin", "")).strip().rstrip("/")
    with get_db() as conn:
        settings = get_site_settings(conn)
        if not valid_url(origin) or not re.fullmatch(r"https?://[^/?#@]+", origin, re.IGNORECASE):
            return settings_response(request, user, settings, sitemap_origin=origin,
                                     sitemap_error=t(pick_lang(request), "sitemap.invalid_origin"), status_code=400)
        paths = ["/", "/about", "/contact"]
        for prefix, query in (
            ("category", "SELECT slug FROM categories ORDER BY slug"),
            ("posts", "SELECT slug FROM posts WHERE status = 'published' ORDER BY slug"),
            ("pages", "SELECT slug FROM custom_pages WHERE published = 1 ORDER BY slug"),
        ):
            paths.extend(f"/{prefix}/{quote(row['slug'], safe='')}" for row in conn.execute(query))

    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for path in paths:
        ET.SubElement(ET.SubElement(urlset, "url"), "loc").text = origin + path
    ET.indent(urlset)
    xml = ET.tostring(urlset, encoding="utf-8", xml_declaration=True)
    if len(paths) > 50_000 or len(xml) > 52_428_800:
        return settings_response(request, user, settings, sitemap_origin=origin,
                                 sitemap_error=t(pick_lang(request), "sitemap.too_large"), status_code=400)

    try:
        with get_db() as conn:
            set_site_settings(conn, {"sitemap_xml": xml.decode("utf-8")})
    except sqlite3.Error:
        logging.getLogger(__name__).exception("Could not save sitemap to the site database")
        return settings_response(request, user, settings, sitemap_origin=origin,
                                 sitemap_error=t(pick_lang(request), "sitemap.write_error"), status_code=500)
    return RedirectResponse("/admin/settings?sitemap=generated#sitemap", status_code=303)


DESIGN_SETTING_KEYS = (
    "color_page_bg", "color_footer_bg", "color_footer_text", "color_footer_border",
    "color_nav",
    "color_nav_hover",
    "color_nav_active",
    "color_feature_bg",
    "color_feature_text",
    "color_feature_border",
    "color_accent_primary",
    "color_accent_secondary",
    "color_separator_1",
    "color_separator_2",
    "color_separator_3",
)

HOMEPAGE_SETTING_KEYS = (
    "show_feature_strip",
    "show_feature_blog",
    "show_feature_notes",
    "show_feature_contact",
    "feature_blog_desc_secondary",
    "feature_blog_desc_en",
    "feature_notes_desc_secondary",
    "feature_notes_desc_en",
    "feature_contact_desc_secondary",
    "feature_contact_desc_en",
    "hero_background_enabled",
    "hero_background_image_path",
    "homepage_mode",
    "show_featured_post",
    "featured_post_id",
    "show_featured_image",
    "show_latest_writing",
    "latest_writing_category",
    "latest_writing_count",
    "show_latest_notes",
    "latest_notes_category",
    "latest_notes_count",
    "homepage_layout",
    "show_empty_placeholders",
    "homepage_categories_json",
)


@app.get("/admin/cms-design", response_class=HTMLResponse)
async def cms_category_design(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    with get_db() as conn:
        categories = [dict(row) for row in conn.execute(
            "SELECT id, name, slug, archive_design_json FROM categories ORDER BY name COLLATE NOCASE")]
        requested = request.query_params.get("category", "")
        preview_category = next((cat for cat in categories if str(cat["id"]) == requested), None)
        if preview_category is None and categories:
            preview_category = categories[0]
        preview_posts = [dict(row) for row in fetch_posts(conn, preview_category["slug"], 8)] if preview_category else []
    requested = request.query_params.get("category", "")
    selected = next((cat for cat in categories if str(cat["id"]) == requested), None)
    if selected is None and categories:
        selected = categories[0]
    design = parse_archive_design(selected["archive_design_json"] if selected else None)
    return render_template(request, "admin/cms_design.html", "CMS Design", {
        "active_admin": "cms_design", "categories": categories, "selected": selected,
        "design": design, "preview_posts": preview_posts, "editor_token": custom_home_token(user),
        "saved": request.query_params.get("saved") == "1",
    }, user)


@app.post("/admin/cms-design")
async def save_cms_category_design(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    if not custom_home_authorized(request, form):
        return Response("Forbidden", status_code=403)
    raw_id = str(form.get("category_id", ""))
    if not re.fullmatch(r"[0-9]{1,18}", raw_id):
        return Response("Invalid category", status_code=400)
    try:
        design = validate_archive_design(form)
    except ValueError as error:
        return Response(str(error), status_code=400)
    with get_db() as conn:
        updated = conn.execute("UPDATE categories SET archive_design_json=? WHERE id=?",
                               (json.dumps(design, sort_keys=True), int(raw_id)))
        if not updated.rowcount:
            return Response("Category not found", status_code=404)
    return RedirectResponse(f"/admin/cms-design?category={int(raw_id)}&saved=1", status_code=303)


NAVBAR_DESIGN_CHOICES = {
    'navbar_style': {'classic', 'minimal', 'glass', 'solid'},
    'navbar_position': {'sticky', 'static'},
    'navbar_alignment': {'left', 'center', 'right'},
    'navbar_width': {'contained', 'wide', 'full'},
    'navbar_font': {'sans', 'serif', 'monospace'},
    'navbar_logo_mode': {'initials', 'image', 'none'},
}
NAVBAR_DESIGN_RANGES = {
    'navbar_font_size': (11, 22),
    'navbar_font_weight': (400, 800),
    'navbar_height': (52, 112),
    'navbar_logo_size': (24, 100),
}

def validated_navbar_settings(form, current):
    changes = {}
    for key, valid in NAVBAR_DESIGN_CHOICES.items():
        value = str(form.get(key, current[key])).strip()
        if value not in valid:
            raise ValueError('Invalid navbar setting: ' + key)
        changes[key] = value
    for key, (minimum, maximum) in NAVBAR_DESIGN_RANGES.items():
        value = str(form.get(key, current[key])).strip()
        if not value.isdecimal() or not minimum <= int(value) <= maximum:
            raise ValueError('Invalid navbar size: ' + key)
        changes[key] = str(int(value))
    logo = str(form.get('navbar_logo_url', current['navbar_logo_url'])).strip()
    if logo and not (logo.startswith('/static/uploads/') and valid_url(logo, relative=True)
                     or logo.startswith('https://') and valid_url(logo)):
        raise ValueError('Invalid navbar logo URL')
    changes['navbar_logo_url'] = logo
    changes['navbar_show_tagline'] = '1' if form.get('navbar_show_tagline') else '0'
    return changes


@app.get("/admin/design", response_class=HTMLResponse)
async def admin_design(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    lang = pick_lang(request)
    with get_db() as conn:
        settings = get_site_settings(conn)
    return render_template(
        request,
        "admin/design.html",
        t(lang, "admin.design"),
        {
            "settings": settings,
            "saved": request.query_params.get("saved") == "1",
            "active_admin": "design",
            "color_templates": list_templates(),
            "navbar_upload_token": custom_home_token(user),
        },
        user,
    )


@app.post('/admin/design/navbar-logo')
async def upload_navbar_logo(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return JSONResponse({'error': 'Login required'}, status_code=401)
    form = await request.form()
    if not hmac.compare_digest(str(form.get('editor_token', '')), custom_home_token(user)):
        return JSONResponse({'error': 'Invalid token'}, status_code=403)
    try:
        path = await store_image_upload(form.get('file'), UPLOAD_DIR, prefix='navbar-')
    except ImageUploadError as exc:
        return JSONResponse({'error': exc.message}, status_code=exc.status_code)
    if not path:
        return JSONResponse({'error': 'Choose an image'}, status_code=400)
    return JSONResponse({'url': path})


@app.get("/admin/homepage", response_class=HTMLResponse)
async def admin_homepage(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    lang = pick_lang(request)
    with get_db() as conn:
        settings = get_site_settings(conn)
        all_categories = conn.execute("SELECT * FROM categories ORDER BY sort_order ASC, name ASC").fetchall()
        all_posts = conn.execute("SELECT id, title, title_secondary, status FROM posts ORDER BY datetime(created_at) DESC").fetchall()

    # Parse homepage categories JSON if present
    try:
        homepage_categories_config = json.loads(settings.get("homepage_categories_json", "[]"))
        if not isinstance(homepage_categories_config, list):
            homepage_categories_config = []
    except Exception:
        homepage_categories_config = []

    # Map configured settings to category list
    config_by_id = {str(item.get("id")): item for item in homepage_categories_config if isinstance(item, dict)}
    categories_with_hp_settings = []
    for cat in all_categories:
        cat_id_str = str(cat["id"])
        c_conf = config_by_id.get(cat_id_str, {})
        categories_with_hp_settings.append({
            "id": cat["id"],
            "slug": cat["slug"],
            "name": cat["name"],
            "menu_label_en": cat["menu_label_en"],
            "menu_label_secondary": cat["menu_label_secondary"],
            "hp_enabled": c_conf.get("enabled", "0") == "1",
            "hp_order": c_conf.get("order", cat["sort_order"]),
            "hp_count": c_conf.get("count", "3"),
        })
    categories_with_hp_settings.sort(key=lambda x: (int(x["hp_order"]) if str(x["hp_order"]).isdigit() else 999, x["name"].casefold()))

    return render_template(
        request,
        "admin/homepage.html",
        t(lang, "admin.homepage"),
        {
            "settings": settings,
            "saved": request.query_params.get("saved") == "1",
            "active_admin": "homepage",
            "all_categories": all_categories,
            "all_posts": all_posts,
            "homepage_categories": categories_with_hp_settings,
            "documents": {language['suffix']: read_document(settings.get('custom_home_' + language['suffix'], ''))
                          for language in content_languages(settings)},
            "builder_categories": [dict(cat) for cat in all_categories],
            "editor_token": custom_home_token(user),
        },
        user,
    )


@app.post("/admin/design", response_class=HTMLResponse)
async def save_design(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    stale = stale_language_form(request, form)
    if stale is not None:
        return stale
    with get_db() as conn:
        settings = get_site_settings(conn)
        for key in DESIGN_SETTING_KEYS:
            value = str(form.get(key, settings.get(key, ""))).strip()
            if re.fullmatch(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?", value):
                settings[key] = value.lower()
        for key in ("footer_text_secondary", "footer_text_en"):
            settings[key] = str(form.get(key, settings.get(key, ""))).strip()
        settings["show_footer"] = "1" if form.get("show_footer") else "0"
        try:
            settings.update(validated_navbar_settings(form, settings))
        except ValueError:
            return Response('Invalid navbar configuration', status_code=400)
        set_site_settings(conn, settings)
    return RedirectResponse("/admin/design?saved=1", status_code=303)


@app.post("/admin/homepage", response_class=HTMLResponse)
async def save_homepage(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    stale = stale_language_form(request, form)
    if stale is not None:
        return stale
    with get_db() as conn:
        settings = get_site_settings(conn)
        if form.get('homepage_mode') == 'custom':
            # A mode-only request must not clear inactive feed settings.
            set_site_settings(conn, {'homepage_mode': 'custom'})
            return RedirectResponse('/admin/homepage?saved=1', status_code=303)
        if form.get('homepage_general_present'):
            for key in ('show_feature_strip', 'show_feature_blog', 'show_feature_notes', 'show_feature_contact', 'hero_background_enabled'):
                settings[key] = '1' if form.get(key) else '0'
            for feature in ('blog', 'notes', 'contact'):
                for language in content_languages(settings):
                    key = f"feature_{feature}_desc_{language['suffix']}"
                    settings[key] = str(form.get(key, settings.get(key, ''))).strip()
            try:
                hero_image = await save_upload(form.get('hero_background_image'))
            except ImageUploadError as exc:
                return HTMLResponse(exc.message, status_code=exc.status_code)
            if hero_image:
                settings['hero_background_image_path'] = hero_image
        settings['homepage_mode'] = 'custom' if form.get('homepage_mode') == 'custom' else 'feed'

        # Featured content
        settings["show_featured_post"] = "1" if form.get("show_featured_post") else "0"
        settings["featured_post_id"] = str(form.get("featured_post_id", "")).strip()
        settings["show_featured_image"] = "1" if form.get("show_featured_image") else "0"

        # Latest writing & notes
        settings["show_latest_writing"] = "1" if form.get("show_latest_writing") else "0"
        settings["latest_writing_category"] = str(form.get("latest_writing_category", "blog")).strip()
        latest_writing_count = str(form.get("latest_writing_count", "4")).strip()
        settings["latest_writing_count"] = latest_writing_count if latest_writing_count.isdigit() else "4"

        settings["show_latest_notes"] = "1" if form.get("show_latest_notes") else "0"
        settings["latest_notes_category"] = str(form.get("latest_notes_category", "notlar")).strip()
        latest_notes_count = str(form.get("latest_notes_count", "5")).strip()
        settings["latest_notes_count"] = latest_notes_count if latest_notes_count.isdigit() else "5"

        # Layout and empty behavior
        homepage_layout = str(form.get("homepage_layout", "editorial_split")).strip()
        settings["homepage_layout"] = homepage_layout if homepage_layout in ("editorial_split", "single_column") else "editorial_split"
        settings["show_empty_placeholders"] = "1" if form.get("show_empty_placeholders") else "0"

        # Homepage categories
        all_categories = conn.execute("SELECT id, slug FROM categories").fetchall()
        hp_cat_configs = []
        for cat in all_categories:
            cat_id = str(cat["id"])
            if form.get(f"hp_cat_enabled_{cat_id}"):
                order_val = str(form.get(f"hp_cat_order_{cat_id}", "0")).strip()
                count_val = str(form.get(f"hp_cat_count_{cat_id}", "3")).strip()
                hp_cat_configs.append({
                    "id": cat["id"],
                    "slug": cat["slug"],
                    "enabled": "1",
                    "order": int(order_val) if order_val.isdigit() else 0,
                    "count": int(count_val) if count_val.isdigit() else 3,
                })
        hp_cat_configs.sort(key=lambda x: x["order"])
        settings["homepage_categories_json"] = json.dumps(hp_cat_configs)

        set_site_settings(conn, settings)
    return RedirectResponse("/admin/homepage?saved=1", status_code=303)


def custom_home_token(user):
    return hmac.new(SECRET_KEY.encode(), f'custom-home:{user}'.encode(), hashlib.sha256).hexdigest()


def custom_home_enabled():
    with get_db() as conn:
        return get_site_settings(conn).get('homepage_mode') == 'custom'


def custom_home_authorized(request, form):
    user = require_user(request)
    return user and hmac.compare_digest(str(form.get('editor_token', '')).encode(), custom_home_token(user).encode())


@app.get('/admin/custom-home', response_class=HTMLResponse)
async def admin_custom_home(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse('/login', status_code=303)
    return RedirectResponse('/admin/homepage?mode=custom', status_code=303)


@app.get('/admin/about', response_class=HTMLResponse)
async def admin_about(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse('/login', status_code=303)
    with get_db() as conn:
        settings = get_site_settings(conn)
        categories = conn.execute('SELECT * FROM categories ORDER BY sort_order ASC, name ASC').fetchall()
    return render_template(request, 'admin/about.html', t(pick_lang(request), 'admin.about'), {
        'settings': settings, 'active_admin': 'about', 'builder_page': 'about',
        'documents': {language['suffix']: read_document(settings.get('about_page_' + language['suffix'], ''))
                      for language in content_languages(settings)},
        'builder_categories': [dict(category) for category in categories],
        'editor_token': custom_home_token(user),
    }, user)


def builder_page(request):
    """The route, never submitted fields, determines the persistence namespace."""
    if request.url.path.startswith('/admin/posts/'):
        return 'post'
    if request.url.path.startswith('/admin/pages/'):
        return 'page'
    return 'about' if request.url.path.startswith('/admin/about') else 'home'


@app.get('/admin/pages', response_class=HTMLResponse)
async def admin_pages(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse('/login', status_code=303)
    with get_db() as conn:
        pages = conn.execute('SELECT * FROM custom_pages ORDER BY id DESC').fetchall()
    return render_template(request, 'admin/pages.html', t(pick_lang(request), 'admin.pages'), {
        'pages': pages, 'active_admin': 'pages', 'editor_token': custom_home_token(user),
    }, user)


@app.post('/admin/pages')
async def create_custom_page(request: Request) -> Response:
    form = await request.form()
    if not custom_home_authorized(request, form):
        return Response(status_code=403)
    title = str(form.get('title', '')).strip()
    if not title or len(title) > 200:
        return HTMLResponse(t(pick_lang(request), 'pages.invalid'), status_code=400)
    with get_db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        slug = unique_slug(conn, 'custom_pages', slugify(title)[:70])
        cursor = conn.execute('INSERT INTO custom_pages (title, slug, created_at, updated_at) VALUES (?, ?, ?, ?)',
                              (title, slug, now_iso(), now_iso()))
        page_id = cursor.lastrowid
    return RedirectResponse(f'/admin/pages/{page_id}', status_code=303)


@app.get('/admin/pages/{page_id:int}', response_class=HTMLResponse)
async def edit_custom_page(page_id: int, request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse('/login', status_code=303)
    with get_db() as conn:
        page = conn.execute('SELECT * FROM custom_pages WHERE id=?', (page_id,)).fetchone()
        if page is None:
            return Response(status_code=404)
        settings = get_site_settings(conn)
        categories = conn.execute('SELECT * FROM categories ORDER BY sort_order, name').fetchall()
    documents = json.loads(page['documents_json'])
    return render_template(request, 'admin/page.html', page['title'], {
        'page_record': page, 'settings': settings, 'active_admin': 'pages', 'builder_page': 'page',
        'builder_endpoint': f'/admin/pages/{page_id}',
        'documents': {language['suffix']: read_document(documents.get(language['code'], ''))
                      for language in content_languages(settings)},
        'builder_categories': [dict(category) for category in categories],
        'editor_token': custom_home_token(user),
    }, user)


@app.post('/admin/pages/{page_id:int}')
async def save_custom_page(page_id: int, request: Request) -> Response:
    form = await request.form()
    lang = pick_lang(request)
    if not custom_home_authorized(request, form):
        return JSONResponse({'error': t(lang, 'builder.session_error')}, status_code=403)
    if stale_language_form(request, form) is not None:
        return JSONResponse({'error': t(lang, 'language.stale')}, status_code=409)
    title, slug = str(form.get('title', '')).strip(), str(form.get('slug', '')).strip()
    if not title or len(title) > 200 or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or len(slug) > 80:
        return JSONResponse({'error': t(lang, 'pages.invalid')}, status_code=400)
    with get_db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        page = conn.execute('SELECT * FROM custom_pages WHERE id=?', (page_id,)).fetchone()
        if page is None:
            return JSONResponse({'error': t(lang, 'common.empty')}, status_code=404)
        if conn.execute('SELECT id FROM custom_pages WHERE slug=? AND id!=?', (slug, page_id)).fetchone():
            return JSONResponse({'error': t(lang, 'pages.slug_taken')}, status_code=409)
        documents = json.loads(page['documents_json'])
        try:
            for language in content_languages(get_site_settings(conn)):
                key = 'page_' + language['suffix']
                if key not in form:
                    raise ValueError('Missing document')
                documents[language['code']] = json.dumps(validate_document(str(form[key])), ensure_ascii=False)
        except ValueError:
            return JSONResponse({'error': t(lang, 'builder.invalid')}, status_code=400)
        conn.execute('''UPDATE custom_pages SET title=?, slug=?, documents_json=?, show_in_menu=?,
                        published=1, updated_at=? WHERE id=?''',
                     (title, slug, json.dumps(documents, ensure_ascii=False),
                      int(form.get('show_in_menu') == '1'), now_iso(), page_id))
    return JSONResponse({'message': t(lang, 'pages.saved'), 'url': f'/pages/{slug}'})


@app.post('/admin/pages/{page_id:int}/delete')
async def delete_custom_page(page_id: int, request: Request) -> Response:
    form = await request.form()
    if not custom_home_authorized(request, form):
        return Response(status_code=403)
    with get_db() as conn:
        conn.execute('DELETE FROM custom_pages WHERE id=?', (page_id,))
    return RedirectResponse('/admin/pages', status_code=303)


@app.get('/pages/{slug}', response_class=HTMLResponse)
async def public_custom_page(slug: str, request: Request) -> Response:
    with get_db() as conn:
        page = conn.execute('SELECT * FROM custom_pages WHERE slug=? AND published=1', (slug,)).fetchone()
    if page is None:
        return Response(status_code=404)
    documents = json.loads(page['documents_json'])
    blocks = read_document(documents.get(pick_lang(request), '')) or read_document(documents.get('en', ''))
    return render_template(request, 'custom_home.html', page['title'], {
        'custom_blocks': prepare_custom_blocks(blocks, pick_lang(request)),
    }, current_user(request))


@app.post('/admin/about')
@app.post('/admin/custom-home')
async def save_custom_home(request: Request) -> Response:
    form = await request.form()
    if not custom_home_authorized(request, form):
        return JSONResponse({'error': t(pick_lang(request), 'builder.session_error')}, status_code=403)
    if builder_page(request) == 'home' and form.get('homepage_mode') != 'custom' and not custom_home_enabled():
        return JSONResponse({'error': t(pick_lang(request), 'builder.disabled')}, status_code=409)
    stale = stale_language_form(request, form)
    if stale is not None:
        return JSONResponse({'error': t(pick_lang(request), 'language.stale')}, status_code=409)
    with get_db() as conn:
        settings = get_site_settings(conn)
        updates = {}
        prefix = 'about_page_' if builder_page(request) == 'about' else 'custom_home_'
        try:
            for language in content_languages(settings):
                key = prefix + language['suffix']
                if key not in form:
                    continue
                blocks = validate_document(str(form[key]))
                updates[key] = json.dumps(blocks, ensure_ascii=False) if blocks else ''
        except ValueError:
            return JSONResponse({'error': t(pick_lang(request), 'builder.invalid')}, status_code=400)
        if builder_page(request) == 'about':
            if 'about_page_en' not in updates:
                return JSONResponse({'error': t(pick_lang(request), 'builder.invalid')}, status_code=400)
            updates['enable_about_page'] = '1'
        elif form.get('homepage_mode') == 'custom':
            if 'custom_home_en' not in updates:
                return JSONResponse({'error': t(pick_lang(request), 'builder.invalid')}, status_code=400)
            # Editors can modify the content, but only admins change the site mode.
            if actor(request)['role'] == 'admin':
                updates['homepage_mode'] = 'custom'
        set_site_settings(conn, updates)
    return JSONResponse({'message': t(pick_lang(request), 'builder.about_saved' if builder_page(request) == 'about' else 'builder.saved')})


@app.post('/admin/posts/new/preview', response_class=HTMLResponse)
@app.post('/admin/posts/{post_id:int}/edit/preview', response_class=HTMLResponse)
@app.post('/admin/about/preview', response_class=HTMLResponse)
@app.post('/admin/pages/{page_id:int}/preview', response_class=HTMLResponse)
@app.post('/admin/custom-home/preview', response_class=HTMLResponse)
async def preview_custom_home(request: Request) -> Response:
    form = await request.form()
    if not custom_home_authorized(request, form):
        return JSONResponse({'error': t(pick_lang(request), 'builder.session_error')}, status_code=403)
    if builder_page(request) == 'home' and form.get('homepage_mode') != 'custom' and not custom_home_enabled():
        return JSONResponse({'error': t(pick_lang(request), 'builder.disabled')}, status_code=409)
    try:
        blocks = validate_document(str(form.get('document', '[]')))
    except ValueError:
        return JSONResponse({'error': t(pick_lang(request), 'builder.invalid')}, status_code=400)
    if builder_page(request) == 'post':
        lang = pick_lang(request)
        with get_db() as conn:
            settings = get_site_settings(conn)
            category = conn.execute('SELECT name FROM categories WHERE id=?', (str(form.get('category_id', '')),)).fetchone()
            post_id = request.path_params.get('post_id')
            existing = conn.execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone() if post_id else None
        languages = content_languages(settings)
        suffix = next((item['suffix'] for item in languages if item['code'] == lang), languages[0]['suffix'])
        post = {'title': str(form.get('title_' + suffix) or form.get('title_' + languages[0]['suffix'], '')),
                'excerpt': str(form.get('excerpt_' + suffix) or form.get('excerpt_' + languages[0]['suffix'], '')),
                'created_at': existing['created_at'] if existing else now_iso(),
                'category_name': category['name'] if category else '',
                'image_path': existing['image_path'] if existing else ''}
        return render_template(request, 'post_detail.html', post['title'], {
            'post': post, 'tags': [tag.strip() for tag in str(form.get('tags', '')).split(',') if tag.strip()],
            'custom_blocks': prepare_custom_blocks(blocks, lang), 'body_html': '',
        }, require_user(request))
    title = t(pick_lang(request), 'admin.pages' if builder_page(request) == 'page' else ('nav.about' if builder_page(request) == 'about' else 'nav.home'))
    return render_template(request, 'custom_home.html', title, {'custom_blocks': prepare_custom_blocks(blocks, pick_lang(request))}, require_user(request))


@app.post('/admin/section-svg')
async def save_section_svg(request: Request) -> Response:
    form = await request.form()
    if not custom_home_authorized(request, form):
        return JSONResponse({'error': t(pick_lang(request), 'builder.session_error')}, status_code=403)
    defaults = {
        'svg_pattern': 'ribbons', 'svg_primary': '#7466ef',
        'svg_secondary': '#5ed8ce', 'svg_tertiary': '#f2c14e',
        'svg_quaternary': '#a28bdd', 'svg_colors': 2, 'svg_opacity': 100,
        'svg_placement': 'full', 'svg_rotation': 0, 'svg_scale': 100,
        'svg_frequency': 3, 'svg_amplitude': 45,
        'svg_density': 8, 'svg_stroke': 3,
    }
    raw = {key: form.get(key, default) for key, default in defaults.items()}
    try:
        for key, default in defaults.items():
            if type(default) is int:
                raw[key] = int(str(raw[key]))
        options = validate_appearance(raw, SECTION_SVG_FIELDS)
    except (ValueError, TypeError):
        return JSONResponse({'error': t(pick_lang(request), 'builder.invalid')}, status_code=400)
    svg = render_svg(options).encode('utf-8')
    if str(form.get('preview', '')) == '1':
        return Response(svg, media_type='image/svg+xml',
                        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    digest = hashlib.sha256(svg).hexdigest()[:32]
    filename = f'friperi-section-{digest}.svg'
    asset = STATIC_DIR / 'images' / filename
    temporary = None
    try:
        if not asset.is_file():
            asset.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=asset.parent, prefix='.section-svg-', delete=False) as output:
                temporary = Path(output.name)
                output.write(svg)
            temporary.chmod(0o644)
            temporary.replace(asset)
    except OSError:
        try:
            with get_db() as conn:
                set_site_settings(conn, {f'section_svg:{filename}': svg.decode('utf-8')})
        except sqlite3.Error:
            logging.getLogger(__name__).exception("Could not store generated section SVG")
            return JSONResponse({'error': t(pick_lang(request), 'builder.section_svg_error')}, status_code=500)
    finally:
        if temporary:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                logging.getLogger(__name__).exception("Could not remove temporary section SVG %s", temporary)
    return JSONResponse({'url': f'/static/images/{filename}'})


@app.post('/admin/posts/new/upload')
@app.post('/admin/posts/{post_id:int}/edit/upload')
@app.post('/admin/about/upload')
@app.post('/admin/pages/{page_id:int}/upload')
@app.post('/admin/custom-home/upload')
async def upload_custom_home_media(request: Request) -> Response:
    form = await request.form()
    if not custom_home_authorized(request, form):
        return JSONResponse({'error': t(pick_lang(request), 'builder.session_error')}, status_code=403)
    if builder_page(request) == 'home' and form.get('homepage_mode') != 'custom' and not custom_home_enabled():
        return JSONResponse({'error': t(pick_lang(request), 'builder.disabled')}, status_code=409)
    upload = form.get('file')
    kind = str(form.get('kind', 'image'))
    if kind not in {'image', 'video'}:
        return JSONResponse({'error': t(pick_lang(request), 'builder.upload_error')}, status_code=400)
    if kind == 'image':
        try:
            path = await store_image_upload(upload, UPLOAD_DIR, prefix="home-")
        except ImageUploadError as exc:
            return JSONResponse({'error': exc.message, 'code': exc.code}, status_code=exc.status_code)
        if not path:
            return JSONResponse({'error': 'Choose an image to upload.', 'code': 'invalid'}, status_code=400)
        return JSONResponse({'url': path})

    # Video behavior stays unchanged: accepted MIME and container signatures.
    allowed = {'video/mp4': '.mp4', 'video/webm': '.webm'}
    extension = allowed.get(getattr(upload, 'content_type', ''))
    if not extension or not hasattr(upload, 'read'):
        return JSONResponse({'error': t(pick_lang(request), 'builder.upload_error')}, status_code=400)
    limit = 40 * 1024 * 1024
    data = await upload.read(limit + 1)
    signatures = {
        '.mp4': data[4:8] == b'ftyp', '.webm': data.startswith(b'\x1a\x45\xdf\xa3'),
    }
    if len(data) > limit:
        return JSONResponse({'error': 'Video exceeds the 40 MB limit.'}, status_code=413)
    if not signatures.get(extension):
        return JSONResponse({'error': 'Invalid or unsupported video file.'}, status_code=400)
    filename = f'home-{secrets.token_hex(16)}{extension}'
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        (UPLOAD_DIR / filename).write_bytes(data)
    except OSError:
        logging.getLogger(__name__).exception("Video upload failed")
        return JSONResponse({'error': 'The server could not save the video.'}, status_code=500)
    return JSONResponse({'url': f'/static/uploads/{filename}'})


CONTACT_DETAIL_KEYS = (
    "show_contact_link",
    "contact_intro_secondary",
    "contact_intro_en",
    "contact_email",
    "contact_details_secondary",
    "contact_details_en",
)


@app.get("/admin/contact-details", response_class=HTMLResponse)
async def admin_contact_details(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    lang = pick_lang(request)
    with get_db() as conn:
        settings = get_site_settings(conn)
    return render_template(
        request,
        "admin/contact_details.html",
        t(lang, "admin.contact_details"),
        {"settings": settings, "saved": request.query_params.get("saved") == "1", "active_admin": "contact_details"},
        user,
    )


@app.post("/admin/contact-details", response_class=HTMLResponse)
async def save_contact_details(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    lang = pick_lang(request)
    form = await request.form()
    stale = stale_language_form(request, form)
    if stale is not None:
        return stale
    with get_db() as conn:
        settings = get_site_settings(conn)
    for key in CONTACT_DETAIL_KEYS:
        if key in form:
            settings[key] = str(form.get(key, "")).strip()
    settings["show_contact_link"] = "1" if form.get("show_contact_link") else "0"
    if settings["contact_email"] and not valid_email(settings["contact_email"]):
        return render_template(
            request,
            "admin/contact_details.html",
            t(lang, "admin.contact_details"),
            {"settings": settings, "saved": False, "error": t(lang, "admin.invalid_destination"), "active_admin": "contact_details"},
            user,
            status_code=400,
        )
    with get_db() as conn:
        set_site_settings(conn, settings)
    return RedirectResponse("/admin/contact-details?saved=1", status_code=303)



@app.get("/admin/social-links", response_class=HTMLResponse)
async def admin_social_links(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    lang = pick_lang(request)
    with get_db() as conn:
        settings = get_site_settings(conn)
    return render_template(
        request,
        "admin/social_links.html",
        t(lang, "admin.social_links_title"),
        {"settings": settings, "saved": request.query_params.get("saved") == "1", "active_admin": "social_links", "social_platforms": SOCIAL_PLATFORMS},
        user,
    )


@app.post("/admin/social-links", response_class=HTMLResponse)
async def save_social_links(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    lang = pick_lang(request)
    form = await request.form()
    with get_db() as conn:
        settings = get_site_settings(conn)
    updated = dict(settings)
    for platform, name in SOCIAL_PLATFORMS:
        key = f"social_{platform}_url"
        value = str(form.get(key, "")).strip()
        if value and not valid_url(value):
            return render_template(
                request, "admin/social_links.html", t(lang, "admin.social_links_title"),
                {"settings": settings, "saved": False, "active_admin": "social_links",
                 "social_platforms": SOCIAL_PLATFORMS,
                 "error": f"{name}: " + t(lang, "admin.social_error")},
                user, status_code=400)
        updated[key] = value
        visible_key = f"social_{platform}_visible"
        updated[visible_key] = "1" if form.get(visible_key) else "0"
    with get_db() as conn:
        set_site_settings(conn, updated)
    return RedirectResponse("/admin/social-links?saved=1", status_code=303)

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


def language_page_context(request, settings, translations=None, error=None):
    secondary = secondary_language(settings)
    with get_db() as conn:
        existing = dict(conn.execute('SELECT translation_key, translation_value FROM ui_translations WHERE language_code=?',
                                    ((secondary or {}).get('code', settings.get('secondary_language_code', '')),)).fetchall())
    groups = {'navigation': [], 'contact': [], 'forms': [], 'common': [], 'other': [], 'admin': []}
    for key, value in TRANSLATIONS['en'].items():
        prefix = key.split('.')[0]
        group = {'nav': 'navigation', 'contact': 'contact', 'auth': 'forms', 'content': 'forms',
                 'common': 'common', 'home': 'other'}.get(prefix, 'admin')
        groups[group].append((key, value))
    return {'settings': settings, 'active_admin': 'language', 'builtin_languages': LANGUAGES,
            'detected': detect_locale(request.headers.get('accept-language', '')),
            'translation_groups': groups, 'custom_translations': existing if translations is None else translations,
            'saved': request.query_params.get('saved') == '1', 'error': error}


@app.get('/admin/language', response_class=HTMLResponse)
async def admin_language(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse('/login', status_code=303)
    with get_db() as conn:
        settings = get_site_settings(conn)
    return render_template(request, 'admin/language.html', t(pick_lang(request), 'language.title'),
                           language_page_context(request, settings), user)


@app.post('/admin/language', response_class=HTMLResponse)
async def save_language(request: Request) -> Response:
    user = require_user(request)
    if not user:
        return RedirectResponse('/login', status_code=303)
    lang = pick_lang(request)
    form = await request.form()
    with get_db() as conn:
        settings = get_site_settings(conn)
    updated = dict(settings)
    mode = str(form.get('secondary_language', '')).strip()
    code = str(form.get('secondary_language_code', '')).strip().lower()
    name = str(form.get('secondary_language_name', '')).strip()
    updated.update(secondary_language=mode, secondary_language_code=code, secondary_language_name=name,
                   show_language_switcher='1' if form.get('show_language_switcher') else '0')
    custom = {key: str(form.get(f'translation_{key}', '')).strip() for key in TRANSLATIONS['en']}
    invalid = mode not in ({'', 'custom'} | (set(LANGUAGES) - {'en'}))
    if mode == 'custom':
        invalid = invalid or not secondary_language(updated) or len(name) > 80 or not all(char.isalpha() or char in " -'." for char in name) or len(code) > 35
    if invalid or any(len(value) > 4000 for value in custom.values()):
        return render_template(request, 'admin/language.html', t(lang, 'language.title'),
                               language_page_context(request, updated, custom, t(lang, 'language.invalid')), user, status_code=400)
    secondary = secondary_language(updated)
    with get_db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        current = get_site_settings(conn)
        switch_secondary_content(conn, current, (secondary or {}).get('code', ''), set_site_settings)
        set_site_settings(conn, {key: updated[key] for key in ('secondary_language', 'secondary_language_code',
                                                              'secondary_language_name', 'show_language_switcher')})
        if mode == 'custom':
            # A changed custom code must not inherit another language's editor text.
            editor_code = str(form.get('translation_language_code', code)).lower()
            if editor_code == code:
                for key, value in custom.items():
                    if f'translation_{key}' in form:
                        conn.execute('''INSERT INTO ui_translations VALUES (?, ?, ?)
                            ON CONFLICT(language_code, translation_key) DO UPDATE SET translation_value=excluded.translation_value''',
                                     (code, key, value))
    return RedirectResponse('/admin/language?saved=1', status_code=303)


def _same_origin_admin_request(request: Request) -> bool:
    """Reject browser cross-origin mutation attempts, including sibling domains.

    This complements explicit form tokens on high-impact backup endpoints.
    """
    host = request.headers.get("host", "").lower()
    if not host:
        return False
    site = request.headers.get("sec-fetch-site", "").lower()
    if site in {"cross-site", "same-site"}:
        return False
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    for candidate in (origin, referer):
        if not candidate:
            continue
        try:
            parsed = urlsplit(candidate)
            if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != host:
                return False
        except ValueError:
            return False
    return True


@app.middleware('http')
async def first_run_gate(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and (
        request.url.path.startswith("/admin/") or request.url.path in {"/first-run", "/admin"}
    ):
        if not _same_origin_admin_request(request):
            return Response("Cross-origin administrative request rejected", status_code=403)
    # A cheap file identity check handles deletion/replacement and other workers;
    # schema checks occur only on startup or a changed installation file.
    try:
        stat = DB_PATH.stat()
        identity = (str(DB_PATH), stat.st_ino, stat.st_size == 0)
    except FileNotFoundError:
        identity = (str(DB_PATH), None)
    if getattr(app.state, 'database_identity', None) != identity:
        app.state.initialized = is_initialized(DB_PATH)
        app.state.database_identity = identity
        if app.state.initialized:
            refresh_secret()
    initialized = app.state.initialized
    path = request.url.path
    if path.rstrip('/') == '/first-run':
        if initialized:
            return RedirectResponse('/', status_code=303) if request.method in ('GET', 'HEAD') else HTMLResponse('FriPeri is already initialized.', status_code=409)
    elif not initialized and not path.startswith(('/static/', '/user_files/')):
        return RedirectResponse('/first-run', status_code=303)
    return await call_next(request)


SETUP_FIELDS = (
    ('site_name', 'Site name', 'text', True),
    ('site_description', 'Site description', 'text', True),
    ('hero_kicker_en', 'Short introduction — English', 'text', False),
    ('hero_title_en', 'Welcome heading — English', 'text', False),
    ('hero_copy_en', 'Welcome message — English', 'text', False),
    ('hero_kicker_secondary', 'Short introduction — translation', 'text', False),
    ('hero_title_secondary', 'Welcome heading — translation', 'text', False),
    ('hero_copy_secondary', 'Welcome message — translation', 'text', False),
    ('social_linkedin_url', 'LinkedIn URL', 'url', False),
    ('social_twitter_url', 'Twitter/X URL', 'url', False),
    ('contact_email', 'Contact email', 'email', False),
    ('hero_background_image_path', 'Homepage background image', 'text', False),
    ('admin_username', 'Admin username', 'text', True),
)


def setup_page(request, values=None, errors=None, status=200):
    token = contact_token()
    response = templates.TemplateResponse(request=request, name='first_run.html', context={
        'values': values if values is not None else setup_defaults(), 'errors': errors or {},
        'fields': SETUP_FIELDS, 'setup_token': token,
    }, status_code=status)
    response.set_cookie('friperi_setup', token, httponly=True, samesite='strict', secure=request.url.scheme == 'https', max_age=7200)
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/first-run', response_class=HTMLResponse)
async def first_run(request: Request):
    return setup_page(request)


@app.post('/first-run', response_class=HTMLResponse)
async def create_friperi(request: Request):
    if is_initialized(DB_PATH):
        return HTMLResponse('FriPeri is already initialized.', status_code=409)
    form = await request.form()
    token = str(form.get('setup_token', ''))
    if not valid_contact_token(token) or not hmac.compare_digest(token, request.cookies.get('friperi_setup', '')):
        return setup_page(request, errors={'setup': 'The setup form expired. Please try again.'}, status=403)
    values = setup_defaults()
    for key, *_ in SETUP_FIELDS:
        values[key] = str(form.get(key, '')).strip()
    values['secondary_language'] = str(form.get('secondary_language', ''))
    values['hero_background_enabled'] = str(form.get('hero_background_enabled', '0'))
    try:
        initialize_database(DB_PATH, values, values['admin_username'],
                            str(form.get('admin_password', '')), str(form.get('password_confirmation', '')))
    except SetupError as exc:
        return setup_page(request, values, exc.errors, 400)
    except (OSError, sqlite3.Error, RuntimeError):
        return setup_page(request, values, {'setup': 'FriPeri could not create the database. Check database directory permissions and available disk space, then try again.'}, 500)
    app.state.initialized = True
    refresh_secret()
    response = RedirectResponse('/login?setup=ready', status_code=303)
    response.delete_cookie('friperi_setup')
    return response


# Account administration is intentionally not self-service. Only an admin can
# assign roles or select a content creator's allowed categories.
@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request) -> Response:
    username = require_user(request)
    if not username:
        return RedirectResponse("/login", status_code=303)
    account = actor(request)
    if account is None:
        return RedirectResponse("/login", status_code=303)
    if account["role"] == "editor":
        with get_db() as conn:
            creators = [dict(row) for row in conn.execute(
                "SELECT id, username FROM users WHERE role='cc' ORDER BY username COLLATE NOCASE")]
            categories = [dict(row) for row in conn.execute(
                "SELECT id, name FROM categories ORDER BY name COLLATE NOCASE")]
            for person in creators:
                person["category_ids"] = [row[0] for row in conn.execute(
                    "SELECT category_id FROM user_categories WHERE user_id=?", (person["id"],))]
        return render_template(request, "admin/category_access.html", "Category access", {
            "active_admin": "users", "creators": creators,
            "categories": categories, "editor_token": custom_home_token(username),
        }, username)
    if account["role"] != "admin":
        return Response("Forbidden", status_code=403)
    with get_db() as conn:
        people = [dict(row) for row in conn.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY id")]
        categories = [dict(row) for row in conn.execute(
            "SELECT id, name FROM categories ORDER BY name")]
        for person in people:
            person["category_ids"] = [r[0] for r in conn.execute(
                "SELECT category_id FROM user_categories WHERE user_id=?",
                (person["id"],))]
    return render_template(request, "admin/users.html", "Users", {
        "active_admin": "users", "accounts": people,
        "categories": categories, "editor_token": custom_home_token(username),
    }, username)


def _user_admin_form_valid(request: Request, form: Any) -> bool:
    username = require_user(request)
    return bool(username and form.get("editor_token")
                and hmac.compare_digest(str(form.get("editor_token")), custom_home_token(username)))


def _selected_categories(conn: sqlite3.Connection, form: Any) -> list[int] | None:
    raw = form.getlist("categories") if hasattr(form, "getlist") else []
    if any(not re.fullmatch(r"[0-9]{1,18}", str(value)) for value in raw):
        return None
    ids = sorted(set(int(value) for value in raw))
    if ids:
        placeholders = ",".join("?" for _ in ids)
        found = conn.execute(f"SELECT COUNT(*) FROM categories WHERE id IN ({placeholders})", ids).fetchone()[0]
        if found != len(ids):
            return None
    return ids


@app.post("/admin/users")
async def create_account(request: Request) -> Response:
    form = await request.form()
    if not _user_admin_form_valid(request, form):
        return Response("Forbidden", status_code=403)
    name = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    role = str(form.get("role", ""))
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", name) or role not in {"cc", "editor", "admin"} or len(password) < 8:
        return Response("Invalid username, role or password (minimum eight characters)", status_code=400)
    with get_db() as conn:
        ids = _selected_categories(conn, form)
        if ids is None:
            return Response("Invalid category assignment", status_code=400)
        salt, secret = hash_password(password)
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, password_salt, password_hash, created_at, role) VALUES (?, ?, ?, ?, ?)",
                (name, salt, secret, now_iso(), role))
        except sqlite3.IntegrityError:
            return Response("Username already exists", status_code=409)
        for cid in ids if role == "cc" else []:
            conn.execute("INSERT INTO user_categories (user_id, category_id) VALUES (?, ?)",
                         (cursor.lastrowid, cid))
    return RedirectResponse("/admin/users", status_code=303)


@app.post("/admin/users/{account_id:int}/categories")
async def assign_creator_categories(account_id: int, request: Request) -> Response:
    """Editor/admin may only change category grants of content creators."""
    account = actor(request)
    if account is None or account["role"] not in ("admin", "editor"):
        return Response("Forbidden", status_code=403)
    form = await request.form()
    if not _user_admin_form_valid(request, form):
        return Response("Forbidden", status_code=403)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        target = conn.execute("SELECT role FROM users WHERE id=?", (account_id,)).fetchone()
        if target is None:
            return Response(status_code=404)
        if target["role"] != "cc":
            return Response("Category grants can only be assigned to content creators", status_code=403)
        category_ids = _selected_categories(conn, form)
        if category_ids is None:
            return Response("Invalid category selection", status_code=400)
        existing = {row[0] for row in conn.execute(
            "SELECT category_id FROM user_categories WHERE user_id=?", (account_id,))}
        if existing != set(category_ids):
            conn.execute("DELETE FROM user_categories WHERE user_id=?", (account_id,))
            conn.executemany(
                "INSERT INTO user_categories (user_id, category_id) VALUES (?, ?)",
                [(account_id, category_id) for category_id in category_ids])
            conn.execute("UPDATE users SET session_epoch=? WHERE id=?",
                         (time.time_ns(), account_id))
    return RedirectResponse("/admin/users", status_code=303)


@app.post("/admin/users/{account_id:int}")
async def update_account(account_id: int, request: Request) -> Response:
    form = await request.form()
    if not _user_admin_form_valid(request, form):
        return Response("Forbidden", status_code=403)
    role = str(form.get("role", ""))
    password = str(form.get("password", ""))
    if role not in {"cc", "editor", "admin"} or (password and len(password) < 8):
        return Response("Invalid role or password", status_code=400)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT id, role, username FROM users WHERE id=?", (account_id,)).fetchone()
        if existing is None:
            return Response(status_code=404)
        me = actor(request)
        if existing["id"] == me["id"] and role != "admin":
            return Response("You cannot demote your own admin account", status_code=403)
        if existing["role"] == "admin" and role != "admin" and conn.execute(
                "SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0] <= 1:
            return Response("At least one admin is required", status_code=409)
        ids = _selected_categories(conn, form)
        if ids is None:
            return Response("Invalid category assignment", status_code=400)
        # Revoke old tokens after a role change, password reset or grant update.
        conn.execute("UPDATE users SET role=?, session_epoch=? WHERE id=?",
                     (role, time.time_ns(), account_id))
        if password:
            salt, secret = hash_password(password)
            conn.execute("UPDATE users SET password_salt=?, password_hash=? WHERE id=?",
                         (salt, secret, account_id))
        conn.execute("DELETE FROM user_categories WHERE user_id=?", (account_id,))
        for cid in ids if role == "cc" else []:
            conn.execute("INSERT INTO user_categories (user_id, category_id) VALUES (?, ?)",
                         (account_id, cid))
    return RedirectResponse("/admin/users", status_code=303)


@app.post("/admin/users/{account_id:int}/delete")
async def delete_account(account_id: int, request: Request) -> Response:
    form = await request.form()
    if not _user_admin_form_valid(request, form):
        return Response("Forbidden", status_code=403)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT role FROM users WHERE id=?", (account_id,)).fetchone()
        if existing is None:
            return Response(status_code=404)
        me = actor(request)
        if me["id"] == account_id:
            return Response("Cannot delete your own account", status_code=403)
        if existing["role"] == "admin" and conn.execute(
                "SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0] <= 1:
            return Response("At least one admin is required", status_code=409)
        conn.execute("UPDATE posts SET author_id=NULL WHERE author_id=?", (account_id,))
        conn.execute("DELETE FROM user_categories WHERE user_id=?", (account_id,))
        conn.execute("DELETE FROM users WHERE id=?", (account_id,))
    return RedirectResponse("/admin/users", status_code=303)


def privilege_site_name():
    with get_db() as conn:
        return get_site_settings(conn).get("site_name", "FriPeri")


# Directory-scoped privileges are deliberately isolated from CMS users.
app.include_router(create_router(
    db=get_db,
    static_dir=USER_FILES_DIR,
    secret=lambda: SECRET_KEY,
    secure_cookie=SESSION_COOKIE_SECURE,
    password_hash=hash_password,
    password_verify=verify_password,
    admin_account=actor,
    admin_token=lambda request, username: settings_form_token(request, username),
    now=now_iso,
    site_name=privilege_site_name,
    render_admin=lambda request, template, title, context, username:
        render_template(request, template, title, context, username),
))


# Root Files: explicitly published, administrator-managed root-level documents.
@app.api_route("/{root_name}", methods=["GET", "HEAD"], include_in_schema=False)
async def published_root_file(request: Request, root_name: str) -> Response:
    if not root_filename(root_name):
        return Response(status_code=404)
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT published FROM root_files WHERE name=?", (root_name,)).fetchone()
    except sqlite3.Error:
        return Response(status_code=503, headers={"Cache-Control": "no-store"})
    if not row or not row["published"]:
        return Response(status_code=404)
    path = safe_root_file(ROOT_FILES_DIR, root_name)
    if not path or not path.is_file():
        return Response(status_code=404)
    return FileResponse(path, media_type=ROOT_FILE_TYPES[path.suffix.lower()],
                        headers={"Cache-Control": "public, max-age=300",
                                 "X-Content-Type-Options": "nosniff"})


@app.get("/admin/root-files", response_class=HTMLResponse)
async def admin_root_files(request: Request, edit: str = "") -> Response:
    account = actor(request)
    if not account:
        return RedirectResponse("/login", status_code=303)
    if account["role"] != "admin":
        return Response(status_code=403)
    with get_db() as conn:
        records = [dict(row) for row in conn.execute(
            "SELECT name,published,updated_at FROM root_files ORDER BY name")]
    editing = None
    if edit:
        path = safe_root_file(ROOT_FILES_DIR, edit)
        if not edit.endswith(".txt") or not path or not path.is_file() or not any(r["name"] == edit for r in records):
            return Response(status_code=404)
        if path.stat().st_size > 1024 * 1024:
            return Response(status_code=400)
        editing = {"name": edit, "content": path.read_text(encoding="utf-8")}
    return render_template(request, "admin/root_files.html", "Root Files", {
        "editing": editing,
        "active_admin": "root_files", "root_files": records,
        "settings_token": settings_form_token(request, account["username"]),
    }, account["username"])


@app.post("/admin/root-files")
async def admin_root_files_action(request: Request) -> Response:
    account = actor(request)
    if not account or account["role"] != "admin":
        return Response(status_code=403)
    form = await request.form()
    token = str(form.get("settings_token", ""))
    if not hmac.compare_digest(token, settings_form_token(request, account["username"])):
        return Response(status_code=403)
    name = str(form.get("name", "")).strip()
    action = str(form.get("action", ""))
    if not root_filename(name) or action not in {"upload", "create", "edit", "publish", "disable", "delete"}:
        return Response(status_code=400)
    path = safe_root_file(ROOT_FILES_DIR, name)
    if path is None:
        return Response(status_code=400)
    if action in {"upload", "create", "edit"}:
        if action == "upload":
            upload = form.get("file")
            if not isinstance(upload, StarletteUploadFile):
                return Response("Select a file", status_code=400)
            if upload.filename != name:
                return Response("File name must match the publishing name", status_code=400)
            data = await upload.read(1024 * 1024 + 1)
        else:
            if not name.endswith(".txt"):
                return Response("Only .txt files can be created or edited", status_code=400)
            with get_db() as conn:
                exists = conn.execute("SELECT 1 FROM root_files WHERE name=?", (name,)).fetchone()
            if action == "create" and (exists or path.exists()):
                return Response("File already exists; use Edit", status_code=409)
            if action == "edit" and (not exists or not path.is_file()):
                return Response(status_code=404)
            data = str(form.get("content", "")).encode("utf-8")
        if not data or len(data) > 1024 * 1024 or b"\x00" in data:
            return Response("Invalid file (max 1 MB, plain text)", status_code=400)
        try:
            decoded = data.decode("utf-8")
        except UnicodeDecodeError:
            return Response("UTF-8 text required", status_code=400)
        if name.endswith(".html") and decoded.strip() != f"google-site-verification: {name}":
            return Response("Google verification HTML must contain only its verification token", status_code=400)
        ROOT_FILES_DIR.mkdir(parents=True, exist_ok=True)
        temp = ROOT_FILES_DIR / (".upload-" + secrets.token_hex(16))
        try:
            with temp.open("xb") as stream:
                stream.write(data)
            os.chmod(temp, 0o600)
            if path.is_symlink():
                return Response(status_code=400)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
        with get_db() as conn:
            conn.execute("""INSERT INTO root_files(name,published,updated_at) VALUES(?,0,?)
                ON CONFLICT(name) DO UPDATE SET published=0,updated_at=excluded.updated_at""",
                         (name, now_iso()))
    else:
        with get_db() as conn:
            row = conn.execute("SELECT 1 FROM root_files WHERE name=?", (name,)).fetchone()
            if not row:
                return Response(status_code=404)
            if action == "publish":
                if not path.is_file():
                    return Response(status_code=404)
                conn.execute("UPDATE root_files SET published=1,updated_at=? WHERE name=?",
                             (now_iso(), name))
            elif action == "disable":
                conn.execute("UPDATE root_files SET published=0,updated_at=? WHERE name=?",
                             (now_iso(), name))
            else:
                conn.execute("DELETE FROM root_files WHERE name=?", (name,))
                path.unlink(missing_ok=True)
    return RedirectResponse("/admin/root-files", status_code=303)
