## Detailed Usage

### Finding Your Way Around the Admin Panel

Sign in at `/login`, then open `/admin`. Available screens depend on your account role; see [Users and permissions](user-roles.md). The administrator's sidebar groups tools by purpose:

| Group | Screen | Purpose |
| --- | --- | --- |
| Overview | Dashboard | Review recent content, publication totals, and category counts. |
| Overview | Messages | Read submissions from the contact form. |
| Content | Content list | Create, edit, and delete posts and notes. |
| Content | Categories | Create and delete content categories. |
| Content | Pages | Create and manage standalone pages with the block editor. |
| Website | Homepage | Choose the homepage mode and edit its settings or blocks. |
| Website | About | Edit the public About page with the block editor. |
| Website | Design | Configure public website colors and the footer. |
| Website | Menu | Configure category navigation and custom links. |
| Configuration | Settings | Edit site identity, welcome text, built-in link visibility, and category card options. |
| Configuration | Social Links | Configure social profile URLs and visibility. |
| Configuration | Language | Configure the secondary language and custom interface translations. |
| Configuration | Contact Details | Configure contact-page text and the optional contact email address. |
| Configuration | Backup | Create, download, upload, and restore ZIP backups. |
| Configuration | Users | Create accounts, assign content roles and grant creators access to categories. |

The navigation collapses on small screens. The admin interface uses its own colors; changing public website colors does not change the admin theme. Interface labels follow the selected language.

### Creating and Publishing Content

1. Open the content list and choose **New Content**.
2. Enter the English title and excerpt.
3. Build the body with the shared block editor: add headings, formatted text, lists, links, tables, images, and other supported blocks.
4. Select a category, or leave the content uncategorized (editor/admin only). Content creators must choose an assigned category.
5. Add optional tags separated by commas and an optional preview image.
6. If a secondary language is configured, use the editor's language selector to add its title, excerpt, and blocks.
7. Choose **Save as draft** to keep the post unpublished, or **Publish** to make it publicly available. The editor has separate buttons for these actions.

Published content appears in its category and in relevant homepage lists. Drafts are excluded from public lists and are not accessible to anonymous visitors through their post URLs. Administrators and editors can view draft detail pages; content creators can view only their own drafts.

Each post receives a URL derived from its title, such as `/posts/my-first-post`. Open an existing item from the dashboard or content list to edit it. Deleting content removes the post; use a draft when you want to keep the content without publishing it.

For example, create a post titled **Project Update**, choose a **News** category, and add `updates, projects` as tags. Preview it, save it as a draft, then change its status to Published when ready. Existing HTML-based posts are wrapped in a legacy-content block when opened in the current editor; their original body fields remain stored.

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

**Nested navigation:** In **Website → Menu**, add a custom menu item named **Resources** and leave its URL empty to make it a group. In the **Custom pages** section, select **Resources** as the parent of pages such as **Getting Started** and **Project Overview**, enable their menu visibility, and save. The published pages will appear inside the Resources dropdown. New groups are selectable before saving.

Categories, custom links, custom pages, and built-in page links can be assigned to a parent menu. Sort order applies within each group. Up to five levels are supported; circular relationships are rejected. Hidden groups hide their descendants, empty groups are omitted, and deleting a group promotes its direct children to the top level without deleting their pages. Dropdowns support touch and keyboard navigation.

Open **Content → Custom Page**, enter a title, and select **Create & edit**. The new page starts as a draft and uses the same visual builder as Custom Home and About, including translated blocks, media uploads and cropping, category lists, undo/redo, and desktop/mobile preview.

Homepage, About, custom page, and post editors use the full available admin workspace width. The block palette is 260–320 px wide on desktop and stacks above the canvas on small screens. Set the page title and address, then choose **Show in menu** if you want a link in the public navigation. **Save & publish** saves both the page settings and its content. Published pages are available at `/pages/<address>`. Turning off menu visibility removes the navigation link but keeps the page accessible by its address.

Use the Custom Page list to reopen, view, or delete a page. Deleting a page also removes its automatic navigation link. Each page has its own content and does not change the homepage or About page. Existing databases receive the new page table automatically when the application starts.

