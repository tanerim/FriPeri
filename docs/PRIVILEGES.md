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

## External directory mappings

Create a symbolic link inside an eligible static directory on the server, then
open Configuration → Privileges → External directory mappings. Enter the
relative link path, exact canonical absolute target directory, and optionally
comma-separated file extensions. Save to enable. Edit, disable or remove the
mapping in the same panel. Removing a mapping does not delete files or links.

Existing video deployments must register their existing link in this panel
after upgrading; the old video-specific environment variable is no longer used.
No external links are automatically trusted. Until registered, they return 404.

Private folder approval is checked before serving files. Nested symlinks,
overlapping mappings and non-regular files are rejected. Video Range requests
remain supported. Keep external archives administrator-controlled and use
extension restrictions for media; an empty extension list permits all regular
files, including active content. Do not map sensitive or untrusted directories.
The service user must have filesystem read and traversal permissions.
Never bypass the application using an Nginx alias.

Run: `python -m pytest -q tests/test_privilege_video_archive.py`

## User interface and form protection

The access screen displays the configured CMS site name followed by **Controlled Access**. Login and registration occupy mutually exclusive views. Internal directory paths and redundant Home/Access links are not displayed on the public form.

Registration requests require a signed, time-limited CSRF token. A browser-supplied `Origin: null` is accepted **only** with `Sec-Fetch-Site: same-origin` and a valid signed token; otherwise the submission is rejected. A normal non-null Origin must match the server's Host or explicitly configured `FRIPERI_PUBLIC_ORIGIN`. This setting should be an HTTPS origin such as `https://example.org`. Do not trust unvalidated client-supplied forwarding headers as proof of origin.

The administrator's Privileges dashboard separates the visibility policy from access requests. Request actions depend on status (Approve, Deny, Revoke). Password reset is intentionally collapsed until requested. CMS administrative users and privilege accounts remain independent.

For a summary of all newly added administration features, see [Recent features](recent-features.md).
