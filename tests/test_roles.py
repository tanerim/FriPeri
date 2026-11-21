"""Role and category permission integration tests; use only disposable SQLite data."""
import sqlite3

from initialization import hash_password
from test_integration_flows import site, sign_in  # noqa: F401
import main


def _make_user(db, name, role="cc", categories=()):
    salt, secret = hash_password("writer-password-2026")
    with sqlite3.connect(db) as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_salt, password_hash, role, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, salt, secret, role, "2026-11-22T00:00:00"))
        uid = cursor.lastrowid
        conn.executemany(
            "INSERT INTO user_categories (user_id, category_id) VALUES (?, ?)",
            [(uid, cid) for cid in categories])
    return uid


def _as(client, name):
    client.cookies.clear()
    result = client.post("/login", data={"username": name, "password": "writer-password-2026"})
    assert result.status_code == 303


def _create_post(client, title, category):
    return client.post("/admin/posts/new", data={
        "title_en": title, "excerpt_en": "A user permission test",
        "body_html_en": "<p>Test body</p>", "status": "draft",
        "category_id": str(category),
    })


def test_migration_keeps_legacy_admin_and_new_creator_columns(site):
    client, db = site
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT role FROM users WHERE username='admin'").fetchone()[0] == "admin"
        assert "author_id" in [row[1] for row in conn.execute("PRAGMA table_info(posts)")]
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='user_categories'").fetchone()
    sign_in(client)
    assert client.get("/admin/users").status_code == 200


def test_creator_cannot_manage_site_or_edit_other_posts(site):
    client, db = site
    with sqlite3.connect(db) as conn:
        cats = [row[0] for row in conn.execute("SELECT id FROM categories ORDER BY id LIMIT 2")]
    assert len(cats) == 2
    uid = _make_user(db, "writer", categories=[cats[0]])
    _make_user(db, "writer2", categories=[cats[0]])
    _as(client, "writer")
    assert client.get("/admin/users").status_code == 403
    assert client.get("/admin/settings").status_code == 403
    assert client.get("/admin/pages").status_code == 403
    assert client.post("/admin/backup/create").status_code == 403
    assert _create_post(client, "Allowed content", cats[0]).status_code == 303
    assert _create_post(client, "Denied category", cats[1]).status_code == 403
    with sqlite3.connect(db) as conn:
        post = conn.execute("SELECT id, author_id FROM posts WHERE title='Allowed content'").fetchone()
    assert post and post[1] == uid
    assert client.get(f"/admin/posts/{post[0]}/edit").status_code == 200
    assert client.post(f"/admin/posts/{post[0]}/delete").status_code == 403
    _as(client, "writer2")
    assert client.get(f"/admin/posts/{post[0]}/edit").status_code == 403
    assert client.post(f"/admin/posts/{post[0]}/edit", data={
        "title_en": "Hijack", "excerpt_en": "No", "body_html_en": "<p>Attack</p>",
        "category_id": str(cats[0])}).status_code == 403
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT title FROM posts WHERE id=?", (post[0],)).fetchone()[0] == "Allowed content"


def test_creator_category_creation_grants_only_new_category(site):
    client, db = site
    uid = _make_user(db, "writer")
    _as(client, "writer")
    assert client.post("/admin/categories", data={"name": "Blog"}).status_code == 303
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM user_categories WHERE user_id=?", (uid,)).fetchone()[0] == 0
    assert client.post("/admin/categories", data={"name": "Writer own category"}).status_code == 303
    with sqlite3.connect(db) as conn:
        cid = conn.execute("SELECT id FROM categories WHERE name='Writer own category'").fetchone()[0]
        assert conn.execute("SELECT 1 FROM user_categories WHERE user_id=? AND category_id=?", (uid, cid)).fetchone()


def test_editor_can_manage_content_but_not_site_users(site):
    client, db = site
    _make_user(db, "ed", "editor")
    _as(client, "ed")
    assert client.get("/admin/pages").status_code == 200
    assert client.get("/admin/posts").status_code == 200
    assert client.get("/admin/users").status_code == 200
    assert client.get("/admin/backup").status_code == 403
    assert client.post("/admin/settings", data={}).status_code == 403


