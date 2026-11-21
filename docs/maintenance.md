## Maintenance and Backups

### Backing Up and Restoring

**Configuration → Backup** provides ZIP creation, download, upload, and restoration. Archives are stored under `backups/` and include these standard paths when present:

- `db/site.db`: database content, accounts, settings, and messages.
- `static/uploads/`: uploaded images and videos.
- `static/images/`: bundled site images.
- `.env`: stored in the archive as `env/.env`.

**Current releases use the configured `SITE_DB_PATH`, `SITE_UPLOAD_DIR`, and `SITE_STATIC_DIR` when building and restoring backups.** Older versions used fixed paths; consult the hardened-backup notes below and verify the configured paths before restoring a legacy archive. ZIP backups do not include the application source, templates, or all static assets. They may contain credentials and private messages; keep downloaded archives private.

Restore only trusted FriPeri archives. Restoration overwrites matching files and does not remove extra files absent from the archive. SQLite is captured using its backup API, including committed WAL content. Restoring the database and media together is not atomic: stop writes during restoration, keep a separate backup, and restart afterward to reload configuration and session state.

For a straightforward consistent backup:

1. Stop the FriPeri process or service.
2. Copy the configured database, its directory contents as needed, the uploaded media directory, and any `.env` configuration to your backup location.
3. Retain the matching application version and any locally customized templates or assets.
4. Start FriPeri again.

To restore, stop FriPeri, restore the saved files to their configured locations, check ownership and permissions, and restart using the matching application version. Copying only the database does not preserve uploaded media.

### Updating an Installation

1. Back up the installation.
2. Stop the service.
3. Update the application source, preserving any local modifications.
4. Activate the virtual environment and install the updated `requirements.txt`.
5. Restart the service and check the logs, public homepage, and admin panel.

Existing databases are migrated at startup. The language migration creates a sibling backup named `<database>.pre-language-v1.bak` before its first applicable upgrade. This migration backup does not replace regular backups.

For rollback, restore the compatible application code and database backup together. See [language migration details](../translations/LANGUAGE_MIGRATION.md) before reverting an installation with translated content.

### Factory Reset

**A factory reset permanently deletes site content, settings, accounts, translations, uploads, and database backups within its reset scope.**

Stop FriPeri and back up anything you want to retain, then run:

```bash
python scripts/reset_friperi.py
```

Confirm with `y` or `yes`, then type the exact phrase `RESET FriPeri`.

The script removes supported database files and migration backups under `db/`, uploaded files under `static/uploads/`, and `.env` / `.env.bak`. It preserves application source, templates, CSS/JS, built-in translations, and the uploads directory itself. Storage overrides outside the supported reset scope cause the script to refuse the reset.

ZIP archives in `backups/` are outside the reset scope and remain on disk.

Start the application again and open the website to return to first-run setup.

## Hardened backup and restore (2026-11)

- Backup archives use the configured `SITE_DB_PATH`, `SITE_STATIC_DIR`, `SITE_UPLOAD_DIR` and project `.env` where present. SQLite is captured with its official backup API, including committed WAL content.
- Created and uploaded archives are owner-only (`0600`) and receive unique filenames. Backups contain credentials and potentially personal data; restrict filesystem and archive access.
- Backup create, upload and restore require an authenticated admin and a session-bound anti-CSRF form token. Other admin mutations are additionally protected by a same-origin browser request check.
- ZIP upload limit: **256 MiB**; maximum uncompressed archive payload **512 MiB**, **2,000** entries and **128 MiB** per member. Only recognized database, environment and media paths are accepted. Unknown source-code or executable paths, symlinks, traversal and duplicate members are rejected.
- Archive integrity is checked before restore. SQLite `PRAGMA quick_check` and required tables are validated before changing the live database; restoration uses SQLite's backup API, not a raw byte copy.
- **Maintenance window required:** database and media files cannot be atomically replaced together. Stop or isolate writes during restoration. A failed media write after the database has been replaced can still leave a partially restored installation. Make a separate pre-restore snapshot and verify backups before any destructive operation.
- The database may contain a restored session secret and administrator credentials. Expect to sign in again. Changes to `.env` take effect after a service restart.
- Older backup ZIP files that violate the new whitelist or size limits will be rejected; migrate them after reviewing the archive in a controlled environment.

### Local security tests

```bash
python -m pytest -q tests/test_backup_security.py tests/test_security_guards.py
python -m pip check
python -m pip_audit -r requirements.txt
```

---

[Documentation index](index.md) · [Project README](../README.md)
