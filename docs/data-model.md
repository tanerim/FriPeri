# SQLite data and persistence guide

This document summarizes the tables explicitly created by the initialization/migration code. Migration routines may add columns and other structures over time; consult `initialization.py` and an initialized database for authoritative DDL.

## Tables created or migrated

| Table | Data domain |
| --- | --- |
| `custom_pages` | Standalone content pages |
| `site_settings` | Persistent site configuration, including session secrets |
| `users` | Administrator accounts and credential hashes |
| `categories` | Content categories |
| `posts` | Published and draft posts |
| `tags` | Reusable content tags |
| `post_tags` | Post-to-tag relationships |
| `contact_messages` | Contact form submissions and sender details |
| `custom_menu_items` | Configurable navigation |
| `revoked_session_tokens` | Invalidated login tokens |

## Data ownership

- Content and settings, including personal information submitted through contact forms, are stored in SQLite.
- Administrator credentials are stored as salted password hashes rather than plaintext passwords.
- Generated and user-uploaded images are stored under `static/uploads/` by default.
- Full recovery needs **both** the database and media uploads.
- Database files, SQLite WAL/SHM sidecars, backups and uploaded media must remain excluded from version control.

## Database lifecycle

1. Fresh install: browser-based first-run workflow or `scripts/generate_db.py`.
2. Existing install: automatic migration runs at application startup.
3. Maintenance: back up SQLite and uploads together; validate backups with a restore test.
4. Factory reset: use `scripts/reset_friperi.py` only after confirming destructive implications and creating a recovery point.

See [configuration](configuration.md), [installation](installation.md) and [maintenance](maintenance.md).
