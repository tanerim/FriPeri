# User Files migration (FriPeri)

The core system resources stay under `static/`. The Privileges-controlled applications live in `user_files/`.

On startup, FriPeri moves directories recorded in the Privileges database from `static/<folder>` to `user_files/<folder>`. Account records, approvals, and external directory mapping records remain unchanged; existing symlinks move with their parent folder. Existing destinations cause startup to fail if a same-named legacy source remains (no silent merging). Folders not recorded in Privileges are left in `static` and should be moved manually after review.

The canonical URL is `/user_files/<folder>/index.html`. Legacy `/static/<folder>/...` URLs are redirected to their canonical counterparts by FastAPI. Ensure Nginx forwards **both** `/static/` and `/user_files/` to the application; never use an `alias` or direct filesystem route for protected directories.

**Important:** The site's static system JS/CSS must stay public to function. Never put secrets in browser JavaScript or CSS. `/user_files` must be physically separate from `/static`; both must be served through the intended FastAPI mounts.

After pulling, run `python -m pytest -q tests/test_privilege*.py`, restart the service, and confirm `/user_files/<folder>/index.html` access rules before testing old links.

## Root Files

The administrator can manage explicitly published files under Configuration → Root Files. Allowed file names: ASCII-safe `.txt` files (including `ads.txt`, `app-ads.txt`, and `test.txt`) or `google<token>.html` verification files. Reserved route names cannot be replaced. Google HTML verification files must contain only `google-site-verification: <filename>` (no executable HTML). The files are kept in `root_files/`, separate from public CMS assets, and **do not** become public until the administrator explicitly clicks Publish.

For existing Google verification or app-ads files, upload them in the Root Files interface and publish. Files that previously existed at `static/app-ads.txt` are not automatically published.

Nginx must forward root URL requests such as `/app-ads.txt` to FastAPI; a direct Nginx static alias would bypass publishing controls.

## Upgrade warnings

The old `/static/<folder>` entrypoints are compatibility redirects (307), not additional public file mounts. The system static mount explicitly blocks directories registered in the Privileges database. The proxy must forward **both** routes to FastAPI; `/user_files/` must never be configured with an Nginx `alias`.

Before starting FriPeri, back up the site database and `static/gorsel_sorgu`, `static/video_sorgu` directories and external symlink targets independently. The existing backup ZIP intentionally covers the CMS database/uploads, not all external archive bytes.

CMS ZIP backups now include registered Root Files payloads (non-symlink UTF-8 text files) along with their database publication metadata. Backups do **not** copy external symlink targets or the large application datasets under `user_files/`; archive these separately according to your storage/retention policy.
