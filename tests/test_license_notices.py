"""Source-distribution license notice regression checks."""
from pathlib import Path

from scripts.audit_third_party_licenses import pinned_requirements


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_license_texts_and_documentation_present():
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    for name, holder in [
        ("HyperUI-MIT.txt", "Mark Mead"),
        ("TailwindCSS-MIT.txt", "Tailwind Labs, Inc."),
        ("packageurl-python-MIT.txt", "the purl authors"),
    ]:
        text = (ROOT / "licenses" / name).read_text(encoding="utf-8")
        assert text.startswith("MIT License")
        assert holder in text
        assert "THE SOFTWARE IS PROVIDED" in text
        assert name in notices
    assert "THIRD_PARTY_NOTICES.md" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_every_direct_requirement_is_listed_in_third_party_notices():
    requirements = pinned_requirements(ROOT / "requirements.txt")
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    import re
    listed = {
        re.sub(r"[-_.]+", "-", row.split("|")[1].strip()).lower()
        for row in notices.splitlines()
        if row.startswith("| ") and " | " in row and row.count("|") >= 4
    }
    missing = sorted(set(requirements) - listed)
    assert not missing, f"Unlisted direct dependencies: {missing}"


def test_tailwind_css_compiled_header_is_preserved():
    compiled = (ROOT / "static" / "admin.css").read_text(encoding="utf-8")
    assert "tailwindcss v4.1.18" in compiled
    assert "MIT License" in compiled[:250]
