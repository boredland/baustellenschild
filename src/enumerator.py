import asyncio
from typing import Iterator
from playwright.async_api import async_playwright

FORM_URL = "https://www.bauaufsicht-frankfurt.de/service/bauschild"
GEMARKUNGEN = list(range(460, 519))


async def enumerate_all_parcels_async() -> list[tuple[int, str, str]]:
    """Enumerate all parcels using Playwright to extract dropdown options."""
    parcels = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(FORM_URL)
        await page.wait_for_timeout(2000)

        gemarkung_select = page.locator("#form-gemarkung")

        for gemark_id in GEMARKUNGEN:
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
                print(f"✗ Gemarkung {gemark_id}: no Flur values")
                continue

            print(f"Gemarkung {gemark_id}: {len(flur_values)} Flur values")

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

    return parcels


def enumerate_all_parcels() -> Iterator[tuple[int, str, str]]:
    """Wrapper to run async enumeration and yield results."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        parcels = loop.run_until_complete(enumerate_all_parcels_async())
        for parcel in parcels:
            yield parcel
    finally:
        loop.close()


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


def enumerate_test() -> Iterator[tuple[int, str, str]]:
    """Wrapper to run async test and yield results."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        parcels = loop.run_until_complete(enumerate_test_async())
        for parcel in parcels:
            yield parcel
    finally:
        loop.close()
