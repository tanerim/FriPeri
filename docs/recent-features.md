# Recent features: administration, visual design, and protected access

This page summarizes functionality introduced in FriPeri's November 2026 development cycle. It describes the current implementation rather than a future roadmap.

## Administration dashboard

The **Dashboard** displays a welcome banner, post totals, published posts, drafts, categories, recent posts, and posts grouped by category. Administrator accounts additionally see:

| Metric | Source / meaning |
| --- | --- |
| Published pages | Count of rows with `published=1` in `custom_pages` |
| CMS users | Accounts in `users` (administrator, editor, and content creator) |
| Private directories | Private entries in `privilege_directories`, excluding reserved `images` and `uploads` |
| Access accounts | Separate accounts in `privilege_accounts` |
| Pending access requests | Rows in `privilege_requests` with status `pending` |

Two lightweight horizontal stacked charts visualize **post publishing status** (published / draft) and **page publishing status** (published / unpublished). Values are generated server-side from SQLite; zero-result cases remain empty. Users without administrator rights do not receive the administrator-only counters.

The administrator sidebar uses a compact logo with height constrained to the viewport. Its navigation area scrolls independently to keep menu entries reachable, and the collapse/expand arrow has higher contrast.

## Website Design

**Website → Design** allows administrators to select preset color templates and configure the site's public-facing appearance. Controls include navigation styling and positioning, typography, logo options, page background, navigation colors, homepage feature bar, accent colors, separator colors, and footer. Color-field explanations identify the affected UI regions. Global site styling and category-specific **CMS Design** are separate features.

## Homepage composition

**Website → Homepage** offers a content-feed experience or a visual **Custom Home**. The builder includes starter layouts, a reusable block palette, a page-structure outline, edit-in-place controls, previews, and **Save & publish**. Public changes are not published merely by choosing a different layout; they must be saved.

## Controlled directory privileges

**Configuration → Privileges** controls **top-level folders under `/static`**, with Public as the default. The `images` and `uploads` folders are not eligible for per-directory privilege management and remain publicly served by this mechanism. A Private folder requires a distinct directory-access account and administrator approval. This is independent of CMS login accounts.

Users can register (first name, last name, email, password), request access, and sign in to view approval status. New requests start as **Pending**. Administrators can **Approve**, **Deny**, **Revoke**, or reset an account password. Revocation and password resets invalidate previously issued directory sessions. An email address supplied during registration is **not automatically verified**; administrators should confirm the applicant's identity before approving.

The public access screen uses the configured **site name** followed by “Controlled Access.” Login and registration are mutually exclusive views and do not expose the protected directory name or unnecessary navigation links. Registration requires a signed form token. For browsers sending `Origin: null`, the backend accepts the request only when `Sec-Fetch-Site: same-origin` and the signed token validates. Cross-site submissions remain rejected.

**Deployment is security-sensitive:** all `/static/` requests must reach FastAPI rather than bypassing authorization through a reverse-proxy file alias or CDN. Private mode also requires `PRIVILEGES_STATIC_PROXY_CONFIRMED=1` after checking the proxy. Read [the full privileges and Nginx guide](PRIVILEGES.md) before enabling Private access.

## Protected external video archive

A deliberately narrow symbolic-link exception allows:

```text
/static/video_sorgu/videos/  ->  /home/taner/6feb_data/videos/
```

The target can be configured with `PRIVILEGES_VIDEO_ARCHIVE_DIR`. The symlink must resolve to the exact approved archive root; other external symlinks and nested symlinks remain blocked. Authorization is enforced before streaming videos; approved sessions can receive HTTP 200 or partial-content HTTP 206 responses. Video player URLs must use the protected `/static/video_sorgu/videos/` prefix, not a separate `/videos/` URL or unprotected Nginx alias.

See [Privileges](PRIVILEGES.md) for security checks, operational requirements, and the regression test checklist.

## Verification

For local or development installations:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q tests/test_integration_flows.py tests/test_roles.py
python -m pytest -q tests/test_privileges.py tests/test_privilege_proxy.py \
  tests/test_privilege_folder_filters.py tests/test_privilege_video_archive.py
```

The Starlette test client in the pinned application requires `httpx2`, which is included in `requirements-dev.txt`.

## Screenshots

The repository README presents screenshots of the Dashboard, Website Design, and Homepage editor under **Admin interface**.
