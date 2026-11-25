"""Safe root-file metadata: no arbitrary file hosting or route overrides."""
from pathlib import Path
import re

ROOT_FILE_TYPES = {".txt": "text/plain; charset=utf-8", ".html": "text/html; charset=utf-8"}
ROOT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\.(?:txt|html)$")
# Reserved names belong to existing application routes or web infrastructure.
RESERVED = frozenset({"robots.txt", "sitemap.xml", "favicon.ico", "index.html"})


def root_filename(name: str) -> bool:
    if not ROOT_NAME_RE.fullmatch(name) or name in RESERVED or ".." in name:
        return False
    # Prevent root-file hosting from overriding arbitrary application routes.
    return name.endswith(".txt") or bool(
        re.fullmatch(r"google[A-Za-z0-9_-]{8,90}\.html", name))


def safe_root_file(root: Path, name: str) -> Path | None:
    if not root_filename(name) or root.is_symlink():
        return None
    path = root / name
    if path.is_symlink() or (root.exists() and root.resolve() != path.parent.resolve()):
        return None
    return path


def install_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS root_files(
        name TEXT PRIMARY KEY,
        published INTEGER NOT NULL DEFAULT 0 CHECK(published IN(0,1)),
        updated_at TEXT NOT NULL
    )""")
