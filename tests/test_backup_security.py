"""Unit tests for backup validation, SQLite snapshots and safe restores."""
import io
import sqlite3
import zipfile

import pytest

from backup_security import (
    BackupError, _validated_archive, create_backup, restore_backup,
    safe_backup_path, validate_backup,
)


def make_db(path, name="original"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
        con.execute("CREATE TABLE site_settings (key TEXT, value TEXT)")
        con.execute("INSERT INTO users (username) VALUES (?)", (name,))
        con.commit()


def read_user(path):
    with sqlite3.connect(path) as con:
        return con.execute("SELECT username FROM users LIMIT 1").fetchone()[0]


def test_backup_is_consistent_and_can_restore_configured_db(tmp_path):
    db = tmp_path / "private" / "configured.sqlite3"
    make_db(db)
    static = tmp_path / "static"
    images = static / "images"
    uploads = tmp_path / "media"
    images.mkdir(parents=True)
    uploads.mkdir(parents=True)
    (images / "sample.png").write_bytes(b"png")
    (uploads / "photo.webp").write_bytes(b"webp")
    environment = tmp_path / ".env"
    environment.write_text("SITE_NAME=Example", encoding="utf-8")
    folder = tmp_path / "backups"
    backup = safe_backup_path(folder, "backup-001.zip")
    create_backup(backup, db, static, uploads, environment)
    validate_backup(backup)
    with zipfile.ZipFile(backup) as archive:
        assert {"db/site.db", "static/uploads/photo.webp", "static/images/sample.png", "env/.env"}.issubset(
            archive.namelist()
        )

    with sqlite3.connect(db) as con:
        con.execute("UPDATE users SET username='changed'")
        con.commit()
    (uploads / "photo.webp").unlink()
    restore_backup(backup, db, static, uploads, environment)
    assert read_user(db) == "original"
    assert (uploads / "photo.webp").read_bytes() == b"webp"


@pytest.mark.parametrize("name", ["../secret.zip", "/tmp/f.zip", ".hidden.zip", "file.txt", "dir/name.zip"])
def test_backup_names_cannot_escape_directory(tmp_path, name):
    with pytest.raises(BackupError):
        safe_backup_path(tmp_path, name)


@pytest.mark.parametrize("member", [
    "../escape.txt", "static/uploads/../../secrets.env",
    "static/evil.js", "static/uploads/script.js", "/etc/passwd",
    "static\\uploads\\evil.jpg",
])
def test_archive_rejects_untrusted_paths(member):
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w") as zf:
        zf.writestr("db/site.db", b"fake")
        zf.writestr(member, b"bad")
    memory.seek(0)
    with zipfile.ZipFile(memory) as archive:
        with pytest.raises(BackupError):
            _validated_archive(archive)


def test_archive_requires_database(tmp_path):
    archive = tmp_path / "only-assets.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("static/uploads/a.png", b"fake")
    with pytest.raises(BackupError):
        validate_backup(archive)


def test_corrupt_restore_does_not_replace_running_database(tmp_path):
    db = tmp_path / "db" / "live.db"
    make_db(db, "safe")
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("db/site.db", b"not sqlite")
    with pytest.raises((BackupError, sqlite3.DatabaseError)):
        restore_backup(archive, db, tmp_path / "static", tmp_path / "uploads", tmp_path / ".env")
    assert read_user(db) == "safe"

def test_root_file_is_backed_up_and_restored(tmp_path):
    from root_files import install_schema
    db = tmp_path / "db" / "site.db"
    make_db(db)
    with sqlite3.connect(db) as conn:
        install_schema(conn)
        conn.execute("INSERT INTO root_files(name,published,updated_at) VALUES('app-ads.txt',1,'now')")
    static = tmp_path / "static"
    images = static / "images"
    images.mkdir(parents=True)
    uploads = static / "uploads"
    uploads.mkdir(parents=True)
    root = tmp_path / "root_files"
    root.mkdir()
    (root / "app-ads.txt").write_text("google.com, publisher, DIRECT, relationship")
    archive = tmp_path / "backup.zip"
    create_backup(archive, db, static, uploads, tmp_path / ".env", root)
    with zipfile.ZipFile(archive) as zip_file:
        assert "root_files/app-ads.txt" in zip_file.namelist()
    (root / "app-ads.txt").unlink()
    restore_backup(archive, db, static, uploads, tmp_path / ".env", root)
    assert (root / "app-ads.txt").is_file()
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT published FROM root_files WHERE name='app-ads.txt'").fetchone()[0] == 1
