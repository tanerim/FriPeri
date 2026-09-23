"""Additive compatibility migration. Legacy columns and settings are retained."""
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from localization import LOCALIZED_SETTINGS, SECONDARY_COLUMNS


def backup_before_language_migration(path):
    if not path.exists() or not path.stat().st_size:
        return
    with closing(sqlite3.connect(path)) as source:
        exists = source.execute("SELECT 1 FROM sqlite_master WHERE name='site_settings'").fetchone()
        if exists and source.execute("SELECT 1 FROM site_settings WHERE key='language_model_version'").fetchone():
            return
        backup = path.with_name(path.name + '.pre-language-v1.bak')
        if not backup.exists():
            descriptor, temporary = tempfile.mkstemp(prefix=backup.name, dir=path.parent)
            os.close(descriptor)
            try:
                with closing(sqlite3.connect(temporary)) as destination:
                    source.backup(destination)
                try:
                    # Concurrent workers may back up, but never replace a backup.
                    os.link(temporary, backup)
                except FileExistsError:
                    pass
            finally:
                os.unlink(temporary)


def migrate_languages(conn, add_column, set_settings):
    if conn.execute("SELECT 1 FROM site_settings WHERE key='language_model_version'").fetchone():
        return
    old = {row['key']: row['value'] for row in conn.execute('SELECT key, value FROM site_settings')}
    columns = {table: {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')} for table in SECONDARY_COLUMNS}
    legacy = any(key.endswith('_tr') for key in old) or any('menu_label_tr' in cols or 'label_tr' in cols for cols in columns.values())
    for table, fields in SECONDARY_COLUMNS.items():
        for field in fields:
            add_column(conn, table, field, "TEXT NOT NULL DEFAULT ''")
    conn.execute('''CREATE TABLE IF NOT EXISTS ui_translations (
        language_code TEXT NOT NULL, translation_key TEXT NOT NULL,
        translation_value TEXT NOT NULL DEFAULT '',
        PRIMARY KEY(language_code, translation_key))''')
    updates = {}
    for field in LOCALIZED_SETTINGS:
        legacy_key = f'{field}_tr'
        value = old.get(legacy_key, os.getenv(legacy_key.upper(), '') if legacy else '')
        updates[f'{field}_secondary'] = old.get(f'{field}_secondary', value)
    if 'menu_label_tr' in columns['categories']:
        conn.execute("UPDATE categories SET menu_label_secondary=menu_label_tr WHERE menu_label_secondary=''")
    if 'label_tr' in columns['custom_menu_items']:
        conn.execute("UPDATE custom_menu_items SET label_secondary=label_tr WHERE label_secondary=''")
        # Older custom items allowed English to be empty and used Turkish as fallback.
        conn.execute("UPDATE custom_menu_items SET label_en=label_tr WHERE label_en=''")
    conn.execute("UPDATE categories SET menu_label_en=name WHERE menu_label_en=''")
    # Posts previously had shared, unlabelled text. Preserve it verbatim as base
    # content and as the legacy secondary version; never infer its written language.
    if legacy:
        conn.execute('''UPDATE posts SET title_secondary=title,
            excerpt_secondary=excerpt, body_html_secondary=CASE WHEN body_html='' THEN body ELSE body_html END''')
    updates.update(secondary_language='tr' if legacy else '', secondary_language_code='',
                   secondary_language_name='', show_language_switcher='1',
                   secondary_content_code='tr' if legacy else '', language_model_version='1')
    set_settings(conn, updates)


def insert_custom_menu(conn, values):
    """Old installations retain a NOT NULL label_tr column without a default."""
    legacy = 'label_tr' in {row['name'] for row in conn.execute('PRAGMA table_info(custom_menu_items)')}
    columns = 'label_secondary,label_en,url,sort_order,show_in_menu,new_tab'
    if legacy:
        columns += ',label_tr'
        values = (*values, '')
    return conn.execute(f"INSERT INTO custom_menu_items ({columns}) VALUES ({','.join('?' for _ in values)})", values)


def switch_secondary_content(conn, settings, new_code, set_settings):
    """Keep only two active field sets, archiving secondary values on a switch."""
    previous = settings.get('secondary_content_code', '')
    if not new_code or previous == new_code:
        return
    if previous:
        archive = {'settings': {f'{field}_secondary': settings.get(f'{field}_secondary', '') for field in LOCALIZED_SETTINGS}}
        for table, fields in SECONDARY_COLUMNS.items():
            archive[table] = {str(row['id']): {field: row[field] for field in fields}
                              for row in conn.execute(f"SELECT id,{','.join(fields)} FROM {table}")}
        set_settings(conn, {f'secondary_archive_{previous}': json.dumps(archive, ensure_ascii=False)})
    saved = conn.execute('SELECT value FROM site_settings WHERE key=?', (f'secondary_archive_{new_code}',)).fetchone()
    archive = json.loads(saved['value']) if saved else {}
    set_settings(conn, {f'{field}_secondary': archive.get('settings', {}).get(f'{field}_secondary', '') for field in LOCALIZED_SETTINGS})
    for table, fields in SECONDARY_COLUMNS.items():
        conn.execute(f"UPDATE {table} SET " + ','.join(f"{field}=''" for field in fields))
        for row_id, values in archive.get(table, {}).items():
            conn.execute(f"UPDATE {table} SET " + ','.join(f'{field}=?' for field in fields) + ' WHERE id=?',
                         (*[values.get(field, '') for field in fields], row_id))
    set_settings(conn, {'secondary_content_code': new_code})
