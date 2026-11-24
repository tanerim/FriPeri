"""Page Builder structure navigation, palette distinction and bulk controls."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/"static/home-builder.js").read_text(encoding="utf-8")
HTML=(ROOT/"templates/admin/custom_home.html").read_text(encoding="utf-8")
CSS=(ROOT/"static/page-builder-refresh.css").read_text(encoding="utf-8")


def test_bulk_buttons_are_both_present_in_the_workspace():
    assert 'id="builder-collapse-all"' in HTML
    assert 'id="builder-expand-all"' in HTML
    assert HTML.index('id="builder-collapse-all"') < HTML.index('id="builder-canvas"')
    assert "allBlocks(blocks()).forEach(block=>collapsedBlocks.add(block))" in JS
    assert "allBlocks(blocks()).forEach(block=>collapsedBlocks.delete(block))" in JS


def test_section_navigator_uses_custom_labels_and_keeps_save_data_untouched():
    assert 'id="builder-section-map"' in HTML
    assert "block.editor_name||'Section'" in JS
    assert "renderStructureMap()" in JS
    assert "target.scrollIntoView({behavior:'smooth',block:'start'})" in JS
    assert "block.editor_name=value;checkpoint();renderStructureMap()" in JS


def test_section_colors_are_editor_only_and_use_real_design_colors():
    for role in ("--color-accent", "--color-separator-1", "--color-separator-2",
                 "--color-separator-3", "--color-nav"):
        assert role in JS
    assert "sectionPaletteRoles" in JS
    assert "data-editor-section=true" in CSS
    assert "var(--editor-section-accent,#286e7a) 16%" in CSS
    assert "border-inline-start:5px" in CSS
    assert ".public-site" not in CSS.split("/* Editor Section palette:")[1]


def test_focus_mode_does_not_remove_block_data():
    assert 'id="builder-focus"' in HTML
    assert "layout.classList.toggle('is-focus-mode')" in JS
    assert ".builder-layout.is-focus-mode > .builder-palette{display:none}" in CSS
