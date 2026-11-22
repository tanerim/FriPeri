"""Validated, language-aware page blocks for the visual homepage builder."""
import html
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qs

MAX_DOCUMENT_BYTES = 500_000
SECTION_SVG_FILENAME = r'friperi-section-[0-9a-f]{32}\.svg'
SECTION_SVG_FIELDS = {'svg_pattern': ('ribbons', 'waves', 'grid'), 'svg_primary': 'color',
                      'svg_secondary': 'color', 'svg_opacity': (0, 100)}
BLOCK_TYPES = {'section', 'heading', 'text', 'list', 'table', 'image', 'video', 'button', 'divider', 'category', 'quote', 'callout', 'stats', 'team', 'faq', 'legacy_html'}

# Optional presentation settings keep existing documents on their theme defaults.
APPEARANCE_FIELDS = {
    'section': {'layout': ('stack', 'two', 'split', 'reverse_split', 'three', 'six', 'actions'),
                'surface': ('standard', 'full'), 'vertical_align': ('start', 'center', 'end'),
                'content_width': (360, 1920), 'min_height': (0, 1200), 'padding_y': (0, 200),
                'padding_x': (0, 120), 'gap': (0, 100), 'radius': (0, 120),
                'background_fit': ('cover', 'contain'), 'background_position': ('center', 'left', 'right', 'top', 'bottom'),
                'overlay_color': 'color', 'overlay_opacity': (0, 100),
                'svg_pattern': ('none', 'ribbons', 'waves', 'grid'),
                'svg_primary': 'color', 'svg_secondary': 'color',
                'svg_opacity': (0, 100), 'edge': ('flat', 'wave'), 'edge_color': 'color'},
    'heading': {'font_size': (18, 160), 'font_weight': ('normal', 'bold', 'heavy'),
                'accent_color': 'color', 'accent_opacity': (0, 100), 'accent_style': ('color_only', 'underline'), 'accent_new_line': ('yes', 'no')},
    'list': {'font_size': (10, 72), 'item_gap': (0, 48)},
    'table': dict.fromkeys(('cell_background', 'cell_color', 'header_background', 'header_color'), 'color'),
    'button': {'button_background': 'color', 'button_hover': 'color', 'button_text': 'color',
               'button_hover_text': 'color', 'font_size': (10, 48), 'width_mode': ('auto', 'full', 'custom'),
               'width_px': (40, 1200), 'height': (24, 240), 'radius': (0, 120),
               'variant': ('solid', 'outline', 'ghost', 'text_link', 'underlined'),
               'icon': ('external', 'arrow', 'none'), 'border_width': (0, 8),
               'border_color': 'color', 'padding_x': (0, 96), 'padding_y': (0, 48),
               'target': ('same_tab', 'new_tab')},
    'quote': {'font_size': (12, 72), 'attribution_size': (10, 36), 'quote_color': 'color',
              'attribution_color': 'color', 'border_color': 'color', 'border_width': (0, 12),
              'font_style': ('normal', 'italic')},
    'stats': {'value_color': 'color', 'label_color': 'color', 'card_background': 'color',
              'value_size': (16, 120), 'label_size': (10, 48), 'columns': (1, 4),
              'gap': (0, 64), 'padding': (0, 64)},
}


