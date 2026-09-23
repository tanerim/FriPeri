# English-first language model

English is always the default public language. Only an explicit supported `lang`
query or language cookie selects the secondary language. `Accept-Language` is
used solely for the suggestion in **Admin > Language**.

## Storage and fallback

- `localization.py` owns metadata, lookup, English fallback, and content-field lookup.
- `translations/{en,tr,de,fr}.json` contain stable UI keys. English is canonical;
  missing secondary UI entries fall back to English.
- Custom UI entries use `ui_translations(language_code, translation_key,
  translation_value)` with a composite primary key. Add keys to the English
  dictionary to expose them in the grouped custom translation editor.
- Settings, category labels, and custom menu labels use `_en` and `_secondary`.
- Posts retain their original `title`, `excerpt`, and `body_html` as the English
  base, adding `title_secondary`, `excerpt_secondary`, and `body_html_secondary`.
  Post URLs, IDs, and shared metadata remain unchanged.
- Empty secondary content falls back to English. Optional empty blocks are omitted.

## First startup after upgrade

`init_db()` invokes the additive migration in `language_migration.py`. Before the
first upgrade of an existing database, SQLite's backup API writes a sibling file
named `<database>.pre-language-v1.bak`. Backups contain the site's private data
and use owner-only permissions; keep them with the database's normal backups.

The migration runs transactionally and records `language_model_version=1`.
Existing bilingual installations select Turkish as their secondary language;
fresh databases start with no secondary language. Legacy `_tr` settings and
columns are retained. Their values are copied to `_secondary`, and existing
English values are preserved. Previously unlabelled post text is kept verbatim
as base content and copied to the legacy secondary fields without guessing its
written language. Old custom links whose English labels were empty retain their
previous label as the base fallback.

Changing the secondary language archives its settings and content fields under
`secondary_archive_<code>` in the existing settings store. Selecting that language
again restores its fields for records that still exist. Selecting None hides the
secondary fields without deleting their values. Other languages begin empty and
fall back to English. Custom UI translations are independently retained by code.
Forms opened before a language change reject a stale save to avoid mixing content.

The migration does not drop legacy columns. For rollback to the old application,
restore the pre-upgrade database backup along with the old code; the old code does
not understand new secondary-language edits. Keep a fresh backup of any subsequent
edits before performing a rollback.

## Verification

Run with the project's configured Python interpreter:

```
.venv/bin/python -m unittest discover -s tests -v
```

The tests use temporary databases and test credentials. They cover fresh and
legacy schemas, language configuration, locale suggestions, cookies, custom
translations, fallback, secondary-content restoration, posts, menus, categories,
social settings, Design, contact submission, and authentication.
