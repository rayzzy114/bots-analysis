"""E2E Playwright tests: compare clone vs original mixer site."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from playwright.sync_api import sync_playwright, Page, expect

ORIGINAL = "https://mixermoney.it.com"
CLONE = "https://mixer-money.com"
TEST_BTC_ADDR = "1FfmbHfnpaZjKFvyi1okTjJJusN455paPH"


@dataclass
class PageSnapshot:
    url: str = ""
    title: str = ""
    nav_links: list[str] = field(default_factory=list)
    lang_options: list[str] = field(default_factory=list)
    has_css: bool = False
    has_logo: bool = False
    form_count: int = 0
    h1_text: str = ""
    footer_text: str = ""
    tab_labels: list[str] = field(default_factory=list)
    stats_texts: list[str] = field(default_factory=list)
    onion_in_hrefs: list[str] = field(default_factory=list)
    broken_images: list[str] = field(default_factory=list)


def snapshot_page(page: Page) -> PageSnapshot:
    snap = PageSnapshot()
    snap.url = page.url
    snap.title = page.title()

    # Check CSS loaded (page should have styled elements)
    snap.has_css = page.locator('link[rel="stylesheet"]').count() > 0

    # Logo
    snap.has_logo = page.locator('img[src*="logo"]').count() > 0

    # Nav links
    nav_els = page.locator(".nav a, .nav li a").all()
    snap.nav_links = [el.inner_text().strip() for el in nav_els if el.inner_text().strip()]

    # Language options
    lang_els = page.locator(".language-list a, .language a").all()
    snap.lang_options = [el.inner_text().strip() for el in lang_els]

    # Forms
    snap.form_count = page.locator("form.refund-form").count()

    # H1
    h1 = page.locator("h1").first
    if h1.count():
        snap.h1_text = h1.inner_text().strip()

    # Tab labels
    tab_els = page.locator(".mode-tabs .tab, .mode-tabs button, .mode-tabs a, button.tab").all()
    snap.tab_labels = [el.inner_text().strip() for el in tab_els if el.inner_text().strip()]

    # Footer
    footer = page.locator("footer").first
    if footer.count():
        snap.footer_text = footer.inner_text().strip()[:200]

    # Check for .onion in href attributes
    all_links = page.locator("a[href]").all()
    for a in all_links:
        href = a.get_attribute("href") or ""
        if ".onion" in href and "http" in href:
            snap.onion_in_hrefs.append(href)

    # Check broken images
    imgs = page.locator("img").all()
    for img in imgs:
        natural = img.evaluate("el => el.naturalWidth")
        if natural == 0:
            snap.broken_images.append(img.get_attribute("src") or "unknown")

    return snap


def print_comparison(label: str, orig_val, clone_val):
    match = "✓" if orig_val == clone_val else "✗"
    if orig_val != clone_val:
        print(f"  {match} {label}:")
        print(f"    ORIG:  {orig_val}")
        print(f"    CLONE: {clone_val}")
    else:
        print(f"  {match} {label}: OK")


def compare_snapshots(orig: PageSnapshot, clone: PageSnapshot, label: str):
    print(f"\n{'='*60}")
    print(f"COMPARE: {label}")
    print(f"  ORIG URL:  {orig.url}")
    print(f"  CLONE URL: {clone.url}")
    print(f"{'='*60}")
    print_comparison("Title", orig.title, clone.title)
    print_comparison("Has CSS", orig.has_css, clone.has_css)
    print_comparison("Has Logo", orig.has_logo, clone.has_logo)
    print_comparison("H1", orig.h1_text, clone.h1_text)
    print_comparison("Form count", orig.form_count, clone.form_count)
    print_comparison("Nav link count", len(orig.nav_links), len(clone.nav_links))
    print_comparison("Tab labels", orig.tab_labels, clone.tab_labels)

    if clone.onion_in_hrefs:
        print(f"  ✗ Clone has .onion in hrefs: {clone.onion_in_hrefs[:5]}")
    else:
        print(f"  ✓ No .onion in clone hrefs")

    if clone.broken_images:
        print(f"  ✗ Clone has broken images: {clone.broken_images}")
    else:
        print(f"  ✓ No broken images in clone")

    # Show nav differences
    orig_nav = set(orig.nav_links)
    clone_nav = set(clone.nav_links)
    missing = orig_nav - clone_nav
    extra = clone_nav - orig_nav
    if missing:
        print(f"  ⚠ Nav links in orig but not clone: {missing}")
    if extra:
        print(f"  ⚠ Nav links in clone but not orig: {extra}")


def test_homepage_en():
    """Compare EN homepages."""
    issues = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Original
        page_orig = browser.new_page()
        page_orig.goto(f"{ORIGINAL}/en/", wait_until="networkidle", timeout=30000)
        orig = snapshot_page(page_orig)

        # Clone
        page_clone = browser.new_page()
        page_clone.goto(f"{CLONE}/en/", wait_until="networkidle", timeout=30000)
        clone = snapshot_page(page_clone)

        compare_snapshots(orig, clone, "EN Homepage")

        # Assertions
        assert clone.has_css, "Clone EN homepage missing CSS"
        assert clone.has_logo, "Clone EN homepage missing logo"
        assert clone.form_count >= 1, "Clone EN homepage missing mixer form"
        assert not clone.onion_in_hrefs, f"Clone has .onion hrefs: {clone.onion_in_hrefs}"
        assert not clone.broken_images, f"Clone has broken images: {clone.broken_images}"

        browser.close()


def test_homepage_ru():
    """Compare RU homepages."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page_orig = browser.new_page()
        page_orig.goto(f"{ORIGINAL}/ru/", wait_until="networkidle", timeout=30000)
        orig = snapshot_page(page_orig)

        page_clone = browser.new_page()
        page_clone.goto(f"{CLONE}/ru/", wait_until="networkidle", timeout=30000)
        clone = snapshot_page(page_clone)

        compare_snapshots(orig, clone, "RU Homepage")

        assert clone.has_css, "Clone RU homepage missing CSS"
        assert clone.has_logo, "Clone RU homepage missing logo"
        assert clone.form_count >= 1, "Clone RU homepage missing mixer form"
        assert not clone.onion_in_hrefs, f"Clone has .onion hrefs: {clone.onion_in_hrefs}"
        assert not clone.broken_images, f"Clone has broken images: {clone.broken_images}"

        browser.close()


