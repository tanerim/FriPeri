"""Validated, language-aware page blocks for the visual homepage builder."""
import html
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qs

MAX_DOCUMENT_BYTES = 500_000
BLOCK_TYPES = {'heading', 'text', 'list', 'table', 'image', 'video', 'button', 'divider', 'category', 'quote', 'callout', 'stats', 'faq', 'legacy_html'}


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


class InlineHTML(HTMLParser):
    allowed = {'strong', 'b', 'em', 'i', 'u', 'a', 'br', 'p', 'img'}

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
            href = safe_url(dict(attrs).get('href', ''))
            if href:
                attributes = f' href="{html.escape(href, quote=True)}" rel="noopener noreferrer"'
        self.parts.append(f'<{tag}{attributes}>')
        if tag not in {'br', 'img'}:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in {'br', 'img'}:
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


def validate_document(raw):
    if not isinstance(raw, str) or len(raw.encode('utf-8')) > MAX_DOCUMENT_BYTES:
        raise ValueError('Page is too large')
    try:
        data = json.loads(raw or '[]')
    except (ValueError, RecursionError) as exc:
        raise ValueError('Invalid page data') from exc
    if not isinstance(data, list) or len(data) > 80:
        raise ValueError('Use at most 80 blocks')
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
        elif kind in {'stats', 'faq'}:
            items = item.get('items', [])
            if not isinstance(items, list) or len(items) > (8 if kind == 'stats' else 20):
                raise ValueError('Invalid block items')
            fields = {'value': 100, 'label': 500} if kind == 'stats' else {'question': 500, 'answer': 5000}
            block['items'] = []
            for entry in items:
                if not isinstance(entry, dict):
                    raise ValueError('Invalid block item')
                block['items'].append({key: text(entry.get(key, ''), limit) for key, limit in fields.items()})
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
        elif kind in {'image', 'video'}:
            url = text(item.get('url', ''), 2048)
            block['url'] = safe_url(url, media=True)
            if url and (not block['url'] or (kind == 'video' and not video_source(url))):
                raise ValueError('Invalid media URL')
            block['caption'] = text(item.get('caption', ''), 500)
            block['alt'] = text(item.get('alt', ''), 500)
        elif kind == 'button':
            url = text(item.get('url', ''), 2048)
            block['url'] = safe_url(url)
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
    """Add trusted video rendering metadata without storing derived attributes."""
    return [dict(block, video=video_source(block['url'])) if block['type'] == 'video'
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
