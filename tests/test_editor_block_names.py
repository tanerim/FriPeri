"""Editor block labels remain private, portable, and backwards compatible."""
import json
import pytest
from custom_home import validate_document


def test_editor_name_round_trips_in_nested_sections():
    payload = [
        {"type": "section", "editor_name": "Homepage introduction",
         "children": [
             {"type": "heading", "editor_name": "Hero heading", "text": "Welcome"},
             {"type": "text", "editor_name": "Opening paragraph", "html": "<p>Hello</p>"},
             {"type": "callout", "editor_name": "Key takeaway",
              "title": "Note", "text": "Details"}
         ]}
    ]
    saved = validate_document(json.dumps(payload))
    assert saved[0]["editor_name"] == "Homepage introduction"
    assert [child["editor_name"] for child in saved[0]["children"]] == [
        "Hero heading", "Opening paragraph", "Key takeaway"]
    assert saved[0]["children"][1]["html"] == "<p>Hello</p>"


def test_legacy_blocks_do_not_need_editor_names():
    saved = validate_document(json.dumps([{"type": "heading", "text": "Hello"}]))[0]
    assert "editor_name" not in saved


def test_empty_name_restores_default_title():
    saved = validate_document(json.dumps([
        {"type": "heading", "editor_name": "  ", "text": "Hello"}
    ]))[0]
    assert "editor_name" not in saved


def test_editor_name_length_limit():
    with pytest.raises(ValueError):
        validate_document(json.dumps([
            {"type": "heading", "editor_name": "A" * 101, "text": "Hello"}
        ])


def test_editor_name_is_plain_text():
    saved = validate_document(json.dumps([
        {"type": "heading", "editor_name": "<script>alert(1)</script>", "text": "Hello"}
    ]))[0]
    assert saved["editor_name"] == "<script>alert(1)</script>"
