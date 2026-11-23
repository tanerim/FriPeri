"""Standalone Icon, arrow choices, and backwards compatible Button defaults."""
import json
import pytest
from custom_home import validate_document, ICON_BUTTON_NAMES, BLOCK_TYPES

ARROWS = {
    "arrow-up-light", "arrow-up-heavy", "arrow-down-light", "arrow-down-heavy",
    "arrow-left-light", "arrow-left-heavy", "arrow-right-light", "arrow-right-heavy",
}

@pytest.mark.parametrize("name", sorted(ARROWS))
def test_button_directional_arrow_variants(name):
    block = {"type": "button", "text": "Read", "url": "/about",
             "appearance": {"variant": "plain", "hover_effect": "none", "icon": name}}
    saved = validate_document(json.dumps([block]))[0]
    assert saved["appearance"]["icon"] == name
    assert saved["appearance"]["variant"] == "plain"
    assert saved["appearance"]["hover_effect"] == "none"

@pytest.mark.parametrize("icon", [
    "arrow-down", "arrow-down-circle-fill", "arrow-up", "arrow-up-circle-fill",
    "arrow-left", "arrow-left-circle-fill", "arrow-right", "arrow-right-circle-fill",
    "star", "database", "diagram-3", "mortarboard",
])
def test_standalone_icon_can_be_saved(icon):
    assert icon in ICON_BUTTON_NAMES
    block = {"type": "icon", "icon_name": icon, "icon_label": "Research icon",
             "appearance": {"icon_size": 56, "icon_color": "#286e7a",
                            "background_mode": "circle", "frame_size": 84}}
    saved = validate_document(json.dumps([block]))[0]
    assert saved["icon_name"] == icon
    assert saved["icon_label"] == "Research icon"
    assert "url" not in saved

def test_legacy_solid_button_unchanged():
    saved = validate_document(json.dumps([
        {"type": "button", "text": "Discover", "url": "/about"}
    ]))[0]
    assert "appearance" not in saved

@pytest.mark.parametrize("name", ["javascript", "not-an-icon", "x;onclick=alert(1)"])
def test_icon_names_are_allowlisted(name):
    with pytest.raises(ValueError):
        validate_document(json.dumps([{"type": "icon", "icon_name": name}]))

def test_icon_size_boundaries_rejected():
    for size in (0, 300):
        with pytest.raises(ValueError):
            validate_document(json.dumps([
                {"type":"icon","icon_name":"star","appearance":{"icon_size":size}}
            ]))

def test_icon_block_available():
    assert "icon" in BLOCK_TYPES

def test_callout_inside_dark_section_keeps_text():
    page=[{"type":"section","tone":"dark","children":[{
        "type":"callout","title":"An important finding",
        "text":"A visible, editable description.",
        "appearance":{"body_color":"#17243b","title_color":"#17243b"}
    }]}]
    saved=validate_document(json.dumps(page))
    assert saved[0]["children"][0]["text"]=="A visible, editable description."
    assert saved[0]["children"][0]["appearance"]["body_color"]=="#17243b"
