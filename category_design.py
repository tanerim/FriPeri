"""Safe, compact visual customization for individual category archives."""
import json
import re

DEFAULTS = {
    "columns": "3",
    "card_style": "raised",
    "accent": "",
    "background": "",
    "card_background": "",
    "text_color": "",
}
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
    if str(values.get("columns")) in ("1", "2", "3"):
        result["columns"] = str(values["columns"])
    if values.get("card_style") in ("raised", "outlined", "flat"):
        result["card_style"] = values["card_style"]
    for key in PALETTE_FIELDS:
        value = values.get(key, "")
        if isinstance(value, str) and (not value or PALETTE.fullmatch(value)):
            result[key] = value.lower()
    return result


def validate_archive_design(form):
    columns = str(form.get("columns", "3"))
    style = str(form.get("card_style", "raised"))
    if columns not in ("1", "2", "3") or style not in ("raised", "outlined", "flat"):
        raise ValueError("Invalid archive layout")
    values = {"columns": columns, "card_style": style}
    for key in PALETTE_FIELDS:
        value = str(form.get(key, "")).strip()
        if value and not PALETTE.fullmatch(value):
            raise ValueError(f"Invalid archive color: {key}")
        values[key] = value.lower()
    return values


def archive_inline_styles(values):
    """Only server-validated hex colors may reach an inline style declaration."""
    design = parse_archive_design(values)
    mapping = {
        "accent": "--archive-accent",
        "background": "--archive-page-bg",
        "card_background": "--archive-card-bg",
        "text_color": "--archive-card-text",
    }
    return " ".join(f"{css}: {design[key]};" for key, css in mapping.items() if design[key])
