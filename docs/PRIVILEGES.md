# FriPeri Privileges — deployment security gate

**Public by default.** Only top-level directories marked Private in
Admin → Settings → Privileges are restricted. Access rules apply to the entire
directory tree, including `.html`, `.js`, `.css`, images and API-like static JSON.

## Mandatory Nginx change

Every request to `/static/` **must pass through FastAPI**. Remove any
`location /static/` with `alias`, `root`, `try_files` or a CDN/origin shortcut
that serves files directly. Recommended shape (adjust the upstream to FriPeri):

```nginx
location ^~ /static/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_no_cache 1;
    proxy_cache_bypass 1;
}
```

Verify all other Nginx `location` precedence, redirects, CDN rules and caches.
Purge any cached private asset URLs. Ensure the underlying static directory is
not exposed via a second vhost, file server or alternate URL.

**Only after verification**, configure the FriPeri systemd service:

```ini
Environment=PRIVILEGES_STATIC_PROXY_CONFIRMED=1
```

Reload systemd and restart the app. Without this switch, the admin UI refuses
to enable Private mode with HTTP 409. This setting records the operator's
verification; it cannot inspect remote Nginx settings itself.

## Test checklist

1. Set `video_sorgu` Private under Admin → Privileges.
2. In a private/incognito browser, request
   `/static/video_sorgu/index.html`; expect redirect to `/access/video_sorgu`.
3. Request a JS, image or JSON asset in that folder without a session;
   expect 403.
4. Register with first name, surname, email and a strong password.
   Pending users must still be denied.
5. Approve the request in Admin. Verify HTML **and** assets now work.
6. Revoke the grant; existing sessions must stop working immediately.
7. Reset the password through Admin; old login sessions must be invalidated.
8. Confirm `/static/images/` and other Public folders remain reachable.

Private assets return `Cache-Control: private, no-store`.

## Operational notes

- Directory access accounts are separate from FriPeri CMS users and never get
  Admin permissions.
- Privilege passwords use versioned PBKDF2-HMAC-SHA256 with 600,000 iterations and individual random salts. Legacy privilege hashes remain verifiable, and CMS passwords are unchanged. No plaintext passwords are stored.
- Reset replaces the password; the administrator must transmit it out of band
  using a secure channel. No email service is silently used.
- Approve, Deny and Revoke are scoped to the selected folder.
- On multiple workers, configure a shared reverse-proxy rate limit for
  `/access/` POST requests; the built-in limiter is per process.
- Do not host **untrusted third-party HTML/JavaScript** on the same origin
  as FriPeri Admin; same-origin scripts can interact with authenticated pages.
- Do not expose private static files through backup downloads, symlinks,
  alternate domains, CDN object stores or other secondary routes.

Run regression tests locally:

```bash
python -m pytest -q tests/test_privileges.py
```

## Approved external video archive symlink

The controlled directory `/static/video_sorgu/videos/` may refer to
`/home/taner/6feb_data/videos` through an explicit symbolic link:

```sh
ln -s /home/taner/6feb_data/videos \
  /home/taner/websites/network_analiz/static/video_sorgu/videos
```

The authorized root defaults to `/home/taner/6feb_data/videos`. Override it
using the FriPeri service environment variable `PRIVILEGES_VIDEO_ARCHIVE_DIR`
when deploying elsewhere. The link **must** resolve to that exact root.
Other out-of-tree symlinks and nested symlinks within the video archive are
not followed. Directories and non-regular files are not served by this rule.

The existing Private/Approved checks happen before the static file lookup.
Starlette's `FileResponse` handles `Range` video requests (HTTP 206).
Confirm the web server user can traverse the source's parent directories and
read video files; symlink permissions do not override filesystem permissions.
Avoid any Nginx `alias` or other static shortcut around FriPeri's application
authorization layer.

```sh
python -m pytest -q tests/test_privilege_video_archive.py
```
