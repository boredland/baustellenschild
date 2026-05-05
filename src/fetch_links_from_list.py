#!/usr/bin/env python3
"""Extract detail page links from the list HTML and fetch with Playwright."""
import asyncio
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

OUTPUT_DIR = Path(__file__).parent.parent / "debug"

# Read the list page we already have
list_html_file = OUTPUT_DIR / "bauschild_478_414_203.html"
with open(list_html_file, "r", encoding="utf-8") as f:
    list_html = f.read()

soup = BeautifulSoup(list_html, "lxml")

# Extract all permit links
links = []
for row in soup.find_all("tr"):
    cells = row.find_all("td")
    if len(cells) >= 2:
        link_elem = cells[0].find("a")
        if link_elem and link_elem.get("href"):
            aktenzeichen = link_elem.get_text(strip=True)
            href = link_elem.get("href")
            links.append((aktenzeichen, href))

print(f"Found {len(links)} permit links")
for aktz, href in links[:3]:
    print(f"  {aktz}: {href}")

async def fetch_detail_links():
    """Use Playwright to fetch detail pages from links."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.set_default_timeout(20000)

        for idx, (aktenzeichen, href) in enumerate(links[:2]):  # First 2 permits
            try:
                print(f"\n[{idx+1}/{len(links[:2])}] Fetching {aktenzeichen}...")

                full_url = f"https://www.bauaufsicht-frankfurt.de{href}"
                await page.goto(full_url)
                await page.wait_for_timeout(2000)

                html = await page.content()

                # Save HTML
                output_file = OUTPUT_DIR / f"detail_{aktenzeichen}.html"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"  ✓ Saved to {output_file}")

                # Analyze
                soup_detail = BeautifulSoup(html, "lxml")
                dts = soup_detail.find_all("dt")
                dds = soup_detail.find_all("dd")

                if dts and dds:
                    print(f"  Found {len(dts)} dt/dd pairs")
                    print(f"  Sample fields:")
                    for dt, dd in list(zip(dts, dds))[:5]:
                        dt_text = dt.get_text(strip=True)[:30]
                        dd_text = dd.get_text(strip=True)[:50]
                        print(f"    {dt_text}: {dd_text}")
                else:
                    main = soup_detail.find("main")
                    if main:
                        text = main.get_text(strip=True)[:200]
                        print(f"  No dt/dd pairs. Main text preview: {text}")

            except Exception as e:
                print(f"  Error: {e}")
                continue

        await browser.close()

if __name__ == "__main__":
    asyncio.run(fetch_detail_links())
