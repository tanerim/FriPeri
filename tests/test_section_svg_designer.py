"""Regression coverage for server-generated Section SVG backgrounds."""
import re
from xml.etree import ElementTree as ET

import pytest

from custom_home import SECTION_SVG_FIELDS, validate_appearance
from section_svg_design import render_svg


DEFAULTS = {
    "svg_pattern": "waves", "svg_primary": "#286e7a",
    "svg_secondary": "#68b6b9", "svg_tertiary": "#f2c14e",
    "svg_quaternary": "#aa77dd", "svg_colors": 4,
    "svg_opacity": 85, "svg_placement": "top_right",
    "svg_rotation": 45, "svg_scale": 125, "svg_frequency": 6,
    "svg_amplitude": 50, "svg_density": 10, "svg_stroke": 3,
}


@pytest.mark.parametrize("pattern", [
    "ribbons", "waves", "grid", "dots", "orbits", "topography",
    "diagonals", "mesh",
])
@pytest.mark.parametrize("colors", [2, 3, 4])
def test_all_patterns_and_color_counts_produce_valid_svg(pattern, colors):
    settings = validate_appearance({
        **DEFAULTS, "svg_pattern": pattern, "svg_colors": colors
    }, SECTION_SVG_FIELDS)
    svg = render_svg(settings)
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert root.attrib["viewBox"] == "0 0 1440 760"
    assert len(svg) < 1_500_000
    assert "translate(" in svg


def test_changes_are_deterministic_and_modify_geometry():
    a = render_svg(validate_appearance(DEFAULTS, SECTION_SVG_FIELDS))
    b = render_svg(validate_appearance(DEFAULTS, SECTION_SVG_FIELDS))
    c = render_svg(validate_appearance(
        {**DEFAULTS, "svg_frequency": 10}, SECTION_SVG_FIELDS))
    assert a == b
    assert a != c


@pytest.mark.parametrize("field,value", [
    ("svg_colors", 1), ("svg_colors", 5),
    ("svg_frequency", 0), ("svg_frequency", 99),
    ("svg_density", 0), ("svg_scale", 1000),
    ("svg_rotation", 190), ("svg_amplitude", -1),
    ("svg_stroke", 0), ("svg_placement", "javascript"),
    ("svg_primary", "red;onload=alert(1)"),
])
def test_unsafe_or_out_of_range_svg_options_rejected(field, value):
    with pytest.raises(ValueError):
        validate_appearance({**DEFAULTS, field: value}, SECTION_SVG_FIELDS)


def test_legacy_svg_options_still_validate():
    old = {"svg_pattern": "ribbons", "svg_primary": "#7466ef",
           "svg_secondary": "#5ed8ce", "svg_opacity": 100}
    assert validate_appearance(old, SECTION_SVG_FIELDS) == old
    ET.fromstring(render_svg(old))


def test_four_palette_colors_used_only_when_selected():
    settings = validate_appearance(DEFAULTS, SECTION_SVG_FIELDS)
    four = render_svg(settings)
    two = render_svg({**settings, "svg_colors": 2})
    assert DEFAULTS["svg_quaternary"] in four
    assert DEFAULTS["svg_quaternary"] not in two
