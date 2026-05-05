import asyncio
from typing import Iterator
from playwright.async_api import async_playwright

FORM_URL = "https://www.bauaufsicht-frankfurt.de/service/bauschild"
GEMARKUNGEN = list(range(460, 519))


async def enumerate_all_parcels_async() -> list[tuple[int, str, str]]:
    """Enumerate all parcels using Playwright to extract dropdown options."""
    parcels = []

    async with async_playwright() as p:
        print("Launching Chromium browser...")
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"Navigating to {FORM_URL}...")
        await page.goto(FORM_URL)
        await page.wait_for_timeout(2000)

        gemarkung_select = page.locator("#form-gemarkung")
        print(f"Starting enumeration of {len(GEMARKUNGEN)} Gemarkungen...")

        for i, gemark_id in enumerate(GEMARKUNGEN, 1):
            # Select Gemarkung
            await gemarkung_select.select_option(str(gemark_id))
            await page.wait_for_timeout(500)

            # Extract Flur options (use name selector to avoid duplicate IDs)
            flur_select = page.locator('select[name="tx_vierwdbafinfothek_constructionsign[FLUR]"]')
            flur_options = await flur_select.locator("option").all()

            flur_values = []
            for opt in flur_options:
                value = await opt.get_attribute("value")
                if value and value.strip():  # Skip empty/placeholder options
                    flur_values.append(value)

            if not flur_values:
                print(f"  [{i}/{len(GEMARKUNGEN)}] ✗ Gemarkung {gemark_id}: no Flur values")
                continue

            print(f"  [{i}/{len(GEMARKUNGEN)}] Gemarkung {gemark_id}: {len(flur_values)} Flur values")

            for flur in flur_values:
                # Select Flur
                await flur_select.select_option(flur)
                await page.wait_for_timeout(500)

                # Extract Flurstück options
                flst_select = page.locator("select[name*='FLST']")
                flst_options = await flst_select.locator("option").all()

                flst_values = []
                for opt in flst_options:
                    value = await opt.get_attribute("value")
                    if value and value.strip():
                        flst_values.append(value)

                for flst in flst_values:
                    parcels.append((gemark_id, flur, flst))

        await browser.close()

    print(f"Enumeration complete: {len(parcels)} total parcels found")
    return parcels


def _run_async(coro):
    """Helper to run async code in a non-async context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        return asyncio.run(coro)
    else:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()


def enumerate_all_parcels() -> list[tuple[int, str, str]]:
    """Run async enumeration and return all parcels."""
    return _run_async(enumerate_all_parcels_async())


async def enumerate_test_async() -> list[tuple[int, str, str]]:
    """Quick test using Playwright: just Gemarkung 460."""
    parcels = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(FORM_URL)
        await page.wait_for_timeout(2000)

        gemarkung_select = page.locator("#form-gemarkung")
        gemark_id = 460

        # Select Gemarkung
        await gemarkung_select.select_option(str(gemark_id))
        await page.wait_for_timeout(500)

        # Extract Flur options (use name selector to avoid duplicate IDs)
        flur_select = page.locator('select[name="tx_vierwdbafinfothek_constructionsign[FLUR]"]')
        flur_options = await flur_select.locator("option").all()

        flur_values = []
        for opt in flur_options:
            value = await opt.get_attribute("value")
            if value and value.strip():
                flur_values.append(value)

        print(f"✓ Gemarkung {gemark_id}: {len(flur_values)} Flur values")

        for flur in flur_values[:5]:  # Only first 5 Flur for quick test
            # Select Flur
            await flur_select.select_option(flur)
            await page.wait_for_timeout(500)

            # Extract Flurstück options (use name selector since there are duplicate IDs)
            flst_select = page.locator('select[name="tx_vierwdbafinfothek_constructionsign[FLST_ZAE;FLST_NEN]"]')
            flst_options = await flst_select.locator("option").all()

            flst_values = []
            for opt in flst_options:
                value = await opt.get_attribute("value")
                if value and value.strip():
                    flst_values.append(value)

            print(f"  Flur {flur}: {len(flst_values)} Flurstück values")

            for flst in flst_values[:10]:  # Only first 10 for quick test
                parcels.append((gemark_id, flur, flst))

        await browser.close()

    return parcels


def enumerate_test() -> list[tuple[int, str, str]]:
    """Run async test enumeration and return parcels."""
    return _run_async(enumerate_test_async())
