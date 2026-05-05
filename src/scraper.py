import asyncio
from typing import Optional
import aiohttp
from bs4 import BeautifulSoup

BASE_URL = "https://www.bauaufsicht-frankfurt.de"
LIEGENSCHAFT_URL = f"{BASE_URL}/service/bauschild/liegenschaft"

DELAY_MS = 50  # Reduced since we're running concurrently
MAX_CONCURRENT = 10  # Max concurrent requests
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

    for dt in soup.find_all("dt"):
        label = _normalize_field(dt.get_text())
        dd = dt.find_next("dd")
        if label and dd:
            value = _normalize_field(dd.get_text())
            if value:
                fields[label] = value

    if not fields:
        return None

    result = {}
    for de_key, en_key in [
        ("Straße", "street"),
        ("Hausnummer", "house_number"),
        ("Postleitzahl", "postal_code"),
        ("Bauherr", "permit_holder"),
        ("Entwurfsverfasser", "architect"),
        ("Bauleiter", "project_manager"),
        ("Bauvorhaben", "description"),
        ("Aktenzeichen", "permit_number"),
        ("Datum", "permit_date"),
        ("Behörde", "authority"),
    ]:
        if de_key in fields:
            result[en_key] = fields[de_key]

    return result if result else None


async def scrape_liegenschaft_async(
    session: aiohttp.ClientSession, gemarkung_id: int, flur: str, flurstueck: str
) -> Optional[dict]:
    """Async scraper for a single parcel with retries."""
    await asyncio.sleep(DELAY_MS / 1000)

    payload = {
        "tx_vierwdbafinfothek_constructionsign[GEMARK]": str(gemarkung_id),
        "tx_vierwdbafinfothek_constructionsign[FLUR]": flur,
        "tx_vierwdbafinfothek_constructionsign[FLST_ZAE;FLST_NEN]": flurstueck,
        "tx_vierwdbafinfothek_constructionsign[bauschild]": "1",
    }

    for attempt in range(MAX_RETRIES):
        try:
            async with session.post(LIEGENSCHAFT_URL, data=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status()
                html = await resp.text()
                parsed = parse_bauschild_html(html)
                if parsed:
                    parsed["raw_html"] = html
                return parsed
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
