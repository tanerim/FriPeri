"""Structural regression checks for the Custom Home editor layout.

These are intentionally source-level checks: browser sizing is verified in
manual responsive testing, while these checks prevent known regressions.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static/page-builder-refresh.css").read_text()
JS = (ROOT / "static/home-builder.js").read_text()


def test_focus_mode_expands_workspace_and_hides_palette():
    assert ".builder-layout.is-focus-mode" in CSS
    assert "grid-template-columns:minmax(0,1fr)!important" in CSS
    assert ".builder-layout.is-focus-mode > .builder-palette" in CSS
    assert "display:none!important" in CSS
    assert "grid-column:1/-1" in CSS


def test_section_settings_use_responsive_columns():
    assert "grid-template-columns:repeat(3,minmax(0,1fr))" in CSS
    assert ".builder-section-svg-panel" in CSS
    assert "grid-template-columns:minmax(0,1fr)" in CSS
    assert "layout.classList.add('builder-section-layout-panel')" in JS


def test_section_add_controls_have_plain_label_and_aligned_action():
    assert "Choose a block to add…" in JS
    assert "section_add_placeholder" not in JS
    assert ".builder-section-add-button" in CSS
    assert "min-height:44px;align-self:end" in CSS


def test_child_blocks_are_wide_and_colors_are_named():
    assert ".custom-section > .builder-section-content" in CSS
    assert "width:94%;max-width:none" in CSS
    assert "Background color" in JS
    assert "Overlay color" in JS
    assert "Title text color" in JS
    assert "Text color" in JS


def test_block_color_pickers_distinguish_foreground_and_background():
    assert "field('Text color',block.foreground" in JS
    assert "field('Block background color',block.background" in JS
    assert "field(t('color_selection')" not in JS


def test_section_controls_before_general_style_bar():
    assert "card.insertBefore(tools,card.querySelector(':scope > .builder-style-controls'))" in JS
    assert "card._sectionAddControls=addControls" in JS
    assert "if(card._sectionAddControls)card.append(card._sectionAddControls)" in JS


def test_add_block_toolbar_has_explicit_button():
    assert "Add a block to this section" in JS
    assert "button('+ Add block',addSelectedBlock" in JS
    assert "add.addEventListener('change',()=>{" not in JS
    assert "grid-template-columns:minmax(220px,1fr) minmax(220px,2fr) auto auto" in CSS


def test_top_level_sections_have_black_dividers():
    assert "border-top:5px solid #000" in CSS
    assert ".builder-block[data-editor-section=true] ~ .builder-block[data-editor-section=true]" in CSS


def test_sunlit_horizon_editor_child_headers():
    assert "card.dataset.sunlitChild='true'" in JS
    for color in ("#0d3b66", "#f4d35e", "#ee964b", "#f95738", "#faf0ca"):
        assert color in JS
    assert ".builder-block[data-sunlit-child=true] > .builder-block-header" in CSS
