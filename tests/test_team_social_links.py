"""Optional Team contact icons and title typography validation."""
import json

import pytest
from custom_home import validate_document


def team(member, appearance=None):
    value = {"type": "team", "items": [member]}
    if appearance is not None:
        value["appearance"] = appearance
    return value


def test_team_contact_links_and_title_typography():
    item = {
        "name": "Researcher", "title": "Computational Linguistics",
        "twitter": "https://x.com/researcher",
        "linkedin": "https://www.linkedin.com/in/researcher/",
        "website": "https://example.org",
        "email": "researcher@example.org",
    }
    appearance = {
        "title_size": 18, "title_color": "#20435b",
        "title_weight": "semibold", "title_style": "italic",
        "title_font": "serif",
    }
    value = validate_document(json.dumps([team(item, appearance)]))[0]
    for key in ("twitter", "linkedin", "website", "email"):
        assert value["items"][0][key] == item[key]
    assert value["appearance"] == appearance


def test_empty_social_links_are_saved_as_empty_strings():
    value = validate_document(json.dumps([
        team({"name": "Researcher", "title": "Professor"})
    ]))[0]["items"][0]
    assert not any(value[key] for key in ("twitter", "linkedin", "website", "email"))


@pytest.mark.parametrize("key,url", [
    ("twitter", "javascript:alert(1)"),
    ("twitter", "https://example.org/not-twitter"),
    ("linkedin", "https://linkedin.com.evil.example/in/example"),
    ("website", "javascript:alert(1)"),
    ("email", "not-an-email"),
    ("email", "bad@invalid"),
])
def test_invalid_team_links_are_rejected(key, url):
    with pytest.raises(ValueError):
        validate_document(json.dumps([team({
            "name": "Researcher", "title": "Professor", key: url
        })]))


@pytest.mark.parametrize("settings", [
    {"title_size": 60}, {"title_color": "red"},
    {"title_weight": "gigantic"}, {"title_style": "underline"},
    {"title_font": "unsafe"},
])
def test_invalid_title_typography_is_rejected(settings):
    with pytest.raises(ValueError):
        validate_document(json.dumps([team({"name": "R"}, settings)]))
