"""Validated, backward-compatible per-category archive presentation."""
import json
import re

CHOICES = {
    "columns": ("1", "2", "3"),
    "card_style": ("raised", "outlined", "flat"),
    "layout": ("grid", "masonry", "list", "featured"),
    "orientation": ("vertical", "horizontal"),
    "image_position": ("top", "left", "right"),
    "image_ratio": ("original", "square", "four_three", "wide", "portrait"),
    "card_height": ("equal", "auto"),
    "spacing": ("compact", "normal", "spacious"),
    "text_align": ("left", "center"),
    "excerpt_length": ("hidden", "short", "medium", "full"),
}
DEFAULTS = {
    "columns": "3", "card_style": "raised", "layout": "grid",
    "orientation": "vertical", "image_position": "top",
    "image_ratio": "wide", "card_height": "equal",
    "spacing": "normal", "text_align": "left", "excerpt_length": "short",
    "accent": "", "background": "", "card_background": "", "text_color": "",
    "show_image": True, "show_title": True, "show_date": True,
    "show_excerpt": True, "show_author": False, "show_category": True,
    "show_likes": False, "show_comments": False,
}
BOOLEAN_FIELDS = tuple(k for k in DEFAULTS if k.startswith("show_"))
PALETTE_FIELDS = ("accent", "background", "card_background", "text_color")
PALETTE = re.compile(r"#[0-9a-fA-F]{6}\Z")


def parse_archive_design(raw):
    try:
        values = json.loads(raw or "{}") if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return DEFAULTS.copy()
    if not isinstance(values, dict):
        return DEFAULTS.copy()
    result = DEFAULTS.copy()
    for key, options in CHOICES.items():
        if values.get(key) in options:
            result[key] = values[key]
    for key in PALETTE_FIELDS:
        value = values.get(key, "")
        if isinstance(value, str) and (not value or PALETTE.fullmatch(value)):
            result[key] = value.lower()
    for key in BOOLEAN_FIELDS:
        if isinstance(values.get(key), bool):
            result[key] = values[key]
    return result


def validate_archive_design(form):
    values = {}
    for key, options in CHOICES.items():
        value = str(form.get(key, DEFAULTS[key]))
        if value not in options:
            raise ValueError(f"Invalid archive setting: {key}")
        values[key] = value
    for key in PALETTE_FIELDS:
        value = str(form.get(key, "")).strip()
        if value and not PALETTE.fullmatch(value):
            raise ValueError(f"Invalid archive color: {key}")
        values[key] = value.lower()
    for key in BOOLEAN_FIELDS:
        values[key] = form.get(key) == "on"
    return values


def archive_inline_styles(values):
    """Only server-validated hex colors reach inline CSS."""
    design = parse_archive_design(values)
    mapping = {
        "accent": "--archive-accent",
        "background": "--archive-page-bg",
        "card_background": "--archive-card-bg",
        "text_color": "--archive-card-text",
    }
    return " ".join(f"{css}: {design[key]};" for key, css in mapping.items() if design[key])
