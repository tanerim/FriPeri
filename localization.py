"""English-first UI dictionaries and the two active content languages."""
import json
import re
from pathlib import Path

LANGUAGES = {
    'en': {'code': 'en', 'name': 'English', 'native_name': 'English'},
    'tr': {'code': 'tr', 'name': 'Turkish', 'native_name': 'Türkçe'},
    'de': {'code': 'de', 'name': 'German', 'native_name': 'Deutsch'},
    'fr': {'code': 'fr', 'name': 'French', 'native_name': 'Français'},
}
TRANSLATIONS = {
    code: json.loads((Path(__file__).parent / 'translations' / f'{code}.json').read_text())
    for code in LANGUAGES
}
# Keep the unchanged About template's historical identifiers compatible.
ALIASES = {'about': 'nav.about', 'focus_copy': 'home.focus_copy'}
LOCALIZED_SETTINGS = (
    'hero_kicker', 'hero_title', 'hero_copy', 'contact_intro', 'contact_details', 'footer_text',
    'feature_blog_desc', 'feature_notes_desc', 'feature_contact_desc', 'custom_home', 'about_page'
)
SECONDARY_COLUMNS = {
    'categories': ('menu_label_secondary', 'description_secondary'),
    'custom_menu_items': ('label_secondary',),
    'posts': ('title_secondary', 'excerpt_secondary', 'body_html_secondary'),
}


def primary_language(settings=None):
    return LANGUAGES['en']


def secondary_language(settings):
    mode = settings.get('secondary_language', '')
    if mode in LANGUAGES and mode != 'en':
        return LANGUAGES[mode]
    if mode == 'custom':
        code = settings.get('secondary_language_code', '')
        name = settings.get('secondary_language_name', '').strip()
        if re.fullmatch(r'[a-z]{2,3}(?:-[a-z0-9]{2,8})*', code) and code not in LANGUAGES and name:
            return {'code': code, 'name': name, 'native_name': name}
    return None


def content_languages(settings):
    result = [dict(LANGUAGES['en'], suffix='en')]
    secondary = secondary_language(settings)
    if secondary:
        result.append(dict(secondary, suffix='secondary'))
    return result


def localized_value(values, field, lang):
    """Secondary text is optional; the English value is always canonical."""
    values = dict(values)
    primary = values.get(f'{field}_en', values.get(field, '')) or ''
    return (values.get(f'{field}_secondary', '') or primary) if lang != 'en' else primary


def translate(lang, key, custom=None):
    key = ALIASES.get(key, key)
    base = TRANSLATIONS['en'].get(key, key)
    value = (custom or {}).get(key) or TRANSLATIONS.get(lang, {}).get(key)
    return value if value and value.strip() else base


def detect_locale(header):
    """Accept-Language is advisory only; ignore malformed and disabled entries."""
    candidates = []
    for index, part in enumerate(header[:1024].split(',')):
        pieces = part.strip().split(';')
        locale = pieces[0].strip()
        if not re.fullmatch(r'[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*', locale):
            continue
        try:
            quality = float(pieces[1].strip().removeprefix('q=')) if len(pieces) > 1 else 1
        except ValueError:
            continue
        if 0 < quality <= 1:
            candidates.append((-quality, index, locale))
    if not candidates:
        return None
    locale = min(candidates)[2]
    code = locale.split('-')[0].lower()
    return {'locale': locale, 'code': code, 'name': LANGUAGES.get(code, {}).get('name', code.upper()),
            'supported': code in LANGUAGES}
