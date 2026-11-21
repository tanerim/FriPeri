## Troubleshooting

| Problem | What to check |
| --- | --- |
| Login returns to the login screen on local HTTP. | Start with `SESSION_COOKIE_SECURE=false` locally; use `true` with HTTPS in production. |
| First-run setup appears for an existing site. | Confirm `SITE_DB_PATH` points to the intended initialized database and that the service account can access it. |
| The database is read-only or saving fails. | Check write permissions on the database directory as well as the file; SQLite needs access to create supporting files. |
| Uploaded images do not appear. | Check the upload directory, file permissions, and the `/static/uploads/` URL mapping, especially after overriding storage paths. |
| A large upload fails before reaching the editor. | Check reverse-proxy request limits and the Custom Home editor's per-file limits. |
| A panel backup omits the active database or uploads. | The panel archives standard paths only. Back up overridden storage locations manually. |
| Setup fails on native Windows. | The initializer uses `fcntl`, and dependencies include `uvloop`; use a Linux environment such as WSL. |
| Custom Home still shows the content feed. | Select Custom Home and use **Save & publish**. An empty custom document falls back to the feed. |
| Category content is missing from a list. | Confirm the content is published, belongs to the selected category, and fits within the selected item count. |
| Card appearance does not change in the automatic feed. | Category card settings control category archives and custom category blocks; the automatic feed has its own layouts. |
| Contact messages cannot be saved. | Verify database write access and available disk space. Submitted messages appear under Admin → Messages. |
| A form reports that the language changed. | Reload the form after changing the secondary language, then edit and save again. |
| A UI label appears in English in the secondary language. | Its translation may be empty or missing; English is the fallback. |
| The block editor or cropper is unavailable. | Enable JavaScript and check that the bundled files under `/static` load successfully. |

---

[Documentation index](index.md) · [Project README](../README.md)
