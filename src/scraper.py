import asyncio
import os
from typing import Optional
import aiohttp
from bs4 import BeautifulSoup

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

    fields = {}

    # Parse table-based structure (th/td pairs in tables)
    for table in soup.find_all("table", class_="baustellenschild-table"):
        for row in table.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if th and td:
                label = _normalize_field(th.get_text())
                value = _normalize_field(td.get_text())
                if label and value:
                    fields[label] = value

    # Fallback: Try to find dt/dd pairs (definition list format)
    if not fields:
        for dt in soup.find_all("dt"):
            label = _normalize_field(dt.get_text())
            dd = dt.find_next("dd")
            if label and dd:
                value = _normalize_field(dd.get_text())
                if value:
                    fields[label] = value

    # Try alternative structure: divs with data attributes or class names
    if not fields:
        for div in soup.find_all("div", class_="vierwd-field") or soup.find_all("div", class_="field"):
            label_elem = div.find(class_="vierwd-label") or div.find(class_="label")
            value_elem = div.find(class_="vierwd-value") or div.find(class_="value")
            if label_elem and value_elem:
                label = _normalize_field(label_elem.get_text())
                value = _normalize_field(value_elem.get_text())
                if label and value:
                    fields[label] = value

    if not fields:
        return None

    result = {}
    for de_key, en_key in [
        ("Straße/Hausnummer", "address"),
        ("Straße", "street"),
        ("Hausnummer", "house_number"),
        ("Postleitzahl", "postal_code"),
        ("Vorname und Name", "name"),
        ("Aktenzeichen", "permit_number"),
        ("Bauvorhaben", "description"),
        ("Datum", "permit_date"),
        ("Behörde", "authority"),
    ]:
        if de_key in fields:
            result[en_key] = fields[de_key]

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
                    # This is a list page - extract first permit's detail link
                    first_row = list_table.find("tr")
                    if first_row:
                        permit_link = first_row.find("a")
                        if permit_link and permit_link.get("href"):
                            detail_url = "https://www.bauaufsicht-frankfurt.de" + permit_link.get("href")
                            # Fetch detail page with longer timeout
                            try:
                                async with session.get(
                                    detail_url,
                                    headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=30, connect=10)
                                ) as detail_resp:
                                    detail_resp.raise_for_status()
                                    detail_html = await detail_resp.text()
                                    parsed = parse_bauschild_html(detail_html)
                                    return parsed if parsed else None
                            except Exception:
                                # Fallback to list summary if detail fetch fails
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

        except asyncio.TimeoutError:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAY * (2 ** attempt)
                await asyncio.sleep(wait)
            continue
        except aiohttp.ClientError:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAY * (2 ** attempt)
                await asyncio.sleep(wait)
            continue
        except Exception:
            return None

    return None
