"""Divider appearance validation, SVG generation and published markup."""
import json
import re
import sqlite3
from pathlib import Path

import pytest

from custom_home import divider_wave_path, validate_document
from test_integration_flows import site  # noqa: F401


def divider(**options):
    return [{"type": "divider", **options}]


def test_legacy_divider_gets_safe_defaults():
    block = validate_document(json.dumps(divider()))[0]
    assert block["line_width"] == 2
    assert block["line_style"] == "single"
    assert block["line_color"] == "#a5b3be"
    assert "line_path" not in block


@pytest.mark.parametrize("style", ["single", "dashed", "dotted", "wave", "wave-tight", "zigzag"])
@pytest.mark.parametrize("width", [2, 10, 20])
def test_divider_saves_valid_styles_and_widths(style, width):
    block = validate_document(json.dumps(divider(
        line_width=width, line_style=style, line_color="#AABBCC"
    )))[0]
    assert block["line_width"] == width
    assert block["line_style"] == style
    assert block["line_color"] == "#aabbcc"
    if style in {"wave", "wave-tight", "zigzag"}:
        assert block["line_path"] == divider_wave_path(style)
        assert re.fullmatch(r"[MCLQST0-9. \-]+", block["line_path"])
    else:
        assert "line_path" not in block


@pytest.mark.parametrize("options", [
    {"line_width": 1}, {"line_width": 21},
    {"line_width": 2.2}, {"line_width": "10"},
    {"line_width": True}, {"line_color": "red"},
    {"line_color": "var(--bad)"}, {"line_color": "#abc"},
    {"line_style": "custom"}, {"line_style": "wave'><script>"},
])
def test_divider_rejects_invalid_properties(options):
    with pytest.raises(ValueError):
        validate_document(json.dumps(divider(**options)))


@pytest.mark.parametrize("style", ["single", "dashed", "dotted", "wave", "wave-tight", "zigzag"])
def test_divider_renders_on_public_page(site, style):
    client, db = site
    blocks = validate_document(json.dumps(divider(
        line_width=12, line_style=style, line_color="#246789"
    )))
    with sqlite3.connect(db) as conn:
        conn.execute("""
            INSERT INTO posts(title, slug, excerpt, body, body_html, post_blocks_json,
                              status, created_at, updated_at)
            VALUES (?, ?, '', '', '', ?, 'published', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, ("Divider rendering", "divider-style", json.dumps({"en": blocks})))
    response = client.get("/posts/divider-style")
    assert response.status_code == 200
    assert f"style-{style}" in response.text
    assert "--divider-width: 12px" in response.text
    assert "--divider-color: #246789" in response.text
    if style in ("wave", "wave-tight", "zigzag"):
        assert 'class="custom-divider-wave"' in response.text
        assert '<path d="M 0 24 ' in response.text
    else:
        assert '<hr aria-hidden="true">' in response.text


def test_editor_includes_divider_style_controls():
    root = Path(__file__).resolve().parents[1]
    script = (root / "static/home-builder.js").read_text(encoding="utf-8")
    template = (root / "templates/admin/custom_home.html").read_text(encoding="utf-8")
    assert "divider_line_width" in script
    assert "divider_line_style" in script
    assert "divider_line_color" in script
    assert "wave-tight" in script and "zigzag" in script
    assert "'divider_wave_tight'" in template