### The About Page

Edit `/about` under **Website → About** using the shared block editor, including language versions, media, category lists, and previews. Saving enables the block-based About page. Before that, the application renders its default About template.

The **Show About** setting controls both its public navigation link and the About entry in the admin sidebar. Hiding the link does not disable the `/about` route; the editor remains reachable at `/admin/about`.

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
| Text | Compose rich text with headings, lists, tables, quotations, code, links, colors, and embedded images. |
| List | Add a bulleted or numbered list. |
| Table | Edit cells, add or remove rows and columns, and supply a caption. |
| Image | Upload or link an image; add alternative text and a caption. |
| Video | Upload a video or use a supported video URL. |
| Button | Add a labeled link. |
| Quote | Add a quotation with attribution. |
| Callout | Highlight a titled message. |
| Statistics | Display value-and-label pairs. |
| Team | Display up to eight people with a photo, full name, and title. Choose a round or rectangular portrait for each member. |
| FAQ | Add questions and answers. |
| Divider | Separate parts of the page. |

Above the block list, **Split hero section** inserts the existing text-and-image hero. Directly underneath it, **Two Column Hero** inserts two equal-width columns, each with editable heading, text, and button blocks. Both columns stack on small screens; use the section layout controls to change the arrangement. The existing Light split hero remains available.

A **Team** block follows the Statistics block's repeatable-item workflow. Each person has three content fields: a photo (upload or secure image URL), full name, and title. Choose **Rectangle** or **Circle** for each portrait. You can add up to eight members, change the ordering with the block's editing controls, and preview the resulting responsive grid.

Blocks can be moved up or down, duplicated, and removed. **Undo** and **Redo** restore editor changes within the current editing session.

A **Text** block has a full-width formatting toolbar directly below Background, Alignment, and Width. Formatting actions use grouped icons with tooltips and accessible labels; content retains its chosen reading width. The toolbar supports: paragraphs and H1–H6 headings; bold, italic, underline, strikethrough, subscript and superscript; nested bulleted/numbered lists and indentation; four-way alignment; quotations and code blocks; inline code, keyboard input, abbreviations, citations and small text; font family, size, text color and highlighting; text direction; definition lists, expandable text, and dividers. Links support HTTP(S), site paths, anchors, email and telephone addresses. Insert tables within the text and use the row/column controls with the cursor in a cell. The table caption and cells are directly editable. Shared Undo/Redo also covers text formatting.

Pasting formatted HTML preserves supported structures and presentation while filtering scripts, unsafe links, event handlers and unsupported styles. The server applies its allowlist again when saving or previewing. Editor, preview and published text use the same typography.

In a **Text** block, open **Image in text**. Place the cursor where you want the image, upload a PNG/JPEG/WebP (up to 8 MB) or enter an HTTPS/site-upload URL, and add alternative text. Choose **Image left · text right**, **Image right · text left**, or **No wrapping**, plus an image width, then select **Insert image into text**. When you edit an existing image’s settings, an **Unapplied changes** badge and a highlighted message appear. Select **Apply image changes** to update the text; a confirmation then reminds you to save the page. Click an embedded image to change its settings or remove it. Small screens stack images and text. These controls are shared by Custom Home, About, and Custom Pages; preview and **Save & publish** work as usual.

Each block provides background, alignment, and width controls:

- **Background:** None, Soft, Accent, Dark, White, or a custom **Color Selection** picker. None leaves the background transparent.
- **Alignment:** left, center, or right.
- **Width:** normal reading width or wide.

The Soft and Accent options use the configured public site palette. Use **Website → Design** to change those site colors.

Additional appearance controls sit below the shared block settings and update the editor immediately:

| Block | Appearance controls |
| --- | --- |
| List | Text size (10–72 px) and spacing between items (0–48 px). |
| Table | Default cell/header background and text colors. Select a cell to override its background/text colors independently; reset cell colors to inherit the table defaults. |
| Button | Background/text colors, hover/focus background/text colors, text size, corner radius, minimum height (24–240 px), and content-sized, full-width, or custom width (40–1200 px, capped by the available space). Full width fills the block's content area. |
| Quote | Quote and attribution text sizes/colors, normal or italic text, and line color/thickness (0 hides the line). |
| Statistics | Value/label colors and sizes, card background/padding, spacing, and 1–4 columns. Small screens stack the cards. |

