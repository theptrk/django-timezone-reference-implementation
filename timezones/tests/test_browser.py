"""Optional: uv sync --group browser && uv run playwright install chromium."""

import pytest
from django.core.management import call_command

playwright = pytest.importorskip("playwright.sync_api")


def choose_timezone(page, label, value):
    picker = page.get_by_role("combobox", name=label)
    picker.locator("..").click()
    picker.fill(value or "Use actual browser timezone")
    page.locator(f'.ts-dropdown:visible [data-value="{value}"]').click()


@pytest.fixture
def browser_page(live_server):
    call_command("setup_demo")
    with playwright.sync_playwright() as engine:
        browser = engine.chromium.launch()
        context = browser.new_context(base_url=live_server.url, timezone_id="Asia/Tokyo")
        page = context.new_page()
        page.goto(live_server.url + "/accounts/login/")
        page.get_by_label("Username").fill("demouser")
        page.get_by_label("Password").fill("demopassword")
        page.get_by_role("button", name="Sign in").click()
        playwright.expect(page.locator("#detection-status")).to_contain_text("Detected Asia/Tokyo")
        yield page
        browser.close()


@pytest.mark.django_db(transaction=True)
def test_profile_save_updates_examples_and_accepts_simulation(browser_page):
    page = browser_page
    winter = page.get_by_role("row").filter(has_text="Winter standup")
    summer = page.get_by_role("row").filter(has_text="Summer standup")
    playwright.expect(winter.locator(".event-local")).to_contain_text("12:00:00")
    playwright.expect(summer.locator(".event-local")).to_contain_text("13:00:00")
    stored = page.locator(".event-utc").all_text_contents()
    choose_timezone(page, "Account timezone", "America/Los_Angeles")
    page.get_by_role("button", name="Save timezone", exact=True).click()
    playwright.expect(winter.locator(".event-local")).to_contain_text("09:00:00")
    playwright.expect(summer.locator(".event-local")).to_contain_text("10:00:00")
    choose_timezone(page, "Simulated browser timezone", "America/Los_Angeles")
    playwright.expect(page.locator("#detection-status")).to_contain_text(
        "Detected America/Los_Angeles"
    )
    choose_timezone(page, "Simulated browser timezone", "Asia/Tokyo")
    playwright.expect(page.locator("#timezone-dialog")).to_be_visible()
    page.get_by_role("button", name="Set to Asia/Tokyo").click()
    playwright.expect(page.locator(".zone strong")).to_have_text("Asia/Tokyo")
    assert page.locator(".event-utc").all_text_contents() == stored
    playwright.expect(page.locator("#timezone-dialog")).not_to_be_visible()
    playwright.expect(page.locator("#actual-browser-zone")).to_have_text("Asia/Tokyo")


