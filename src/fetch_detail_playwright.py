#!/usr/bin/env python3
"""Use Playwright to fetch detail pages for construction permits."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

OUTPUT_DIR = Path(__file__).parent.parent / "debug"

async def fetch_detail_page():
    """Navigate to list, click first permit link, extract detail structure."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.set_default_timeout(15000)

        print("Navigating to form...")
        await page.goto("https://www.bauaufsicht-frankfurt.de/service/bauschild")
        await page.wait_for_timeout(1000)

        print("Dismissing cookie consent...")
        await page.evaluate("""
            () => {
                const root = document.getElementById('usercentrics-root');
                if (root) root.style.display = 'none';
            }
        """)
        await page.wait_for_timeout(500)

        print("Selecting Gemarkung 478...")
        await page.select_option("#form-gemarkung", "478")
        await page.wait_for_timeout(1000)

        print("Selecting Flur 414...")
        await page.select_option('select[name="tx_vierwdbafinfothek_constructionsign[FLUR]"]', "414")
        await page.wait_for_timeout(2000)

        print("Waiting for Flurstück options to load...")
        await page.wait_for_function(
            """
            () => {
                const select = document.querySelector('select[name="tx_vierwdbafinfothek_constructionsign[FLST_ZAE;FLST_NEN]"]');
                return select && Array.from(select.options).length > 1;
            }
            """,
            timeout=20000
        )

        print("Getting first available Flurstück...")
        first_flst = await page.evaluate(
            """
            () => {
                const select = document.querySelector('select[name="tx_vierwdbafinfothek_constructionsign[FLST_ZAE;FLST_NEN]"]');
                const options = Array.from(select.options);
                return options[1]?.value || options[0]?.value;
            }
            """
        )
        print(f"  Selected: {first_flst}")
        await page.select_option('select[name="tx_vierwdbafinfothek_constructionsign[FLST_ZAE;FLST_NEN]"]', first_flst)
        await page.wait_for_timeout(500)

        print("Submitting form to get list...")
        bauschild_btn = page.locator('button[name="tx_vierwdbafinfothek_constructionsign[bauschild]"]').first
        await bauschild_btn.click()
        await page.wait_for_timeout(3000)

        # Now click first permit link
        print("Clicking first permit link...")
        first_link = page.locator("table.baustellenschild-searchresults tr:first-child a").first
        await first_link.click()
        await page.wait_for_timeout(3000)

        html = await page.content()

        # Save full HTML
        output_file = OUTPUT_DIR / "detail_page_B-2018-1590-3.html"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✓ Saved detail page to {output_file}")

        # Analyze structure
        soup = BeautifulSoup(html, "lxml")

        dts = soup.find_all("dt")
        dds = soup.find_all("dd")
        print(f"\n=== Detail Page Structure ===")
        print(f"dt/dd pairs: {len(dts)} dt, {len(dds)} dd")

        if dts and dds:
            print("\n=== Field Labels & Values ===")
            for dt, dd in list(zip(dts, dds))[:20]:
                label = dt.get_text(strip=True)
                value = dd.get_text(strip=True)[:70]
                print(f"  {label}: {value}")

        # Save prettified main
        main = soup.find("main")
        if main:
            main_file = OUTPUT_DIR / "detail_page_B-2018-1590-3_main.html"
            with open(main_file, "w", encoding="utf-8") as f:
                f.write(str(main.prettify()))
            print(f"\n✓ Saved main content to {main_file}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(fetch_detail_page())
