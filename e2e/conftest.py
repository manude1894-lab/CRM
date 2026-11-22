"""Browser tests per role (review 22-11-2026, package 6). They run against a running CRM with the demo users
(`python -m app.seed`) - in CI on a fresh database, locally against your own. Never point them at UAT or production.

    E2E_APP_URL   the frontend (default http://localhost:5173)
"""
import os

import pytest
from playwright.sync_api import sync_playwright

APP_URL = os.environ.get("E2E_APP_URL", "http://localhost:5173").rstrip("/")
assert "railway.app" not in APP_URL, "browser tests run on a local or CI copy only"


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.problems = []  # crashes in the page and server errors, checked by every test
    pg.on("pageerror", lambda e: pg.problems.append(f"page error: {e}"))
    pg.on("response", lambda r: r.status >= 500 and pg.problems.append(f"{r.status} {r.request.method} {r.url}"))
    yield pg
    ctx.close()


def sign_in(pg, email, password):
    pg.goto(APP_URL)
    pg.fill("input[type=email]", email)
    pg.fill("input[type=password]", password)
    pg.keyboard.press("Enter")
    pg.locator("aside nav").wait_for()
    pg.wait_for_load_state("networkidle")
