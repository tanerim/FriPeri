"""Public category archive rendering and card-option regressions."""
import sqlite3

from test_integration_flows import site  # noqa: F401


def _category(db):
    with sqlite3.connect(db) as conn:
        return conn.execute("SELECT id, slug FROM categories ORDER BY id LIMIT 1").fetchone()


def test_archive_renders_text_first_articles_without_numeric_placeholders(site):
    client, db = site
    category_id, slug = _category(db)
    with sqlite3.connect(db) as conn:
        conn.execute("""
            INSERT INTO posts (title, slug, excerpt, body, body_html, category_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'published', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, ("An article without a cover", "without-cover", "An informative summary", "Body", "<p>Body</p>", category_id))
    response = client.get(f"/category/{slug}")
    assert response.status_code == 200
    assert 'category-archive.css' in response.text
    assert 'category-publication-header' in response.text
    assert 'category-publication-card no-image' in response.text
    assert 'An article without a cover' in response.text
    assert 'An informative summary' in response.text
    assert 'href="/posts/without-cover"' in response.text
    assert 'post-cover-placeholder' not in response.text
    assert 'category-publication-image' not in response.text


def test_archive_only_lists_published_posts(site):
    client, db = site
    category_id, slug = _category(db)
    with sqlite3.connect(db) as conn:
        for name, status in (("Visible article", "published"), ("Private draft", "draft")):
            conn.execute("""
                INSERT INTO posts (title, slug, excerpt, body, body_html, category_id, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (name, name.lower().replace(" ", "-"), "Description", "Body", "<p>Body</p>", category_id, status))
    response = client.get(f"/category/{slug}")
    assert response.status_code == 200
    assert "Visible article" in response.text
    assert "Private draft" not in response.text


def test_archive_empty_state_preserves_category_heading(site):
    client, db = site
    _, slug = _category(db)
    response = client.get(f"/category/{slug}")
    assert response.status_code == 200
    assert 'id="category-title"' in response.text
    assert 'category-publication-empty' in response.text
