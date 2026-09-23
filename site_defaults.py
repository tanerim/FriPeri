import os

DEFAULT_SITE_SETTINGS = {
    "site_name": os.getenv("SITE_NAME", "Personal Site"),
    "site_description": os.getenv("SITE_DESCRIPTION", "A personal publishing site."),
    "hero_kicker_secondary": os.getenv("HERO_KICKER_SECONDARY", ""),
    "hero_kicker_en": os.getenv("HERO_KICKER_EN", "Personal Publishing"),
    "hero_title_secondary": os.getenv("HERO_TITLE_SECONDARY", ""),
    "hero_title_en": os.getenv("HERO_TITLE_EN", os.getenv("SITE_NAME", "Personal Site")),
    "hero_copy_secondary": os.getenv("HERO_COPY_SECONDARY", ""),
    "hero_copy_en": os.getenv(
        "HERO_COPY_EN",
        "A personal publishing system for blog posts, notes, and content.",
    ),
    "social_linkedin_url": os.getenv("SOCIAL_LINKEDIN_URL", ""),
    "social_twitter_url": os.getenv("SOCIAL_TWITTER_URL", ""),
    "contact_email": os.getenv("CONTACT_EMAIL", ""),
    "hero_background_enabled": os.getenv("HERO_BACKGROUND_ENABLED", "0"),
    "hero_background_image_path": os.getenv("HERO_BACKGROUND_IMAGE_PATH", ""),
    "show_login_link": os.getenv("SHOW_LOGIN_LINK", "0"),
    "show_contact_link": os.getenv("SHOW_CONTACT_LINK", "1"),
    "show_about_link": os.getenv("SHOW_ABOUT_LINK", "1"),
    "contact_intro_secondary": os.getenv("CONTACT_INTRO_SECONDARY", ""),
    "contact_intro_en": os.getenv("CONTACT_INTRO_EN", ""),
    "contact_details_secondary": os.getenv("CONTACT_DETAILS_SECONDARY", ""),
    "contact_details_en": os.getenv("CONTACT_DETAILS_EN", ""),
    "color_nav": os.getenv("COLOR_NAV", "#07468d"),
    "color_nav_hover": os.getenv("COLOR_NAV_HOVER", "#b95f3a"),
    "color_nav_active": os.getenv("COLOR_NAV_ACTIVE", "#07468d"),
    "color_feature_bg": os.getenv("COLOR_FEATURE_BG", "#f1c83a"),
    "color_feature_text": os.getenv("COLOR_FEATURE_TEXT", "#1d0303"),
    "color_feature_border": os.getenv("COLOR_FEATURE_BORDER", "#d9a900"),
    "color_accent_primary": os.getenv("COLOR_ACCENT_PRIMARY", "#2563eb"),
    "color_accent_secondary": os.getenv("COLOR_ACCENT_SECONDARY", "#b95f3a"),
    "color_separator_1": os.getenv("COLOR_SEPARATOR_1", "#b95f3a"),
    "color_separator_2": os.getenv("COLOR_SEPARATOR_2", "#07468d"),
    "color_separator_3": os.getenv("COLOR_SEPARATOR_3", "#f1c83a"),
}


SOCIAL_PLATFORMS = (
    ("linkedin", "LinkedIn"), ("twitter", "X / Twitter"),
    ("github", "GitHub"), ("orcid", "ORCID"),
    ("google_scholar", "Google Scholar"), ("researchgate", "ResearchGate"),
    ("bluesky", "Bluesky"), ("mastodon", "Mastodon"),
    ("youtube", "YouTube"), ("instagram", "Instagram"), ("facebook", "Facebook"),
)
for platform, _ in SOCIAL_PLATFORMS:
    DEFAULT_SITE_SETTINGS.setdefault(f"social_{platform}_url", "")
    DEFAULT_SITE_SETTINGS[f"social_{platform}_visible"] = "1" if platform in {"linkedin", "twitter"} else "0"
DEFAULT_SITE_SETTINGS.update({
    "secondary_language": "", "secondary_language_code": "", "secondary_language_name": "",
    "show_language_switcher": "1",
    "color_page_bg": "#f7f8f5",
    "color_footer_bg": "#e9f0ed",
    "color_footer_text": "#5d6864",
    "color_footer_border": "#182b231f",
    "footer_text_secondary": "", "footer_text_en": "", "show_footer": "1",
    # Homepage feature strip
    "show_feature_strip": "1",
    "show_feature_blog": "1",
    "show_feature_notes": "1",
    "show_feature_contact": "1",
    "feature_blog_desc_en": "Essays, articles, and long-form thoughts.",
    "feature_blog_desc_secondary": "",
    "feature_notes_desc_en": "Short observations, links, and ideas.",
    "feature_notes_desc_secondary": "",
    "feature_contact_desc_en": "Get in touch or start a conversation.",
    "feature_contact_desc_secondary": "",
    # Featured content
    "show_featured_post": "0",
    "featured_post_id": "",
    "show_featured_image": "1",
    # Latest writing & notes
    "show_latest_writing": "1",
    "latest_writing_category": "blog",
    "latest_writing_count": "4",
    "show_latest_notes": "1",
    "latest_notes_category": "notlar",
    "latest_notes_count": "5",
    # Layout and empty behavior
    "homepage_layout": "editorial_split",
    "homepage_mode": "custom",
    "category_cards_json": "{}",
    "custom_home_en": "",
    "custom_home_secondary": "",
    "show_empty_placeholders": "0",
    # Homepage category modules (JSON string format or comma-separated: [{"slug": "...", "enabled": "1", "count": "3"}])
    "homepage_categories_json": "[]",
    # About Page (block builder)
    "enable_about_page": "0",
    "about_page_en": "",
    "about_page_secondary": "",
})
