"""Guard the completeness of all global Design color templates."""
from color_templates import ROLE_KEYS, TEMPLATES, list_templates, validate_templates


def test_all_presets_have_ten_swatches_and_every_design_role():
    validate_templates()
    assert len(TEMPLATES) == 4
    for template in list_templates():
        assert len(template["colors"]) == 10
        assert set(template["settings"]) == set(ROLE_KEYS)
        assert all(len(color) == 7 and color.startswith("#") for color in template["settings"].values())


def test_original_user_palettes_are_preserved():
    presets = {item["id"]: item for item in list_templates()}
    assert presets["tidal-ember"]["colors"] == [
        "#001219", "#005f73", "#0a9396", "#94d2bd", "#e9d8a6",
        "#ee9b00", "#ca6702", "#bb3e03", "#ae2012", "#9b2226"]
    assert presets["ember-after-dark"]["colors"] == [
        "#03071e", "#370617", "#6a040f", "#9d0208", "#d00000",
        "#dc2f02", "#e85d04", "#f48c06", "#faa307", "#ffba08"]
    assert presets["sunlit-horizon"]["colors"][:5] == [
        "#0d3b66", "#faf0ca", "#f4d35e", "#ee964b", "#f95738"]
    assert presets["electric-orchid"]["colors"] == [
        "#f72585", "#b5179e", "#7209b7", "#560bad", "#480ca8",
        "#3a0ca3", "#3f37c9", "#4361ee", "#4895ef", "#4cc9f0"]
