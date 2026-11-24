"""Builder accordion state must not be reset when unrelated blocks change.

These checks protect the JS behavior used by Homepage, About and Pages.
"""
from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / "static/home-builder.js").read_text(encoding="utf-8")


def test_section_svg_has_no_forced_open_on_every_render():
    assert "generator.open = depth === 0 && !hero" not in JS
    assert "panel.open=true;\n    panel.append(el('summary','','SVG background designer'))" not in JS
    assert "bindPanelState(block,'section:svg',sectionSvgGenerator(block,body))" in JS


def test_independent_section_panels_remember_open_state():
    assert "new WeakMap()" in JS
    assert "bindPanelState(block,'section:layout'" in JS
    assert "bindPanelState(block,'section:background'" in JS
    assert "state.set(key,panel.open)" in JS


def test_callout_and_image_panels_do_not_open_unrelated_controls():
    assert "new Set(['Accent & frame','Heading typography','Body typography','Image layout'])" not in JS
    assert "bindPanelState(block,'callout:'+name" in JS
    assert "bindPanelState(block,'image:'+title" in JS


def test_svg_preview_is_lazy_and_cancels_when_panel_closes():
    assert "if(panel.open && panel.isConnected)redraw()" in JS
    assert "if(!panel.open){clearTimeout(previewTimer);requestCounter++;}" in JS


def test_divider_changes_do_not_touch_section_panels():
    assert "block.line_style=styleInput.value;draw();change();" in JS
    assert "renderBlocks(blocks(),canvas,0)" in JS
