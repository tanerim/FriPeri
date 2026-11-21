"""Tests for the authenticated admin documentation parser's file boundaries."""
from pathlib import Path

import pytest

from documentation import list_documents, render_document


def test_documentation_index_and_links(tmp_path: Path):
    root = tmp_path / "docs"
    root.mkdir()
    (root / "index.md").write_text("# Contents\n\n[Read more](usage.md)\n", encoding="utf-8")
    (root / "usage.md").write_text("# Usage\n\n| A | B |\n|---|---|\n| 1 | 2 |\n", encoding="utf-8")
    items = list_documents(root)
    allowed = {item["name"] for item in items}
    assert [item["name"] for item in items] == ["index.md", "usage.md"]
    rendered = render_document(root, "index.md", allowed)
    assert "/admin/documentation?file=usage.md" in rendered
    assert "<h1" in rendered
    assert "<table>" in render_document(root, "usage.md", allowed)


def test_html_is_escaped_and_unsafe_links_are_rejected(tmp_path: Path):
    root = tmp_path / "docs"
    root.mkdir()
    (root / "index.md").write_text(
        "# Test\n\n<script>alert(1)</script>\n\n[Bad](javascript:alert(1))",
        encoding="utf-8",
    )
    rendered = render_document(root, "index.md", {"index.md"})
    assert "<script>" not in rendered
    assert 'href="#"' in rendered


def test_path_traversal_and_unlisted_files_are_rejected(tmp_path: Path):
    root = tmp_path / "docs"
    root.mkdir()
    (root / "index.md").write_text("# Index", encoding="utf-8")
    (tmp_path / "private.md").write_text("# Private", encoding="utf-8")
    allowed = {item["name"] for item in list_documents(root)}
    with pytest.raises(FileNotFoundError):
        render_document(root, "../private.md", allowed)
    with pytest.raises(FileNotFoundError):
        render_document(root, "/etc/passwd", allowed)
