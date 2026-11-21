# Dependency security review

**Date:** 2026-11-21. **Scope:** pinned requirements in FriPeri's `requirements.txt`. This is a security advisory review, *not* a completed local `pip-audit` scan or compatibility test.

## Known vulnerable pinned versions

| Package | Previously pinned | Advisory | First known fixed version |
| --- | --- | --- | --- |
| `python-multipart` | 0.0.20 | CVE-2026-53540 (multipart parser resource exhaustion); CVE-2026-24486 (path traversal in non-default configuration) | 0.0.31 (covers both) |
| `starlette` | 0.47.3 | CVE-2025-62727 (quadratic HTTP Range processing in `FileResponse`) | 0.49.1 |
| `pillow` | 12.3.0 | CVE-2026-112900 (EPS/Ghostscript argument injection under certain conditions) | 13.0.0 |

Sources:

- https://security-tracker.debian.org/tracker/CVE-2026-53540
- https://security-tracker.debian.org/tracker/CVE-2026-24486
- https://github.com/advisories/GHSA-7f5h-v6xp-fcq8
- https://github.com/python-pillow/Pillow/blob/main/docs/releasenotes/13.0.0.rst

The FriPeri app serves files through `FileResponse`, so the Starlette finding warrants special attention. Normal image uploads are documented as JPEG, PNG and WebP rather than EPS, so the Pillow EPS exploit may not be reachable through that UI. Nonetheless, vulnerable dependencies should be upgraded.

**Compatibility caution:** FastAPI and Starlette must be updated as a compatible pair based on their package constraints. Do not install incompatible pins using `--no-deps`.

## Local dependency check

```bash
python3 -m venv .venv-audit
source .venv-audit/bin/activate
python -m pip install --upgrade pip pip-audit
python -m pip install -r requirements.txt
python -m pip check
python -m pip_audit -r requirements.txt
python -m pytest -q
deactivate
```

Run smoke tests for setup, login, post editing, file uploads, custom homepages, language switching, contact messages, backup/download/restore, sitemap, and static file delivery.

## Release criteria

- Pin security-fixed packages and resolve their transitive constraints.
- Record the full `pip-audit` output for every installed runtime package.
- Validate actual application behavior in a clean environment.
- Record tested Python version and operating system.
- Do not declare the repository security-cleared until these steps have passed.

No GitHub Actions should be enabled or executed for this project.
