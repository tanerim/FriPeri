#!/usr/bin/env python3
"""Inspect installed Python distributions for provenance and license notices.

No network access, external package dependencies, or GitHub Actions required.
Use --strict to fail when pinned dependencies have missing/unknown licenses.
"""
from __future__ import annotations

import argparse
import importlib.metadata as metadata
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LICENSE_NAMES = ("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS")


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def pinned_requirements(path: Path) -> dict[str, str]:
    output = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9_.-]*)==([^\s;]+)", line)
        if not match:
            raise ValueError(f"Cannot inventory unpinned requirement: {raw}")
        output[normalized(match.group(1))] = match.group(2)
    return output


def distribution_license(dist: metadata.Distribution) -> str:
    expr = dist.metadata.get("License-Expression", "").strip()
    if expr:
        return expr
    classifiers = [
        value.rsplit("::", 1)[-1].strip()
        for value in dist.metadata.get_all("Classifier", [])
        if value.startswith("License ::")
    ]
    if classifiers:
        return "; ".join(classifiers)
    legacy = dist.metadata.get("License", "").strip()
    # Legacy metadata may contain entire license text: avoid duplicating it in a table.
    if legacy and len(legacy) < 120 and "\n" not in legacy:
        return legacy
    return "UNKNOWN"


def license_files(dist: metadata.Distribution) -> list[str]:
    declared = set(dist.metadata.get_all("License-File", []) or [])
    candidates = []
    for path in dist.files or []:
        name = Path(str(path)).name.upper()
        if any(name.startswith(prefix) for prefix in LICENSE_NAMES) or str(path) in declared:
            candidates.append(str(path))
    return sorted(set(candidates))


def report() -> tuple[str, bool]:
    pinned = pinned_requirements(ROOT / "requirements.txt")
    installed = {normalized(d.metadata.get("Name", "")): d for d in metadata.distributions()}
    bad = False
    rows = []
    for name in sorted(installed | pinned):
        dist = installed.get(name)
        direct = name in pinned
        if not dist:
            if direct:
                rows.append((name, pinned[name], "MISSING", "MISSING", "not installed", "direct"))
                bad = True
            continue
        version = dist.version
        license_name = distribution_license(dist)
        paths = license_files(dist)
        if direct and (license_name == "UNKNOWN" or not paths or version != pinned[name]):
            bad = True
        status = "OK"
        if direct and version != pinned[name]:
            status = f"VERSION MISMATCH (pin {pinned[name]})"
        elif license_name == "UNKNOWN":
            status = "UNKNOWN"
        elif not paths:
            status = "NO LICENSE FILE FOUND"
        rows.append((name, version, license_name, status,
                     ", ".join(paths) if paths else "—",
                     "direct" if direct else "transitive / environment"))

    def clean(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")
    output = [
        "# Installed Python third-party licenses",
        "",
        "Generated using Python distribution metadata from the current environment.",
        "Inspect package LICENSE/NOTICE files for full legal terms; this is not legal advice.",
        "",
        "| Distribution | Installed version | Reported license | Status | Included license files | Scope |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    output.extend("| " + " | ".join(clean(x) for x in row) + " |" for row in rows)
    output.extend(["", "Metadata from installed wheels may be incomplete. Unknown entries require review.",
                   "This report deliberately includes environment-only and transitive packages.",
                   ""])
    return "\n".join(output), bad


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write a Markdown license inventory to this file")
    parser.add_argument("--strict", action="store_true", help="Exit with an error for incomplete pinned package license data")
    args = parser.parse_args()
    content, incomplete = report()
    if args.output:
        args.output.write_text(content, encoding="utf-8")
        print(f"Wrote: {args.output}")
    else:
        print(content)
    if args.strict and incomplete:
        parser.exit(1, "Some direct requirements lack verifiable license metadata/files or do not match pins.\n")


if __name__ == "__main__":
    main()
