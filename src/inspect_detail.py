#!/usr/bin/env python3
"""Fetch a Bauschild detail page to understand its structure."""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "debug"

async def inspect_detail():
    """Fetch detail page for permit B-2018-1590-3."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Detail page uses action=bauschild and aktenzeichen parameter
    url = "https://www.bauaufsicht-frankfurt.de/service/bauschild"
    params = {
        "tx_vierwdbafinfothek_constructionsign[action]": "bauschild",
        "tx_vierwdbafinfothek_constructionsign[aktenzeichen]": "B-2018-1590-3",
        "tx_vierwdbafinfothek_constructionsign[controller]": "Main",
    }

    headers = {
        "User-Agent": "Frankfurt-Bauschild-Inspector/1.0",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            html = await resp.text()

    # Save full HTML
    output_file = OUTPUT_DIR / "bauschild_detail_B-2018-1590-3.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ Saved detail page to {output_file}")

    soup = BeautifulSoup(html, "lxml")

    # Analyze structure
    print("\n=== Detail Page Structure ===")

    # Check for dt/dd pairs
    dts = soup.find_all("dt")
    dds = soup.find_all("dd")
    print(f"dt/dd pairs: {len(dts)} dt, {len(dds)} dd")
    if dts and dds:
        print("\n  Sample content:")
        for dt, dd in list(zip(dts, dds))[:10]:
            dt_text = dt.get_text(strip=True)
            dd_text = dd.get_text(strip=True)[:60]
            print(f"    {dt_text}: {dd_text}")

    # Check for div-based fields
    divs_field = soup.find_all("div", class_="field")
    divs_vierwd = soup.find_all("div", class_="vierwd-field")
    print(f"\ndiv.field: {len(divs_field)}")
    print(f"div.vierwd-field: {len(divs_vierwd)}")

    # Look for main content area
    main = soup.find("main")
    if main:
        main_file = OUTPUT_DIR / "bauschild_detail_B-2018-1590-3_main.html"
        with open(main_file, "w", encoding="utf-8") as f:
            f.write(str(main.prettify()))
        print(f"\n✓ Saved main content to {main_file}")

        main_text = main.get_text(strip=True)
        print(f"  Main content length: {len(main_text)} chars")
        print(f"  First 500 chars: {main_text[:500]}")


if __name__ == "__main__":
    asyncio.run(inspect_detail())