**Reset appearance** restores theme defaults for that block; individual table-cell overrides have their own reset. Existing blocks retain their defaults until you change a setting. Save and preview preserve these settings for all shared-editor pages and posts.

A **Category list** block supports 1–16 items from any available category, including Blog and Notes. It updates automatically as matching content is published. Use **Preview** to see the current list; card appearance comes from the category card settings described below. An empty or missing source category does not turn the block into an all-content feed.

Use **Preview** to inspect the unsaved page at desktop or mobile width. **Save & publish** saves the custom documents and activates Custom Home. The site's navigation and footer remain around the custom page.

The editor supports up to 80 blocks per language and 500,000 bytes per serialized document. Tables support up to 30 rows and 8 columns. A document is stored as validated block data; arbitrary scripts and iframe markup are not supported.

#### Homepage Media and Languages

These upload limits apply to media blocks in the shared editor for posts, Custom Home, About, and custom pages:

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

Under **Website → Design**, configure page, navigation, feature, accent, separator, and footer colors. On mobile screens, the footer's site name/date and Powered by information are centered on separate lines; social icons remain centered between them when configured. You can also edit the footer text in each configured content language and control footer visibility.

Under **Website → Menu**, configure category labels, sort order, and visibility. Add custom links with a label, URL, order, visibility setting, and optional new-tab behavior. Supply a translated label when using a secondary language.

Under **Configuration → Settings**, edit site identity, homepage welcome text, and public built-in link visibility. The `/login` route remains available when its navigation link is hidden.

Under **Configuration → Social Links**, set profile URLs and individual visibility for LinkedIn, X/Twitter, GitHub, ORCID, Google Scholar, ResearchGate, Bluesky, Mastodon, YouTube, Instagram, and Facebook.

### Managing Languages

English is always the primary content language. Under **Configuration → Language**, select no secondary language, Turkish, German, French, or a custom language.

For a custom language, enter its name and code, then fill in the grouped interface translations. Missing interface translations and empty secondary content fields fall back to English. You can show or hide the public language switcher.

Content translations share the original post IDs, URLs, categories, tags, and images. The translated title, excerpt, and body are edited alongside the English content. Custom homepage documents are separate for each configured language.

Changing the secondary language archives its translated content and settings. Selecting that language again restores its archived fields for records that still exist. Selecting None hides secondary-language fields without deleting their values. Forms opened before a language change may reject a stale save; reload them before continuing.

For storage and migration details, see [the language model documentation](../translations/LANGUAGE_MIGRATION.md).

### Contact Details and Messages

Under **Configuration → Contact Details**, configure the contact-page introduction and public contact text. The contact email address is optional; it is not a delivery destination.

The public `/contact` form stores each valid submission in the site's SQLite database. No email is sent and no SMTP service or external account is required. Administrators can open **Messages** in the left navigation to read the sender's name, email address, message and submission date. Messages are listed newest first, with 25 per page. The inbox requires an administrator login.

Existing installations receive the additive `contact_messages` table at startup. Include the database in your normal backups to preserve messages. Validation and the existing anti-spam checks remain in place; if a submission cannot be saved, the form retains its contents for retrying.

## Reading the built-in documentation

The **Configuration → Documentation** item opens `/admin/documentation`. An authenticated administrator can browse the Markdown guides stored in the project's `docs/` directory without leaving the admin interface. The reader includes a table of contents, supports tables, fenced code blocks and normal links, and links between files in `docs/` navigate within the viewer.

Adding or changing an ordinary `.md` file under `docs/` updates the list on the next request; no database migration is required. Documentation is read-only in the admin interface and is deployed alongside the application source. Other local files, including secrets and database contents, are not exposed by the reader.

On desktop, a **left-pointing arrow** at the top of the sidebar collapses the menu to icons. The arrow turns right to expand it again. The state persists for that browser. On narrower screens the original responsive navigation remains in place.

---

[Documentation index](index.md) · [Project README](../README.md)
