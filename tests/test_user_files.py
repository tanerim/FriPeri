"""User Files migration and canonical privilege URL tests."""
import sqlite3
from pathlib import Path

from privileges import migrate_user_folders, safe_target


def test_migrate_recorded_folder_only(tmp_path):
    static = tmp_path / "static"
    users = tmp_path / "user_files"
    (static / "video_sorgu").mkdir(parents=True)
    (static / "site_assets").mkdir()
    (static / "video_sorgu" / "index.html").write_text("protected")
    with sqlite3.connect(":memory:") as conn:
        from privileges import install_schema
        install_schema(conn)
        conn.execute("INSERT INTO privilege_directories(folder,is_private,updated_at) VALUES('video_sorgu',1,'now')")
        assert migrate_user_folders(static, users, conn) == ["video_sorgu"]
    assert (users / "video_sorgu" / "index.html").read_text() == "protected"
    assert (static / "site_assets").is_dir()


def test_canonical_target_allows_legacy_entrypoint():
    assert safe_target("/static/video_sorgu/index.html", "video_sorgu") == "/user_files/video_sorgu/index.html"
    assert safe_target("/user_files/video_sorgu/index.html", "video_sorgu") == "/user_files/video_sorgu/index.html"
    assert safe_target("https://evil.test", "video_sorgu") == "/user_files/video_sorgu/index.html"
