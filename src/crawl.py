#!/usr/bin/env python3
import json
import sys
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Tuple
import os

print("[DEBUG] Script started, importing modules...", flush=True)

from enumerator import enumerate_all_parcels, enumerate_test
from scraper import scrape_liegenschaft_async

print("[DEBUG] Modules imported successfully", flush=True)


def log_progress(msg: str):
    """Log with timestamp and flush immediately."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_FILE = DATA_DIR / "baustellen.json"
PARCELS_CACHE_FILE = DATA_DIR / "parcels.json"

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


def load_or_enumerate_parcels(force_enumerate: bool = False) -> list[Tuple[int, str, str]]:
    """Load cached parcels or enumerate them if cache doesn't exist."""
    if PARCELS_CACHE_FILE.exists() and not force_enumerate:
        print("Loading parcels from cache...")
        with open(PARCELS_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    print("Enumerating parcels...")
    parcels = enumerate_all_parcels()

    with open(PARCELS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(parcels, f, indent=2)
    print(f"Cached {len(parcels)} parcels to {PARCELS_CACHE_FILE}")

    return parcels


def scrape_with_concurrency(
    parcels: Iterator[Tuple[int, str, str]], max_workers: int = None
) -> tuple[list, int]:
    """Scrape parcels with thread workers. Auto-determines worker count if not specified."""
    parcels_list = list(parcels)
    total_parcels = len(parcels_list)

    # Auto-determine worker count if not specified
    if max_workers is None:
        max_workers = int(os.getenv("CRAWL_CONCURRENCY", "50"))

    # Determine actual worker count (don't exceed total parcels)
    actual_workers = min(max_workers, total_parcels, 1000)  # Cap at 1000 to avoid resource exhaustion

    sites = []
    errors = 0
    last_log = [0]
    start_time = datetime.now(timezone.utc)

    def scrape_one_sync(args):
        """Synchronous wrapper for scraping a single parcel."""
        nonlocal errors
        i, gemark, flur, flst = args

        try:
            # Run async scraper in a new event loop (thread-safe)
            import aiohttp

            async def run_scrape():
                async with aiohttp.ClientSession() as session:
                    session.headers.update({
                        "User-Agent": "Frankfurt-Bauschild-Crawler/1.0 (public data; contact: jo.strassel@gmail.com)"
                    })
                    return await scrape_liegenschaft_async(session, gemark, flur, flst)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(run_scrape())
            finally:
                loop.close()

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

        # Log progress
        should_log = (i % 20 == 0) or (i <= 100 and i % 5 == 0)
        if should_log and i > last_log[0]:
            last_log[0] = i
            progress = 100 * i / total_parcels
            elapsed = datetime.now(timezone.utc) - start_time
            elapsed_sec = elapsed.total_seconds()

            if i > 0 and elapsed_sec > 0:
                rate = i / elapsed_sec
                remaining = total_parcels - i
                eta_sec = remaining / rate if rate > 0 else 0
                eta_time = datetime.now(timezone.utc) + timedelta(seconds=eta_sec)
                eta_str = eta_time.strftime("%H:%M:%S")
            else:
                eta_str = "calculating..."

            log_progress(f"  [{i:6d}/{total_parcels}] {progress:5.1f}% | {len(sites):4d} sites | {errors:3d} errors | ETA {eta_str}")

        return result

    # Use ThreadPoolExecutor for worker management
    with ThreadPoolExecutor(max_workers=actual_workers) as executor:
        log_progress(f"Starting {actual_workers} worker threads...")
        # Submit all tasks
        futures = [
            executor.submit(scrape_one_sync, (i, gemark, flur, flst))
            for i, (gemark, flur, flst) in enumerate(parcels_list, 1)
        ]
        # Wait for completion
        for future in futures:
            future.result()

    return sites, errors


def main():
    parser = argparse.ArgumentParser(description="Crawl Frankfurt Baustellen data")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run quick test on a small subset",
    )
    parser.add_argument(
        "--force-enumerate",
        action="store_true",
        help="Force re-enumeration even if cache exists",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)

    mode = "TEST" if args.test else "FULL"
    log_progress(f"\n{'='*60}")
    log_progress(f"Starting {mode} crawl")
    log_progress(f"{'='*60}")

    log_progress("Step 1: Getting parcels...")
    if args.test:
        parcels = enumerate_test()
    else:
        parcels = load_or_enumerate_parcels(force_enumerate=args.force_enumerate)
    log_progress(f"✓ Found {len(parcels)} parcels to scrape")

    max_workers = int(os.getenv("CRAWL_CONCURRENCY", "50"))
    log_progress(f"Step 2: Scraping {len(parcels)} parcels (workers: {max_workers})...")

    sites, errors = scrape_with_concurrency(parcels, max_workers=max_workers)
    log_progress(f"✓ Scraping complete: {len(sites)} sites found, {errors} errors")

    log_progress("Step 3: Writing output...")
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

    log_progress(f"✓ Output written to {OUTPUT_FILE}")
    log_progress(f"{'='*60}")
    log_progress(f"✓ Crawl complete!")
    log_progress(f"  • Sites found: {len(sites)}")
    log_progress(f"  • Errors: {errors}")
    if len(sites) + errors > 0:
        log_progress(f"  • Success rate: {100*len(sites)/(len(sites)+errors):.1f}%")
    log_progress(f"{'='*60}\n")


if __name__ == "__main__":
    main()
