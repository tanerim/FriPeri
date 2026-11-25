# User Files migration (FriPeri)

The core system resources stay under `static/`. The Privileges-controlled applications live in `user_files/`.

On startup, FriPeri moves directories recorded in the Privileges database from `static/<folder>` to `user_files/<folder>`. Account records, approvals, and external directory mapping records remain unchanged; existing symlinks move with their parent folder. Existing destinations cause startup to fail if a same-named legacy source remains (no silent merging). Folders not recorded in Privileges are left in `static` and should be moved manually after review.

The canonical URL is `/user_files/<folder>/index.html`. Legacy `/static/<folder>/...` URLs are redirected to their canonical counterparts by FastAPI. Ensure Nginx forwards **both** `/static/` and `/user_files/` to the application; never use an `alias` or direct filesystem route for protected directories.

**Important:** The site's static system JS/CSS must stay public to function. Never put secrets in browser JavaScript or CSS. `/user_files` must be physically separate from `/static`; both must be served through the intended FastAPI mounts.

After pulling, run `python -m pytest -q tests/test_privilege*.py`, restart the service, and confirm `/user_files/<folder>/index.html` access rules before testing old links.

## Root Files

The administrator can manage explicitly published files under Configuration → Root Files. Allowed file names: `ads.txt`, `app-ads.txt`, or `google<token>.html`. The files are kept in `root_files/`, separate from public CMS assets, and **do not** become public until the administrator explicitly clicks Publish.

For existing Google verification or app-ads files, upload them in the Root Files interface and publish. Files that previously existed at `static/app-ads.txt` are not automatically published.

Nginx must forward root URL requests such as `/app-ads.txt` to FastAPI; a direct Nginx static alias would bypass publishing controls.