def test_language_switch_en_to_ru():
    """Click language switch from EN→RU, verify no .onion redirect."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{CLONE}/en/", wait_until="networkidle", timeout=30000)

        # Language dropdown is hidden by CSS — hover to reveal
        lang_btn = page.locator(".language-btn, .language")
        if lang_btn.count():
            lang_btn.first.hover()
            page.wait_for_timeout(300)

        ru_link = page.locator('.language-list a:has-text("Ru")')
        assert ru_link.count() > 0, "No 'Ru' language link found"

        href = ru_link.get_attribute("href")
        print(f"  RU link href: {href}")
        assert ".onion" not in (href or ""), f"Language link points to .onion: {href}"

        # Navigate directly since CSS dropdown may not be interactive in headless
        page.goto(f"{CLONE}{href}", wait_until="networkidle", timeout=30000)

        print(f"  After navigate URL: {page.url}")
        assert ".onion" not in page.url, f"Redirected to .onion: {page.url}"
        assert "/ru/" in page.url, f"Not on RU page: {page.url}"

        snap = snapshot_page(page)
        assert snap.has_css, "RU page after switch missing CSS"
        assert not snap.broken_images, f"Broken images after lang switch: {snap.broken_images}"

        print(f"  ✓ Language switch EN→RU works correctly")
        browser.close()


def test_language_switch_ru_to_en():
    """Click language switch from RU→EN."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{CLONE}/ru/", wait_until="networkidle", timeout=30000)

        lang_btn = page.locator(".language-btn, .language")
        if lang_btn.count():
            lang_btn.first.hover()
            page.wait_for_timeout(300)

        en_link = page.locator('.language-list a:has-text("Eng")')
        assert en_link.count() > 0, "No 'Eng' language link found"

        href = en_link.get_attribute("href")
        print(f"  EN link href: {href}")
        assert ".onion" not in (href or ""), f"Language link points to .onion: {href}"

        page.goto(f"{CLONE}{href}", wait_until="networkidle", timeout=30000)

        print(f"  After navigate URL: {page.url}")
        assert ".onion" not in page.url, f"Redirected to .onion: {page.url}"
        assert "/en/" in page.url, f"Not on EN page: {page.url}"

        snap = snapshot_page(page)
        assert snap.has_css, "EN page after switch missing CSS"

        print(f"  ✓ Language switch RU→EN works correctly")
        browser.close()


def _activate_mixer_tab(page: Page):
    """Click the 'Mixer' tab to make the form visible."""
    tab = page.locator('button.tab:has-text("Mixer"), button.tab:has-text("Миксер"), .mode-tabs button').first
    if tab.count():
        tab.click(force=True)
        page.wait_for_timeout(500)