def validate_appearance(value, fields):
    if not isinstance(value, dict):
        raise ValueError('Invalid appearance settings')
    result = {}
    for key, rule in fields.items():
        if key not in value:
            continue
        setting = value[key]
        if rule == 'color':
            valid = isinstance(setting, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', setting)
            if valid:
                setting = setting.lower()
        elif isinstance(rule[0], int):
            valid = type(setting) is int and rule[0] <= setting <= rule[1]
        else:
            valid = isinstance(setting, str) and setting in rule
        if not valid:
            raise ValueError(f'Invalid appearance setting: {key}')
        result[key] = setting
    return result


def starter_document(settings, suffix='en'):
    """Editable initial homepage, populated only during first installation."""
    def value(key):
        return settings.get(f'{key}_{suffix}') or settings.get(f'{key}_en', '')

    style = {'tone': 'plain', 'align': 'center', 'width': 'normal'}
    blocks = [
        {**style, 'type': 'heading', 'level': 'h3', 'text': value('hero_kicker')},
        {**style, 'type': 'heading', 'level': 'h1', 'text': value('hero_title') or settings['site_name']},
        {**style, 'type': 'text', 'html': html.escape(value('hero_copy'), quote=False)},
    ]
    # Setup permits longer text than builder headings; keep it without truncation.
    for index, block in enumerate(blocks[:2]):
        if len(block['text']) > 500:
            blocks[index] = {**style, 'type': 'text', 'html': html.escape(block['text'], quote=False)}
    if settings.get('show_contact_link', '1') == '1':
        blocks.append({**style, 'type': 'button', 'text': 'Get in touch', 'url': '/contact'})
    for category in ('blog', 'notlar'):
        blocks.append({**style, 'type': 'category', 'category': category, 'count': 4, 'width': 'wide'})
    return json.dumps(validate_document(json.dumps(blocks)), ensure_ascii=False)


def safe_url(value, media=False):
    if not isinstance(value, str) or len(value) > 2048:
        return ''
    value = value.strip()
    if re.search(r'[\s\x00-\x1f\x7f\\]', value):
        return ''
    if value.startswith('/') and not value.startswith('//'):
        return value if not media or re.fullmatch(r'/static/uploads/[A-Za-z0-9_.-]+', value) else ''
    try:
        parsed = urlsplit(value)
        if parsed.scheme in ({'https'} if media else {'http', 'https'}) and parsed.hostname and not parsed.username and not parsed.password:
            _ = parsed.port
            return value
    except ValueError:
        pass
    return ''


def video_source(value):
    """Return a file URL or a canonical embed URL; never accept arbitrary iframes."""
    value = safe_url(value, media=True)
    if not value:
        return None
    parsed = urlsplit(value)
    host = parsed.hostname
    identifier = ''
    if host in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtube-nocookie.com', 'www.youtube-nocookie.com'}:
        if parsed.path == '/watch':
            identifier = parse_qs(parsed.query).get('v', [''])[0]
        elif parsed.path.startswith(('/embed/', '/shorts/')):
            identifier = parsed.path.split('/')[2]
    elif host == 'youtu.be':
        identifier = parsed.path.strip('/')
    if re.fullmatch(r'[A-Za-z0-9_-]{11}', identifier):
        return {'kind': 'embed', 'url': f'https://www.youtube-nocookie.com/embed/{identifier}'}
    if host in {'vimeo.com', 'www.vimeo.com', 'player.vimeo.com'}:
        identifier = parsed.path.rstrip('/').split('/')[-1]
        if re.fullmatch(r'[0-9]{1,12}', identifier):
            return {'kind': 'embed', 'url': f'https://player.vimeo.com/video/{identifier}'}
    if parsed.path.lower().endswith(('.mp4', '.webm', '.ogg')):
        return {'kind': 'file', 'url': value}
    return None


def safe_text_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return ''
    if re.search(r'[\s\x00-\x1f\x7f\\]', value):
        return ''
    if re.fullmatch(r'#[A-Za-z][\w:.-]*|mailto:[^\s<>"\\]+|tel:[+0-9().-]+', value):
        return value
    return safe_url(value)


class InlineHTML(HTMLParser):
    allowed = {'strong', 'b', 'em', 'i', 'u', 's', 'strike', 'del', 'ins',
               'sub', 'sup', 'mark', 'small', 'span', 'a', 'br', 'p', 'div', 'img',
               'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'pre', 'code',
               'kbd', 'samp', 'var', 'abbr', 'cite', 'q', 'hr', 'ul', 'ol', 'li',
               'dl', 'dt', 'dd', 'table', 'caption', 'thead', 'tbody', 'tfoot',
               'tr', 'th', 'td', 'figure', 'figcaption', 'details', 'summary'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.stack = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'iframe', 'object', 'svg', 'math'}:
            self.suppressed += 1
        if self.suppressed or tag not in self.allowed:
            return
        attributes = ''
        values = dict(attrs)
        # Only bounded presentation values, never arbitrary CSS or event handlers.
        styles = []
        for declaration in (values.get('style') or '').split(';'):
            key, sep, value = declaration.partition(':')
            key, value = key.strip().lower(), value.strip().lower()
            if not sep:
                continue
            valid = {
                'text-align': r'left|center|right|justify',
                'color': r'#[0-9a-f]{3,8}|rgb\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)',
                'background-color': r'#[0-9a-f]{3,8}|rgb\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)',
                'font-size': r'(?:[8-9]|[1-6][0-9]|7[0-2])px|smaller|larger',
                'vertical-align': r'sub|super|baseline',
                'font-weight': r'normal|bold|[1-9]00',
                'font-style': r'normal|italic',
                'text-decoration': r'none|underline|line-through',
                'font-family': r'serif|sans-serif|monospace',
                'line-height': r'1|1\.5|2|2\.5|3',
                'margin-left': r'(?:40|80|120)px',
            }.get(key)
            if valid and re.fullmatch(valid, value):
                styles.append(f'{key}:{value}')
        if styles:
            attributes += f' style="{";".join(styles)}"'
        for key in ('title', 'id'):
            if values.get(key):
                attributes += f' {key}="{html.escape(values[key][:500], quote=True)}"'
        if values.get('dir') in {'ltr', 'rtl', 'auto'}:
            attributes += f' dir="{values["dir"]}"'
        for key in ({'colspan', 'rowspan'} if tag in {'td', 'th'} else {'start', 'value'} if tag in {'ol', 'li'} else set()):
            if re.fullmatch(r'[0-9]{1,3}', values.get(key) or ''):
                attributes += f' {key}="{values[key]}"'
        if tag == 'th' and values.get('scope') in {'row', 'col'}:
            attributes += f' scope="{values["scope"]}"'
        if tag == 'details' and 'open' in values:
            attributes += ' open'
        if tag == 'img':
            values = dict(attrs)
            orig_class = (values.get('class') or '').split()
            align = next((value for value in ('left', 'right', 'none') if f'rich-image-{value}' in orig_class), 'none')
            width = next((value for value in ('25', '40', '50', '100') if f'rich-image-width-{value}' in orig_class), '40')
            src = safe_url(values.get('src', ''), media=True)
            if not src:
                return
            alt = html.escape((values.get('alt') or '')[:500], quote=True)
            attributes = (f' src="{html.escape(src, quote=True)}" alt="{alt}"'
                          f' class="rich-image rich-image-{align} rich-image-width-{width}" loading="lazy"')
        if tag == 'a':
            href = safe_text_url(values.get('href', ''))
            if href:
                attributes += f' href="{html.escape(href, quote=True)}" rel="noopener noreferrer"'
                if values.get('target') == '_blank':
                    attributes += ' target="_blank"'
        self.parts.append(f'<{tag}{attributes}>')
        if tag not in {'br', 'img', 'hr'}:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in {'br', 'img', 'hr'}:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'iframe', 'object', 'svg', 'math'}:
            self.suppressed = max(0, self.suppressed - 1)
            return
        if self.suppressed or tag not in self.stack:
            return
        while self.stack:
            current = self.stack.pop()
            self.parts.append(f'</{current}>')
            if current == tag:
                break

    def handle_data(self, data):
        if not self.suppressed:
            self.parts.append(html.escape(data))


