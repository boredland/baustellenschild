#!/usr/bin/env python3
import asyncio
import aiohttp
from scraper import scrape_liegenschaft_async

async def test_scraper():
    async with aiohttp.ClientSession() as session:
        session.headers.update({
            "User-Agent": "Frankfurt-Bauschild-Crawler/1.0 (public data; contact: info@jonas-strassel.de)"
        })

        # Test a few parcels
        test_parcels = [
            (478, "414", "1/3"),
            (460, "0", "0"),
            (470, "0", "0"),
        ]

        for gemark, flur, flst in test_parcels:
            result = await scrape_liegenschaft_async(session, gemark, flur, flst)
            print(f"Parcel {gemark}/{flur}/{flst}: {'✓ Found' if result else '○ No results'}")
            if result and 'raw_html' not in result:
                print(f"  Fields: {list(result.keys())}")

asyncio.run(test_scraper())
