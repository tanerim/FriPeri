"""Team block, two-column preset, and mobile footer regression coverage."""
import json
from pathlib import Path

import pytest

from custom_home import validate_document, render_blocks
from test_integration_flows import site  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def team_doc():
    return [{
        "type": "team", "width": "wide", "items": [
            {"photo": "/static/uploads/example.png", "name": "Ada Yılmaz",
             "title": "Researcher", "shape": "circle"},
            {"photo": "https://example.org/portrait.jpg", "name": "Deniz Demir",
             "title": "Editor", "shape": "rectangle"},
        ]
    }]


def test_team_validation_round_trip_and_shapes():
    blocks = validate_document(json.dumps(team_doc(), ensure_ascii=False))
    assert blocks[0]["type"] == "team"
    assert blocks[0]["width"] == "wide"
    assert blocks[0]["items"][0] == {
        "photo": "/static/uploads/example.png", "name": "Ada Yılmaz",
        "title": "Researcher", "shape": "circle"
    }
    assert blocks[0]["items"][1]["shape"] == "rectangle"
    assert render_blocks(blocks) == blocks


@pytest.mark.parametrize("photo", [
    "javascript:alert(1)", "//example.org/x.png", "/etc/passwd",
    "http://example.org/person.jpg", "https://example.org/pic.png\\oops"
])
def test_team_rejects_unsafe_photos(photo):
    document = team_doc()
    document[0]["items"][0]["photo"] = photo
    with pytest.raises(ValueError, match="Invalid team member photo"):
        validate_document(json.dumps(document))


def test_team_enforces_eight_members_and_text_limit():
    document = team_doc()
    document[0]["items"] = [{"name": f"Person {i}", "title": "Team", "photo": ""}
                             for i in range(9)]
    with pytest.raises(ValueError, match="Invalid block items"):
        validate_document(json.dumps(document))
    document[0]["items"] = [{"name": "x" * 201, "title": "Team", "photo": ""}]
    with pytest.raises(ValueError, match="Invalid text"):
        validate_document(json.dumps(document))


def test_two_equal_columns_retain_editable_children():
    document = [{
        "type": "section", "appearance": {"layout": "two", "surface": "full", "gap": 40},
        "children": [
            {"type": "section", "children": [
                {"type": "heading", "text": "Left"},
                {"type": "text", "html": "<p>Left text</p>"},
                {"type": "button", "text": "Read more", "url": "/about"}
            ]},
            {"type": "section", "children": [
                {"type": "heading", "text": "Right"},
                {"type": "text", "html": "<p>Right text</p>"},
                {"type": "button", "text": "Contact", "url": "/contact"}
            ]}
        ]
    }]
    validated = validate_document(json.dumps(document))
    assert validated[0]["appearance"]["layout"] == "two"
    assert len(validated[0]["children"]) == 2
    assert validated[0]["children"][1]["children"][0]["text"] == "Right"


def test_team_renders_on_published_post(site):
    import sqlite3

    client, db = site
    blocks = validate_document(json.dumps(team_doc(), ensure_ascii=False))
    with sqlite3.connect(db) as conn:
        conn.execute("""
            INSERT INTO posts(title, slug, excerpt, body, body_html, post_blocks_json,
                              status, created_at, updated_at)
            VALUES (?, ?, '', '', '', ?, 'published', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, ("Our team", "our-team", json.dumps({"en": blocks}, ensure_ascii=False)))
    response = client.get("/posts/our-team")
    assert response.status_code == 200
    assert 'class="custom-team-grid"' in response.text
    assert 'shape-circle' in response.text
    assert 'shape-rectangle' in response.text
    assert "Ada Yılmaz" in response.text and "Researcher" in response.text
    assert "Deniz Demir" in response.text and "Editor" in response.text


def test_builder_exposes_both_new_controls(site):
    client, _ = site
    from test_integration_flows import sign_in
    sign_in(client)
    page = client.get("/admin/custom-home")
    assert page.status_code == 200
    assert "two_column_hero" in (ROOT / "static/home-builder.js").read_text(encoding="utf-8")
    assert "addTwoColumnHero()" in (ROOT / "static/home-builder.js").read_text(encoding="utf-8")
    assert "builder-team-grid" in (ROOT / "static/home-builder.js").read_text(encoding="utf-8")
    assert "team_photo" in page.text and "two_column_hero" in page.text


def test_footer_has_social_first_stacked_layout_without_intermediate_breakpoint():
    stylesheet = (ROOT / "static/site.css").read_text(encoding="utf-8")
    section = stylesheet.split("/* Footer has only two layouts:", 1)[1]
    assert "@media (max-width: 900px)" in section
    assert "flex-direction: column" in section
    assert ".public-site .footer-center { order: 0; }" in section
    assert ".public-site .footer-left { order: 1; }" in section
    assert ".public-site .footer-right { order: 2; }" in section
    assert ".public-site .footer-center:not(:has(.footer-social-links)) { display: none; }" in section
