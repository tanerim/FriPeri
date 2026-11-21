## Configuration and Data Storage

Normal content and design configuration belongs in the admin panel. Deployment paths and cookie names can be supplied through environment variables or a `.env` file in the project root.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SITE_DB_PATH` | `db/site.db` | SQLite database location. |
| `SITE_STATIC_DIR` | `static` | Directory served at `/static`. |
| `SITE_TEMPLATES_DIR` | `templates` | Jinja2 template directory. |
| `SITE_UPLOAD_DIR` | `static/uploads` | Destination for uploaded files. |
| `SESSION_COOKIE_NAME` | `site_session` | Administrator session cookie name. |
| `SESSION_COOKIE_SECURE` | `true` | Whether the session cookie uses the Secure flag. Default `true` (production). Set to `0` or `false` for local HTTP development. |
| `LANG_COOKIE_NAME` | `site_lang` | Language preference cookie name. |
| `SITE_SECRET_KEY` | Random fallback | Fallback signing secret before a database secret is loaded. An initialized database's `session_secret` takes precedence. |

Relative paths are resolved from the application directory. Restart the application after changing environment configuration.

For example, a local-development `.env` can contain:

```dotenv
SITE_DB_PATH=db/my-site.db
SESSION_COOKIE_SECURE=false
```

Database-backed settings take precedence over the site defaults in [site_defaults.py](../site_defaults.py). Existing installations have a persistent session secret stored in the database; routine setup does not require manually configuring one.

### Initial values and site defaults

The following variables provide setup inputs or fallback values. They are not an alternative to editing saved site settings in the admin panel. See [site_defaults.py](../site_defaults.py) and [initialization.py](../initialization.py) for defaults; the browser and CLI setup flows can supply their own initial text.

| Area | Environment variables |
| --- | --- |
| Site identity | `SITE_NAME`, `SITE_DESCRIPTION` |
| Welcome text | `HERO_KICKER_EN`, `HERO_KICKER_SECONDARY`, `HERO_TITLE_EN`, `HERO_TITLE_SECONDARY`, `HERO_COPY_EN`, `HERO_COPY_SECONDARY` |
| Hero image | `HERO_BACKGROUND_ENABLED`, `HERO_BACKGROUND_IMAGE_PATH` |
| Initial social URLs | `SOCIAL_LINKEDIN_URL`, `SOCIAL_TWITTER_URL` |
| Contact | `CONTACT_EMAIL`, `CONTACT_INTRO_EN`, `CONTACT_INTRO_SECONDARY`, `CONTACT_DETAILS_EN`, `CONTACT_DETAILS_SECONDARY` |
| Navigation visibility | `SHOW_LOGIN_LINK`, `SHOW_CONTACT_LINK`, `SHOW_ABOUT_LINK` |
| Navigation colors | `COLOR_NAV`, `COLOR_NAV_HOVER`, `COLOR_NAV_ACTIVE` |
| Feature colors | `COLOR_FEATURE_BG`, `COLOR_FEATURE_TEXT`, `COLOR_FEATURE_BORDER` |
| Accent colors | `COLOR_ACCENT_PRIMARY`, `COLOR_ACCENT_SECONDARY` |
| Separator colors | `COLOR_SEPARATOR_1`, `COLOR_SEPARATOR_2`, `COLOR_SEPARATOR_3` |
| CLI setup credentials | `ADMIN_USERNAME`, `ADMIN_PASSWORD` — consumed by `scripts/generate_db.py`; changing them does not reset an existing account. |

Site visibility and hero-background flags use `1` and `0`. Quote hexadecimal colors in `.env`, for example `COLOR_NAV="#245080"`.

Generic setup values might be `SITE_NAME="Example Site"`, `CONTACT_EMAIL=hello@example.com`, and `SOCIAL_LINKEDIN_URL=https://www.linkedin.com/in/example-user/`. Use your own values when deploying. Prefer the CLI's interactive password prompt over a literal password in shell history.

### Persistent data

The database contains posts, custom pages, categories, tags, administrator password hashes, menus, settings, block documents, contact messages, translations, and session data. Uploaded media files live separately in the upload directory. Back up both.

Uploaded URLs use `/static/uploads/<filename>`. If you override storage locations, ensure these URLs still resolve to the actual upload directory through the static directory layout or your web-server configuration. Setting `SITE_UPLOAD_DIR` alone does not create a new public URL mapping.


---

[Documentation index](index.md) · [Complete README](../README.md)
