## Maintenance and Backups

### Backing Up and Restoring

**Configuration → Backup** provides ZIP creation, download, upload, and restoration. Archives are stored under `backups/` and include these standard paths when present:

- `db/site.db`: database content, accounts, settings, and messages.
- `static/uploads/`: uploaded images and videos.
- `static/images/`: bundled site images.
- `.env`: stored in the archive as `env/.env`.

**The panel uses these fixed paths, even if `SITE_DB_PATH`, `SITE_UPLOAD_DIR`, or `SITE_STATIC_DIR` is overridden.** Use a manual backup of the actual configured paths for such installations. ZIP backups do not include the application source, templates, or all static assets. They may contain credentials and private messages; keep downloaded archives private.

Restore only trusted FriPeri archives. Restoration overwrites matching files and does not remove extra files absent from the archive. It is not an atomic deployment or a guaranteed consistent live SQLite snapshot. Avoid concurrent writes during panel backup/restore, keep a separate backup beforehand, and restart after restoring to reload configuration and session state.

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


---

[Documentation index](index.md) · [Complete README](../README.md)
