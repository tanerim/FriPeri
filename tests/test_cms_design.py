"""Per-category CMS Design: isolation, safe colors, and server-only authorization."""
import json
import sqlite3

import pytest

from category_design import parse_archive_design, validate_archive_design, archive_inline_styles
from test_integration_flows import site, sign_in  # noqa: F401
from test_roles import _make_user, _as  # noqa: F401
import main


def _categories(db):
    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT id, slug FROM categories ORDER BY id LIMIT 2").fetchall()
        if len(rows) < 2:
            conn.execute("""INSERT INTO categories(name, slug, description, created_at)
                VALUES('Additional', 'additional', '', CURRENT_TIMESTAMP)""")
            rows = conn.execute("SELECT id, slug FROM categories ORDER BY id LIMIT 2").fetchall()
    assert len(rows) == 2
    return rows


def test_category_design_parser_falls_back_to_safe_defaults():
    assert parse_archive_design(None)["columns"] == "3"
    assert parse_archive_design("{invalid")["card_style"] == "raised"
    assert parse_archive_design({"accent": "url(javascript:bad)", "columns": "9"})["accent"] == ""


@pytest.mark.parametrize("bad", [
    {"columns": "5"}, {"card_style": "other"}, {"accent": "red"},
    {"background": "expression(alert(1))"},
    {"card_background": "#fff; background: red"},
    {"text_color": "#1234"},
])
def test_category_design_rejects_unsafe_values(bad):
    form = {"columns": "3", "card_style": "raised", **bad}
    with pytest.raises(ValueError):
        validate_archive_design(form)


def test_category_design_saved_and_isolated(site):
    client, db = site
    one, two = _categories(db)
    sign_in(client)
    token = main.custom_home_token("admin")
    index = client.get("/admin/cms-design")
    assert index.status_code == 200
    assert "cms-category-selector" in index.text
    assert client.get(f"/admin/cms-design?category={two[0]}").status_code == 200
    update = client.post("/admin/cms-design", data={
        "editor_token": token, "category_id": str(one[0]),
        "columns": "2", "card_style": "outlined",
        "accent": "#123456", "background": "#f4f5f6",
        "card_background": "#ffffff", "text_color": "#151515",
    })
    assert update.status_code == 303
    with sqlite3.connect(db) as conn:
        first = json.loads(conn.execute("SELECT archive_design_json FROM categories WHERE id=?", (one[0],)).fetchone()[0])
        second = json.loads(conn.execute("SELECT archive_design_json FROM categories WHERE id=?", (two[0],)).fetchone()[0])
    assert first["accent"] == "#123456"
    assert second == {}
    first_html = client.get(f"/category/{one[1]}")
    second_html = client.get(f"/category/{two[1]}")
    assert first_html.status_code == second_html.status_code == 200
    assert 'data-archive-columns="2"' in first_html.text
    assert 'data-archive-card-style="outlined"' in first_html.text
    assert "--archive-accent: #123456;" in first_html.text
    assert 'data-archive-columns="3"' in second_html.text
    assert "--archive-accent: #123456;" not in second_html.text


def test_cms_design_admin_only(site):
    client, db = site
    one, _ = _categories(db)
    assert client.get("/admin/cms-design").status_code == 303
    _make_user(db, "ed_cms", role="editor")
    _as(client, "ed_cms")
    assert client.get("/admin/cms-design").status_code == 403
    assert client.post("/admin/cms-design", data={
        "category_id": str(one[0]), "columns": "1",
        "editor_token": main.custom_home_token("ed_cms"),
    }).status_code == 403


def test_category_design_requires_valid_token_and_category(site):
    client, db = site
    one, _ = _categories(db)
    sign_in(client)
    assert client.post("/admin/cms-design", data={
        "category_id": str(one[0]), "columns": "1", "editor_token": "bad",
    }).status_code == 403
    assert client.post("/admin/cms-design", data={
        "category_id": "99999999", "columns": "1",
        "editor_token": main.custom_home_token("admin"),
    }).status_code == 404


def test_global_design_explains_palette_scope(site):
    client, _ = site
    sign_in(client)
    response = client.get("/admin/design")
    assert response.status_code == 200
    assert "design-scope-help" in response.text
    assert "color_accent_primary" in response.text
    assert "scope_accent" not in response.text
    assert "CMS Design" in client.get("/admin/cms-design").text
