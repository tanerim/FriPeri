"""Regression checks for the redesigned FriPeri landing page building blocks."""
import json

from custom_home import validate_document


def test_brand_logo_is_a_safe_reusable_block():
    blocks = validate_document(json.dumps([
        {"type": "brand_logo", "width": "wide", "align": "center"}
    ]))
    assert blocks[0]["type"] == "brand_logo"
    assert blocks[0]["align"] == "center"


def test_landing_sections_have_valid_styles():
    names = ("hero", "intro", "features", "showcase", "steps", "contrast", "closing")
    payload = [{"type": "section", "children": [],
                "tone": "custom", "background": "#142e52",
                "appearance": {"layout": "two", "landing_style": name,
                               "edge": "wave", "svg_pattern": "ribbons"}}
               for name in names]
    result = validate_document(json.dumps(payload))
    assert [item["appearance"]["landing_style"] for item in result] == list(names)


def test_brand_logo_inside_nested_split_hero():
    blocks = [{"type": "section", "appearance": {
        "layout": "two", "landing_style": "hero", "surface": "full"},
        "children": [
            {"type": "section", "children": [{"type": "heading", "text": "Ideas deserve a home.", "level": "h1"}]},
            {"type": "brand_logo", "width": "wide"},
        ]}]
    assert validate_document(json.dumps(blocks))[0]["children"][1]["type"] == "brand_logo"
