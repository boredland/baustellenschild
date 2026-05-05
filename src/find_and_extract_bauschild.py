#!/usr/bin/env python3
"""
Use Playwright to find a parcel with actual construction sites and extract the structure.
"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

FORM_URL = "https://www.bauaufsicht-frankfurt.de/service/bauschild"
OUTPUT_DIR = Path(__file__).parent.parent / "debug"


async def find_and_extract_bauschild():
    """Try multiple parcels to find one with actual construction sites."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("Navigating to form...")
        await page.goto(FORM_URL)
        await page.wait_for_timeout(2000)

        print("Dismissing cookie consent...")
        await page.evaluate("""
            () => {
                const root = document.getElementById('usercentrics-root');
                if (root) root.style.display = 'none';
            }
        """)
        await page.wait_for_timeout(500)

        # Try parcels we know exist in cache
        test_cases = [
            (460, "3", None),    # Gemarkung 460, Flur 3
            (460, "5", None),    # Gemarkung 460, Flur 5
            (460, "8", None),    # Gemarkung 460, Flur 8
            (460, "10", None),   # Gemarkung 460, Flur 10
        ]

        for gemark, flur, _ in test_cases:
            print(f"\nTrying Gemarkung {gemark}, Flur {flur}...")

            # Reset form
            await page.goto(FORM_URL)
            await page.wait_for_timeout(1000)

            # Dismiss cookie
            await page.evaluate("""
                () => {
                    const root = document.getElementById('usercentrics-root');
                    if (root) root.style.display = 'none';
                }
            """)

            try:
                # Select Gemarkung
                gemarkung_select = page.locator("#form-gemarkung")
                await gemarkung_select.select_option(str(gemark))
                await page.wait_for_timeout(800)

                # Select Flur
                flur_select = page.locator('select[name="tx_vierwdbafinfothek_constructionsign[FLUR]"]')
                await flur_select.select_option(flur)
                await page.wait_for_timeout(800)

                # Wait for Flurstück options
                await page.wait_for_function(
                    """
                    () => {
                        const select = document.querySelector('select[name="tx_vierwdbafinfothek_constructionsign[FLST_ZAE;FLST_NEN]"]');
                        return select && Array.from(select.options).length > 1;
                    }
                    """,
                    timeout=3000
                )

                flst_select = page.locator('select[name="tx_vierwdbafinfothek_constructionsign[FLST_ZAE;FLST_NEN]"]')
                options = await flst_select.locator("option").all()

                opt_values = []
                for opt in options:
                    val = await opt.get_attribute("value")
                    if val and val.strip():
                        opt_values.append(val)

                if not opt_values:
                    print(f"  No flurstück options available")
                    continue

                print(f"  Available flurstück: {len(opt_values)} options, trying first 5...")

                # Try first 5 flurstück values
                for test_flst in opt_values[1:6]:
                    await flst_select.select_option(test_flst)
                    await page.wait_for_timeout(300)

                    # Submit form
                    bauschild_btn = page.locator('button[name="tx_vierwdbafinfothek_constructionsign[bauschild]"]').first
                    await bauschild_btn.click()
                    await page.wait_for_timeout(2000)

                    # Get the response HTML
                    html = await page.content()

                    # Check if we have actual results (not "keine aktuellen")
                    if "keine aktuellen" not in html.lower() and "kein" not in html.lower():
                        print(f"  ✓✓✓ FOUND RESULTS at {gemark}/{flur}/{test_flst}!")

                        # Save the full HTML
                        output_file = OUTPUT_DIR / f"bauschild_WITH_DATA_{gemark}_{flur}_{test_flst}.html"
                        with open(output_file, "w", encoding="utf-8") as f:
                            f.write(html)
                        print(f"      Saved HTML to {output_file}")

                        # Parse and extract structure
                        soup = BeautifulSoup(html, "lxml")
                        main = soup.find("main")
                        if main:
                            content = main.get_text()
                            print(f"      Main content preview (first 500 chars):")
                            print(f"      {content[:500]}")

                        # Look for various possible structures
                        print(f"\n      HTML structure analysis:")
                        print(f"      - dt/dd pairs: {len(soup.find_all('dt'))}")
                        print(f"      - div.field: {len(soup.find_all('div', class_='field'))}")
                        print(f"      - div.row: {len(soup.find_all('div', class_='row'))}")

                        # Save prettified main content
                        main_html = str(main) if main else "No main element"
                        main_file = OUTPUT_DIR / f"bauschild_WITH_DATA_{gemark}_{flur}_{test_flst}_main.html"
                        with open(main_file, "w", encoding="utf-8") as f:
                            f.write(main_html)
                        print(f"      Saved main content to {main_file}")

                        await browser.close()
                        return

                    # Go back to form for next iteration
                    await page.goto(FORM_URL)
                    await page.wait_for_timeout(500)

            except Exception as e:
                print(f"  Error: {e}")
                continue

        print("\nNo parcels with construction sites found in test set")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(find_and_extract_bauschild())
