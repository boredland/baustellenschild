#!/usr/bin/env python3
import json
import sys
import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Tuple

import aiohttp

from enumerator import enumerate_all_parcels, enumerate_test
from scraper import scrape_liegenschaft_async, MAX_CONCURRENT

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_FILE = DATA_DIR / "baustellen.json"

GEMARKUNG_LABELS = {
    460: "Frankfurt Bezirk 01",
    461: "Frankfurt Bezirk 09",
    462: "Frankfurt Bezirk 10",
    463: "Frankfurt Bezirk 11",
    464: "Frankfurt Bezirk 12",
    465: "Frankfurt Bezirk 13",
    466: "Frankfurt Bezirk 14",
    467: "Frankfurt Bezirk 15",
    468: "Frankfurt Bezirk 16",
    469: "Frankfurt Bezirk 17",
    470: "Frankfurt Bezirk 18",
    471: "Frankfurt Bezirk 19",
    472: "Frankfurt Bezirk 20",
    473: "Frankfurt Bezirk 21",
    474: "Frankfurt Bezirk 22",
    475: "Frankfurt Bezirk 23",
    476: "Frankfurt Bezirk 24",
    477: "Frankfurt Bezirk 25",
    478: "Frankfurt Bezirk 26",
    479: "Frankfurt Bezirk 27",
    480: "Frankfurt Bezirk 28",
    481: "Frankfurt Bezirk 29",
    482: "Frankfurt Bezirk 30",
    483: "Frankfurt Bezirk 31",
    484: "Frankfurt Bezirk 32",
    485: "Frankfurt Bezirk 33",
    486: "Bergen-Enkheim Bezirk 68",
    487: "Berkersheim Bezirk 50",
    488: "Bockenheim Bezirk 34",
    489: "Bonames Bezirk 49",
    490: "Eckenheim Bezirk 46",
    491: "Eschersheim Bezirk 45",
    492: "Fechenheim Bezirk 51",
    493: "Ginnheim Bezirk 44",
    494: "Griesheim Bezirk 54",
    495: "Harheim Bezirk 66",
    496: "Hausen Bezirk 41",
    497: "Heddernheim Bezirk 43",
    498: "Höchst Bezirk 57",
    499: "Kalbach Bezirk 65",
    500: "Main Bezirk 70",
    501: "Nied Bezirk 56",
    502: "Niederrad Bezirk 37",
    503: "Niederursel/F. Bezirk 48F",
    504: "Niederursel/H. Bezirk 48H",
    505: "Nieder-Erlenbach Bezirk 64",
    506: "Nieder-Eschbach Bezirk 67",
    507: "Oberrad Bezirk 38",
    508: "Praunheim Bezirk 42",
    509: "Preungesheim Bezirk 47",
    510: "Rödelheim Bezirk 40",
    511: "Schwanheim Bezirk 53",
    512: "Seckbach Bezirk 39",
    513: "Sindlingen Bezirk 60",
    514: "Sossenheim Bezirk 63",
    515: "Unterliederbach Bezirk 62",
    516: "Wald Bezirk 71",
    517: "Zeilsheim Bezirk 61",
    518: "Flughafen Bezirk 72",
}


async def scrape_with_concurrency(
    parcels: Iterator[Tuple[int, str, str]], max_concurrent: int = MAX_CONCURRENT
) -> tuple[list, int]:
    """Scrape parcels concurrently with a semaphore to limit concurrency."""
    sites = []
    errors = 0
    semaphore = asyncio.Semaphore(max_concurrent)
    parcels_list = list(parcels)
    total_parcels = len(parcels_list)

    async def scrape_one(session: aiohttp.ClientSession, i: int, gemark: int, flur: str, flst: str):
        nonlocal errors
        async with semaphore:
            try:
                result = await scrape_liegenschaft_async(session, gemark, flur, flst)
                if result:
                    site = {
                        "gemarkung_id": gemark,
                        "gemarkung_label": GEMARKUNG_LABELS.get(gemark, f"Unknown ({gemark})"),
                        "flur": flur,
                        "flurstueck": flst,
                    }
                    site.update(result)
                    sites.append(site)
            except Exception as e:
                errors += 1

            if i % 50 == 0:
                progress = 100 * i / total_parcels
                print(f"  [{i}/{total_parcels}] {progress:.1f}% - {len(sites)} sites, {errors} errors")

    async with aiohttp.ClientSession() as session:
        session.headers.update({
            "User-Agent": "Frankfurt-Bauschild-Crawler/1.0 (public data; contact: jo.strassel@gmail.com)"
        })

        tasks = [
            scrape_one(session, i, gemark, flur, flst)
            for i, (gemark, flur, flst) in enumerate(parcels_list, 1)
        ]
        await asyncio.gather(*tasks)

    return sites, errors


def main():
    parser = argparse.ArgumentParser(description="Crawl Frankfurt Baustellen data")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run quick test on a small subset",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)

    mode = "TEST" if args.test else "FULL"
    print(f"\n{'='*60}")
    print(f"Starting {mode} crawl")
    print(f"{'='*60}\n")

    print("Step 1: Enumerating parcels...")
    parcels = enumerate_test() if args.test else enumerate_all_parcels()
    print(f"✓ Found {len(parcels)} parcels to scrape\n")

    print("Step 2: Scraping parcels (concurrent)...")

    sites, errors = asyncio.run(scrape_with_concurrency(parcels))
    print(f"\n✓ Scraping complete: {len(sites)} sites found, {errors} errors\n")

    print("Step 3: Writing output...")
    data = {
        "meta": {
            "last_updated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "total": len(sites),
            "errors": errors,
            "source": "https://www.bauaufsicht-frankfurt.de/service/bauschild",
        },
        "sites": sites,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✓ Output written to {OUTPUT_FILE}")
    print(f"\n{'='*60}")
    print(f"✓ Crawl complete!")
    print(f"  • Sites found: {len(sites)}")
    print(f"  • Errors: {errors}")
    if len(sites) + errors > 0:
        print(f"  • Success rate: {100*len(sites)/(len(sites)+errors):.1f}%")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
