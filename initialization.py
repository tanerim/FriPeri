"""Shared schema, migrations and atomic first installation; no application imports."""
from __future__ import annotations
import hashlib
import hmac
import os
import secrets
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from contextlib import closing
from language_migration import backup_before_language_migration, migrate_languages
from site_defaults import DEFAULT_SITE_SETTINGS
from privileges import install_schema as install_privilege_schema
from custom_home import starter_document

class SiteConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def connect_database(path: Path, *, create: bool = False) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path) if create else path.resolve().as_uri() + "?mode=rw", uri=not create, factory=SiteConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def set_site_settings(conn: sqlite3.Connection, settings: dict[str, str]) -> None:
    for key, value in settings.items():
        conn.execute(
            """
            INSERT INTO site_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, now_iso()),
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 140_000
    ).hex()
    return salt, password_hash


def verify_password(password: str, salt: str, password_hash: str) -> bool:
    _, candidate = hash_password(password, salt)
    return hmac.compare_digest(candidate, password_hash)


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def add_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if column not in table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def migrate_database(path: Path, settings=None, username=None, password=None) -> None:
    backup_before_language_migration(path)
    with connect_database(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute('''CREATE TABLE IF NOT EXISTS custom_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            documents_json TEXT NOT NULL DEFAULT '{}',
            show_in_menu INTEGER NOT NULL DEFAULT 0,
            published INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS site_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                slug TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                menu_label_secondary TEXT NOT NULL DEFAULT '',
                menu_label_en TEXT NOT NULL DEFAULT '',
                show_in_menu INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 100,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                excerpt TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                slug TEXT NOT NULL UNIQUE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS post_tags (
                post_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (post_id, tag_id),
                FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute("""CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS blocked_contact_emails (
            email TEXT PRIMARY KEY COLLATE NOCASE,
            blocked_at TEXT NOT NULL
        )""")
        install_privilege_schema(conn)
        # Role-based access control: legacy users retain full administrator access.
        # Per-category archive presentation, independent of site-wide Design colors.
        add_column(conn, "categories", "archive_design_json", "TEXT NOT NULL DEFAULT '{}'")
        add_column(conn, "users", "role", "TEXT NOT NULL DEFAULT 'admin'")
        add_column(conn, "users", "session_epoch", "INTEGER NOT NULL DEFAULT 0")
        add_column(conn, "posts", "author_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL")
        conn.execute("""CREATE TABLE IF NOT EXISTS user_categories (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, category_id)
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS posts_author_id_idx ON posts(author_id)")
        add_column(conn, "posts", "body_html", "TEXT NOT NULL DEFAULT ''")
        add_column(conn, "posts", "image_path", "TEXT NOT NULL DEFAULT ''")
        legacy_categories = "category_id" not in table_columns(conn, "posts")
        add_column(conn, "posts", "category_id", "INTEGER REFERENCES categories(id) ON DELETE SET NULL")
        # Existing SQLite tables need no destructive rebuild: the trigger provides
        # SET NULL semantics even for the original column without a foreign key.
        conn.execute("""CREATE TRIGGER IF NOT EXISTS category_posts_set_null
            BEFORE DELETE ON categories BEGIN
                UPDATE posts SET category_id = NULL WHERE category_id = OLD.id;
            END""")
        conn.execute("""CREATE TABLE IF NOT EXISTS custom_menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label_secondary TEXT NOT NULL DEFAULT '', label_en TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL, sort_order INTEGER NOT NULL DEFAULT 100,
            show_in_menu INTEGER NOT NULL DEFAULT 1,
            new_tab INTEGER NOT NULL DEFAULT 0
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS revoked_session_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            revoked_at TEXT NOT NULL
        )""")
        add_column(conn, "posts", "updated_at", "TEXT NOT NULL DEFAULT ''")
        add_column(conn, "posts", "status", "TEXT NOT NULL DEFAULT 'published'")
        add_column(conn, "posts", "post_blocks_json", "TEXT NOT NULL DEFAULT ''")
        add_column(conn, "posts", "editor_creation_key", "TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS posts_editor_creation_key ON posts(editor_creation_key)")

        migrate_languages(conn, add_column, set_site_settings)

        for key, value in DEFAULT_SITE_SETTINGS.items():
            conn.execute(
                """
                INSERT OR IGNORE INTO site_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, value, now_iso()),
            )

        if username is not None:
            salt, password_hash = hash_password(password)
            conn.execute(
                "INSERT INTO users (username, password_salt, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (username, salt, password_hash, now_iso()),
            )

        seed_categories = [
            ("Blog", "blog", "", "", "Blog", 1, 10),
            ("Notes", "notlar", "", "", "Notes", 1, 20),
        ]
        if not conn.execute(
            "SELECT 1 FROM site_settings WHERE key = 'seed_descriptions_cleared'"
        ).fetchone():
            # Remove only the old defaults; preserve customized descriptions.
            conn.executemany(
                "UPDATE categories SET description = '' WHERE slug = ? AND description = ?",
                [("blog", "Güncel yazılar"), ("notlar", "Araştırma ve çalışma notları")],
            )
            set_site_settings(conn, {"seed_descriptions_cleared": "1"})
        seed_done = conn.execute("SELECT 1 FROM site_settings WHERE key = 'categories_seeded'").fetchone()
        for name, slug, desc, label_secondary, label_en, show, order in ([] if seed_done else seed_categories):
            if not conn.execute("SELECT 1 FROM categories WHERE slug = ?", (slug,)).fetchone():
                conn.execute(
                    """
                    INSERT INTO categories
                    (name, slug, description, menu_label_secondary, menu_label_en, show_in_menu, sort_order, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (name, slug, desc, label_secondary, label_en, show, order, now_iso()),
                )

        blog = conn.execute("SELECT id FROM categories WHERE slug = 'blog'").fetchone()
        if blog and legacy_categories:
            conn.execute("UPDATE posts SET category_id = ? WHERE category_id IS NULL", (blog["id"],))
        set_site_settings(conn, {"categories_seeded": "1"})
        conn.execute("UPDATE posts SET body_html = body WHERE body_html = ''")
        conn.execute("UPDATE posts SET updated_at = created_at WHERE updated_at = ''")



        if settings is not None:
            set_site_settings(conn, settings)


CORE_COLUMNS = {
    'users': {'id', 'username', 'password_salt', 'password_hash', 'created_at'},
    'site_settings': {'key', 'value', 'updated_at'},
    'posts': {'id', 'title', 'slug', 'excerpt', 'body', 'created_at'},
    'categories': {'id', 'name', 'slug'},
    'tags': {'id', 'name', 'slug'},
    'post_tags': {'post_id', 'tag_id'},
}


def is_initialized(path: Path) -> bool:
    """Read-only recognition also accepts old schemas that startup can migrate."""
    if not path.is_file():
        return False
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
            for table, required in CORE_COLUMNS.items():
                if not required <= {row[1] for row in conn.execute(f'PRAGMA table_info({table})')}:
                    return False
            return bool(conn.execute("SELECT 1 FROM users WHERE username != '' AND password_salt != '' AND length(password_hash)=64").fetchone()
                        and conn.execute("SELECT 1 FROM site_settings WHERE key='site_name' AND value != ''").fetchone())
    except (sqlite3.DatabaseError, OSError):
        return False


def validate_database(path: Path) -> bool:
    if not is_initialized(path):
        return False
    with connect_database(path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {'custom_menu_items', 'ui_translations'} <= tables and conn.execute('PRAGMA quick_check').fetchone()[0] == 'ok'


class SetupError(ValueError):
    def __init__(self, errors):
        super().__init__('Setup validation failed.')
        self.errors = errors


def setup_defaults():
    values = dict(DEFAULT_SITE_SETTINGS)
    values.update(site_name=os.getenv('SITE_NAME', 'My Site'), admin_username='admin')
    values['site_description'] = os.getenv('SITE_DESCRIPTION', 'News, ideas, and updates from our website.')
    values['hero_kicker_en'] = os.getenv('HERO_KICKER_EN', 'Ideas, updates, and stories')
    values['hero_copy_en'] = os.getenv('HERO_COPY_EN', 'Discover what we are working on and explore our latest updates.')
    values['hero_title_en'] = values['site_name']
    return values


def validate_setup(values, password, confirmation):
    from urllib.parse import urlsplit
    import re
    errors = {}
    for key in ('site_name', 'site_description', 'admin_username'):
        if not values.get(key, '').strip():
            errors[key] = 'This field is required.'
    for key, value in values.items():
        if len(value) > 4000:
            errors[key] = 'Use at most 4,000 characters.'
    if len(password) < 8:
        errors['admin_password'] = 'Use at least 8 characters.'
    if len(password) > 1024:
        errors['admin_password'] = 'Use at most 1,024 characters.'
    if password != confirmation:
        errors['password_confirmation'] = 'Passwords do not match.'
    if values.get('secondary_language', '') not in ('', 'tr', 'de', 'fr'):
        errors['secondary_language'] = 'Choose a supported language.'
    for key in ('social_linkedin_url', 'social_twitter_url'):
        value = values.get(key, '')
        try:
            parsed = urlsplit(value)
            if value and (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.port == 0):
                errors[key] = 'Enter a complete HTTP or HTTPS URL.'
        except ValueError:
            errors[key] = 'Enter a valid URL.'
    email = values.get('contact_email', '')
    if email and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        errors['contact_email'] = 'Enter a valid email address.'
    if values.get('hero_background_enabled', '0') not in ('0', '1'):
        errors['hero_background_enabled'] = 'Choose enabled or disabled.'
    if errors:
        raise SetupError(errors)


def initialize_database(path: Path, settings: dict, username: str, password: str, confirmation: str):
    """Build privately, verify, then publish atomically under a cross-process lock."""
    values = {**settings, 'admin_username': username}
    validate_setup(values, password, confirmation)
    path = path.absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    # flock is released even after process failure. The lock file is runtime data.
    import fcntl
    with open(path.parent / '.setup.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if is_initialized(path):
            raise SetupError({'setup': 'FriPeri is already initialized.'})
        if path.is_symlink() or (path.exists() and path.stat().st_size):
            raise SetupError({'setup': 'An invalid, nonempty database already exists. Back it up and use the reset utility before setup.'})
        descriptor, temporary = tempfile.mkstemp(prefix='.friperi-setup-', suffix='.db', dir=path.parent)
        os.close(descriptor)
        staging = Path(temporary)
        try:
            settings = dict(settings)
            settings.pop('admin_username', None)
            defaults = setup_defaults()
            for key in ('hero_kicker_en', 'hero_copy_en'):
                settings[key] = settings.get(key) or defaults[key]
            settings['hero_title_en'] = settings.get('hero_title_en') or settings['site_name']
            settings.setdefault('homepage_mode', 'custom')
            if settings['homepage_mode'] == 'custom' and not settings.get('custom_home_en'):
                settings['custom_home_en'] = starter_document(settings)
                if settings.get('secondary_language') and not settings.get('custom_home_secondary'):
                    settings['custom_home_secondary'] = starter_document(settings, 'secondary')
            settings['secondary_content_code'] = settings.get('secondary_language', '')
            settings['session_secret'] = secrets.token_urlsafe(48)
            migrate_database(staging, settings, username, password)
            if not validate_database(staging):
                raise RuntimeError('Database verification failed.')
            os.replace(staging, path)
        finally:
            for artifact in (staging, Path(str(staging) + '-journal'), Path(str(staging) + '-wal'), Path(str(staging) + '-shm')):
                artifact.unlink(missing_ok=True)
