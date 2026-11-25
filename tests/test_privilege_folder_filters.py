"""Regression checks for reserved privilege folders."""
from pathlib import Path
from privileges import folders


def test_reserved_folders_not_managed(tmp_path: Path):
    for name in ("images", "uploads", "video_sorgu"):
        (tmp_path / name).mkdir()
    assert folders(tmp_path) == ["video_sorgu"]
