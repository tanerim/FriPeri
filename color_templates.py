"""Curated color templates for all global FriPeri Design color fields.

Each template has ten coordinated swatches. Golden Summer Glow originally
has five user-provided swatches; its other five are complementary additions.
"""
import re

ROLE_KEYS = (
    "color_page_bg", "color_nav", "color_nav_hover", "color_nav_active",
    "color_feature_bg", "color_feature_text", "color_feature_border",
    "color_accent_primary", "color_accent_secondary",
    "color_separator_1", "color_separator_2", "color_separator_3",
    "color_footer_bg", "color_footer_text", "color_footer_border",
)

# A named palette consists of ten swatches; roles may reuse those colors.
TEMPLATES = (
    {
        "id": "tidal-ember",
        "name": "Tidal Ember",
        "description": "Deep sea tones, warm sand, and glowing amber.",
        "colors": (
            "#001219", "#005f73", "#0a9396", "#94d2bd", "#e9d8a6",
            "#ee9b00", "#ca6702", "#bb3e03", "#ae2012", "#9b2226",
        ),
        "roles": (
            "#f8faf7", "#005f73", "#0a9396", "#005f73",
            "#e9d8a6", "#001219", "#ca6702", "#005f73",
            "#bb3e03", "#94d2bd", "#ee9b00", "#ae2012",
            "#001219", "#e9d8a6", "#0a9396",
        ),
    },
    {
        "id": "ember-after-dark",
        "name": "Ember After Dark",
        "description": "A dramatic progression from burgundy to sunlight.",
        "colors": (
            "#03071e", "#370617", "#6a040f", "#9d0208", "#d00000",
            "#dc2f02", "#e85d04", "#f48c06", "#faa307", "#ffba08",
        ),
        "roles": (
            "#fff9f3", "#370617", "#9d0208", "#6a040f",
            "#ffba08", "#03071e", "#f48c06", "#9d0208",
            "#dc2f02", "#faa307", "#e85d04", "#d00000",
            "#03071e", "#fff2df", "#9d0208",
        ),
    },
    {
        "id": "sunlit-horizon",
        "name": "Sunlit Horizon",
        "description": "Summer warmth balanced by confident ocean navy.",
        # Five original shades, plus five harmonious additions (last five).
        "colors": (
            "#0d3b66", "#faf0ca", "#f4d35e", "#ee964b", "#f95738",
            "#092b49", "#fffaf0", "#dca72d", "#b84732", "#82b8b1",
        ),
        "roles": (
            "#fffaf0", "#0d3b66", "#b84732", "#092b49",
            "#f4d35e", "#092b49", "#dca72d", "#0d3b66",
            "#f95738", "#82b8b1", "#ee964b", "#f4d35e",
            "#0d3b66", "#faf0ca", "#82b8b1",
        ),
    },
    {
        "id": "electric-orchid",
        "name": "Electric Orchid",
        "description": "Vibrant magenta and violet meeting brilliant sky blue.",
        "colors": (
            "#f72585", "#b5179e", "#7209b7", "#560bad", "#480ca8",
            "#3a0ca3", "#3f37c9", "#4361ee", "#4895ef", "#4cc9f0",
        ),
        "roles": (
            "#f8f7ff", "#3a0ca3", "#7209b7", "#480ca8",
            "#4cc9f0", "#3a0ca3", "#4361ee", "#3a0ca3",
            "#b5179e", "#f72585", "#4361ee", "#4cc9f0",
            "#240d49", "#f3eaff", "#4361ee",
        ),
    },
)


def list_templates():
    """Return JSON-friendly metadata with all resolved Design settings."""
    result = []
    for template in TEMPLATES:
        settings = dict(zip(ROLE_KEYS, template["roles"]))
        result.append({
            "id": template["id"],
            "name": template["name"],
            "description": template["description"],
            "colors": list(template["colors"]),
            "settings": settings,
        })
    return result


def validate_templates():
    """Check all presets remain exhaustive, correctly sized, and well formed."""
    hex_color = re.compile(r"#[0-9a-fA-F]{6}\Z")
    for template in TEMPLATES:
        assert len(template["colors"]) == 10
        assert len(template["roles"]) == len(ROLE_KEYS)
        assert all(hex_color.fullmatch(color) for color in (*template["colors"], *template["roles"]))
    assert len({template["id"] for template in TEMPLATES}) == len(TEMPLATES)
