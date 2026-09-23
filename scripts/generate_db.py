from __future__ import annotations

import argparse
import getpass
import locale
import os
import re
import secrets
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")
from initialization import initialize_database, setup_defaults, SetupError


def slugify(value: str) -> str:
    mapping = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    normalized = value.translate(mapping).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return slug or "site"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set up a standalone SQLite-backed personal publishing site."
    )
    parser.add_argument("--secondary-language", choices=("", "tr", "de", "fr"), default="", help="Optional secondary language; English is always the base.")
    parser.add_argument("--site-name", help="Public site name.")
    parser.add_argument("--site-description", help="Short description used in metadata.")
    parser.add_argument("--hero-kicker-secondary", help="Secondary-language hero kicker.")
    parser.add_argument("--hero-kicker-en", help="English hero kicker.")
    parser.add_argument("--hero-title-secondary", help="Secondary-language hero title.")
    parser.add_argument("--hero-title-en", help="English hero title.")
    parser.add_argument("--hero-copy-secondary", help="Secondary-language hero copy.")
    parser.add_argument("--hero-copy-en", help="English hero copy.")
    parser.add_argument("--linkedin-url", help="LinkedIn profile URL.")
    parser.add_argument("--twitter-url", help="Twitter/X profile URL.")
    parser.add_argument("--contact-email", help="Public contact email.")
    parser.add_argument("--hero-background-enabled", choices=("0", "1"), help="Use hero background image.")
    parser.add_argument("--hero-background-image-path", help="Existing hero background image path.")
    parser.add_argument(
        "--db-path",
        help="SQLite database path. Defaults to db/<site-slug>.db.",
    )
    parser.add_argument("--admin-username", help="Admin username.")
    parser.add_argument("--admin-password", help="Admin password.")
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Run non-interactively. Required values must be provided as arguments or env vars.",
    )
    return parser.parse_args()


