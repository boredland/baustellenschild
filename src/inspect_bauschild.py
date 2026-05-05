#!/usr/bin/env python3
"""
Fetch a known working parcel and analyze its HTML structure to understand
how construction site data is formatted.
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "debug"

async def inspect_parcel():
    """Fetch Gemarkung 478, Flur 414, Flurstück 203 and analyze structure."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    payload = {
        "tx_vierwdbafinfothek_constructionsign[SKZ]": "",
        "tx_vierwdbafinfothek_constructionsign[HAUSNR]": "",
        "tx_vierwdbafinfothek_constructionsign[bauschild]": "",
        "tx_vierwdbafinfothek_constructionsign[GEMARK]": "478",
        "tx_vierwdbafinfothek_constructionsign[FLUR]": "414",
        "tx_vierwdbafinfothek_constructionsign[FLST_ZAE;FLST_NEN]": "203",
    }

    headers = {
        "Origin": "https://www.bauaufsicht-frankfurt.de",
        "Referer": "https://www.bauaufsicht-frankfurt.de/service/bauschild",
        "User-Agent": "Frankfurt-Bauschild-Inspector/1.0",
    }

    url = "https://www.bauaufsicht-frankfurt.de/service/bauschild/liegenschaft"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            html = await resp.text()

    # Save full HTML
    output_file = OUTPUT_DIR / "bauschild_478_414_203.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ Saved full HTML to {output_file}")

    soup = BeautifulSoup(html, "lxml")

    # Check for "keine aktuellen" indicators
    text = soup.get_text().lower()
    if "keine aktuellen" in text or "nicht vorhanden" in text:
        print("✗ Response indicates no construction sites found")
        return

    print("✓ Found construction site data!")

    # Analyze structure
    print("\n=== HTML Structure Analysis ===")

    # Check for dt/dd pairs
    dts = soup.find_all("dt")
    dds = soup.find_all("dd")
    print(f"dt/dd pairs: {len(dts)} dt elements, {len(dds)} dd elements")
    if dts and dds:
        print("\n  Sample dt/dd content:")
        for dt, dd in list(zip(dts, dds))[:5]:
            dt_text = dt.get_text(strip=True)[:40]
            dd_text = dd.get_text(strip=True)[:40]
            print(f"    <dt> {dt_text}")
            print(f"    <dd> {dd_text}")

    # Check for div-based fields
    divs_field = soup.find_all("div", class_="field")
    divs_vierwd = soup.find_all("div", class_="vierwd-field")
    divs_row = soup.find_all("div", class_="row")
    print(f"\ndiv.field: {len(divs_field)}")
    print(f"div.vierwd-field: {len(divs_vierwd)}")
    print(f"div.row: {len(divs_row)}")

    # Check for table structure
    tables = soup.find_all("table")
    print(f"tables: {len(tables)}")

    # Check for common data attribute patterns
    divs_data = soup.find_all("div", attrs={"data-field": True})
    print(f"div[data-field]: {len(divs_data)}")

    # Look for main content area
    main = soup.find("main")
    if main:
        print(f"\n<main> element found")
        main_text = main.get_text(strip=True)
        print(f"  Content length: {len(main_text)} chars")
        print(f"  First 300 chars: {main_text[:300]}")

    # Look for specific labels/values
    print("\n=== Looking for common field patterns ===")
    for label in ["Straße", "Hausnummer", "Postleitzahl", "Bauherr", "Entwurfsverfasser",
                   "Bauleiter", "Bauvorhaben", "Aktenzeichen", "Datum", "Behörde"]:
        if label in html:
            print(f"  ✓ Found '{label}' in HTML")
            # Find the context around it
            soup_section = soup.find(string=lambda text: text and label in text)
            if soup_section:
                parent = soup_section.parent
                if parent:
                    next_elem = parent.find_next()
                    if next_elem:
                        print(f"    Next element: <{next_elem.name}> {next_elem.get_text(strip=True)[:60]}")

    # Save prettified main content
    if main:
        main_file = OUTPUT_DIR / "bauschild_478_414_203_main.html"
        with open(main_file, "w", encoding="utf-8") as f:
            f.write(str(main.prettify()))
        print(f"\n✓ Saved main content to {main_file}")


if __name__ == "__main__":
    asyncio.run(inspect_parcel())
