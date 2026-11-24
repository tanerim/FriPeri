"""Divider vertical padding, decorative curves, and backwards compatibility."""
import json
import pytest
from custom_home import validate_document, divider_wave_path

@pytest.mark.parametrize("style", [
    "single", "double", "dashed", "dotted", "fade",
    "wave", "wave-tight", "zigzag", "arc", "swoosh"
])
def test_divider_styles_round_trip(style):
    block={"type":"divider","line_style":style,"line_width":2,
           "line_color":"#91aabd",
           "appearance":{"padding_top":64,"padding_bottom":12}}
    saved=validate_document(json.dumps([block]))[0]
    assert saved["line_style"]==style
    assert saved["appearance"]=={"padding_top":64,"padding_bottom":12}
    if style in ("wave","wave-tight","zigzag","arc","swoosh"):
        assert saved["line_path"] == divider_wave_path(style)

def test_old_divider_defaults_remain_readable():
    saved=validate_document('[{"type":"divider"}]')[0]
    assert saved["line_style"]=="single"
    assert "appearance" not in saved

@pytest.mark.parametrize("padding", [-1,241])
def test_padding_rejects_out_of_range_values(padding):
    with pytest.raises(ValueError):
        validate_document(json.dumps([{
            "type":"divider","appearance":{"padding_top":padding}
        }]))

@pytest.mark.parametrize("style",["wave","wave-tight","arc","swoosh"])
def test_curves_are_single_smooth_paths(style):
    path=divider_wave_path(style)
    assert path.startswith("M0 ")
    assert " C" in path or " Q" in path
    assert len(path)<240
