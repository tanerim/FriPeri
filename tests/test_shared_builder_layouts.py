"""Shared Page Builder design controls on Homepage, About, and Pages.

These source-level checks guard against the gallery reverting to a Pages-only
implementation, even if route contexts change.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_shared_gallery_is_used_by_all_three_editors():
    library = read("templates/admin/page_layout_library.html")
    assert 'id="page-layout-gallery"' in library
    assert "12 ready-to-edit layouts" in library
    assert "include 'admin/page_layout_library.html'" in read("templates/admin/page.html")
    about = read("templates/admin/about.html")
    assert "include 'admin/page_layout_library.html'" in about
    assert "builder_page|default('home') != 'post'" in about


def test_builder_styles_and_bulk_collapse_shared_except_posts():
    about = read("templates/admin/about.html")
    custom = read("templates/admin/custom_home.html")
    assert "page-builder-refresh.css" in about
    assert "page-builder-refresh" in about
    assert "builder-collapse-all" in custom
    assert "builder_page|default('home') != 'post'" in custom


def test_layouts_never_modify_global_design_settings():
    builder = read("static/home-builder.js")
    assert "const themedLayouts=" in builder
    assert "const gallery=document.getElementById('page-layout-gallery')" in builder
    assert "your global Design settings were not changed" in builder