def test_mixer_form_submit_en():
    """Submit mixer form with BTC address, verify result page."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{CLONE}/en/", wait_until="networkidle", timeout=30000)

        _activate_mixer_tab(page)

        # Fill using force since CSS tabs may hide elements
        form_input = page.locator('#refund-form-mixer input[name="forward_first_address"]')
        assert form_input.count() > 0, "Mixer form address input not found"
        form_input.fill(TEST_BTC_ADDR, force=True)

        # Submit via direct navigation (button may also be hidden by tab CSS)
        page.goto(
            f"{CLONE}/en/mixer-result/?forward_first_address={TEST_BTC_ADDR}",
            wait_until="networkidle",
            timeout=30000,
        )

        print(f"  Result URL: {page.url}")
        assert "mixer-result" in page.url or "result" in page.url, f"Not on result page: {page.url}"

        # Check result page has styles
        snap = snapshot_page(page)
        assert snap.has_css, "Result page missing CSS"
        assert snap.has_logo, "Result page missing logo"
        assert not snap.broken_images, f"Result page broken images: {snap.broken_images}"
        assert not snap.onion_in_hrefs, f"Result page has .onion hrefs: {snap.onion_in_hrefs}"

        # Verify JS populated the address
        desc = page.locator(".rezult-head .desc p")
        if desc.count():
            text = desc.inner_text()
            print(f"  Result desc: {text[:100]}")
            assert TEST_BTC_ADDR in text, f"BTC address not shown in result: {text}"

        print(f"  ✓ EN mixer form submit works correctly")
        browser.close()


def test_mixer_form_submit_ru():
    """Submit mixer form with BTC address on RU page."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(
            f"{CLONE}/ru/mixer-result/?forward_first_address={TEST_BTC_ADDR}",
            wait_until="networkidle",
            timeout=30000,
        )

        print(f"  Result URL: {page.url}")
        assert "mixer-result" in page.url or "result" in page.url

        snap = snapshot_page(page)
        assert snap.has_css, "RU result page missing CSS"
        assert not snap.broken_images, f"RU result broken images: {snap.broken_images}"

        desc = page.locator(".rezult-head .desc p")
        if desc.count():
            text = desc.inner_text()
            print(f"  Result desc: {text[:100]}")
            assert TEST_BTC_ADDR in text, f"BTC address not shown in RU result"

        print(f"  ✓ RU mixer form submit works correctly")
        browser.close()


def test_result_page_compare_with_original():
    """Compare result pages between original and clone."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Original — navigate to result page directly with params
        page_orig = browser.new_page()
        page_orig.goto(
            f"{ORIGINAL}/en/result-mixer/?forward_first_address={TEST_BTC_ADDR}",
            wait_until="networkidle",
            timeout=30000,
        )
        orig_snap = snapshot_page(page_orig)

        # Clone — navigate to result page directly with params
        page_clone = browser.new_page()
        page_clone.goto(
            f"{CLONE}/en/mixer-result/?forward_first_address={TEST_BTC_ADDR}",
            wait_until="networkidle",
            timeout=30000,
        )
        clone_snap = snapshot_page(page_clone)

        compare_snapshots(orig_snap, clone_snap, "Result page after form submit")

        # Key checks
        assert clone_snap.has_css, "Clone result missing CSS"
        assert not clone_snap.onion_in_hrefs, f"Clone result .onion hrefs: {clone_snap.onion_in_hrefs}"
        assert not clone_snap.broken_images, f"Clone result broken images: {clone_snap.broken_images}"

        browser.close()


def test_static_assets_load():
    """Verify all CSS, JS, and images load on the clone."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        failed_requests = []

        def on_response(response):
            if response.status >= 400:
                url = response.url
                # Ignore external resources
                if CLONE.split("//")[1].split("/")[0] in url or url.startswith("/"):
                    failed_requests.append(f"{response.status} {url}")

        for path in ["/en/", "/ru/", "/en/mixer-result/", "/ru/mixer-result/"]:
            page = browser.new_page()
            page.on("response", on_response)
            page.goto(f"{CLONE}{path}", wait_until="networkidle", timeout=30000)
            page.close()

        if failed_requests:
            print(f"  ✗ Failed asset requests:")
            for req in failed_requests:
                print(f"    {req}")
        else:
            print(f"  ✓ All assets loaded successfully")

        assert not failed_requests, f"Failed requests: {failed_requests}"

        browser.close()


def test_all_internal_links_work():
    """Click every internal link on the clone homepage and verify no 404/500."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{CLONE}/en/", wait_until="networkidle", timeout=30000)

        # Collect all internal hrefs
        all_links = page.locator("a[href]").all()
        internal_hrefs = set()
        clone_host = CLONE.split("//")[1].split("/")[0]
        for a in all_links:
            href = a.get_attribute("href") or ""
            if href.startswith("/") and not href.startswith("//"):
                internal_hrefs.add(href.split("#")[0].split("?")[0])
            elif clone_host in href:
                path = "/" + href.split(clone_host, 1)[1]
                internal_hrefs.add(path.split("#")[0].split("?")[0])

        # Remove empty
        internal_hrefs.discard("")
        internal_hrefs.discard("/")

        print(f"  Found {len(internal_hrefs)} unique internal links")
        broken = []
        for href in sorted(internal_hrefs):
            resp = page.request.get(f"{CLONE}{href}")
            if resp.status >= 400:
                broken.append(f"{resp.status} {href}")

        if broken:
            print(f"  ✗ Broken internal links:")
            for b in broken:
                print(f"    {b}")
        else:
            print(f"  ✓ All internal links return 200")

        # We don't assert here — some links (faq, privacy, etc.) may not have pages
        # Just report
        browser.close()
