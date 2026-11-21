"""Optional local browser smoke tests. Never run against a production instance.

Set FRIPERI_TEST_BASE_URL to an isolated local FriPeri instance and provide a
test administrator login. The test never creates or modifies content.
"""
import os
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("FRIPERI_TEST_BASE_URL"),
    reason="Set FRIPERI_TEST_BASE_URL for optional local browser smoke tests",
)


@pytest.fixture(params=["chromium", "firefox"])
def admin_page(request):
    from playwright.sync_api import sync_playwright
    base = os.environ["FRIPERI_TEST_BASE_URL"].rstrip("/")
    host = urlparse(base).hostname
    if host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("Browser smoke tests are restricted to localhost")
    username = os.getenv("FRIPERI_TEST_USER")
    password = os.getenv("FRIPERI_TEST_PASSWORD")
    if not username or not password:
        pytest.skip("Local test credentials not supplied")
    with sync_playwright() as playwright:
        browser = getattr(playwright, request.param).launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(base + "/login")
        page.locator('input[name="username"]').fill(username)
        page.locator('input[name="password"]').fill(password)
        page.locator('button[type="submit"]').click()
        page.wait_for_url("**/admin")
        yield page, context, base
        browser.close()


def test_sidebar_toggle_and_documentation(admin_page):
    page, context, base = admin_page
    page.goto(base + "/admin/documentation")
    assert page.locator(".documentation-list a").count() > 0
    assert page.locator(".documentation-prose h1").count() > 0
    arrow = page.locator(".admin-sidebar-toggle")
    logo = page.locator(".admin-brand-logo")
    assert arrow.bounding_box()["y"] < logo.bounding_box()["y"]
    arrow.click()
    assert page.locator("body").evaluate("(el) => el.classList.contains('admin-sidebar-collapsed')")
    page.reload()
    assert page.locator("body").evaluate("(el) => el.classList.contains('admin-sidebar-collapsed')")
    page.locator(".admin-sidebar-toggle").click()


def test_responsive_docs_and_design_without_shortcuts(admin_page):
    page, context, base = admin_page
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(base + "/admin/documentation")
    assert page.locator(".documentation-article").is_visible()
    assert page.locator(".documentation-list").is_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2")
    page.goto(base + "/admin/design")
    assert page.locator(".design-color-section").count() > 0
    assert page.locator(".settings-section-nav").count() == 0
