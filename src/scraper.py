import asyncio
import os
import logging
from typing import Optional
import aiohttp
from bs4 import BeautifulSoup
import random

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.bauaufsicht-frankfurt.de"
LIEGENSCHAFT_URL = f"{BASE_URL}/service/bauschild/liegenschaft"

MAX_CONCURRENT = int(os.getenv("CRAWL_CONCURRENCY", "50"))  # Configurable via env var
MAX_RETRIES = 3
RETRY_DELAY = 0.5  # seconds, increases exponentially


def _normalize_field(value: str) -> Optional[str]:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned:
        return cleaned
    return None


def parse_bauschild_html(html: str) -> Optional[dict]:
    soup = BeautifulSoup(html, "lxml")

    if "nicht vorhanden" in html.lower() or "kein" in html.lower():
        return None

    # Parse all tables and track which section each field comes from
    tables = soup.find_all("table", class_="baustellenschild-table")
    if not tables:
        return None

    # Extract data from all tables, labeled by their section
    section_data = {}
    section_labels = ["project", "builder", "architect", "site_manager"]

    for idx, table in enumerate(tables):
        section = section_labels[idx] if idx < len(section_labels) else f"section_{idx}"
        section_data[section] = {}

        for row in table.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if th and td:
                label = _normalize_field(th.get_text())
                value = _normalize_field(td.get_text())
                if label and value:
                    section_data[section][label] = value

    result = {}

    # Extract project (Bauvorhaben) info
    if "project" in section_data:
        project = section_data["project"]
        result["permit_number"] = project.get("Aktenzeichen")
        result["description"] = project.get("Bauvorhaben")
        result["site_address"] = project.get("Straße/Hausnummer")
        result["parcel_info"] = project.get("Gemarkung, Flur, Flurstück")
        result["permit_date"] = project.get("Datum")

        # Look for date/timeline fields (various German naming conventions)
        for key in project:
            if key and project[key]:
                key_lower = key.lower()
                if "beginn" in key_lower or "start" in key_lower or "von" in key_lower:
                    result["start_date"] = result.get("start_date") or project[key]
                elif "ende" in key_lower or "bis" in key_lower or "fertigstellung" in key_lower:
                    result.setdefault("end_date", project[key])
                    if "geplante" in key_lower or "geplant" in key_lower:
                        result["estimated_completion"] = project[key]
                elif "status" in key_lower or "zustand" in key_lower:
                    result["permit_status"] = project[key]
                elif "gültig" in key_lower:
                    if "bis" in key_lower:
                        result["validity_end"] = project[key]
                    elif "von" in key_lower:
                        result["validity_start"] = project[key]
                elif "kosten" in key_lower or "summe" in key_lower or "investition" in key_lower or "wert" in key_lower:
                    result["estimated_cost"] = project[key]

    # Extract builder (Bauherrschaft) info
    if "builder" in section_data:
        builder = section_data["builder"]
        result["builder_name"] = builder.get("Vorname und Name")
        result["builder_address"] = builder.get("Straße/Hausnummer")
        result["builder_location"] = builder.get("PLZ/Ort")
        result["represented_by"] = builder.get("Vertreten durch")

    # Extract architect (Entwurfsverfasser) info
    if "architect" in section_data:
        architect = section_data["architect"]
        result["architect_name"] = architect.get("Vorname und Name")
        result["architect_address"] = architect.get("Straße/Hausnummer")
        result["architect_location"] = architect.get("PLZ/Ort")

    # Extract site manager (Bauleitung) info
    if "site_manager" in section_data:
        manager = section_data["site_manager"]
        result["site_manager_name"] = manager.get("Vorname und Name")
        result["site_manager_address"] = manager.get("Straße/Hausnummer")
        result["site_manager_location"] = manager.get("PLZ/Ort")

    # Clean up None values
    result = {k: v for k, v in result.items() if v is not None}

    return result if result else None


async def scrape_liegenschaft_async(
    session: aiohttp.ClientSession, gemarkung_id: int, flur: str, flurstueck: str
) -> Optional[dict]:
    """Async scraper for a single parcel. Fetches detail page for first permit if list."""

    payload = {
        "tx_vierwdbafinfothek_constructionsign[SKZ]": "",
        "tx_vierwdbafinfothek_constructionsign[HAUSNR]": "",
        "tx_vierwdbafinfothek_constructionsign[bauschild]": "",
        "tx_vierwdbafinfothek_constructionsign[GEMARK]": str(gemarkung_id),
        "tx_vierwdbafinfothek_constructionsign[FLUR]": flur,
        "tx_vierwdbafinfothek_constructionsign[FLST_ZAE;FLST_NEN]": flurstueck,
    }

    headers = {
        "Origin": "https://www.bauaufsicht-frankfurt.de",
        "Referer": "https://www.bauaufsicht-frankfurt.de/service/bauschild",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    for attempt in range(MAX_RETRIES):
        try:
            await asyncio.sleep(random.uniform(0.01, 0.05))
            async with session.post(
                LIEGENSCHAFT_URL,
                data=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                resp.raise_for_status()
                html = await resp.text()

                # Check if this is a list page (summary table) or detail page
                soup = BeautifulSoup(html, "lxml")
                list_table = soup.find("table", class_="baustellenschild-searchresults")

                if list_table:
                    # This is a list page - fetch detail page for first permit
                    first_row = list_table.find("tr")
                    if first_row:
                        permit_link = first_row.find("a")
                        if permit_link and permit_link.get("href"):
                            detail_url = "https://www.bauaufsicht-frankfurt.de" + permit_link.get("href")
                            try:
                                async with session.get(
                                    detail_url,
                                    headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=15, connect=5)
                                ) as detail_resp:
                                    detail_resp.raise_for_status()
                                    detail_html = await detail_resp.text()
                                    parsed = parse_bauschild_html(detail_html)
                                    if parsed:
                                        parsed["url"] = detail_url
                                    return parsed if parsed else None
                            except Exception as e:
                                logger.warning(f"Detail page fetch failed for {gemarkung_id}:{flur}:{flurstueck}, using list fallback: {type(e).__name__}")
                                # Fallback: extract from list if detail fetch fails
                                cells = first_row.find_all("td")
                                if len(cells) >= 2:
                                    result = {}
                                    result["permit_number"] = _normalize_field(permit_link.get_text())
                                    result["description"] = _normalize_field(cells[1].get_text())
                                    return result
                    return None

                # Otherwise try to parse as detail page (table-based structure)
                parsed = parse_bauschild_html(html)
                if parsed:
                    return parsed

                return None

        except asyncio.TimeoutError as e:
            logger.warning(f"Timeout on {gemarkung_id}:{flur}:{flurstueck} (attempt {attempt + 1}/{MAX_RETRIES})")
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAY * (2 ** attempt)
                await asyncio.sleep(wait)
            continue
        except aiohttp.ClientError as e:
            error_msg = f"ClientError on {gemarkung_id}:{flur}:{flurstueck}: {type(e).__name__}"
            if hasattr(e, 'status'):
                error_msg += f" (HTTP {e.status})"
            error_msg += f" (attempt {attempt + 1}/{MAX_RETRIES})"
            logger.warning(error_msg)
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAY * (2 ** attempt)
                await asyncio.sleep(wait)
            continue
        except Exception as e:
            logger.exception(f"Unexpected error on {gemarkung_id}:{flur}:{flurstueck}: {e}")
            return None

    logger.warning(f"Failed after {MAX_RETRIES} retries: {gemarkung_id}:{flur}:{flurstueck}")
    return None
