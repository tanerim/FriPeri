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


## Security pin update (2026-11-21)

The current `requirements.txt` pins were changed to `fastapi==0.120.4`, `starlette==0.49.3`, `python-multipart==0.0.31`, and `pillow==13.0.0`. FastAPI was upgraded alongside Starlette because the previous FastAPI release constrained Starlette below the security-fixed range. These are version changes in source control; **they are not proof that a clean installation, audit or application regression test has passed.** Run the local release checks below before production use.

```bash
python -m pip install -r requirements.txt
python -m pip check
python -m pip_audit -r requirements.txt
python -m pytest -q tests/test_backup_security.py tests/test_security_guards.py tests/test_nested_sections.py tests/test_documentation.py
```

Keep the previously reviewed vulnerable pins in the historical table above as audit context; the table no longer describes the current source requirements. Any remaining issues found by the scanner need triage before declaring a production-ready release.


## Additional November 2026 upstream advisory check

An online advisory review on 2026-11-21 found that the repository's current **starlette==0.49.3** remains affected by important newer vulnerabilities:

- **CVE-2026-48710 / GHSA-86qp-5c8j-p5mr:** malformed HTTP Host header can poison `request.url.path`, potentially bypassing path-based security checks. The advisory calls for **Starlette >=1.0.1**. FriPeri has security-sensitive middleware that checks `request.url.path`, so this deserves priority.
- **CVE-2026-54283 / GHSA-82w8-qh3p-5jfq:** `application/x-www-form-urlencoded` parsing ignores field count/size constraints, enabling denial-of-service; fixed in **Starlette >=1.3.1**. FriPeri calls `request.form()` extensively.

Upstream references:
- https://github.com/advisories/GHSA-86qp-5c8j-p5mr
- https://github.com/advisories/GHSA-82w8-qh3p-5jfq

FastAPI published **GHSA-f56c-v883-vx8r** on 2026-11-17, affecting FastAPI **>=0.123.2,<0.163.2** and fixed in 0.163.2. FriPeri's current **fastapi==0.120.4** is *outside the affected range listed by that particular advisory*, but a future upgrade through that range should not stop at an affected release.

- https://github.com/fastapi/fastapi/security/advisories/GHSA-f56c-v883-vx8r

**Compatibility gate:** do not update Starlette independently of FastAPI's declared dependency range. Plan and test a compatible FastAPI/Starlette upgrade (target at least Starlette 1.3.1), resolve fresh packages, and rerun all integration and optional browser tests before production rollout. The current pin set cannot be called fully vulnerability-free.

### Audit status

The assistant environment did **not** execute `pip-audit`: network access prevented installing the scanner. This section is an advisory check, not a full dependency-tree scan. Run the following locally and review the actual output:

```bash
python -m pip install --upgrade pip-audit
python -m pip_audit -r requirements.txt
python -m pip_audit
```

The first audit checks repository pins and resolved dependencies; the second examines the current Python environment. Preserve audit results in release notes. Avoid blanket suppression of findings.


## November 21 audit remediation: repository pins

The user's local `pip-audit -r requirements.txt` output reported **10 advisory rows for Starlette 0.49.3**, with fixes from 1.0.1 through 1.3.1 (some rows were duplicates). The full environment audit also reported **three advisory rows for setuptools 79.0.1**, in addition to the Starlette findings.

In response, `requirements.txt` has been updated to:

- `fastapi==0.165.0`
- `starlette==1.10.0`

FastAPI 0.165.0 declares `starlette>=1.6.0`, so the two constraints are compatible. Starlette 1.10.0 was available on PyPI before this update. Because the changes cross major Starlette versions, run the complete integration and browser suite before deploying.

**Setuptools is not in FriPeri's runtime requirements.** The environment-level advisory is addressed separately by upgrading the virtual environment's `setuptools` to at least 84.1.0, preferably the verified available release `84.2.1`:

```bash
python -m pip install --upgrade 'setuptools==84.2.1'
python -m pip install -r requirements-dev.txt
python -m pip check
python -m pytest -q tests/
python -m pip_audit -r requirements.txt
python -m pip_audit
```

A clean audit must be observed on the installed system. The code changes alone do not certify that the deployed environment is vulnerability-free.
