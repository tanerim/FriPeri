"""Image block presentation remains validated, accessible, and backward compatible."""
import json

import pytest

from custom_home import validate_document


def image(**overrides):
    return {"type": "image", "url": "/static/uploads/example.jpg",
            "alt": "A group examining a visualization", "caption": "Research collaboration",
            **overrides}


def test_image_with_all_presentation_options():
    options = {
        "ratio": "wide", "fit": "contain", "position": "top_right",
        "width_mode": "custom", "width_px": 780, "height_px": 420,
        "radius": 20, "border_width": 2, "border_color": "#334455",
        "frame_background": "#f1f2f3", "padding": 12,
        "shadow": "medium", "hover": "zoom",
        "caption_align": "center", "caption_size": 16,
        "loading": "eager", "decoding": "async", "fetch_priority": "high",
        "image_action": "lightbox",
    }
    result = validate_document(json.dumps([image(appearance=options)]))[0]
    assert result["appearance"] == options
    assert result["alt"] == "A group examining a visualization"


def test_existing_image_without_appearance_stays_valid():
    result = validate_document(json.dumps([image()]))[0]
    assert "appearance" not in result
    assert result["url"] == "/static/uploads/example.jpg"


def test_external_link_keeps_safe_target():
    result = validate_document(json.dumps([
        image(link_url="https://example.org/research", link_target="new_tab",
              appearance={"image_action": "link"})]))[0]
    assert result["link_url"] == "https://example.org/research"
    assert result["link_target"] == "new_tab"


@pytest.mark.parametrize("bad", [
    "javascript:alert(1)", "//example.net", "data:text/html,broken"
])
def test_image_unsafe_link_rejected(bad):
    with pytest.raises(ValueError, match="Invalid image link URL"):
        validate_document(json.dumps([image(link_url=bad)]))


@pytest.mark.parametrize("settings", [
    {"ratio": "42:1"}, {"width_px": 5000}, {"radius": -1},
    {"shadow": "javascript"}, {"image_action": "unsafe"},
    {"loading": "now"}, {"border_color": "red;display:none"},
])
def test_invalid_style_rejected(settings):
    with pytest.raises(ValueError, match="Invalid appearance setting"):
        validate_document(json.dumps([image(appearance=settings)]))


def test_empty_image_placeholder_supported_for_editing():
    blocks = validate_document(json.dumps([{"type": "image", "url": "", "alt": ""}]))
    assert blocks[0]["url"] == ""
