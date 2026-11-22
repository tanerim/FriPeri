"""Regression tests for localization and image format validation."""
import io

from PIL import Image

from localization import (
    LANGUAGES, TRANSLATIONS, content_languages, detect_locale,
    localized_value, secondary_language, translate,
)
from main import _detect_image_format


def test_all_builtin_ui_locales_have_admin_navigation_and_builder_labels():
    required = (
        "dashboard.wizard_intro", "dashboard.wizard_text", "dashboard.wizard_action",
        "builder.section_add", "builder.section_add_placeholder", "builder.section_add_section",
        "admin.documentation", "admin.users", "users.title", "users.role_cc",
        "users.role_editor", "users.role_admin", "users.categories",
        "categories.edit_title",
        "builder.team", "builder.team_name", "builder.team_title",
        "builder.team_photo", "builder.team_shape",
        "builder.team_rectangle", "builder.team_circle",
        "builder.team_orientation", "builder.team_landscape", "builder.team_portrait",
        "builder.two_column_hero", "builder.two_column_first_heading",
        "builder.two_column_second_heading",
    )
    for lang in LANGUAGES:
        for key in required:
            assert TRANSLATIONS[lang].get(key, "").strip(), (lang, key)
            assert translate(lang, key) != key


def test_secondary_language_and_canonical_english_content():
    settings = {"secondary_language": "tr", "hero_title_en": "Welcome", "hero_title_secondary": "Hoş geldiniz"}
    assert secondary_language(settings)["code"] == "tr"
    assert [language["code"] for language in content_languages(settings)] == ["en", "tr"]
    assert localized_value(settings, "hero_title", "en") == "Welcome"
    assert localized_value(settings, "hero_title", "tr") == "Hoş geldiniz"
    settings["hero_title_secondary"] = ""
    assert localized_value(settings, "hero_title", "tr") == "Welcome"


def test_accept_language_q_weight_and_invalid_input():
    assert detect_locale("de-DE,de;q=0.8,en;q=0.5")["code"] == "de"
    assert detect_locale("tr;q=0.3,en;q=0.9")["code"] == "en"
    assert detect_locale("not a locale") is None


def test_real_image_magic_and_invalid_content():
    stream = io.BytesIO()
    Image.new("RGB", (4, 4), color=(20, 30, 40)).save(stream, format="PNG")
    stream.seek(0)
    assert _detect_image_format(stream) == ("PNG", ".png")
    assert _detect_image_format(io.BytesIO(b"not-an-image")) == (None, None)