def test_admin_account_creation_and_last_admin_guards(site):
    client, db = site
    sign_in(client)
    token = main.custom_home_token("admin")
    created = client.post("/admin/users", data={
        "editor_token": token, "username": "newwriter",
        "password": "very-strong-password", "role": "cc",
    })
    assert created.status_code == 303
    with sqlite3.connect(db) as conn:
        new_id = conn.execute("SELECT id FROM users WHERE username='newwriter'").fetchone()[0]
        admin_id = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
    assert client.post(f"/admin/users/{admin_id}", data={
        "editor_token": token, "role": "cc"}).status_code == 403
    assert client.post(f"/admin/users/{admin_id}/delete", data={"editor_token": token}).status_code == 403
    assert client.post(f"/admin/users/{new_id}/delete", data={"editor_token": token}).status_code == 303
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT 1 FROM users WHERE id=?", (new_id,)).fetchone() is None


def test_editor_can_edit_category_metadata_but_not_site_menu(site):
    client, db = site
    _make_user(db, "ed", "editor")
    _as(client, "ed")
    with sqlite3.connect(db) as conn:
        cid = conn.execute("SELECT id FROM categories ORDER BY id LIMIT 1").fetchone()[0]
    assert client.get(f"/admin/categories/{cid}/edit").status_code == 200
    saved = client.post(f"/admin/categories/{cid}/edit", data={
        "editor_token": main.custom_home_token("ed"),
        "name": "Edited category", "description": "Editor updated",
    })
    assert saved.status_code == 303
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT description FROM categories WHERE id=?", (cid,)).fetchone()[0] == "Editor updated"
    assert client.get("/admin/menu").status_code == 403


def test_changed_role_invalidates_existing_session(site):
    client, db = site
    uid = _make_user(db, "writer")
    _as(client, "writer")
    old_session = client.cookies.get(main.SESSION_COOKIE)
    assert client.get("/admin").status_code == 200
    client.cookies.clear()
    sign_in(client)
    response = client.post(f"/admin/users/{uid}", data={
        "editor_token": main.custom_home_token("admin"),
        "role": "editor",
    })
    assert response.status_code == 303
    client.cookies.clear()
    client.cookies.set(main.SESSION_COOKIE, old_session)
    assert client.get("/admin").status_code == 303


def test_block_editor_enforces_creator_categories_and_ownership(site):
    client, db = site
    with sqlite3.connect(db) as conn:
        cats = [row[0] for row in conn.execute("SELECT id FROM categories ORDER BY id LIMIT 2")]
    assert len(cats) == 2
    _make_user(db, "writer", categories=[cats[0]])
    _make_user(db, "writer2", categories=[cats[0]])
    _as(client, "writer")
    form = {
        "title_en": "Visual builder author",
        "excerpt_en": "Creator-owned document",
        "category_id": str(cats[0]),
        "status": "draft",
        "post_en": "[]",
        "editor_token": main.custom_home_token("writer"),
        "creation_key": "a" * 32,
    }
    created = client.post("/admin/posts/new", data=form)
    assert created.status_code == 200, created.text
    pid = int(created.json()["endpoint"].split("/")[3])
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT author_id FROM posts WHERE id=?", (pid,)).fetchone()[0] is not None
    denied = client.post("/admin/posts/new", data={
        **form, "title_en": "Wrong category", "category_id": str(cats[1]),
        "creation_key": "b" * 32,
    })
    assert denied.status_code == 403
    _as(client, "writer2")
    assert client.post(f"/admin/posts/{pid}/edit", data={
        **form, "editor_token": main.custom_home_token("writer2"),
    }).status_code == 403



def test_editor_sign_in_lands_in_content_workspace(site):
    client, db = site
    _make_user(db, "another_editor", role="editor")
    client.cookies.clear()
    response = client.post("/login", data={
        "username": "another_editor", "password": "writer-password-2026",
    })
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/posts"
    page = client.get("/admin/posts")
    assert page.status_code == 200
    assert "another_editor" in page.text
    assert client.get("/admin/pages").status_code == 200
    assert client.get("/admin/users").status_code == 200


def test_creator_publishes_to_category_just_created(site):
    client, db = site
    _make_user(db, "category_writer")
    _as(client, "category_writer")
    response = client.post("/admin/categories", data={"name": "Author's own category"})
    assert response.status_code == 303
    with sqlite3.connect(db) as conn:
        cat = conn.execute("SELECT id FROM categories WHERE name=?", ("Author's own category",)).fetchone()[0]
        assert conn.execute(
            "SELECT COUNT(*) FROM user_categories WHERE category_id=?",
            (cat,)
        ).fetchone()[0] == 1
    editor = client.get("/admin/posts/new")
    assert editor.status_code == 200
    assert f'value="{cat}"' in editor.text
    payload = {
        "editor_token": main.custom_home_token("category_writer"),
        "title_en": "Published from own category",
        "excerpt_en": "Description",
        "category_id": str(cat),
        "status": "published",
        "post_en": "[]",
        "creation_key": "c" * 32,
    }
    save = client.post("/admin/posts/new", data=payload)
    assert save.status_code == 200, save.text
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT category_id, status, author_id FROM posts WHERE title=?",
            ("Published from own category",)
        ).fetchone()
    assert row is not None
    assert row[0] == cat
    assert row[1] == "published"


