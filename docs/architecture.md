# Application architecture

## Structure

FriPeri is a Python FastAPI application with server-rendered Jinja2 templates, browser-side JavaScript and CSS, and a local SQLite database. A basic deployment requires neither a separate database server nor an external SMTP service.

| Module or directory | Role |
| --- | --- |
| `main.py` | FastAPI routes, admin pages, authentication, sessions, uploads, backups and public pages. |
| `initialization.py` | Database initialization, schema migration, first-run validation and password hashing. |
| `site_defaults.py` | Default setting values, optionally derived from environment variables. |
| `localization.py`, `language_migration.py` | Language support and content migration. |
| `custom_home.py` | Custom homepage facilities. |
| `navigation.py` | Navigation helpers. |
| `scripts/generate_db.py` | CLI setup of a new instance. |
| `scripts/reset_friperi.py` | Factory reset helper. |
| `templates/` | Jinja2 public and administrator page templates. |
| `static/` | Styles, browser JavaScript and static assets. |
| `static/uploads/` | Runtime media files (not tracked in Git). |
| `db/` | Local SQLite database storage (database files not tracked in Git). |
| `translations/` | Language dictionaries and migration notes. |

## Request and startup lifecycle

1. Runtime paths, cookie flags and fallback signing key are configured from the environment.
2. At startup, an existing initialized database is migrated; a fresh database requires first-run setup.
3. First-run setup creates administrator credentials, persistent site configuration and a session secret.
4. Public HTTP routes render content with Jinja2; authenticated administrators use `/admin`.
5. Persistent content, administrator password hashes, messages and site configuration live in SQLite. Media files live separately in the uploads directory.

## Security-sensitive areas

- An initialized site's persistent session signing secret is loaded from database settings; a random fallback or `SITE_SECRET_KEY` is used before this point.
- Authentication uses salted password hashes; deployment must keep database files private.
- Backup endpoints, upload handling, static file serving, CSRF protection and administrative authorization require ongoing review.
- The new-installation screen must not be exposed to untrusted visitors before an administrator account is created.
- Uploaded images and contact-form content are untrusted input. Filesystem paths and resulting HTML output require appropriate checks.

This document is an architectural description, not a penetration-testing report.

## Related guides

[Installation](installation.md) · [Configuration](configuration.md) · [User guide](user-guide.md) · [Security policy](../SECURITY.md)
