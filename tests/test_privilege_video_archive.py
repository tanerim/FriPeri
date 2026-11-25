"""Integration tests for the protected external video archive symlink."""
from pathlib import Path

from test_privileges import app_site, set_private, register, admin_action


def test_external_video_symlink_requires_approval(app_site, tmp_path, monkeypatch):
    client, db, folder = app_site
    archive = tmp_path / "external-videos"
    archive.mkdir()
    (archive / "sample.mp4").write_bytes(b"video-test-data")
    (folder / "videos").symlink_to(archive, target_is_directory=True)
    monkeypatch.setenv("PRIVILEGES_VIDEO_ARCHIVE_DIR", str(archive))

    url = "/static/video_sorgu/videos/sample.mp4"
    set_private(client)
    assert client.get(url).status_code == 403
    register(client)
    assert client.get(url).status_code == 403
    admin_action(client, db, "approve")
    result = client.get(url)
    assert result.status_code == 200
    assert result.content == b"video-test-data"
    assert result.headers["cache-control"] == "private, no-store"

    partial = client.get(url, headers={"Range": "bytes=0-4"})
    assert partial.status_code == 206
    assert partial.content == b"video"

    admin_action(client, db, "revoke")
    assert client.get(url).status_code == 403


def test_unapproved_symlinks_stay_blocked(app_site, tmp_path, monkeypatch):
    client, db, folder = app_site
    archive = tmp_path / "videos"
    archive.mkdir()
    (archive / "file.mp4").write_bytes(b"allowed")
    (archive / "outside.mp4").write_bytes(b"outside")
    other = tmp_path / "other"
    other.mkdir()
    (other / "private.txt").write_text("secret")
    (folder / "videos").symlink_to(archive, target_is_directory=True)
    (folder / "other").symlink_to(other, target_is_directory=True)
    (archive / "escape.mp4").symlink_to(other / "private.txt")
    monkeypatch.setenv("PRIVILEGES_VIDEO_ARCHIVE_DIR", str(archive))

    set_private(client)
    register(client)
    admin_action(client, db, "approve")

    assert client.get("/static/video_sorgu/videos/file.mp4").status_code == 200
    assert client.get("/static/video_sorgu/videos/escape.mp4").status_code == 404
    assert client.get("/static/video_sorgu/other/private.txt").status_code == 404

    # Repointing the approved link must not grant access to another root.
    (folder / "videos").unlink()
    (folder / "videos").symlink_to(other, target_is_directory=True)
    assert client.get("/static/video_sorgu/videos/private.txt").status_code == 404
