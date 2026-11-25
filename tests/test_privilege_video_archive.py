"""Integration tests for the protected external video archive symlink."""
from pathlib import Path

from test_privileges import app_site, set_private, register, admin_action


def test_external_video_symlink_requires_approval(app_site, tmp_path, monkeypatch):
    client, db, folder = app_site
    archive = tmp_path / "external-videos"
    archive.mkdir()
    (archive / "sample.mp4").write_bytes(b"video-test-data")
    (folder / "videos").symlink_to(archive, target_is_directory=True)
    client.cookies.set("priv_admin_test", "yes")
    assert client.post("/admin/privileges/video_sorgu/mapping", data={
        "settings_token": "admin-csrf", "relative_path": "videos",
        "target_path": str(archive), "allowed_extensions": "mp4",
    }).status_code == 303
    client.cookies.delete("priv_admin_test")

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
    client.cookies.set("priv_admin_test", "yes")
    assert client.post("/admin/privileges/video_sorgu/mapping", data={
        "settings_token": "admin-csrf", "relative_path": "videos",
        "target_path": str(archive), "allowed_extensions": "mp4",
    }).status_code == 303
    client.cookies.delete("priv_admin_test")

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


def test_generic_mapping_lifecycle(app_site, tmp_path):
    client, db, folder = app_site
    generic = folder.parent / "research"
    generic.mkdir()
    archive = tmp_path / "pictures"
    archive.mkdir()
    (archive / "photo.jpg").write_bytes(b"photo")
    (archive / "secret.txt").write_text("secret")
    (generic / "media").symlink_to(archive, target_is_directory=True)
    url = "/static/research/media/photo.jpg"
    route = "/admin/privileges/research/mapping"
    data = {"settings_token": "admin-csrf", "relative_path": "media",
            "target_path": str(archive), "allowed_extensions": "jpg"}
    assert client.get(url).status_code == 404
    assert client.post(route, data=data).status_code == 403
    client.cookies.set("priv_admin_test", "yes")
    assert client.post(route, data={**data, "settings_token": "wrong"}).status_code == 403
    assert client.post(route, data=data).status_code == 303
    assert client.get(url).status_code == 200
    assert client.get("/static/research/media/secret.txt").status_code == 404
    with db() as conn:
        mid = conn.execute("SELECT id FROM privilege_external_mappings WHERE folder='research'").fetchone()["id"]
    assert client.post(route, data={**data, "mapping_id": mid, "action": "disable"}).status_code == 303
    assert client.get(url).status_code == 404
    assert client.post(route, data={**data, "mapping_id": mid}).status_code == 303
    assert client.get(url).status_code == 200
    assert client.post(route, data={**data, "mapping_id": mid, "action": "delete"}).status_code == 303
    assert client.get(url).status_code == 404
