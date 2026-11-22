"""Page Builder regression checks for theme-aware icon-only buttons."""
import json

import pytest

from custom_home import validate_document, ICON_BUTTON_NAMES


def test_icon_button_is_accessible_and_validated():
    blocks = [{
        "type": "icon_button",
        "text": "Go home",
        "url": "/",
        "icon_name": "house",
        "appearance": {"variant": "solid", "button_background": "#286e7a"},
    }]
    result = validate_document(json.dumps(blocks))
    assert result[0]["icon_name"] == "house"
    assert result[0]["text"] == "Go home"
    assert result[0]["appearance"]["button_background"] == "#286e7a"


def test_unknown_icon_is_rejected():
    blocks = [{"type": "icon_button", "text": "Alert", "url": "/", "icon_name": "fake-icon"}]
    with pytest.raises(ValueError, match="Invalid icon"):
        validate_document(json.dumps(blocks))


def test_icon_button_requires_accessible_label():
    blocks = [{"type": "icon_button", "text": "", "url": "/", "icon_name": "house"}]
    with pytest.raises(ValueError, match="accessible label"):
        validate_document(json.dumps(blocks))


def test_button_without_icon_remains_supported():
    blocks = [{"type": "button", "text": "Read more", "url": "/about", "appearance": {"icon": "none"}}]
    assert validate_document(json.dumps(blocks))[0]["appearance"]["icon"] == "none"


def test_icon_library_is_unique_and_bounded():
    assert len(ICON_BUTTON_NAMES) >= 20
    assert len(set(ICON_BUTTON_NAMES)) == len(ICON_BUTTON_NAMES)
