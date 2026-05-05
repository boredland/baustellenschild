#!/usr/bin/env python3
"""Debug crawler to save sample responses for parser inspection."""
import requests
from pathlib import Path

session = requests.Session()
session.headers.update({
    "User-Agent": "Frankfurt-Bauschild-Crawler/1.0 (debug)"
})

BASE_URL = "https://www.bauaufsicht-frankfurt.de/service/bauschild/liegenschaft"
DEBUG_DIR = Path("debug_responses")
DEBUG_DIR.mkdir(exist_ok=True)

# Try a few sample parcels
samples = [
    (460, "1", "1/1"),
    (460, "1", "6/3"),  # This one was in the Playwright output
    (460, "1", "11/1"),
    (460, "2", "1/1"),
]

for i, (gemark, flur, flst) in enumerate(samples):
    payload = {
        "tx_vierwdbafinfothek_constructionsign[GEMARK]": str(gemark),
        "tx_vierwdbafinfothek_constructionsign[FLUR]": flur,
        "tx_vierwdbafinfothek_constructionsign[FLST_ZAE;FLST_NEN]": flst,
        "tx_vierwdbafinfothek_constructionsign[bauschild]": "1",
    }

    print(f"[{i+1}] Fetching {gemark}/{flur}/{flst}...")
    resp = session.post(BASE_URL, data=payload)

    filename = DEBUG_DIR / f"{gemark}_{flur}_{flst.replace('/', '-')}.html"
    filename.write_text(resp.text, encoding="utf-8")
    print(f"  Saved: {filename}")

print(f"\nDebug responses saved to {DEBUG_DIR}/")
print("Inspect these HTML files to understand the page structure and fix the parser.")
