# FriPeri
<p align="center">
<img height="250" src="static/images/FriPeri_Logo.png"/>
</p>

**A free and simple personal publishing framework.**

FriPeri is a self-hosted publishing application for personal websites, blogs, notes, and other category-based content. It combines a public website with a browser-based administration panel, stores content and configuration in SQLite, and lets you choose between an automatically updated content feed and a custom homepage built from visual blocks.

## Contents

- [General Information](#general-information)
- [Installation](#installation)
- [Detailed Usage](#detailed-usage)
- [Configuration and Data Storage](#configuration-and-data-storage)
- [Deployment](#deployment)
- [Maintenance and Backups](#maintenance-and-backups)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## General Information

### What FriPeri provides

- **Content publishing:** a rich-text editor, drafts, published posts, categories, comma-separated tags, excerpts, and preview images.
- **Two homepage modes:** Content feed and Custom Home, managed from the same screen.
- **A visual homepage editor:** headings, formatted text, lists, tables, images, videos, buttons, dividers, and dynamic category lists.
- **Image cropping:** aspect-ratio selection, zoom, dragging, and position sliders for content images and uploaded images in the homepage editor.
- **Category presentation controls:** individual card colors and date, title, and excerpt visibility settings for each category.
- **Website customization:** navigation, social links, public site colors, footer text, welcome text, and contact details.
- **Multilingual content:** English as the primary language, with one optional secondary language and English fallback.
- **An administration dashboard:** recent content, published and draft totals, category counts, and shortcuts to common tasks.
- **Browser-based installation:** the first-run form creates the database and administrator account.

Blog and Notes are categories within the same content system. You can create additional categories and use them in navigation, the content feed, and custom homepage blocks.

### Technical overview

FriPeri uses Python, FastAPI, Uvicorn, Jinja2 templates, SQLite, and bundled JavaScript/CSS. The Python dependencies are pinned in [requirements.txt](requirements.txt).

Running the application does not require Node.js, a frontend build, an external database server, or a hosted editor service. JavaScript is required for interactive features such as the visual homepage editor, immediate homepage mode switching, and image cropping. Externally linked images and embedded videos still depend on their respective hosts.

## Installation

### Requirements

- Python 3.11 or newer, including the `venv` module and pip.
- A Unix-like environment with Python's `fcntl` module, which the first-run initializer uses for file locking. On Windows, use a Linux environment such as WSL rather than native Windows Python.
- Write access to the database directory and upload directory.
- A modern browser for the admin interface.
- Git if cloning the repository; alternatively, download and extract the source archive.

Contact-form messages are stored in the admin **Messages** inbox. No email service or SMTP configuration is required. See [Contact Details and Messages](#contact-details-and-messages).

### 1. Get the source code

```bash
git clone https://github.com/tanerim/friperi.git
cd friperi
```

If you downloaded an archive, extract it and open a terminal in the directory containing `main.py` and `requirements.txt`.

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

The commands below assume this environment is active and your current directory is the project root.

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Start the application

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** in your browser. A new installation opens the first-run setup screen.

### 5. Complete first-run setup

Enter your site name and description, homepage welcome text, and administrator credentials. You can also configure an optional secondary language, social links, a contact email address, and initial hero image settings.

The administrator password must contain at least eight characters and match its confirmation. Setup stores a salted password hash in SQLite; it does not write a plaintext password to an environment file.

After completing setup, sign in at **http://127.0.0.1:8000/login**. Your administration panel is available at **http://127.0.0.1:8000/admin**.

By default, the database is created at `db/site.db`. No manual SQL import, separate database-generation step, or restart is needed. An existing initialized database is migrated at startup instead of being reinstalled.

### Optional command-line initialization

For scripted or terminal-based installation, use the same initializer through the CLI:

```bash
python scripts/generate_db.py
```

To inspect non-interactive options:

```bash
python scripts/generate_db.py --help
```

The initializer refuses to overwrite an initialized database. If you specify `--db-path`, configure the application with the same `SITE_DB_PATH` before starting it.

## Detailed Usage

### Finding Your Way Around the Admin Panel

Sign in at `/login`, then open `/admin`. The sidebar groups tools by purpose:

| Group | Screen | Purpose |
| --- | --- | --- |
| Overview | Dashboard | Review recent content, publication totals, and category counts. |
| Content | Content list | Create, edit, and delete posts and notes. |
| Content | Categories | Create categories and manage their membership structure. |
| Website | Homepage | Choose the homepage mode and edit its settings or blocks. |
| Website | Design | Configure public website colors and the footer. |
| Website | Menu | Configure category navigation and custom links. |
| Configuration | Settings | Edit site identity, welcome text, social links, login-link visibility, and category card options. |
| Configuration | Language | Configure the secondary language and custom interface translations. |
| Overview | Messages | Read submissions from the contact form. |
| Configuration | Contact Details | Configure contact-page text and the optional contact email address. |

The navigation collapses on small screens. The admin interface uses its own colors; changing public website colors does not change the admin theme. Interface labels follow the selected language.

### Creating and Publishing Content

1. Open the content list and choose **New Content**.
2. Enter the English title, excerpt, and body text.
3. Use the editor toolbar for formatting, headings, lists, code blocks, links, and tables.
4. Select a category, or leave the content uncategorized.
5. Add optional tags separated by commas and an optional preview image.
6. If a secondary language is configured, enable the translation fields and add translated content.
7. Choose **Draft** or **Published**, then save using the corresponding action.

Published content appears in its category and in relevant homepage lists. Drafts are excluded from public lists and are not accessible to anonymous visitors through their post URLs. A signed-in administrator can view draft detail pages.

Each post receives a URL derived from its title, such as `/posts/my-first-post`. Open an existing item from the dashboard or content list to edit it. Deleting content removes the post; use a draft when you want to keep the content without publishing it.

### Selecting and Cropping Images

Content images support PNG, JPEG, and WebP.

1. Choose an image in the content editor, or open a post with an existing uploaded image.
2. Select **Crop image** in the image preview.
3. Choose Original, 1:1, 3:2, 16:9, or 3:4 as the aspect ratio.
4. Adjust the zoom, drag the image, or use the horizontal and vertical position sliders.
5. Select **Apply crop**, then save the content to persist the new image selection.

**Cancel** leaves the current selection unchanged. Cropping creates a new image file and preserves the original uploaded file. The cropper exports WebP where supported, with a PNG fallback, and limits the output's longest dimension to 4,096 pixels.

For uploaded images in Custom Home, use the image block's crop action. Applying a crop uploads a new image and updates the block; **Save & publish** is still required to publish the changed page. Cropping is available for local uploads, not externally linked image URLs.

### Managing Categories

Use **Content → Categories** to create a category with a name and optional description. Translation fields are available when a secondary language is configured.

New installations include:

| Category | Default URL |
| --- | --- |
| Blog | `/category/blog` |
| Notes | `/category/notlar` |

The default Notes slug is `notlar`, even when its visible label is English. Navigation labels can be changed separately from URLs.

Assign content to categories in the content editor. Configure category navigation labels, ordering, and menu visibility under **Website → Menu**. Hiding a category from the menu does not unpublish its content.

Deleting a category requires confirmation. Its posts are preserved and become uncategorized. Review any homepage category selections after deleting a category.

### Custom Pages

**Nested navigation:** In **Website → Menu**, add a custom menu item named **Games** and leave its URL empty to make it a group. In the **Custom pages** section, select **Games** as the parent of **GhostTouch** and **SözcükDizisi**, enable their menu visibility, and save. The published pages will appear inside the Games dropdown. New groups are selectable before saving.

Categories, custom links, custom pages, and built-in page links can be assigned to a parent menu. Sort order applies within each group. Up to five levels are supported; circular relationships are rejected. Hidden groups hide their descendants, empty groups are omitted, and deleting a group promotes its direct children to the top level without deleting their pages. Dropdowns support touch and keyboard navigation.

Open **Content → Custom Page**, enter a title, and select **Create & edit**. The new page starts as a draft and uses the same visual builder as Custom Home and About, including translated blocks, media uploads and cropping, category lists, undo/redo, and desktop/mobile preview.

Set the page title and address, then choose **Show in menu** if you want a link in the public navigation. **Save & publish** saves both the page settings and its content. Published pages are available at `/pages/<address>`. Turning off menu visibility removes the navigation link but keeps the page accessible by its address.

Use the Custom Page list to reopen, view, or delete a page. Deleting a page also removes its automatic navigation link. Each page has its own content and does not change the homepage or About page. Existing databases receive the new page table automatically when the application starts.

### Choosing a Homepage Experience

Open **Website → Homepage**. Under **Homepage experience**, choose one of the two modes:

| Mode | What appears below the selection | How to publish it |
| --- | --- | --- |
| Content feed | Settings for an automatically populated homepage. | Save the feed settings. |
| Custom Home | The complete visual block editor. | Select **Save & publish**. |

The selection changes the visible controls immediately. Inactive settings are hidden, and switching between modes on this screen preserves your in-progress feed settings and custom blocks. Changing the selection alone does not change the public homepage; saving activates the selected mode.

Custom Home is part of this screen, not a separate sidebar entry. An older `/admin/custom-home` link redirects to the integrated editor.

#### Content Feed

The feed combines welcome text, a hero image or decorative site monogram, and automatically updated content sections.

Configure these sections under **Website → Homepage** while Content feed is selected:

| Section | Available controls |
| --- | --- |
| Homepage — General | Show or hide the feature strip and its Blog, Notes, and Contact links; edit their descriptions. |
| Hero Background | Enable the hero image and upload or replace it. |
| Featured Content | Select a featured item and control whether its image appears. Only published content is displayed publicly. |
| Latest Content | Choose source categories and item counts for the writing and notes sections, and enable or disable each section. |
| Homepage Categories | Add independent category sections and choose their order and item counts. |
| Layout and Empty State | Choose an editorial split or single-column layout and control empty-category placeholders. |

The writing count supports 1–12 items, the notes count 1–16, and additional category sections 1–12 through the admin controls.

Edit the welcome kicker, heading, and introductory copy under **Configuration → Settings → Hero**. Hero image settings and **Homepage — General** are on the Homepage screen.

#### Custom Home

New installations start in **Custom Home** mode with an editable layout using the title and welcome text entered during setup, a contact button, and Blog/Notes blocks that appear once content is published. Existing installations keep their saved homepage mode and documents.

Choose **Custom Home** to reveal the editor. You can edit these blocks, start with an empty page, or insert the starter layout.

Use the **Add a block** palette in the wide left column to insert content after the selected block, or at the end when no block is selected. Block types are arranged in a single vertical list without an internal scrollbar. On small screens, the palette stacks above the canvas:

| Block | Purpose |
| --- | --- |
| Category list | Show the latest published items from a selected category. |
| Heading | Add an H1, H2, or H3 heading. |
| Text | Add formatted text, emphasis, links, and embedded images with text wrapping. |
| List | Add a bulleted or numbered list. |
| Table | Edit cells, add or remove rows and columns, and supply a caption. |
| Image | Upload or link an image; add alternative text and a caption. |
| Video | Upload a video or use a supported video URL. |
| Button | Add a labeled link. |
| Divider | Separate parts of the page. |

Blocks can be moved up or down, duplicated, and removed. **Undo** and **Redo** restore editor changes within the current editing session.

In a **Text** block, open **Image in text**. Place the cursor where you want the image, upload a PNG/JPEG/WebP (up to 8 MB) or enter an HTTPS/site-upload URL, and add alternative text. Choose **Image left · text right**, **Image right · text left**, or **No wrapping**, plus an image width, then select **Insert / update image**. Click an embedded image to change its settings or remove it. Small screens stack images and text. These controls are shared by Custom Home, About, and Custom Pages; preview and **Save & publish** work as usual.

Each block provides background, alignment, and width controls:

- **Background:** None, Soft, Accent, Dark, White, or a custom **Color Selection** picker. None leaves the background transparent.
- **Alignment:** left, center, or right.
- **Width:** normal reading width or wide.

The Soft and Accent options use the configured public site palette. Use **Website → Design** to change those site colors.

A **Category list** block supports 1–16 items from any available category, including Blog and Notes. It updates automatically as matching content is published. Use **Preview** to see the current list; card appearance comes from the category card settings described below. An empty or missing source category does not turn the block into an all-content feed.

Use **Preview** to inspect the unsaved page at desktop or mobile width. **Save & publish** saves the custom documents and activates Custom Home. The site's navigation and footer remain around the custom page.

The editor supports up to 80 blocks per language. Tables support up to 30 rows and 8 columns. A custom page is stored as validated block data; arbitrary scripts and iframe markup are not supported.

#### Homepage Media and Languages

These upload limits apply specifically to the Custom Home editor:

| Media | Supported sources | Upload limit |
| --- | --- | --- |
| Images | PNG, JPEG, WebP uploads; HTTPS image URLs. | 8 MB per uploaded file |
| Videos | MP4 or WebM uploads; HTTPS video-file URLs; supported YouTube and Vimeo links. | 40 MB per uploaded file |

Use the editor's language selector to maintain a separate page for each configured content language. An empty secondary-language page falls back to English. If no usable custom page exists for the requested language or its English fallback, the normal content feed remains visible.

Switching back to Content feed preserves saved custom pages for future use. Unsaved changes are kept while switching modes on the screen, but are not durable storage: save before leaving or closing the browser.

### Configuring Category Cards

Open **Configuration → Settings → Category cards**. For each category, choose:

- Card background color.
- Card text color.
- Whether to show the date.
- Whether to show the title.
- Whether to show the excerpt.

These settings apply to category archives and Category list blocks in Custom Home. They do not configure the separate featured, writing, and notes layouts of the automatic content feed.

Blog and Notes archive pages omit the large heading above the cards. Hiding card fields changes their presentation without deleting the underlying content or preventing readers from opening it.

### Customizing Design and Navigation

Under **Website → Design**, configure page, navigation, feature, accent, separator, and footer colors. You can also edit the footer text in each configured content language and control footer visibility.

Under **Website → Menu**, configure category labels, sort order, and visibility. Add custom links with a label, URL, order, visibility setting, and optional new-tab behavior. Supply a translated label when using a secondary language.

Under **Configuration → Settings**, edit site identity, homepage welcome text, social profile links and their visibility, and the public login-link setting. The `/login` route remains available when its navigation link is hidden.

### Managing Languages

English is always the primary content language. Under **Configuration → Language**, select no secondary language, Turkish, German, French, or a custom language.

For a custom language, enter its name and code, then fill in the grouped interface translations. Missing interface translations and empty secondary content fields fall back to English. You can show or hide the public language switcher.

Content translations share the original post IDs, URLs, categories, tags, and images. The translated title, excerpt, and body are edited alongside the English content. Custom homepage documents are separate for each configured language.

Changing the secondary language archives its translated content and settings. Selecting that language again restores its archived fields for records that still exist. Selecting None hides secondary-language fields without deleting their values. Forms opened before a language change may reject a stale save; reload them before continuing.

For storage and migration details, see [the language model documentation](translations/LANGUAGE_MIGRATION.md).

### Contact Details and Messages

Under **Configuration → Contact Details**, configure the contact-page introduction and public contact text. The contact email address is optional; it is not a delivery destination.

The public `/contact` form stores each valid submission in the site's SQLite database. No email is sent and no SMTP service or external account is required. Administrators can open **Messages** in the left navigation to read the sender's name, email address, message and submission date. Messages are listed newest first, with 25 per page. The inbox requires an administrator login.

Existing installations receive the additive `contact_messages` table at startup. Include the database in your normal backups to preserve messages. Validation and the existing anti-spam checks remain in place; if a submission cannot be saved, the form retains its contents for retrying.

## Configuration and Data Storage

Normal content and design configuration belongs in the admin panel. Deployment paths and cookie names can be supplied through environment variables or a `.env` file in the project root.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SITE_DB_PATH` | `db/site.db` | SQLite database location. |
| `SITE_STATIC_DIR` | `static` | Directory served at `/static`. |
| `SITE_TEMPLATES_DIR` | `templates` | Jinja2 template directory. |
| `SITE_UPLOAD_DIR` | `static/uploads` | Destination for uploaded files. |
| `SESSION_COOKIE_NAME` | `site_session` | Administrator session cookie name. |
| `SESSION_COOKIE_SECURE` | `true` | Whether the session cookie uses the Secure flag. Default `true` (production). Set to `0` or `false` for local HTTP development. |
| `LANG_COOKIE_NAME` | `site_lang` | Language preference cookie name. |

Relative paths are resolved from the application directory. Restart the application after changing environment configuration.

For example, to use another database file:

```dotenv
SITE_DB_PATH=db/my-site.db
```

Database-backed settings take precedence over the site defaults in [site_defaults.py](site_defaults.py). Existing installations have a persistent session secret stored in the database; routine setup does not require manually configuring one.

The database contains posts, categories, tags, administrator credentials, menus, settings, custom homepage documents, and translations. Uploaded media files live separately in the upload directory. Back up both.

Uploaded URLs use `/static/uploads/<filename>`. If you override storage locations, ensure these URLs still resolve to the actual upload directory through the static directory layout or your web-server configuration. Setting `SITE_UPLOAD_DIR` alone does not create a new public URL mapping.

## Deployment

### Running as a Linux Service

The following example assumes FriPeri is installed at `/opt/friperi`, its virtual environment is at `/opt/friperi/.venv`, and `www-data` is the chosen service account. Adjust the paths and account for your server. The account needs read access to the application and write access to the database directory and upload directory.

Create `/etc/systemd/system/friperi.service`:

```ini
[Unit]
Description=FriPeri personal publishing site
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/friperi
EnvironmentFile=-/opt/friperi/.env
ExecStart=/opt/friperi/.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now friperi
sudo systemctl status friperi
```

Inspect its logs with:

```bash
sudo journalctl -u friperi -f
```

### Serving a Public Website

Place a reverse proxy such as Nginx or Caddy in front of `127.0.0.1:8000` and configure HTTPS for your domain. Complete first-run setup before opening the installation to public traffic.

Ensure proxy upload limits accommodate your intended image and video uploads, including multipart request overhead. Serve only the intended public paths; database files, backups, and `.env` are private application data.

Do not use Uvicorn's development `--reload` option for the service. If exposing `/health`, note that its response includes the configured database and upload paths.

## Maintenance and Backups

### Backing Up and Restoring

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

For rollback, restore the compatible application code and database backup together. See [language migration details](translations/LANGUAGE_MIGRATION.md) before reverting an installation with translated content.

### Factory Reset

**A factory reset permanently deletes site content, settings, accounts, translations, uploads, and database backups within its reset scope.**

Stop FriPeri and back up anything you want to retain, then run:

```bash
python scripts/reset_friperi.py
```

Confirm with `y` or `yes`, then type the exact phrase `RESET FriPeri`.

The script removes supported database files and migration backups under `db/`, uploaded files under `static/uploads/`, and `.env` / `.env.bak`. It preserves application source, templates, CSS/JS, built-in translations, and the uploads directory itself. Storage overrides outside the supported reset scope cause the script to refuse the reset.

Start the application again and open the website to return to first-run setup.

## Development

### Repository Layout

| Path | Responsibility |
| --- | --- |
| `main.py` | Application routes, authentication, public rendering, and admin handlers. |
| `initialization.py` | Database initialization, schema updates, and credential hashing. |
| `custom_home.py` | Custom homepage block validation and safe rendering metadata. |
| `localization.py` | Language metadata, UI translations, and content fallback. |
| `language_migration.py` | Language schema migration and secondary-language archives. |
| `site_defaults.py` | Default site configuration and supported social platforms. |
| `templates/` | Public and admin Jinja2 templates. |
| `templates/admin/homepage.html` | Unified homepage mode selector and feed settings. |
| `templates/admin/custom_home.html` | Custom editor fragment included in the Homepage screen. |
| `static/` | Runtime CSS, JavaScript, and uploaded media. |
| `assets/` | Source stylesheets for the admin and first-run interfaces. |
| `translations/` | Built-in UI dictionaries and language migration documentation. |
| `scripts/` | CLI initialization, reset, and test-suite entry point. |
| `tests/` | Automated regression tests. |
| `licenses/` | Third-party license notices. |

For local development, start the application with automatic reload:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### Working on Styles

The admin and first-run styles use Tailwind CSS **v4.1.18**. Their compiled stylesheets are committed, so end users do not need a frontend build.

With the matching Tailwind standalone CLI installed, rebuild from the project root:

```bash
tailwindcss -i assets/admin.css -o static/admin.css --minify
tailwindcss -i assets/first-run.css -o static/first-run.css --minify
```

Rebuild the relevant stylesheet when changing its source or Tailwind utility classes in its templates. Keep source and compiled assets together in commits. Public styles, homepage editor styles, and image crop styles also have dedicated files under `static/`.

### Running Tests

With the project virtual environment active:

```bash
python -m unittest discover -s tests -v
```

The compatibility test entry point is also available:

```bash
python scripts/check_admin_changes.py
```

Tests use temporary databases. Coverage includes setup, homepage settings, custom homepage documents, validation, language behavior, and related admin operations. For changes to browser interactions, also check mode switching, preview, saving, image cropping, and mobile layouts in a browser.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| First-run setup appears for an existing site. | Confirm `SITE_DB_PATH` points to the intended initialized database and that the service account can access it. |
| The database is read-only or saving fails. | Check write permissions on the database directory as well as the file; SQLite needs access to create supporting files. |
| Uploaded images do not appear. | Check the upload directory, file permissions, and the `/static/uploads/` URL mapping, especially after overriding storage paths. |
| A large upload fails before reaching the editor. | Check reverse-proxy request limits and the Custom Home editor's per-file limits. |
| Custom Home still shows the content feed. | Select Custom Home and use **Save & publish**. An empty custom document falls back to the feed. |
| Category content is missing from a list. | Confirm the content is published, belongs to the selected category, and fits within the selected item count. |
| Card appearance does not change in the automatic feed. | Category card settings control category archives and custom category blocks; the automatic feed has its own layouts. |
| Contact messages cannot be saved. | Verify database write access and available disk space. Submitted messages appear under Admin → Messages. |
| A form reports that the language changed. | Reload the form after changing the secondary language, then edit and save again. |
| A UI label appears in English in the secondary language. | Its translation may be empty or missing; English is the fallback. |
| The block editor or cropper is unavailable. | Enable JavaScript and check that the bundled files under `/static` load successfully. |

## License

FriPeri is distributed under the **MIT License**.

Copyright © 2026 **Taner Sezer — NextNLP**.

See [LICENSE](LICENSE) for the full terms, including the copyright notice requirement and warranty disclaimer.

Parts of the admin interface adapt HyperUI application patterns by **Mark Mead**, also under the MIT License. The corresponding third-party notice is included in [licenses/HyperUI-MIT.txt](licenses/HyperUI-MIT.txt).
