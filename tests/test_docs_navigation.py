"""Keep the short README and topic documentation navigable without GitHub Actions."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDES = {
    "overview.md": ("## What Is FriPeri?", "## Features"),
    "installation.md": ("### Requirements", "### 5. Complete first-run setup"),
    "user-guide.md": ("### Creating and Publishing Content", "### Contact Details and Messages"),
    "configuration.md": ("### Initial values and site defaults", "### Persistent data"),
    "deployment.md": ("### Running as a Linux Service", "## Security hardening notes"),
    "maintenance.md": ("### Backing Up and Restoring", "## Hardened backup and restore"),
    "development.md": ("### Repository Layout", "## License inventory"),
    "support.md": ("## Contributing and Support",),
    "troubleshooting.md": ("## Troubleshooting", "The block editor or cropper is unavailable."),
}


def test_readme_is_a_landing_page():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert len(readme.splitlines()) <= 150
    assert "## Quick start" in readme
    assert "docs/index.md" in readme
    for name in GUIDES:
        assert f"docs/{name}" in readme or f"({name})" in readme or name in (ROOT / "docs/index.md").read_text(encoding="utf-8")


def test_migrated_topics_are_present():
    for name, headings in GUIDES.items():
        content = (ROOT / "docs" / name).read_text(encoding="utf-8")
        for heading in headings:
            assert heading in content, f"{name} does not contain {heading}"


def test_relative_markdown_links_resolve():
    """Verify file targets, including relative links moving from README to docs/."""
    files = [ROOT / "README.md", *(ROOT / "docs").glob("*.md")]
    pattern = re.compile(r"\]\(([^)]+)\)")
    missing = []
    for source in files:
        body = source.read_text(encoding="utf-8")
        for link in pattern.findall(body):
            if not link or link.startswith(("#", "http://", "https://", "mailto:", "data:")):
                continue
            target = link.split("#", 1)[0].split("?", 1)[0]
            if target and not (source.parent / target).exists():
                missing.append(f"{source.relative_to(ROOT)}: {link}")
    assert not missing, "Broken documentation links:\n" + "\n".join(missing)
