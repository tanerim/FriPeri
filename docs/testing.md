# Local regression and UI testing

FriPeri tests are designed to run **locally**, without GitHub Actions and without using production data. No test is intended to modify an existing deployment.

## 1. Prepare a disposable environment

```bash
python3 -m venv .venv-test
source .venv-test/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip check
```

For security advisory checks install the optional scanner and run it separately:

```bash
python -m pip install pip-audit
python -m pip_audit -r requirements.txt
```

## 2. Python and ASGI regression suite

```bash
python -m pytest -q tests/
```

- `test_documentation.py`: Markdown parsing, internal links, path isolation, HTML escaping, caching and cache invalidation.
- `test_nested_sections.py`: section nesting, depth and block count limits.
- `test_backup_security.py`: SQLite backup/restore, archive path safety and corrupt archive handling.
- `test_security_guards.py`: same-origin administrative requests and login attempt thresholds.
- `test_localization_media.py`: UI labels in four languages, secondary-language fallback and image signature validation.
- `test_integration_flows.py`: a temporary initialized site, first-run setup, login/logout, authorization, post create/edit/delete, contact submissions, documentation route and health response.
- `test_browser_smoke.py`: optional Playwright checks; skipped unless an isolated local test URL is explicitly configured.

The integration tests use a temporary SQLite database and temporary backup/upload directories. They do not need a running FriPeri service or access to live site data. They require `httpx`, declared in `requirements-dev.txt`.

## 3. Optional browser smoke checks

Use a dedicated *localhost* installation with disposable content. Install the Chromium browser used by Playwright:

```bash
python -m playwright install chromium firefox
```

Start that disposable FriPeri instance, then in another terminal:

```bash
export FRIPERI_TEST_BASE_URL=http://127.0.0.1:8000
export FRIPERI_TEST_USER=admin
read -rsp 'Disposable test password: ' FRIPERI_TEST_PASSWORD
echo
export FRIPERI_TEST_PASSWORD
python -m pytest -q tests/test_browser_smoke.py
unset FRIPERI_TEST_PASSWORD
```

The optional browser tests run in both Chromium and Firefox and check that the sidebar control sits above the logo, collapse state survives a reload, the Markdown reader loads, the mobile viewport does not exhibit horizontal overflow, and Design lacks its redundant shortcuts. Browser availability and the test service determine whether these checks can run; they are not part of the default mandatory test environment.

For a local HTTP instance, set `SESSION_COOKIE_SECURE=false` on **that disposable instance only**.

## 4. Manual regression checklist

Before a public release, verify in Firefox and Chromium, at desktop (e.g. 1440×900), tablet (768×1024) and phone (390×844) sizes:

1. First-run page cannot be reopened after initialization.
2. Invalid login is rejected, valid login works, logout revokes the session.
3. Create a post with text and a real image; edit it, then delete the test post.
4. Create and preview sections nested to the allowed depth, then save and reload.
5. Select a secondary language and confirm translations persist/fallback correctly.
6. Submit a contact message, confirm it appears only in the admin inbox.
7. Generate a backup and restore it in a **separate disposable installation**.
8. Browse Documentation, including internal links, tables and code fences.
9. Collapse/expand the sidebar; inspect keyboard focus and reduced motion.
10. Ensure there is no horizontal overflow, missing button label, or inaccessible form field on mobile.
11. Verify the Design page has no auto-generated shortcut row.
12. Inspect console errors, broken requests and accessibility warnings.

## 5. Release reporting

Record Python version, OS, installed dependency versions, all test outputs, and any remaining manual discrepancies. **Adding a test does not mean it has passed.** Do not mark a release verified without executing these steps on a compatible environment.
