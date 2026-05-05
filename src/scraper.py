import time
from typing import Optional
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.bauaufsicht-frankfurt.de"
LIEGENSCHAFT_URL = f"{BASE_URL}/service/bauschild/liegenschaft"

DELAY_MS = 100  # 100ms between requests, more aggressive


def _sleep():
    time.sleep(DELAY_MS / 1000)


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


def scrape_liegenschaft(
    session: requests.Session, gemarkung_id: int, flur: str, flurstueck: str
) -> Optional[dict]:
    _sleep()

    payload = {
        "tx_vierwdbafinfothek_constructionsign[GEMARK]": str(gemarkung_id),
        "tx_vierwdbafinfothek_constructionsign[FLUR]": flur,
        "tx_vierwdbafinfothek_constructionsign[FLST_ZAE;FLST_NEN]": flurstueck,
        "tx_vierwdbafinfothek_constructionsign[bauschild]": "1",
    }

    resp = session.post(LIEGENSCHAFT_URL, data=payload)
    resp.raise_for_status()

    parsed = parse_bauschild_html(resp.text)
    if parsed:
        parsed["raw_html"] = resp.text
    return parsed