def test_admin_post_form_exposes_separate_publish_and_draft(site):
    client, _ = site
    sign_in(client)
    page = client.get("/admin/posts/new")
    assert page.status_code == 200
    assert 'id="builder-save-draft"' in page.text
    assert 'id="builder-save"' in page.text
    assert 'value="published"' in page.text


def test_creator_cannot_view_another_creator_draft(site):
    client, db = site
    with sqlite3.connect(db) as conn:
        cat = conn.execute("SELECT id FROM categories ORDER BY id LIMIT 1").fetchone()[0]
    _make_user(db, "draft_author", categories=[cat])
    _make_user(db, "draft_other", categories=[cat])
    _as(client, "draft_author")
    result = _create_post(client, "Private creator draft", cat)
    assert result.status_code == 303
    with sqlite3.connect(db) as conn:
        slug = conn.execute("SELECT slug FROM posts WHERE title=?", ("Private creator draft",)).fetchone()[0]
    assert client.get(f"/posts/{slug}").status_code == 200
    _as(client, "draft_other")
    assert client.get(f"/posts/{slug}").status_code == 404


def test_editor_dashboard_documentation_and_footer_identity(site):
    client, db = site
    _make_user(db, "the_editor", role="editor")
    _as(client, "the_editor")
    for url in ("/admin", "/admin/documentation"):
        response = client.get(url)
        assert response.status_code == 200, (url, response.text[:300])
    # Trailing-slash requests must not fail with insufficient permissions.
    for url in ("/admin/", "/admin/documentation/"):
        response = client.get(url)
        assert response.status_code in (200, 307, 308), (url, response.status_code)
    page = client.get("/admin")
    assert 'class="admin-current-username">the_editor</span>' in page.text
    assert 'class="admin-current-role">Editor</span>' in page.text


def test_editor_can_assign_categories_to_cc_only(site):
    client, db = site
    with sqlite3.connect(db) as conn:
        cats = [row[0] for row in conn.execute("SELECT id FROM categories ORDER BY id LIMIT 2")]
        admin_id = conn.execute("SELECT id FROM users WHERE role='admin' LIMIT 1").fetchone()[0]
    assert len(cats) == 2
    cc_id = _make_user(db, "writer_grants", categories=[cats[0]])
    ed_id = _make_user(db, "grant_editor", role="editor")
    _as(client, "grant_editor")
    page = client.get("/admin/users")
    assert page.status_code == 200
    assert "writer_grants" in page.text
    assert '<span class="users-account-name"><strong>grant_editor</strong>' not in page.text
    assert 'name="role"' not in page.text
    assert 'name="password"' not in page.text
    token = main.custom_home_token("grant_editor")
    response = client.post(f"/admin/users/{cc_id}/categories", data={
        "editor_token": token, "categories": str(cats[1]),
    })
    assert response.status_code == 303, response.text[:300]
    with sqlite3.connect(db) as conn:
        ids = [row[0] for row in conn.execute(
            "SELECT category_id FROM user_categories WHERE user_id=?", (cc_id,))]
    assert ids == [cats[1]]
    assert client.post(f"/admin/users/{admin_id}/categories", data={
        "editor_token": token, "categories": str(cats[0]),
    }).status_code == 403
    assert client.post(f"/admin/users/{ed_id}/categories", data={
        "editor_token": token, "categories": str(cats[0]),
    }).status_code == 403
    assert client.post(f"/admin/users/{cc_id}", data={
        "editor_token": token, "role": "admin",
    }).status_code == 403
    assert client.post(f"/admin/users/{cc_id}/delete", data={
        "editor_token": token,
    }).status_code == 403
    assert client.post("/admin/users", data={
        "editor_token": token, "username": "newadmin",
        "password": "strong-password", "role": "admin",
    }).status_code == 403


def test_creator_cannot_assign_categories_to_other_users(site):
    client, db = site
    cc1 = _make_user(db, "writer_permissions")
    cc2 = _make_user(db, "other_permissions")
    _as(client, "writer_permissions")
    assert client.get("/admin/users").status_code == 403
    assert client.post(f"/admin/users/{cc2}/categories", data={
        "editor_token": main.custom_home_token("writer_permissions"),
    }).status_code == 403