@pytest.mark.django_db(transaction=True)
def test_dismissed_transition_is_not_repeated_after_reload(browser_page):
    page = browser_page
    choose_timezone(
        page, "Simulated browser timezone", "America/New_York"
    )  # Saved zone: no need for a suggestion.
    playwright.expect(page.locator("#detection-status")).to_contain_text(
        "Detected America/New_York"
    )
    choose_timezone(page, "Simulated browser timezone", "America/Los_Angeles")
    playwright.expect(page.locator("#timezone-dialog")).to_be_visible()
    page.get_by_role("button", name="Keep my timezone").click()
    playwright.expect(page.locator("#detection-status")).to_contain_text("Kept America/New_York")
    page.reload()
    playwright.expect(page.locator("#detection-status")).to_contain_text(
        "Detected America/Los_Angeles"
    )
    playwright.expect(page.locator("#timezone-dialog")).not_to_be_visible()
    choose_timezone(page, "Simulated browser timezone", "America/New_York")
    playwright.expect(page.locator("#detection-status")).to_contain_text(
        "Detected America/New_York"
    )
    choose_timezone(page, "Simulated browser timezone", "America/Los_Angeles")
    playwright.expect(page.locator("#detection-status")).to_contain_text(
        "Detected America/Los_Angeles"
    )
    playwright.expect(page.locator("#timezone-dialog")).not_to_be_visible()
    playwright.expect(page.locator(".zone strong")).to_have_text("America/New_York")
    choose_timezone(page, "Simulated browser timezone", "Europe/London")
    playwright.expect(page.locator("#timezone-dialog")).to_be_visible()
    page.keyboard.press("Escape")
    playwright.expect(page.locator("#timezone-dialog")).not_to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_anonymous_inspector_has_no_writes(live_server):
    with playwright.sync_playwright() as engine:
        browser = engine.chromium.launch()
        context = browser.new_context(timezone_id="Asia/Kathmandu")
        page = context.new_page()
        requests = []
        page.on("request", lambda request: requests.append((request.method, request.url)))
        page.goto(live_server.url)
        assert page.locator("#browser-zone").inner_text() in {"Asia/Kathmandu", "Asia/Katmandu"}
        playwright.expect(page.locator("#browser-offset")).to_have_text("UTC+05:45")
        playwright.expect(page.locator("#browser-time")).not_to_contain_text("Waiting")
        playwright.expect(page.locator(".world-clock time")).to_have_count(12)
        before_tick = page.locator("#local-clock").get_attribute("datetime")
        page.wait_for_function(
            "previous => document.querySelector('#local-clock').dateTime !== previous",
            arg=before_tick,
        )
        # All clocks derive from one instant, even across date and offset differences.
        assert page.locator(".world-clock time").evaluate_all(
            "clocks => clocks.every(clock => clock.dateTime === "
            "document.querySelector('#local-clock').dateTime)"
        )
        assert not context.cookies()
        assert page.evaluate("localStorage.length + sessionStorage.length") == 0
        assert all(method == "GET" for method, url in requests)
        assert not any("device-timezone" in url for method, url in requests)
        assert page.url.rstrip("/") == live_server.url
        browser.close()


@pytest.mark.django_db(transaction=True)
def test_picker_search_keyboard_and_invalid_text(browser_page):
    page = browser_page
    picker = page.get_by_role("combobox", name="Account timezone")
    picker.locator("..").click()
    first = page.locator(".ts-dropdown:visible .optgroup-header").first
    playwright.expect(first).to_have_text("United States — main regions")
    # Country search is supplied by tzdata metadata, beyond the displayed IANA identifier.
    picker.fill("Japan")
    option = page.locator('.ts-dropdown:visible [data-value="Asia/Tokyo"]')
    playwright.expect(option).to_be_visible()
    playwright.expect(
        page.locator('.ts-dropdown:visible [data-value="America/New_York"]')
    ).not_to_be_visible()
    playwright.expect(option).to_be_visible()
    picker.fill("Asia/Tokyo")
    playwright.expect(page.locator(".ts-dropdown:visible .option")).to_have_count(1)
    playwright.expect(option).to_be_visible()
    picker.press("Enter")
    playwright.expect(page.locator("#id_display_timezone")).to_have_value("Asia/Tokyo")
    page.get_by_role("button", name="Save timezone", exact=True).click()
    playwright.expect(page.locator(".zone strong")).to_have_text("Asia/Tokyo")
    picker.locator("..").click()
    picker.fill("No such timezone 12345")
    playwright.expect(page.locator(".ts-dropdown:visible .no-results")).to_be_visible()
    picker.press("Escape")
    playwright.expect(page.locator("#id_display_timezone")).to_have_value("Asia/Tokyo")
    # The empty-valued "actual browser" option is a legitimate simulator choice.
    choose_timezone(page, "Simulated browser timezone", "Asia/Tokyo")
    playwright.expect(page.locator("#detection-status")).to_contain_text("Detected Asia/Tokyo")
    choose_timezone(page, "Simulated browser timezone", "")
    playwright.expect(page.locator("#detected-zone")).to_have_text("Asia/Tokyo (browser)")
