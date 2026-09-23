"""Rich-text save/reload and untrusted HTML regression coverage."""
import json
import unittest

from custom_home import clean_inline, validate_document


class RichTextTests(unittest.TestCase):
    def test_save_and_reload(self):
        content = ('<h2>Heading</h2><p><s>old</s> <sub>2</sub><sup>3</sup>'
                   '<span style="color:#123456;font-size:24px">color</span></p>'
                   '<ul><li>One<ol><li>Nested</li></ol></li></ul>'
                   '<blockquote>Quote</blockquote><pre><code>x &lt; y</code></pre>'
                   '<table><caption>Data</caption><tbody><tr><th scope="col">Name</th>'
                   '<td colspan="2">Value</td></tr></tbody></table>'
                   '<dl><dt>Term</dt><dd>Meaning</dd></dl>'
                   '<details open><summary>More</summary><p>Details</p></details><hr>')
        saved = validate_document(json.dumps([{'type': 'text', 'html': content}]))
        self.assertEqual(saved[0]['html'], content)
        self.assertEqual(validate_document(json.dumps(saved)), saved)

    def test_untrusted_html(self):
        content = ('<script>alert(1)</script><svg><script>alert(2)</script></svg>'
                   '<p onclick="bad()" style="position:fixed;color:#123456;'
                   'background-image:url(javascript:bad())">Safe</p>'
                   '<a href="javascript:bad()">Link</a><img src="data:text/html,bad">')
        self.assertEqual(clean_inline(content), '<p style="color:#123456">Safe</p><a>Link</a>')

    def test_links_and_images(self):
        for url in ('https://example.com', '/pages/example', '#section',
                    'mailto:hello@example.com', 'tel:+901234567890'):
            result = clean_inline(f'<a href="{url}" target="_blank">Link</a>')
            self.assertIn(f'href="{url}"', result)
            self.assertIn('rel="noopener noreferrer"', result)
        result = clean_inline('<img src="/static/uploads/image.png" alt="A" '
                              'class="rich-image-left rich-image-width-25" onerror="bad()">')
        self.assertIn('rich-image-left rich-image-width-25', result)
        self.assertNotIn('onerror', result)

    def test_browser_style_output(self):
        content = '<span style="vertical-align:super;font-size:smaller;font-weight:700">2</span>'
        self.assertEqual(clean_inline(content), content)
        self.assertEqual(clean_inline('<div style="text-align:justify">Text</div>'),
                         '<div style="text-align:justify">Text</div>')


if __name__ == '__main__':
    unittest.main()
