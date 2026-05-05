#!/usr/bin/env python3
"""
Search for a parcel with actual results and capture its HTML structure.
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

FORM_URL = "https://www.bauaufsicht-frankfurt.de/service/bauschild"
OUTPUT_DIR = Path(__file__).parent.parent / "debug"


async def find_parcel_with_results():
    """Search through parcels to find one with actual construction sites."""
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

        # Test a few gemarkungen and flur combinations
        test_parcels = [
            (460, "3"),    # Central Frankfurt
            (461, "0"),    # Another district
            (470, "0"),    # Another area
        ]

        for gemark, flur in test_parcels:
            print(f"\nTesting Gemarkung {gemark}, Flur {flur}...")

            gemarkung_select = page.locator("#form-gemarkung")
            await gemarkung_select.select_option(str(gemark))
            await page.wait_for_timeout(1000)

            flur_select = page.locator('select[name="tx_vierwdbafinfothek_constructionsign[FLUR]"]')

            # Wait for Flurstück options to load
            await page.wait_for_function(
                """
                () => {
                    const select = document.querySelector('select[name="tx_vierwdbafinfothek_constructionsign[FLST_ZAE;FLST_NEN]"]');
                    const options = select ? Array.from(select.options) : [];
                    return options.length > 1;
                }
                """,
                timeout=5000
            )

            try:
                await flur_select.select_option(flur)
                await page.wait_for_timeout(1000)
            except:
                print(f"  Could not select Flur {flur}, skipping...")
                continue

            flst_select = page.locator('select[name="tx_vierwdbafinfothek_constructionsign[FLST_ZAE;FLST_NEN]"]')

            # Get available Flurstück options
            options = await flst_select.locator("option").all()
            opt_values = []
            for opt in options:
                val = await opt.get_attribute("value")
                if val and val.strip():
                    opt_values.append(val)

            if not opt_values:
                print(f"  No Flurstück options available")
                continue

            print(f"  Found {len(opt_values)} Flurstück options, trying first 3...")

            for flst in opt_values[1:4]:  # Try first 3
                print(f"    Submitting Gemarkung {gemark}, Flur {flur}, Flurstück {flst}...")

                await flst_select.select_option(flst)
                await page.wait_for_timeout(500)

                # Click submit button
                bauschild_btn = page.locator('button[name="tx_vierwdbafinfothek_constructionsign[bauschild]"]').first
                await bauschild_btn.click()
                await page.wait_for_timeout(2000)

                # Check if we have results
                html = await page.content()
                if "keine aktuellen Bauvorgänge" not in html.lower():
                    # Found one with results!
                    print(f"    ✓ FOUND RESULTS for {gemark}/{flur}/{flst}")

                    output_file = OUTPUT_DIR / f"response_WITH_RESULTS_{gemark}_{flur}_{flst}.html"
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(html)
                    print(f"      Saved to {output_file}")

                    # Print the main content area
                    main_content = await page.evaluate("""
                        () => {
                            const main = document.querySelector('main');
                            return main ? main.innerHTML : 'No main element';
                        }
                    """)
                    preview_file = OUTPUT_DIR / f"response_WITH_RESULTS_{gemark}_{flur}_{flst}_main.html"
                    with open(preview_file, "w", encoding="utf-8") as f:
                        f.write(main_content)

                    await browser.close()
                    return
                else:
                    print(f"    (no results)")

                # Go back to form
                await page.goto(FORM_URL)
                await page.wait_for_timeout(1000)

        print("\nNo parcels with results found in test set")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(find_parcel_with_results())
