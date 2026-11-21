"""Bounded, verified, SQLite-consistent backups for FriPeri.

The archive is administrator-controlled, never used as an arbitrary filesystem
extractor. Live restores should be coordinated with a maintenance window.
"""
from __future__ import annotations

import os
import re
import sqlite3
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

MAX_UPLOAD_BYTES = 256 * 1024 * 1024
MAX_UNPACKED_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 2000
MAX_MEMBER_BYTES = 128 * 1024 * 1024
_CHUNK = 1024 * 1024
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico"}
_BACKUP_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\\.zip$")


class BackupError(ValueError):
    """Invalid backup, insufficient space or rejected restore contents."""


def safe_backup_path(directory: Path, name: str) -> Path:
    if not _BACKUP_NAME.fullmatch(name) or name.startswith("."):
        raise BackupError("Invalid backup name")
    path = directory / name
    if path.is_symlink() or path.parent.resolve() != directory.resolve():
        raise BackupError("Unsafe backup path")
    return path


def _allowed_member(name: str) -> bool:
    if "\\" in name or name.startswith("/") or "//" in name or name.endswith("/"):
        return False
    p = PurePosixPath(name)
    if any(part in ("", ".", "..") for part in p.parts):
        return False
    if name in {"db/site.db", "env/.env"}:
        return True
    if len(p.parts) < 3 or p.parts[:2] not in (("static", "uploads"), ("static", "images")):
        return False
    return p.suffix.lower() in _IMAGE_SUFFIXES | {".mp4", ".webm"} if p.parts[1] == "uploads" else p.suffix.lower() in _IMAGE_SUFFIXES


def _validated_archive(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = zf.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise BackupError("Too many files in archive")
    seen = set()
    total = 0
    for member in members:
        name = member.filename
        # ZIP may represent directories; ignore these only if the path itself is safe.
        if member.is_dir():
            bare = name.rstrip("/")
            if not bare or "\\" in bare or bare.startswith("/") or ".." in PurePosixPath(bare).parts:
                raise BackupError("Invalid archive directory")
            continue
        if not _allowed_member(name):
            raise BackupError("Archive contains an unsupported path or file type")
        if name in seen:
            raise BackupError("Duplicate archive entry")
        seen.add(name)
        mode = member.external_attr >> 16
        if stat.S_IFMT(mode) == stat.S_IFLNK:
            raise BackupError("Symlinks are not allowed")
        if member.file_size > MAX_MEMBER_BYTES or member.file_size < 0:
            raise BackupError("Archive file exceeds size limit")
        total += member.file_size
        if total > MAX_UNPACKED_BYTES:
            raise BackupError("Unpacked archive exceeds limit")
        if member.compress_size and member.file_size / member.compress_size > 250:
            raise BackupError("Suspicious compression ratio")
    if "db/site.db" not in seen:
        raise BackupError("Backup does not contain a SQLite database")
    return [m for m in members if not m.is_dir()]


def _copy_limited(src, dst, limit: int) -> None:
    size = 0
    while True:
        data = src.read(_CHUNK)
        if not data:
            break
        size += len(data)
        if size > limit:
            raise BackupError("Backup exceeded its declared size")
        dst.write(data)


def _sqlite_snapshot(db_path: Path, destination: Path) -> None:
    if not db_path.is_file():
        raise BackupError("Database not found")
    with sqlite3.connect(str(db_path)) as source, sqlite3.connect(str(destination)) as target:
        source.backup(target)


def create_backup(destination: Path, db_path: Path, static_dir: Path, upload_dir: Path, env_path: Path) -> None:
    """Write to an exclusive destination; capture SQLite through its backup API."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".backup-stage-", dir=destination.parent) as temp:
        snapshot = Path(temp) / "site.db"
        _sqlite_snapshot(db_path, snapshot)
        with destination.open("xb") as output:
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                zf.write(snapshot, "db/site.db")
                for folder in (static_dir / "images", upload_dir):
                    if not folder.is_dir():
                        continue
                    for path in sorted(folder.rglob("*")):
                        if not path.is_file() or path.is_symlink():
                            continue
                        if folder == upload_dir:
                            archive_name = "static/uploads/" + path.relative_to(folder).as_posix()
                        else:
                            archive_name = "static/images/" + path.relative_to(folder).as_posix()
                        if _allowed_member(archive_name):
                            zf.write(path, archive_name)
                if env_path.is_file() and not env_path.is_symlink():
                    zf.write(env_path, "env/.env")


def validate_backup(path: Path) -> None:
    if not path.is_file() or path.stat().st_size > MAX_UPLOAD_BYTES:
        raise BackupError("Invalid backup size")
    with zipfile.ZipFile(path) as archive:
        _validated_archive(archive)
        if archive.testzip() is not None:
            raise BackupError("Corrupt archive member")


def restore_backup(path: Path, db_path: Path, static_dir: Path, upload_dir: Path, env_path: Path) -> None:
    """Validate and stage every member before touching the running installation."""
    validate_backup(path)
    with tempfile.TemporaryDirectory(prefix=".restore-stage-", dir=path.parent) as temp:
        staging = Path(temp)
        with zipfile.ZipFile(path) as archive:
            members = _validated_archive(archive)
            for member in members:
                staged_file = staging.joinpath(*PurePosixPath(member.filename).parts)
                staged_file.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, staged_file.open("xb") as target:
                    _copy_limited(source, target, min(member.file_size, MAX_MEMBER_BYTES))
        staged_db = staging / "db" / "site.db"
        with sqlite3.connect(str(staged_db)) as incoming:
            if incoming.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise BackupError("Backup database integrity check failed")
            tables = {row[0] for row in incoming.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"users", "site_settings"}.issubset(tables):
                raise BackupError("Unrecognized database schema")

        # Existing DB is never unlinked or replaced with raw bytes. SQLite's
        # backup API writes a consistent, complete snapshot from the staged DB.
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(staged_db)) as source, sqlite3.connect(str(db_path)) as target:
            source.backup(target)

        for member in members:
            if not member.filename.startswith("static/"):
                continue
            rel = PurePosixPath(member.filename)
            if rel.parts[1] == "uploads":
                target = upload_dir.joinpath(*rel.parts[2:])
            else:
                target = static_dir.joinpath(*rel.parts[1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            # Atomic replacement of one file; never create links from the archive.
            fd, tmp_name = tempfile.mkstemp(prefix=".friperi-restore-", dir=target.parent)
            try:
                with os.fdopen(fd, "wb") as output, (staging / member.filename).open("rb") as source:
                    _copy_limited(source, output, MAX_MEMBER_BYTES)
                os.replace(tmp_name, target)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
        staged_env = staging / "env" / ".env"
        if staged_env.is_file():
            env_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix=".friperi-env-", dir=env_path.parent)
            try:
                with os.fdopen(fd, "wb") as out, staged_env.open("rb") as source:
                    _copy_limited(source, out, MAX_MEMBER_BYTES)
                os.replace(tmp_name, env_path)
                os.chmod(env_path, 0o600)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
