# Third-party software and attribution notices

FriPeri itself is distributed under the [MIT License](LICENSE), copyright © 2026 Taner Sezer — NextNLP. This file documents identifiable third-party software and visual assets used by the source repository as of **2026-11-21**. It does not grant rights in material uploaded by site operators or users.

## Adapted or compiled frontend code included in this repository

| Component | Use in FriPeri | License | Copyright / attribution | Complete text |
| --- | --- | --- | --- | --- |
| [HyperUI](https://github.com/markmead/hyperui) (Mark Mead) | Patterns adapted in `assets/admin.css`, admin templates and generated admin styling | MIT | Copyright (c) Mark Mead | [licenses/HyperUI-MIT.txt](licenses/HyperUI-MIT.txt) |
| [Tailwind CSS](https://github.com/tailwindlabs/tailwindcss) **v4.1.18** | Compiled CSS rules in `static/admin.css`; corresponding build source in `assets/admin.css` | MIT | Copyright (c) Tailwind Labs, Inc. | [licenses/TailwindCSS-MIT.txt](licenses/TailwindCSS-MIT.txt) |

The minified `static/admin.css` retains the Tailwind version/license header. Both notices above must accompany copies or substantial portions of the respective MIT-licensed software. The project-level MIT license is **not** a substitute for these third-party notices.

Source license texts were checked against the corresponding upstream repositories:

- [HyperUI upstream LICENSE](https://github.com/markmead/hyperui/blob/main/LICENSE)
- [Tailwind CSS upstream v4.1.18 LICENSE](https://github.com/tailwindlabs/tailwindcss/blob/v4.1.18/LICENSE)

No live Tailwind, HyperUI, Google Fonts, icon CDN, JavaScript package manager or external frontend library is required by the committed site templates. Tailwind is a **build-time** tool and its generated CSS is distributed.

## Python packages installed separately with pip

The following **direct pinned requirements** are declared in [requirements.txt](requirements.txt). They are downloaded separately by the installer rather than copied into this repository. Their license texts, copyright holders, and any required notices ship with their respective installed distributions. License obligations may differ when creating a standalone/bundled executable, container image, wheel, or other distribution that includes dependency files.

| Direct requirement | Pinned version | Official package information |
| --- | --- | --- |
| annotated-types | 0.8.0 | [PyPI](https://pypi.org/project/annotated-types/) |
| anyio | 4.15.1 | [PyPI](https://pypi.org/project/anyio/) |
| click | 8.5.0 | [PyPI](https://pypi.org/project/click/) |
| fastapi | 0.165.0 | [PyPI](https://pypi.org/project/fastapi/) |
| greenlet | 3.5.6 | [PyPI](https://pypi.org/project/greenlet/) |
| h11 | 0.16.0 | [PyPI](https://pypi.org/project/h11/) |
| httptools | 0.8.0 | [PyPI](https://pypi.org/project/httptools/) |
| idna | 3.19 | [PyPI](https://pypi.org/project/idna/) |
| iniconfig | 2.3.0 | [PyPI](https://pypi.org/project/iniconfig/) |
| Jinja2 | 3.1.6 | [PyPI](https://pypi.org/project/Jinja2/) |
| MarkupSafe | 3.0.3 | [PyPI](https://pypi.org/project/MarkupSafe/) |
| Markdown | 3.11.3 | [PyPI](https://pypi.org/project/Markdown/) |
| packaging | 26.3 | [PyPI](https://pypi.org/project/packaging/) |
| pillow | 13.0.0 | [PyPI](https://pypi.org/project/Pillow/) |
| playwright | 1.63.0 | [PyPI](https://pypi.org/project/playwright/) |
| pluggy | 1.6.0 | [PyPI](https://pypi.org/project/pluggy/) |
| pydantic | 2.13.5 | [PyPI](https://pypi.org/project/pydantic/) |
| pydantic_core | 2.46.5 | [PyPI](https://pypi.org/project/pydantic-core/) |
| pyee | 13.0.1 | [PyPI](https://pypi.org/project/pyee/) |
| Pygments | 2.21.0 | [PyPI](https://pypi.org/project/Pygments/) |
| pytest | 9.1.1 | [PyPI](https://pypi.org/project/pytest/) |
| python-dotenv | 1.2.3 | [PyPI](https://pypi.org/project/python-dotenv/) |
| python-multipart | 0.0.31 | [PyPI](https://pypi.org/project/python-multipart/) |
| PyYAML | 6.0.3 | [PyPI](https://pypi.org/project/PyYAML/) |
| starlette | 1.10.0 | [PyPI](https://pypi.org/project/starlette/) |
| typing-inspection | 0.4.4 | [PyPI](https://pypi.org/project/typing-inspection/) |
| typing_extensions | 4.16.0 | [PyPI](https://pypi.org/project/typing-extensions/) |
| uvicorn | 0.35.0 | [PyPI](https://pypi.org/project/uvicorn/) |
| uvloop | 0.22.1 | [PyPI](https://pypi.org/project/uvloop/) |
| watchfiles | 1.2.0 | [PyPI](https://pypi.org/project/watchfiles/) |
| websockets | 17.1 | [PyPI](https://pypi.org/project/websockets/) |

**Environment-only license notice:** [packageurl-python 0.17.6](https://pypi.org/project/packageurl-python/0.17.6/) is MIT licensed (copyright the purl authors). Its installed distribution reports MIT but does not expose a separate license file in our local audit. We preserve the versioned upstream copyright and full MIT terms in [licenses/packageurl-python-MIT.txt](licenses/packageurl-python-MIT.txt). This package is part of the Python tooling environment rather than a direct FriPeri runtime requirement.

Developer-only requirements include `httpx` (defined in [requirements-dev.txt](requirements-dev.txt)) and any dependencies it resolves. Browser binaries installed via `python -m playwright install` also have their own notices (Chromium and Firefox have separate licenses) and are **not included in this Git repository**.

For a fresh, current list of licenses and notices **actually installed** in an environment, run:

```bash
python scripts/audit_third_party_licenses.py
python scripts/audit_third_party_licenses.py --output third-party-installed.md
```

Review entries marked `UNKNOWN`, `MISSING`, or license files not discoverable through the distribution metadata. Always re-run when pins change. The report inventories installed packages, including transitive packages not enumerated above. Do not claim the human-curated table itself is a complete bill of materials for a packaged deployment.

## Icons, brand marks, images and typography

- `templates/admin/partials/icons.html` contains inline SVG path definitions used for admin interface actions. The repository does **not** contain enough provenance to certify that every path was drawn independently rather than adapted from an external icon library. **Attribution review remains open**; if the icons are derived from an existing collection, add that collection's copyright and license notice.
- `templates/partials/social_icon.html` contains SVG marks or simplified representations of external platforms (including LinkedIn, X, GitHub, ORCID, ResearchGate, Bluesky, etc.). These identify services; the corresponding names and logos may be protected as **trademarks** independently of copyright licenses. Do not imply endorsement, partnership or transfer of trademark rights. If any mark was sourced directly from a third-party icon package, retain that package's license as well.
- **FriPeri brand assets:** `static/images/FriPeri.png`, `static/images/FriPeri_Icon.png` and `static/images/FriPeri_Logo.png` belong to **Taner Sezer**, as confirmed by the project owner. They are project-owned branding, not third-party assets. This ownership statement does not independently settle trademark registration or any separate permission terms for using the FriPeri name and logo outside the project.
- The committed CSS uses a system-font fallback chain, including an `Inter` family name, but this repository does not include an Inter font file or download the font from a third-party service. Therefore no Inter font binary is being redistributed with the repo. If a font file is added later, check its license and add its notice.

## User-generated and embedded external content

FriPeri supports media uploads, links, optional iframe embeds (YouTube/Vimeo), and administrator-configured HTML snippets. **Licenses for those externally hosted or user-supplied materials are not covered by FriPeri's MIT license.** The uploading site owner is responsible for obtaining the necessary content rights and observing provider terms.

## Release checklist

1. Retain `LICENSE`, `licenses/HyperUI-MIT.txt`, `licenses/TailwindCSS-MIT.txt`, `licenses/packageurl-python-MIT.txt`, and this file in every source distribution.
2. Run the installed-dependency audit, inspect third-party package metadata and license files, and resolve unknown/missing entries before distributing a bundled runtime.
3. If shipping Playwright browsers, system fonts, native binaries or other bundled dependencies, include their own applicable license notices.
4. Confirm the provenance of inline SVG icons and any other newly introduced images; add notices if an external source is identified. FriPeri logo ownership has been confirmed by the project owner.
5. Recheck the inventory when packages, assets, fonts, icon sets, build tools or embed libraries change.

This inventory is a transparency aid, not a guarantee that no additional third-party rights exist or legal advice.
