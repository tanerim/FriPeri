"""Team block layouts, bounded photos, biographies and backwards compatibility."""
import json
import pytest
from custom_home import validate_document

def make_team(appearance=None, members=None):
    block = {
        "type": "team",
        "items": members if members is not None else [
            {"name": "Researcher", "title": "Computational Linguistics",
             "bio": "Research on digital texts.", "photo": ""}
        ],
    }
    if appearance is not None:
        block["appearance"] = appearance
    return block

@pytest.mark.parametrize("direction", ["horizontal", "vertical"])
@pytest.mark.parametrize("style", ["classic", "cards", "alternating", "checkerboard"])
def test_team_layouts(direction, style):
    appearance = {"direction": direction, "style": style,
                  "columns": 3, "photo_width": 180, "gap": 24}
    saved = validate_document(json.dumps([make_team(appearance)]))[0]
    assert saved["appearance"] == appearance
    assert saved["items"][0]["bio"] == "Research on digital texts."

def test_legacy_single_member():
    saved = validate_document(json.dumps([make_team(
        members=[{"name": "Member", "title": "Researcher", "photo": ""}]
    )]))[0]
    assert len(saved["items"]) == 1
    assert saved["items"][0]["bio"] == ""

@pytest.mark.parametrize("appearance", [
    {"photo_width": 600}, {"photo_width": 0}, {"columns": 5},
    {"direction": "diagonal"}, {"style": "unknown"}, {"gap": -1}
])
def test_invalid_layout_rejected(appearance):
    with pytest.raises(ValueError):
        validate_document(json.dumps([make_team(appearance)]))
