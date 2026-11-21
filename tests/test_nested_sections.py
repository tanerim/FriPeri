"""Regression coverage for supported nested sections in the page builder."""
import json

import pytest

from custom_home import validate_document


def test_sections_can_be_nested_three_levels():
    document = [{"type": "section", "children": [
        {"type": "heading", "text": "Outer heading"},
        {"type": "section", "children": [
            {"type": "text", "html": "<p>Inside</p>"},
            {"type": "section", "children": [
                {"type": "heading", "text": "Nested heading"}
            ]},
        ]},
    ]}]
    validated = validate_document(json.dumps(document))
    assert validated[0]["children"][1]["type"] == "section"
    assert validated[0]["children"][1]["children"][1]["type"] == "section"


def test_section_depth_four_is_rejected():
    block = {"type": "heading", "text": "Leaf"}
    for _ in range(4):
        block = {"type": "section", "children": [block]}
    with pytest.raises(ValueError, match="three levels"):
        validate_document(json.dumps([block]))


def test_total_nested_blocks_are_limited():
    document = [{"type": "section", "children": [
        {"type": "heading", "text": str(i)} for i in range(80)
    ]}]
    with pytest.raises(ValueError, match="80 blocks"):
        validate_document(json.dumps(document))