def ask(prompt: str, default: str = "", required: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = read_prompt(f"{prompt}{suffix}: ").strip()
        value = value or default
        if value or not required:
            return value
        print("This value is required.")


def read_prompt(prompt: str) -> str:
    print(prompt, end="", flush=True)
    raw = sys.stdin.buffer.readline()
    raw = raw.rstrip(b"\r\n")
    encodings = [
        sys.stdin.encoding,
        locale.getpreferredencoding(False),
        "utf-8",
        "cp1254",
        "iso-8859-9",
        "latin-1",
    ]
    for encoding in dict.fromkeys(filter(None, encodings)):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def collect_setup(args: argparse.Namespace) -> dict[str, str]:
    site_name = args.site_name or os.getenv("SITE_NAME", "")
    site_description = args.site_description or os.getenv("SITE_DESCRIPTION", "")

    if not args.no_prompt:
        site_name = ask("Site name", site_name or "My Site", required=True)
        site_description = ask(
            "Site description",
            site_description or "A personal publishing site.",
            required=True,
        )
        hero_kicker_secondary = ask("Hero kicker — Secondary Language", args.hero_kicker_secondary or "") if args.secondary_language else ""
        hero_kicker_en = ask("Hero kicker — English", args.hero_kicker_en or "Personal Publishing")
        hero_title_secondary = ask("Hero title — Secondary Language", args.hero_title_secondary or "") if args.secondary_language else ""
        hero_title_en = ask("Hero title — English", args.hero_title_en or site_name)
        hero_copy_secondary = ask(
            "Hero copy — Secondary Language",
            args.hero_copy_secondary or "",
        ) if args.secondary_language else ""
        hero_copy_en = ask(
            "Hero copy — English",
            args.hero_copy_en or "A personal publishing system for blog posts, notes, and content.",
        )
        linkedin_url = ask("LinkedIn URL", args.linkedin_url or os.getenv("SOCIAL_LINKEDIN_URL", ""))
        twitter_url = ask("Twitter/X URL", args.twitter_url or os.getenv("SOCIAL_TWITTER_URL", ""))
        contact_email = ask("Contact email", args.contact_email or os.getenv("CONTACT_EMAIL", ""))
        hero_background_enabled = args.hero_background_enabled or os.getenv("HERO_BACKGROUND_ENABLED", "0")
        hero_background_image_path = args.hero_background_image_path or os.getenv("HERO_BACKGROUND_IMAGE_PATH", "")
    else:
        hero_kicker_secondary = args.hero_kicker_secondary or os.getenv("HERO_KICKER_SECONDARY", "")
        hero_kicker_en = args.hero_kicker_en or os.getenv("HERO_KICKER_EN", "Personal Publishing")
        hero_title_secondary = args.hero_title_secondary or os.getenv("HERO_TITLE_SECONDARY", "")
        hero_title_en = args.hero_title_en or os.getenv("HERO_TITLE_EN", site_name)
        hero_copy_secondary = args.hero_copy_secondary or os.getenv("HERO_COPY_SECONDARY", "")
        hero_copy_en = args.hero_copy_en or os.getenv("HERO_COPY_EN", "")
        linkedin_url = args.linkedin_url or os.getenv("SOCIAL_LINKEDIN_URL", "")
        twitter_url = args.twitter_url or os.getenv("SOCIAL_TWITTER_URL", "")
        contact_email = args.contact_email or os.getenv("CONTACT_EMAIL", "")
        hero_background_enabled = args.hero_background_enabled or os.getenv("HERO_BACKGROUND_ENABLED", "0")
        hero_background_image_path = args.hero_background_image_path or os.getenv("HERO_BACKGROUND_IMAGE_PATH", "")

    if not site_name:
        raise SystemExit("--site-name is required in --no-prompt mode.")
    if not site_description:
        site_description = "A personal publishing site."

    settings = setup_defaults()
    settings.update({
        "secondary_language": args.secondary_language,
        "secondary_content_code": args.secondary_language,
        "show_language_switcher": "1",
        "site_name": site_name,
        "site_description": site_description,
        "hero_kicker_secondary": hero_kicker_secondary,
        "hero_kicker_en": hero_kicker_en,
        "hero_title_secondary": hero_title_secondary,
        "hero_title_en": hero_title_en or site_name,
        "hero_copy_secondary": hero_copy_secondary or "",
        "hero_copy_en": hero_copy_en or "A personal publishing system for blog posts, notes, and content.",
        "social_linkedin_url": linkedin_url,
        "social_twitter_url": twitter_url,
        "contact_email": contact_email,
        "hero_background_enabled": "1" if hero_background_enabled == "1" else "0",
        "hero_background_image_path": hero_background_image_path,
    })
    return settings


def collect_credentials(args: argparse.Namespace) -> tuple[str, str]:
    username = args.admin_username or os.getenv("ADMIN_USERNAME", "")
    password = args.admin_password or os.getenv("ADMIN_PASSWORD", "")

    if not args.no_prompt:
        username = ask("Admin username", username or "admin", required=True)
        while True:
            first = getpass.getpass("Admin password: ")
            second = getpass.getpass("Admin password again: ")
            if len(first) < 8:
                print("Use at least 8 characters.")
                continue
            if first != second:
                print("Passwords do not match.")
                continue
            password = first
            break

    if not username:
        raise SystemExit("--admin-username is required in --no-prompt mode.")
    if not password:
        raise SystemExit("--admin-password is required in --no-prompt mode.")
    return username, password


def main() -> int:
    args = parse_args()
    settings = collect_setup(args)
    username, password = collect_credentials(args)
    configured = args.db_path or os.getenv("SITE_DB_PATH", "db/site.db")
    db_path = Path(configured)
    if not db_path.is_absolute():
        db_path = ROOT_DIR / db_path
    try:
        initialize_database(db_path, settings, username, password, password)
    except SetupError as exc:
        for message in exc.errors.values():
            print(message, file=sys.stderr)
        return 1
    except (OSError, RuntimeError) as exc:
        print("Database initialization failed. Check the database path and permissions.", file=sys.stderr)
        return 1
    print(f"SQLite database ready: {db_path}")
    if args.db_path:
        print("Set SITE_DB_PATH to this path when starting FriPeri.")
    print("Run locally with: uvicorn main:app --host 127.0.0.1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