def clean_inline(value):
    parser = InlineHTML()
    parser.feed(value)
    parser.close()
    return ''.join(parser.parts) + ''.join(f'</{tag}>' for tag in reversed(parser.stack))


def text(value, limit=20_000):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError('Invalid text')
    value.encode('utf-8')
    return value



def divider_wave_path(style):
    """Generate bounded decorative SVG paths, independent of user-supplied markup."""
    if style not in {'wave', 'wave-tight', 'zigzag'}:
        return ''
    points = ['M 0 24']
    if style == 'wave':
        for x in range(0, 1200, 80):
            points.append(f'C {x + 20} 2 {x + 20} 2 {x + 40} 24 S {x + 60} 46 {x + 80} 24')
    elif style == 'wave-tight':
        for x in range(0, 1200, 40):
            points.append(f'Q {x + 10} 4 {x + 20} 24 T {x + 40} 24')
    else:
        for x in range(0, 1200, 48):
            points.append(f'L {x + 24} 5 L {x + 48} 24')
    return ' '.join(points)

def validate_document(raw):
    if not isinstance(raw, str) or len(raw.encode('utf-8')) > MAX_DOCUMENT_BYTES:
        raise ValueError('Page is too large')
    try:
        data = json.loads(raw or '[]')
    except (ValueError, RecursionError) as exc:
        raise ValueError('Invalid page data') from exc
    return _validate_blocks(data, 0, [80], set())


