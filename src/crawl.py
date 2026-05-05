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
PARCELS_METADATA_FILE = DATA_DIR / "parcels_metadata.json"

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


def select_parcels_for_update(all_parcels: list[Tuple[int, str, str]], batch_size: int = 5000) -> list[Tuple[int, str, str]]:
    """Select parcels evenly distributed across all gemarkungen, choosing oldest/missing first."""
    if PARCELS_METADATA_FILE.exists():
        with open(PARCELS_METADATA_FILE, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    else:
        metadata = {}

    # Group parcels by gemarkung
    by_gemarkung = {}
    for gemark, flur, flst in all_parcels:
        if gemark not in by_gemarkung:
            by_gemarkung[gemark] = []
        by_gemarkung[gemark].append((gemark, flur, flst))

    # Sort each gemarkung's parcels by last_updated (oldest first)
    for gemark in by_gemarkung:
        by_gemarkung[gemark].sort(
            key=lambda p: metadata.get(f"{p[0]}:{p[1]}:{p[2]}", {}).get("last_updated", "1970-01-01T00:00:00Z")
        )

    # Distribute batch_size evenly across gemarkungen
    parcels_per_gemarkung = batch_size // len(by_gemarkung)
    selected = []
    for gemark in sorted(by_gemarkung.keys()):
        selected.extend(by_gemarkung[gemark][:parcels_per_gemarkung])

    log_progress(f"Selected {len(selected)} parcels ({parcels_per_gemarkung} per gemarkung, distributed across {len(by_gemarkung)} districts)")

    return selected


def update_parcels_metadata(scraped_parcels: dict, now_str: str):
    """Update metadata file with last_updated timestamps."""
    if PARCELS_METADATA_FILE.exists():
        with open(PARCELS_METADATA_FILE, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    else:
        metadata = {}

    for gemark, flur, flst in scraped_parcels.keys():
        key = f"{gemark}:{flur}:{flst}"
        metadata[key] = {"last_updated": now_str}

    with open(PARCELS_METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f)


def load_existing_sites() -> dict:
    """Load existing baustellen.json and return sites indexed by parcel key."""
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            sites_by_key = {}
            for site in data.get("sites", []):
                key = f"{site['gemarkung_id']}:{site['flur']}:{site['flurstueck']}"
                sites_by_key[key] = site
            return sites_by_key
    return {}


def scrape_with_concurrency(
    parcels: Iterator[Tuple[int, str, str]], max_workers: int = None
) -> tuple[list, int]:
    """Scrape parcels with thread workers. Auto-determines worker count if not specified."""
    parcels_list = list(parcels)
    total_parcels = len(parcels_list)

    if max_workers is None:
        max_workers = int(os.getenv("CRAWL_CONCURRENCY", "50"))

    actual_workers = min(max_workers, total_parcels, 1000)

    sites = []
    errors = 0
    last_log = [0]
    start_time = datetime.now(timezone.utc)

    def scrape_one_sync(args):
        """Synchronous wrapper for scraping a single parcel."""
        nonlocal errors
        i, gemark, flur, flst = args

        try:
            import aiohttp

            async def run_scrape():
                async with aiohttp.ClientSession() as session:
                    session.headers.update({
                        "User-Agent": "Frankfurt-Bauschild-Crawler/1.0 (public data; contact: info@jonas-strassel.de)"
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

    with ThreadPoolExecutor(max_workers=actual_workers) as executor:
        log_progress(f"Starting {actual_workers} worker threads...")
        futures = [
            executor.submit(scrape_one_sync, (i, gemark, flur, flst))
            for i, (gemark, flur, flst) in enumerate(parcels_list, 1)
        ]
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
    parser.add_argument(
        "--full",
        action="store_true",
        help="Scrape all parcels instead of rotating through batch",
    )
    parser.add_argument(
        "--gemarkung",
        type=int,
        help="Gemarkung ID for manual parcel selection",
    )
    parser.add_argument(
        "--flur",
        type=str,
        help="Flur for manual parcel selection (requires --gemarkung)",
    )
    parser.add_argument(
        "--flurstueck",
        type=str,
        help="Flurstueck for manual parcel selection (requires --gemarkung and --flur)",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)

    # Determine mode
    if args.test:
        mode = "TEST"
    elif args.gemarkung:
        mode = "MANUAL"
    elif args.full:
        mode = "FULL"
    else:
        mode = "BATCH"

    log_progress(f"\n{'='*60}")
    log_progress(f"Starting {mode} crawl")
    log_progress(f"{'='*60}")

    log_progress("Step 1: Getting parcels...")
    if args.test:
        parcels = enumerate_test()
    elif args.gemarkung:
        # Manual parcel selection via command-line args
        if args.flurstueck:
            parcels = [(args.gemarkung, args.flur, args.flurstueck)]
            log_progress(f"✓ Selected 1 parcel: {args.gemarkung}:{args.flur}:{args.flurstueck}")
        elif args.flur:
            all_parcels = load_or_enumerate_parcels(force_enumerate=args.force_enumerate)
            parcels = [p for p in all_parcels if p[0] == args.gemarkung and p[1] == args.flur]
            log_progress(f"✓ Found {len(parcels)} parcels for gemarkung {args.gemarkung}, flur {args.flur}")
        else:
            all_parcels = load_or_enumerate_parcels(force_enumerate=args.force_enumerate)
            parcels = [p for p in all_parcels if p[0] == args.gemarkung]
            log_progress(f"✓ Found {len(parcels)} parcels for gemarkung {args.gemarkung}")
    else:
        all_parcels = load_or_enumerate_parcels(force_enumerate=args.force_enumerate)
        if args.full:
            parcels = all_parcels
        else:
            parcels = select_parcels_for_update(all_parcels, batch_size=5000)
        log_progress(f"✓ Found {len(parcels)} parcels to scrape")

    max_workers = int(os.getenv("CRAWL_CONCURRENCY", "50"))
    log_progress(f"Step 2: Scraping {len(parcels)} parcels (workers: {max_workers})...")

    sites, errors = scrape_with_concurrency(parcels, max_workers=max_workers)
    log_progress(f"✓ Scraping complete: {len(sites)} sites found, {errors} errors")

    log_progress("Step 3: Merging with existing data...")
    existing_sites = load_existing_sites() if not args.full else {}

    # Update with newly scraped sites
    for site in sites:
        key = f"{site['gemarkung_id']}:{site['flur']}:{site['flurstueck']}"
        existing_sites[key] = site

    # Convert back to list
    all_sites = list(existing_sites.values())

    log_progress("Step 4: Writing output...")
    now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data = {
        "meta": {
            "last_updated": now_str,
            "total": len(all_sites),
            "errors": errors,
            "source": "https://www.bauaufsicht-frankfurt.de/service/bauschild",
        },
        "sites": all_sites,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Update metadata
    if not args.test:
        parcel_dict = {(p[0], p[1], p[2]): True for p in parcels}
        update_parcels_metadata(parcel_dict, now_str)

    log_progress(f"✓ Output written to {OUTPUT_FILE}")
    log_progress(f"{'='*60}")
    log_progress(f"✓ Crawl complete!")
    log_progress(f"  • Sites found this run: {len(sites)}")
    log_progress(f"  • Total sites in database: {len(all_sites)}")
    log_progress(f"  • Errors: {errors}")
    if len(sites) + errors > 0:
        log_progress(f"  • Success rate: {100*len(sites)/(len(sites)+errors):.1f}%")
    log_progress(f"{'='*60}\n")


if __name__ == "__main__":
    main()
