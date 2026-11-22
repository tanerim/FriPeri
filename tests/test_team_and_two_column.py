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
        "title": "Researcher", "shape": "circle", "fit": "cover", "orientation": "landscape",
        "zoom": 1.0, "focal_x": 50.0, "focal_y": 50.0,
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


@pytest.mark.parametrize("key,value", [
    ("zoom", 0.5), ("zoom", 3.1), ("zoom", "2"), ("zoom", True),
    ("focal_x", -1), ("focal_x", 101), ("focal_y", -0.1),
    ("focal_y", float("nan")), ("focal_x", float("inf")),
])
def test_team_rejects_invalid_crop_settings(key, value):
    document = team_doc()
    document[0]["items"][0][key] = value
    with pytest.raises(ValueError, match="Invalid team photo crop"):
        validate_document(json.dumps(document))


def test_team_crop_and_member_order_round_trip():
    document = team_doc()
    first, second = document[0]["items"]
    first.update(zoom=2.35, focal_x=12.5, focal_y=76.25)
    second.update(zoom=1.15, focal_x=68, focal_y=32)
    document[0]["items"] = [second, first]  # Reordering is persisted in array order.
    validated = validate_document(json.dumps(document, ensure_ascii=False))
    assert [x["name"] for x in validated[0]["items"]] == ["Deniz Demir", "Ada Yılmaz"]
    assert validated[0]["items"][1]["zoom"] == 2.35
    assert validated[0]["items"][1]["focal_x"] == 12.5
    assert validated[0]["items"][1]["focal_y"] == 76.25


def test_editor_has_team_move_crop_and_zoom_controls():
    script = (ROOT / "static/home-builder.js").read_text(encoding="utf-8")
    assert "builder-team-order" in script
    assert "block.items[i-1]" in script
    assert "block.items[i+1]" in script
    assert "setPointerCapture" in script
    assert "builder-team-zoom" in script
    assert "team_reset_crop" in script
    template = (ROOT / "templates/partials/content_blocks.html").read_text(encoding="utf-8")
    assert "member.focal_x" in template
    assert "member.focal_y" in template
    assert "member.zoom" in template


def test_team_photo_crop_renders_on_published_page(site):
    import sqlite3
    client, db = site
    document = team_doc()
    document[0]["items"][0].update(zoom=2.2, focal_x=20.0, focal_y=70.0)
    blocks = validate_document(json.dumps(document, ensure_ascii=False))
    with sqlite3.connect(db) as conn:
        conn.execute("""
            INSERT INTO posts(title, slug, excerpt, body, body_html, post_blocks_json,
                              status, created_at, updated_at)
            VALUES (?, ?, '', '', '', ?, 'published', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, ("Team crop", "team-crop", json.dumps({"en": blocks}, ensure_ascii=False)))
    response = client.get("/posts/team-crop")
    assert response.status_code == 200
    assert "shape-circle" in response.text
    assert "object-position: 20.0% 70.0%" in response.text
    assert "translate(" in response.text and "scale(2.2)" in response.text


def test_team_photo_fit_modes_are_preserved():
    document = team_doc()
    document[0]["items"][0]["fit"] = "contain"
    validated = validate_document(json.dumps(document, ensure_ascii=False))
    assert validated[0]["items"][0]["fit"] == "contain"
    assert validated[0]["items"][1]["fit"] == "cover"
    assert "object-fit: {{ member.fit" in (
        ROOT / "templates/partials/content_blocks.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("orientation", ["landscape", "portrait"])
def test_rectangle_orientation_is_saved(orientation):
    doc = team_doc()
    doc[0]["items"][1]["orientation"] = orientation
    result = validate_document(json.dumps(doc, ensure_ascii=False))
    assert result[0]["items"][1]["orientation"] == orientation


def test_unknown_team_orientation_defaults_to_landscape():
    doc = team_doc()
    doc[0]["items"][1]["orientation"] = "diagonal"
    assert validate_document(json.dumps(doc))[0]["items"][1]["orientation"] == "landscape"


def test_team_photo_panning_and_orientation_are_exposed():
    js = (ROOT / "static/home-builder.js").read_text(encoding="utf-8")
    css = (ROOT / "static/home-builder.css").read_text(encoding="utf-8")
    published_css = (ROOT / "static/custom-home.css").read_text(encoding="utf-8")
    assert "portrait.dataset.orientation" in js
    assert "team_orientation" in js
    assert "team_landscape" in js and "team_portrait" in js
    assert "portrait.setPointerCapture(event.pointerId)" in js
    assert "translate(${offsetX}%, ${offsetY}%)" in js
    assert "grid-template-columns:minmax(180px,240px)" in css
    assert "orientation-portrait" in published_css
    assert "orientation-landscape" in published_css


def test_published_team_portrait_ratio_and_pan(site):
    import sqlite3

    client, db = site
    doc = team_doc()
    doc[0]["items"][1].update(
        orientation="portrait", shape="rectangle",
        fit="cover", zoom=2.0, focal_x=30.0, focal_y=70.0
    )
    blocks = validate_document(json.dumps(doc, ensure_ascii=False))
    with sqlite3.connect(db) as conn:
        conn.execute("""
            INSERT INTO posts(title, slug, excerpt, body, body_html, post_blocks_json,
                              status, created_at, updated_at)
            VALUES (?, ?, '', '', '', ?, 'published', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, ("Portrait team", "portrait-team", json.dumps({"en": blocks}, ensure_ascii=False)))
    response = client.get("/posts/portrait-team")
    assert response.status_code == 200
    assert "shape-rectangle orientation-portrait" in response.text
    assert "object-position: 30.0% 70.0%" in response.text
    assert "translate(10.0%, -10.0%) scale(2.0)" in response.text
