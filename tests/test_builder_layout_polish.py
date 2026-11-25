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
