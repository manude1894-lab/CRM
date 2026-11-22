"""Each desk signs in, sees its own menu and dashboard, opens every page it has without a crash or a server
error, and signs out (review 22-11-2026, package 6)."""
import pytest

from conftest import sign_in

DEMO = "Demo-2026-pass"
COMMON = ["Dashboard", "Reports"]
ROLES = {
    "kalyan@asktriam.com": dict(
        menu=["Prospects", "New Client Onboarding", "Client Data Maintenance", "Call Reports / Contact Notes",
              "Service Requests", "Invoices"], not_menu=["Compliance Approval", "Admin"],
        tiles=["Clients being prepared", "Awaiting approval", "Approved & active clients", "Open service requests"]),
    "mlro@asktriam.com": dict(
        menu=["Compliance Approval", "Client Data Maintenance"], not_menu=["Admin"],
        tiles=["Awaiting Compliance", "AML reviews due"]),
    "approver@asktriam.com": dict(
        menu=["Compliance Approval", "Client Data Maintenance"], not_menu=["Admin", "Invoices"],
        tiles=["Awaiting final approval", "Awaiting Compliance"]),
    "accounts@asktriam.com": dict(
        menu=["Invoices", "Service Requests"], not_menu=["Compliance Approval", "Admin"],
        tiles=["Invoices to raise", "Overdue invoices", "Unpaid invoices"]),
    "priya@asktriam.com": dict(
        menu=["Prospects"], not_menu=["New Client Onboarding", "Compliance Approval", "Admin"],
        tiles=["Prospects to assign", "Open prospects"]),
    "inquiry@asktriam.com": dict(
        menu=["Compliance Approval", "Invoices"], not_menu=["Admin"],
        tiles=["Open prospects", "Unpaid invoices", "AML reviews due"]),
}


def menu_items(pg):
    return [t.strip() for t in pg.locator("aside nav button, aside nav a").all_inner_texts() if t.strip()]


@pytest.mark.parametrize("email", list(ROLES))
def test_each_desk_sees_its_menu_tiles_and_pages(page, email):
    want = ROLES[email]
    sign_in(page, email, DEMO)
    items = menu_items(page)
    for label in COMMON + want["menu"]:
        assert label in items, f"{email}: {label} missing from {items}"
    for label in want["not_menu"]:
        assert label not in items, f"{email}: should not see {label}"
    tiles = page.locator("div.grid.grid-cols-2 > *").all_inner_texts()
    for label in want["tiles"]:
        assert any(t.startswith(label) for t in tiles), f"{email}: tile {label} missing from {tiles}"
    for label in items:
        page.locator("aside nav").get_by_text(label, exact=True).first.click()
        page.wait_for_load_state("networkidle")
        assert page.get_by_text("This page couldn't load").count() == 0, f"{email}: {label} crashed"
    assert page.problems == [], f"{email}: {page.problems}"


def test_admin_opens_every_page_including_admin(page):
    sign_in(page, "admin@ezeetechgroup.com", "admin123")
    items = menu_items(page)
    assert "Admin" in items and len(page.locator("div.grid.grid-cols-2 > *").all_inner_texts()) >= 8
    for label in items:
        page.locator("aside nav").get_by_text(label, exact=True).first.click()
        page.wait_for_load_state("networkidle")
        assert page.get_by_text("This page couldn't load").count() == 0, f"admin: {label} crashed"
    assert page.problems == [], page.problems


def test_signing_out_returns_to_sign_in(page):
    sign_in(page, "kalyan@asktriam.com", DEMO)
    page.locator("header").get_by_text("Kalyan", exact=True).first.click()
    page.get_by_text("Sign out", exact=True).first.click()
    page.locator("input[type=email]").wait_for()
    assert page.problems == []
