# HTTP route reference

**Generated from:** `main.py`, main branch, 2026-11-21. This is a source-derived route inventory, not an OpenAPI contract or guarantee of public access.

## Public and account routes

| Method | Route |
| --- | --- |
| `API_ROUTE` | `/static/images/friperi-section-{digest}.svg` |
| `API_ROUTE` | `/sitemap.xml` |
| `GET` | `/app-ads.txt` |
| `GET` | `/` |
| `HEAD` | `/` |
| `GET` | `/category/{slug}` |
| `GET` | `/posts/{slug}` |
| `GET` | `/about` |
| `GET` | `/contact` |
| `POST` | `/contact` |
| `GET` | `/set-language/{lang}` |
| `GET` | `/login` |
| `POST` | `/login` |
| `GET` | `/logout` |
| `GET` | `/pages/{slug}` |
| `GET` | `/health` |
| `GET` | `/favicon.ico` |
| `GET` | `/first-run` |
| `POST` | `/first-run` |

## Administrative routes

| Method | Route |
| --- | --- |
| `GET` | `/admin/messages` |
| `GET` | `/admin/backup` |
| `POST` | `/admin/backup/create` |
| `POST` | `/admin/backup/upload` |
| `POST` | `/admin/backup/restore/{backup_name}` |
| `GET` | `/admin/backup/download/{backup_name}` |
| `GET` | `/admin` |
| `GET` | `/admin/posts` |
| `GET` | `/admin/posts/new` |
| `POST` | `/admin/posts/new` |
| `GET` | `/admin/posts/{post_id}/edit` |
| `POST` | `/admin/posts/{post_id}/edit` |
| `POST` | `/admin/posts/{post_id}/delete` |
| `GET` | `/admin/categories` |
| `POST` | `/admin/categories` |
| `POST` | `/admin/categories/{category_id}/delete` |
| `GET` | `/admin/menu` |
| `POST` | `/admin/menu` |
| `GET` | `/admin/settings` |
| `POST` | `/admin/settings` |
| `POST` | `/admin/settings/sitemap` |
| `GET` | `/admin/design` |
| `GET` | `/admin/homepage` |
| `POST` | `/admin/design` |
| `POST` | `/admin/homepage` |
| `GET` | `/admin/custom-home` |
| `GET` | `/admin/about` |
| `GET` | `/admin/pages` |
| `POST` | `/admin/pages` |
| `GET` | `/admin/pages/{page_id:int}` |
| `POST` | `/admin/pages/{page_id:int}` |
| `POST` | `/admin/pages/{page_id:int}/delete` |
| `POST` | `/admin/about` |
| `POST` | `/admin/custom-home` |
| `POST` | `/admin/posts/new/preview` |
| `POST` | `/admin/posts/{post_id:int}/edit/preview` |
| `POST` | `/admin/about/preview` |
| `POST` | `/admin/pages/{page_id:int}/preview` |
| `POST` | `/admin/custom-home/preview` |
| `POST` | `/admin/section-svg` |
| `POST` | `/admin/posts/new/upload` |
| `POST` | `/admin/posts/{post_id:int}/edit/upload` |
| `POST` | `/admin/about/upload` |
| `POST` | `/admin/pages/{page_id:int}/upload` |
| `POST` | `/admin/custom-home/upload` |
| `GET` | `/admin/contact-details` |
| `POST` | `/admin/contact-details` |
| `GET` | `/admin/social-links` |
| `POST` | `/admin/social-links` |
| `GET` | `/admin/language` |
| `POST` | `/admin/language` |

## Route categories

- Publishing: `/`, `/posts/{slug}`, `/category/{slug}`, `/pages/{slug}`, `/about`.
- Contact: `GET /contact` and `POST /contact`; submitted messages are stored in SQLite.
- Authentication and initial setup: `/login`, `/logout`, `/first-run`.
- Administrator: `/admin` and subordinate forms, upload endpoints, editors and previews.
- Backups: `/admin/backup/*`; treat these as sensitive operations.
- Service endpoints: `/health`, `/sitemap.xml`, `/app-ads.txt`, favicon and generated SVG.

**Security note:** The table is grouped by URL prefix only. Authorization, CSRF, HTTP responses, payload validation and access restrictions must be reviewed in each route handler; no entry should be presumed accessible without authentication.

See [architecture](architecture.md), [user guide](user-guide.md), and [security policy](../SECURITY.md).
