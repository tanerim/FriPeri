"""Post detail layout regression tests against temporary SQLite data."""
import sqlite3

from test_integration_flows import site  # noqa: F401


def test_post_detail_uses_wide_reading_layout(site):
    client, db = site
    with sqlite3.connect(db) as conn:
        conn.execute("""
            INSERT INTO posts (title, slug, excerpt, body, body_html, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'published', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, ("Long research article", "long-research-article",
              "A research overview", "Article body",
              "<p>A long text paragraph for reading.</p>"))
    response = client.get("/posts/long-research-article")
    assert response.status_code == 200
    assert "article-detail.css" in response.text
    assert 'class="page article-detail-page"' in response.text
    assert 'class="article article-detail"' in response.text
    assert 'class="article-body article-detail-body"' in response.text
    assert 'id="article-title"' in response.text
    assert "Long research article" in response.text
    assert "A long text paragraph for reading." in response.text
    assert 'class="article-detail-cover"' not in response.text


def test_post_detail_preserves_cover_and_post_link(site):
    client, db = site
    with sqlite3.connect(db) as conn:
        conn.execute("""
            INSERT INTO posts (title, slug, excerpt, body, body_html, status,
                               image_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'published', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, ("Illustrated article", "illustrated-article", "Summary", "Body",
              "<p>Text</p>", "/static/images/FriPeri_Logo.png"))
    response = client.get("/posts/illustrated-article")
    assert response.status_code == 200
    assert 'class="article-detail-cover"' in response.text
    assert "/static/images/FriPeri_Logo.png" in response.text
    assert "Text" in response.text


def test_wide_editor_block_retains_width_class_and_article_override(site):
    """A saved Wide block must render full-width inside the article, not as a centered column."""
    import json
    from pathlib import Path

    client, db = site
    blocks = [
        {"type": "text", "tone": "plain", "align": "left", "width": "wide",
         "html": "<p>Wide published block</p>"},
        {"type": "text", "tone": "plain", "align": "left", "width": "normal",
         "html": "<p>Normal published block</p>"},
    ]
    with sqlite3.connect(db) as conn:
        conn.execute("""
            INSERT INTO posts (title, slug, excerpt, body, body_html, post_blocks_json,
                               status, created_at, updated_at)
            VALUES (?, ?, ?, '', '', ?, 'published', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, ("Block layout", "block-layout", "Summary", json.dumps({"en": blocks})))
    response = client.get("/posts/block-layout")
    assert response.status_code == 200
    assert "custom-text tone-plain align-left width-wide" in response.text
    assert "custom-text tone-plain align-left width-normal" in response.text
    assert "Wide published block" in response.text
    css = (Path(__file__).resolve().parents[1] / "static/article-detail.css").read_text(encoding="utf-8")
    assert ".article-detail-body > .custom-block.width-wide" in css
    assert ".article-detail-body > .custom-block.width-normal" in css
    assert "margin-left: 0;" in css
