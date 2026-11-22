"""Highlighted heading line breaks and portable color opacity controls."""
import json
import sqlite3
from pathlib import Path

import pytest

from custom_home import validate_document
from test_integration_flows import site  # noqa: F401


def heading(**appearance):
    return [{"type": "heading", "level": "h2", "text": "Our",
             "accent": "Team", "appearance": appearance}]


def test_heading_highlight_defaults_preserve_inline_layout():
    block = validate_document(json.dumps(heading()))[0]
    assert block["accent"] == "Team"
    assert block.get("appearance", {}) == {}


def test_heading_can_place_highlight_on_a_separate_line():
    block = validate_document(json.dumps(heading(
        accent_new_line="yes", accent_color="#AABBCC", accent_opacity=45
    )))[0]
    assert block["appearance"] == {
        "accent_color": "#aabbcc",
        "accent_opacity": 45,
        "accent_new_line": "yes"
    }


@pytest.mark.parametrize("options", [
    {"accent_new_line": "break-all"},
    {"accent_new_line": True},
    {"accent_opacity": -1},
    {"accent_opacity": 101},
    {"accent_opacity": "40"},
    {"accent_opacity": 22.5},
    {"accent_color": "transparent;position:absolute"},
])
def test_invalid_heading_appearance_is_rejected(options):
    with pytest.raises(ValueError):
        validate_document(json.dumps(heading(**options)))


def test_published_heading_break_and_opacity(site):
    client, db = site
    block = validate_document(json.dumps(heading(
        accent_new_line="yes", accent_color="#224466", accent_opacity=50
    )))
    with sqlite3.connect(db) as conn:
        conn.execute("""
            INSERT INTO posts(title, slug, excerpt, body, body_html, post_blocks_json,
                              status, created_at, updated_at)
            VALUES (?, ?, '', '', '', ?, 'published', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, ("Our Team", "our-team-highlight", json.dumps({"en": block})))
    response = client.get("/posts/our-team-highlight")
    assert response.status_code == 200
    assert 'data-accent-new-line="yes"' in response.text
    assert '--block-accent-opacity: 50%' in response.text
    assert '<span class="section-heading-accent">Team</span>' in response.text


def test_published_heading_defaults_to_inline_highlight(site):
    client, db = site
    block = validate_document(json.dumps(heading()))
    with sqlite3.connect(db) as conn:
        conn.execute("""
            INSERT INTO posts(title, slug, excerpt, body, body_html, post_blocks_json,
                              status, created_at, updated_at)
            VALUES (?, ?, '', '', '', ?, 'published', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, ("Inline highlight", "inline-heading-highlight", json.dumps({"en": block})))
    response = client.get("/posts/inline-heading-highlight")
    assert response.status_code == 200
    assert 'data-accent-new-line="no"' in response.text


def test_editor_and_css_support_new_line_and_opacity():
    root = Path(__file__).resolve().parents[1]
    js = (root / "static/home-builder.js").read_text(encoding="utf-8")
    css = (root / "static/custom-home.css").read_text(encoding="utf-8")
    assert "accent_new_line" in js
    assert "accent_opacity" in js
    assert "input.type=key==='accent_opacity'?'range'" in js
    assert ".custom-heading[data-accent-new-line=yes]" in css
    assert "var(--block-accent-opacity,100%)" in css
