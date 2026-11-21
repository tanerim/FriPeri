## What Is FriPeri?

FriPeri brings content editing, page building, website configuration, and publishing into one application that runs on your own server. It suits personal websites, portfolios, project pages, blogs, and categorized notes. You manage the site in a browser and keep its content in a local SQLite database.

The public website and administration panel are included in the same repository. No external database server, Node.js runtime, frontend build, or hosted editor account is required to run the application.

## Features

- **Content publishing:** a shared visual block editor, drafts, published posts, categories, comma-separated tags, excerpts, and preview images.
- **Two homepage modes:** Content feed and Custom Home, managed from the same screen.
- **A shared visual editor:** headings, formatted text, lists, tables, images, videos, buttons, dividers, dynamic category lists, quotes, callouts, statistics, and FAQs; undo/redo and desktop/mobile previews.
- **Standalone pages:** custom pages at `/pages/<address>` and a dedicated About page, using the same editor as posts and the homepage.
- **Image cropping:** aspect-ratio selection, zoom, dragging, and position sliders for content images and uploaded images in the homepage editor.
- **Category presentation controls:** individual card colors and date, title, and excerpt visibility settings for each category.
- **Website customization:** nested navigation with up to five levels, category links, custom links, public site colors, footer text, welcome text, and contact details.
- **Social profiles:** URLs and visibility controls for 11 supported platforms.
- **Multilingual content:** English as the primary language, with one optional secondary language and English fallback.
- **Role-based accounts:** content creators restricted to their own posts and assigned categories, editors who manage content, and administrators who manage site settings and users.
- **An administration dashboard:** recent content, published and draft totals, category counts, and shortcuts to common tasks.
- **Browser-based installation:** the first-run form creates the database and administrator account.
- **Contact inbox:** contact-form submissions stored in SQLite and read from the administration panel.
- **Backup tools:** create, download, upload, and restore ZIP archives from the admin panel, subject to the storage-path limits described below.

Blog and Notes are categories within the same content system. You can create additional categories and use them in navigation, the content feed, and custom homepage blocks.

### Technical overview

FriPeri uses Python, FastAPI, Uvicorn, Jinja2 templates, SQLite, and bundled JavaScript/CSS. The Python dependencies are pinned in [requirements.txt](../requirements.txt).

Running the application does not require Node.js, a frontend build, an external database server, or a hosted editor service. JavaScript is required for interactive features such as the visual homepage editor, immediate homepage mode switching, and image cropping. Externally linked images and embedded videos still depend on their respective hosts.

### Current scope

This guide describes the implementation in this checkout. English is the fixed primary language, with at most one active secondary language. Translation is manual. The application provides administrator-managed accounts with three roles; there is no public self-registration. See [Users and permissions](user-roles.md). Contact submissions do not send email. There are no built-in public search, RSS, commenting, or scheduled-publishing screens/routes in this checkout.

---

[Documentation index](index.md) · [Project README](../README.md)
