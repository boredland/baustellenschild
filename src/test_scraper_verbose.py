#!/usr/bin/env python3
import asyncio
import aiohttp
from scraper import scrape_liegenschaft_async, parse_bauschild_html

async def test_scraper():
    async with aiohttp.ClientSession() as session:
        session.headers.update({
            "User-Agent": "Frankfurt-Bauschild-Crawler/1.0 (public data; contact: info@jonas-strassel.de)"
        })

        async with session.post(
            "https://www.bauaufsicht-frankfurt.de/service/bauschild/liegenschaft",
            data={
                "tx_vierwdbafinfothek_constructionsign[SKZ]": "",
                "tx_vierwdbafinfothek_constructionsign[HAUSNR]": "",
                "tx_vierwdbafinfothek_constructionsign[bauschild]": "",
                "tx_vierwdbafinfothek_constructionsign[GEMARK]": "478",
                "tx_vierwdbafinfothek_constructionsign[FLUR]": "414",
                "tx_vierwdbafinfothek_constructionsign[FLST_ZAE;FLST_NEN]": "1/3",
            },
            headers={
                "Origin": "https://www.bauaufsicht-frankfurt.de",
                "Referer": "https://www.bauaufsicht-frankfurt.de/service/bauschild",
            }
        ) as resp:
            html = await resp.text()

            print(f"Status: {resp.status}")
            print(f"Response length: {len(html)} chars")

            # Check for key indicators
            has_no_results = "keine aktuellen" in html.lower()
            has_form_error = "formError" in html

            print(f"Contains 'keine aktuellen': {has_no_results}")
            print(f"Contains 'formError': {has_form_error}")

            # Try parsing
            result = parse_bauschild_html(html)
            print(f"Parse result: {result}")

            # Show snippet
            if has_no_results:
                idx = html.lower().find("keine aktuellen")
                print(f"\nSnippet around 'keine aktuellen':")
                print(html[max(0, idx-100):idx+150])

asyncio.run(test_scraper())
