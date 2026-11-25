"""Root Files allowlist and path safety."""
from root_files import root_filename, safe_root_file, install_schema
import sqlite3


def test_file_name_allowlist(tmp_path):
    for allowed in ("ads.txt", "app-ads.txt", "test.txt", "google123456789abc.html"):
        assert root_filename(allowed)
        assert safe_root_file(tmp_path / "root_files", allowed)
    for denied in (".env", "../app-ads.txt", "robots.txt", "sitemap.xml",
                   "index.html", "private.css", "admin.html", "foo.txt"):
        assert not root_filename(denied)


def test_root_files_schema():
    with sqlite3.connect(":memory:") as db:
        install_schema(db)
        db.execute("INSERT INTO root_files(name,published,updated_at) VALUES('app-ads.txt',0,'now')")
        assert db.execute("SELECT published FROM root_files").fetchone()[0] == 0
