"""Read and render locally maintained Markdown documentation for the admin panel."""
from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import markdown


def list_documents(root: Path) -> list[dict[str, str]]:
    """List only Markdown documents from the checked-in docs directory."""
    if not root.is_dir():
        return []
    results = []
    for file in sorted(root.rglob("*.md")):
        if not file.is_file() or file.is_symlink():
            continue
        relative = file.relative_to(root).as_posix()
        if any(part.startswith(".") for part in file.relative_to(root).parts):
            continue
        text = file.read_text(encoding="utf-8")
        match = re.search(r"^#\s+(.+?)\s*$", text, flags=re.MULTILINE)
        results.append({"name": relative, "title": match.group(1) if match else file.stem.replace("-", " ").title()})
    return sorted(results, key=lambda item: (item["name"] != "index.md", item["title"].casefold()))


def render_document(root: Path, name: str, allowed: set[str]) -> str:
    """Convert trusted repo Markdown to HTML; only allow navigable safe links."""
    if name not in allowed:
        raise FileNotFoundError(name)
    source = root / name
    if not source.is_file() or source.is_symlink():
        raise FileNotFoundError(name)
    # Disable raw HTML embedded in a Markdown file before handing it to the renderer.
    content = source.read_text(encoding="utf-8").replace("<", "&lt;")
    output = markdown.markdown(content, extensions=["tables", "fenced_code", "toc", "sane_lists"], output_format="html5")

    def replace_link(match: re.Match[str]) -> str:
        attribute, raw = match.group(1), html.unescape(match.group(2))
        parsed = urlsplit(raw)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return f'{attribute}="{html.escape(raw, quote=True)}"'
        if parsed.scheme or parsed.netloc or raw.startswith("//"):
            return f'{attribute}="#"'
        if not parsed.path:
            return f'{attribute}="{html.escape(raw, quote=True)}"'
        if attribute == "src":
            return f'{attribute}="#"'
        # Only Markdown files inside docs are rendered in the admin.
        target = (Path(name).parent / unquote(parsed.path)).as_posix()
        from posixpath import normpath
        target = normpath(target)
        if target in allowed:
            link = "/admin/documentation?file=" + quote(target, safe="")
            if parsed.fragment:
                link += "#" + quote(parsed.fragment, safe="-_")
            return f'{attribute}="{html.escape(link, quote=True)}"'
        # Links to project-root documents open the canonical GitHub source.
        if target.startswith("../") and not target.startswith("../../"):
            path = target[3:]
            link = "https://github.com/tanerim/FriPeri/blob/main/" + quote(path, safe="/")
            if parsed.fragment:
                link += "#" + quote(parsed.fragment, safe="-_")
            return f'{attribute}="{html.escape(link, quote=True)}"'
        return f'{attribute}="#"'

    return re.sub(r'(href|src)="([^"]*)"', replace_link, output)
