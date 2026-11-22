"""Callout block presentation and media validation."""
import json
import pytest
from custom_home import validate_document

def callout(**overrides):
    return {"type":"callout","title":"Research insight",
            "text":"A meaningful result.",**overrides}

def test_legacy_callout_is_backward_compatible():
    block=validate_document(json.dumps([callout()]))[0]
    assert block["title"]=="Research insight"
    assert block["text"]=="A meaningful result."
    assert block["image_url"]==""
    assert "appearance" not in block

def test_complete_custom_callout():
    appearance={
        "accent_side":"right","accent_color":"#286e7a","accent_width":7,
        "shadow":"strong","background_color":"#f8fafb",
        "border_color":"#dee2e6","border_width":1,"radius":24,"padding":32,
        "title_color":"#16263f","title_size":38,"title_weight":"heavy",
        "title_style":"italic","title_decoration":"underline",
        "body_color":"#20435b","body_size":19,"body_weight":"semibold",
        "body_style":"italic","body_decoration":"none",
        "image_position":"left","image_width":35,"image_fit":"contain",
        "image_ratio":"square","image_radius":16,"gap":24
    }
    b=validate_document(json.dumps([callout(
        appearance=appearance,image_url="/static/uploads/example.png",
        image_alt="Research visualization")]))[0]
    assert b["appearance"]==appearance
    assert b["image_alt"]=="Research visualization"
    assert b["image_url"]=="/static/uploads/example.png"

@pytest.mark.parametrize("invalid",[
    {"accent_side":"center"},{"accent_width":100},{"title_size":5},
    {"title_weight":"ultra"},{"body_style":"oblique"},{"shadow":"big"},
    {"image_width":90},{"border_color":"red;position:absolute"}
])
def test_invalid_callout_styles_rejected(invalid):
    with pytest.raises(ValueError):
        validate_document(json.dumps([callout(appearance=invalid)]))

@pytest.mark.parametrize("url",["javascript:alert(1)","//attacker.example/image.png","/admin"])
def test_unsafe_callout_image_rejected(url):
    with pytest.raises(ValueError,match="Invalid callout image URL"):
        validate_document(json.dumps([callout(image_url=url)]))
