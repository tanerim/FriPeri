"""Appearance persistence, validation and public rendering regression coverage."""
import json
import unittest
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from custom_home import validate_document


class BlockAppearanceTests(unittest.TestCase):
    def validate(self, block):
        return validate_document(json.dumps([block]))[0]

    def test_round_trip_all_types(self):
        blocks = [
            {'type': 'list', 'items': ['One'], 'appearance': {'font_size': 24, 'item_gap': 12}},
            {'type': 'table', 'rows': [['A', 'B']], 'appearance': {'cell_background': '#ABCDEF'},
             'cell_styles': [[{'background': '#123456', 'color': '#ffffff'}, {}]]},
            {'type': 'button', 'text': 'Go', 'url': '/about', 'appearance': {
                'button_background': '#123456', 'button_hover': '#654321', 'width_mode': 'full',
                'height': 80, 'radius': 8}},
            {'type': 'quote', 'text': 'Quote', 'appearance': {'font_style': 'normal', 'border_width': 0}},
            {'type': 'stats', 'items': [{'label': 'Projects', 'value': '42'}], 'appearance': {
                'value_size': 64, 'label_color': '#123456', 'columns': 4, 'padding': 20}},
        ]
        for block in blocks:
            with self.subTest(kind=block['type']):
                saved = self.validate(block)
                self.assertEqual(self.validate(saved), saved)
                self.assertIn('appearance', saved)
        self.assertEqual(self.validate(blocks[1])['appearance']['cell_background'], '#abcdef')

    def test_invalid_values(self):
        for appearance in ({'font_size': 500}, {'font_size': True}, {'font_size': '24'},
                           {'button_background': 'red;position:fixed'}, {'width_mode': 'bad'},
                           {'height': -1}, []):
            with self.subTest(appearance=appearance), self.assertRaises(ValueError):
                self.validate({'type': 'button', 'appearance': appearance})
        with self.assertRaises(ValueError):
            self.validate({'type': 'table', 'rows': [['A']], 'cell_styles': [[]]})
        with self.assertRaises(ValueError):
            self.validate({'type': 'table', 'rows': [['A']], 'cell_styles': [[{'color': 'red'}]]})

    def test_legacy_defaults(self):
        for kind in ('list', 'table', 'button', 'quote', 'stats'):
            with self.subTest(kind=kind):
                self.assertNotIn('appearance', self.validate({'type': kind}))

    def test_public_styles(self):
        env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parents[1] / 'templates'), autoescape=True)
        blocks = [self.validate({'type': 'table', 'rows': [['A']], 'tone': 'custom',
                                 'background': '#ffffff', 'foreground': '#123456',
                                 'appearance': {'header_color': '#654321'},
                                 'cell_styles': [[{'background': '#abcdef'}]]}),
                  self.validate({'type': 'button', 'url': '/about', 'text': 'Go',
                                 'appearance': {'width_mode': 'full', 'height': 80}})]
        rendered = env.get_template('partials/content_blocks.html').render(custom_blocks=blocks)
        self.assertIn('--block-header-color: #654321;', rendered)
        self.assertIn('background-color: #abcdef;', rendered)
        self.assertIn('data-button-width="full"', rendered)
        self.assertIn('--block-height: 80px;', rendered)
        self.assertIn('background: #ffffff;--text-color: #123456;', rendered)


if __name__ == '__main__':
    unittest.main()