def _validate_blocks(data, depth, remaining, anchors):
    if not isinstance(data, list) or len(data) > remaining[0]:
        raise ValueError('Use at most 80 blocks')
    remaining[0] -= len(data)
    result = []
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get('type'), str) or item.get('type') not in BLOCK_TYPES:
            raise ValueError('Invalid block')
        kind = item['type']
        block = {'type': kind,
                 'tone': item.get('tone') if item.get('tone') in ('plain', 'soft', 'accent', 'dark', 'white', 'custom') else 'plain',
                 'align': item.get('align') if item.get('align') in ('left', 'center', 'right') else 'left',
                 'width': item.get('width') if item.get('width') in ('normal', 'wide') else 'normal'}
        if block['tone'] == 'custom':
            color = item.get('background', '#ffffff')
            if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                raise ValueError('Invalid background color')
            block['background'] = color.lower()
        fg = item.get('foreground')
        if isinstance(fg, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', fg):
            block['foreground'] = fg.lower()
        if kind in APPEARANCE_FIELDS and 'appearance' in item:
            block['appearance'] = validate_appearance(item['appearance'], APPEARANCE_FIELDS[kind])
        if kind == 'divider':
            line_width = item.get('line_width', 2)
            line_style = item.get('line_style', 'single')
            line_color = item.get('line_color', '#a5b3be')
            if type(line_width) is not int or not 2 <= line_width <= 20:
                raise ValueError('Divider line width must be 2–20 px')
            if line_style not in ('single', 'dashed', 'dotted', 'wave', 'wave-tight', 'zigzag'):
                raise ValueError('Invalid divider line style')
            if not isinstance(line_color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', line_color):
                raise ValueError('Invalid divider line color')
            block.update(line_width=line_width, line_style=line_style, line_color=line_color.lower())
            if line_style in ('wave', 'wave-tight', 'zigzag'):
                block['line_path'] = divider_wave_path(line_style)
        if kind == 'category':
            block['category'] = text(item.get('category', ''), 200)
            count = item.get('count', 4)
            if type(count) is not int or not 1 <= count <= 16:
                raise ValueError('Use between 1 and 16 items')
            block['count'] = count
        if kind in {'heading', 'button'}:
            block['text'] = text(item.get('text', ''), 500)
        if kind == 'heading':
            block['level'] = item.get('level') if item.get('level') in ('h1', 'h2', 'h3') else 'h2'
            if 'accent' in item:
                block['accent'] = text(item['accent'], 160)
        elif kind == 'section':
            if depth >= 3:
                raise ValueError('Use at most three levels of sections')
            url = text(item.get('image', ''), 2048)
            block['image'] = safe_url(url, media=True)
            if url and not block['image']:
                raise ValueError('Invalid section image URL')
            svg_url = text(item.get('svg_url', ''), 100)
            if svg_url:
                if not re.fullmatch(r'/static/images/' + SECTION_SVG_FILENAME, svg_url):
                    raise ValueError('Invalid generated section SVG URL')
                block['svg_url'] = svg_url
            anchor = text(item.get('anchor', ''), 80)
            if anchor:
                if anchor in anchors or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', anchor):
                    raise ValueError('Invalid or duplicate section anchor')
                anchors.add(anchor)
            block['anchor'] = anchor
            block['children'] = _validate_blocks(item.get('children', []), depth + 1, remaining, anchors)
        elif kind == 'legacy_html':
            # Keep source verbatim; sanitize only when rendering. Original post fields also remain untouched.
            block['html'] = text(item.get('html', ''), MAX_DOCUMENT_BYTES)
        elif kind == 'text':
            block['html'] = clean_inline(text(item.get('html', '')))
        elif kind == 'quote':
            block['text'] = text(item.get('text', ''), 5000)
            block['attribution'] = text(item.get('attribution', ''), 500)
        elif kind == 'callout':
            block['title'] = text(item.get('title', ''), 500)
            block['text'] = text(item.get('text', ''), 5000)
        elif kind in {'stats', 'team', 'faq'}:
            items = item.get('items', [])
            if not isinstance(items, list) or len(items) > (8 if kind in {'stats', 'team'} else 20):
                raise ValueError('Invalid block items')
            fields = ({'value': 100, 'label': 500} if kind == 'stats'
                      else {'name': 200, 'title': 300} if kind == 'team'
                      else {'question': 500, 'answer': 5000})
            block['items'] = []
            for entry in items:
                if not isinstance(entry, dict):
                    raise ValueError('Invalid block item')
                member = {key: text(entry.get(key, ''), limit) for key, limit in fields.items()}
                if kind == 'team':
                    raw_photo = text(entry.get('photo', ''), 2048)
                    member['photo'] = safe_url(raw_photo, media=True)
                    if raw_photo and not member['photo']:
                        raise ValueError('Invalid team member photo')
                    member['shape'] = entry.get('shape') if entry.get('shape') in ('circle', 'rectangle') else 'rectangle'
                    member['fit'] = entry.get('fit') if entry.get('fit') in ('cover', 'contain') else 'cover'
                    member['orientation'] = entry.get('orientation') if entry.get('orientation') in ('landscape', 'portrait') else 'landscape'
                    # Non-destructive crop: zoom and focal point survive editing and publication.
                    for key, default, minimum, maximum in (
                        ('zoom', 1.0, 1.0, 3.0),
                        ('focal_x', 50.0, 0.0, 100.0),
                        ('focal_y', 50.0, 0.0, 100.0),
                    ):
                        value = entry.get(key, default)
                        if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= maximum:
                            raise ValueError('Invalid team photo crop')
                        member[key] = round(float(value), 2)
                block['items'].append(member)
        elif kind == 'list':
            items = item.get('items', [])
            if not isinstance(items, list) or len(items) > 100:
                raise ValueError('Invalid list')
            block.update(items=[text(entry, 2000) for entry in items], ordered=item.get('ordered') is True)
        elif kind == 'table':
            rows = item.get('rows', [])
            if not isinstance(rows, list) or len(rows) > 30:
                raise ValueError('Use at most 30 rows')
            if any(not isinstance(row, list) or not 1 <= len(row) <= 8 for row in rows):
                raise ValueError('Use at most 8 columns')
            if rows and any(len(row) != len(rows[0]) for row in rows):
                raise ValueError('Table rows must have the same number of cells')
            block['rows'] = [[text(cell, 1000) for cell in row] for row in rows]
            block['caption'] = text(item.get('caption', ''), 500)
            if 'cell_styles' in item:
                styles = item['cell_styles']
                if not isinstance(styles, list) or len(styles) != len(rows):
                    raise ValueError('Invalid table cell styles')
                block['cell_styles'] = []
                for row, style_row in zip(rows, styles):
                    if not isinstance(style_row, list) or len(style_row) != len(row):
                        raise ValueError('Invalid table cell styles')
                    block['cell_styles'].append([
                        validate_appearance(style, {'background': 'color', 'color': 'color'}) for style in style_row
                    ])
        elif kind in {'image', 'video'}:
            url = text(item.get('url', ''), 2048)
            block['url'] = safe_url(url, media=True)
            if url and (not block['url'] or (kind == 'video' and not video_source(url))):
                raise ValueError('Invalid media URL')
            block['caption'] = text(item.get('caption', ''), 500)
            block['alt'] = text(item.get('alt', ''), 500)
        elif kind == 'button':
            url = text(item.get('url', ''), 2048)
            block['url'] = url if re.fullmatch(r'#[A-Za-z][A-Za-z0-9_-]{0,79}', url) else safe_url(url)
            if url and not block['url']:
                raise ValueError('Invalid link URL')
        result.append(block)
    return result


def read_document(raw):
    try:
        return validate_document(raw)
    except ValueError:
        return []


def render_blocks(blocks):
    """Prepare display values for blocks and their nested content."""
    return [dict(block, video=video_source(block['url'])) if block['type'] == 'video'
            else dict(block, children=render_blocks(block['children'])) if block['type'] == 'section'
            else dict(block, html=clean_html(block['html'])) if block['type'] == 'legacy_html'
            else block for block in blocks]


def clean_html(value: str) -> str:
    allowed_tags = {
        "p", "br", "strong", "b", "em", "i", "u", "h1", "h2", "h3", "h4",
        "blockquote", "ul", "ol", "li", "pre", "code", "a", "table", "thead",
        "tbody", "tr", "th", "td",
    }
    value = re.sub(r"<\s*script.*?>.*?<\s*/\s*script\s*>", "", value, flags=re.I | re.S)
    value = re.sub(r"\son\w+\s*=\s*(['\"]).*?\1", "", value, flags=re.I | re.S)

    def replace_tag(match: re.Match[str]) -> str:
        raw = match.group(0)
        tag_match = re.match(r"</?\s*([a-z0-9]+)", raw, flags=re.I)
        if not tag_match:
            return ""
        tag = tag_match.group(1).lower()
        if tag not in allowed_tags:
            return ""
        if raw.startswith("</"):
            return f"</{tag}>"
        attrs = ""
        if tag == "a":
            href_match = re.search(r'href\s*=\s*["\']([^"\']+)["\']', raw, flags=re.I)
            if href_match and href_match.group(1).startswith(("http://", "https://", "mailto:")):
                attrs = f' href="{html.escape(href_match.group(1), quote=True)}" target="_blank" rel="noopener"'
        return f"<{tag}{attrs}>"

    cleaned = re.sub(r"<[^>]+>", replace_tag, value)
    return cleaned.strip() or "<p></p>"
