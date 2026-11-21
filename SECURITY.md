# Security Policy

## Supported versions

FriPeri is maintained from the current `main` branch. Security fixes are prioritized for the latest public release. Older commits, forks and third-party deployments may not receive backports. Do not interpret this policy as a guaranteed support or response SLA.

## Reporting a vulnerability

**Do not open a public GitHub issue, discussion, or pull request containing exploit details, credentials, or personal data.** Prefer the repository's **Security → Report a vulnerability** private reporting feature when it is enabled.

If private vulnerability reporting is not enabled, contact the maintainer privately via the contact route published on the project page: https://nextnlp.com/pages/friperi. Do not include live secrets in the initial message.

Please include:
- Affected FriPeri version or commit SHA and deployment environment.
- A concise impact statement, reproduction steps and a minimal proof of concept where safe.
- The affected component, expected behavior and actual behavior.
- Any mitigation already applied.

The maintainer will assess the report and coordinate a fix or workaround. Response timelines depend on availability and severity; no fixed timeframe is promised. Public disclosure should be coordinated until users have a practical mitigation.

## Deployment security essentials

- Complete the first-run setup **before** exposing a new instance to the public Internet. Restrict access to an uninitialized instance.
- Serve production deployments over HTTPS. Leave `SESSION_COOKIE_SECURE=true` for HTTPS; set it to `false` only for local HTTP development.
- Use strong, unique administrator credentials and restrict filesystem access to the SQLite database, backups, uploaded content and environment files.
- Never commit `.env`, database files, uploaded user content, secret keys, or backups. Keep the corresponding `.gitignore` rules in place.
- Keep operating system and Python dependencies patched. Run `python -m pip install pip-audit && python -m pip_audit -r requirements.txt` locally and investigate findings before deployment.
- Put a maintained TLS-terminating reverse proxy in front of the application and configure request/body limits and access logging appropriate to your environment.
- Back up **both** the SQLite database and `static/uploads/`. Store backups outside the web root with restricted access. Test restore procedures.
- Sanitize user-generated content at appropriate trust boundaries; do not assume an authenticated admin interface alone eliminates XSS/CSRF or uploaded-file risks.
- Review deployment logs and rotate credentials after any suspected compromise.

## Scope and limitations

This document describes a reporting route and safe-deployment recommendations. It is **not** a certification, penetration-test report or guarantee that the application is free of vulnerabilities. Third-party Python and JavaScript dependencies remain subject to upstream security advisories.

See [installation and deployment](docs/installation.md), [maintenance](docs/maintenance.md) and [dependency security review](docs/dependency-security.md).
