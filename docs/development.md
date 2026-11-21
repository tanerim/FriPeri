## Development

### Repository Layout

| Path | Responsibility |
| --- | --- |
| `main.py` | Application routes, authentication, public rendering, and admin handlers. |
| `initialization.py` | Database initialization, schema updates, and credential hashing. |
| `custom_home.py` | Shared block validation, HTML filtering, media URLs, and starter documents. |
| `navigation.py` | Menu hierarchy validation and public navigation trees. |
| `localization.py` | Language metadata, UI translations, and content fallback. |
| `language_migration.py` | Language schema migration and secondary-language archives. |
| `site_defaults.py` | Default site configuration and supported social platforms. |
| `templates/` | Public and admin Jinja2 templates. |
| `templates/admin/homepage.html` | Unified homepage mode selector and feed settings. |
| `templates/admin/custom_home.html` | Custom editor fragment included in the Homepage screen. |
| `static/` | Runtime CSS, JavaScript, and uploaded media. |
| `assets/` | Source stylesheets for the admin and first-run interfaces. |
| `translations/` | Built-in UI dictionaries and language migration documentation. |
| `scripts/` | CLI initialization, reset, and test-suite entry point. |
| `db/`, `static/uploads/`, `backups/` | Runtime database, uploaded media, and ZIP archives; keep persistent copies when deploying. |
| `licenses/` | Third-party license notices. |

For local development, start the application with automatic reload:

```bash
SESSION_COOKIE_SECURE=false python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### Working on Styles

The admin and first-run styles use Tailwind CSS **v4.1.18**. Their compiled stylesheets are committed, so end users do not need a frontend build.

With the matching Tailwind standalone CLI installed, rebuild from the project root:

```bash
tailwindcss -i assets/admin.css -o static/admin.css --minify
tailwindcss -i assets/first-run.css -o static/first-run.css --minify
```

Review the output before replacing a committed stylesheet: runtime CSS also contains additional plain-CSS rules that are not necessarily reproduced from `assets/`. Preserve those rules when rebuilding. Keep source and compiled changes together in commits. Public styles, homepage editor styles, and image crop styles also have dedicated files under `static/`.

### Validation

Run `node tests/rich_text_browser.cjs` for isolated Chromium checks of text formatting, headings, lists, table operations, paste filtering, appearance settings, cell colors and responsive toolbar layout (set `CHROMIUM` if needed). Run `python -m unittest discover -s tests` for rich-text server filtering and document round-trip tests. `scripts/check_admin_changes.py` provides a broader test discovery entry point; these focused tests do not replace checking complete application flows.

For documentation and implementation changes, use an isolated installation and check the relevant flows:

1. Complete first-run setup and sign in.
2. Create a draft, preview it, publish it, and verify anonymous visibility.
3. Edit a custom page and both homepage modes; verify saving and navigation.
4. Upload/crop an image and preview desktop/mobile layouts.
5. Configure a secondary language and verify English fallback.
6. Submit a contact message and check the admin inbox.
7. Exercise backup/restore only on disposable data.

After setup, `GET /health` returns `status`, `database`, and `uploads`. It reports process-level information rather than a full database integrity or readiness check, and includes filesystem paths. Before setup, it redirects to the installer like other non-static routes.


---

[Documentation index](index.md) · [Complete README](../README.md)

## Automated regression tests

For an isolated test environment, dependency installation, ASGI endpoint tests, the optional Playwright browser suite and the manual mobile/browser checklist, see [Local regression and UI testing](testing.md). Tests are run locally, not through GitHub Actions.
