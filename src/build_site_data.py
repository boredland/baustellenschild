"""Build the map payload for bauschild.jonas-strassel.de.

Every Bauschild carries the parcel it stands on (Gemarkung / Flur / Flurstueck).
That triple is resolved against Frankfurt's official ALKIS parcel service —
https://geowebdienste.frankfurt.de/SGK_Flurstuecke, the same one the city's
Geoportal uses — so positions come from the cadastre itself rather than from
geocoding a street address.

Output (``web/public/data/``):
  sites.json    one record per permit, with a marker point
  parcels.json  parcel outlines keyed by Flurstueckskennzeichen
"""

import json
import re
import sys
import time
import urllib.error
import urllib.request
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITES = ROOT / "data" / "baustellen.json"
OUT = ROOT / "web" / "public" / "data"

WFS = "https://geowebdienste.frankfurt.de/SGK_Flurstuecke"
TYPE_NAME = "Amt62_Flurstuecke:Flurstueck"
BATCH_SIZE = 200
PRECISION = 6

# The service answers 503 for minutes at a time. Four attempts spend at most
# ~105s on a batch, which outlasts the short outages; a batch still failing
# after that is the service being down, not the batch being bad.
ATTEMPTS = 4
BACKOFF = 15

# Some parcels are genuinely absent from ALKIS — the register lags splits and
# demolitions — but a run that loses a twentieth of the city has lost the
# service, not the parcels.
MIN_RESOLVED = 0.95

PARCEL_INFO = re.compile(r"^.*?\((\d+)\)\s*,\s*([^,]+),\s*(.+)$")
PARCEL_NUMBER = re.compile(r"^(\d+)\s*/?\s*(\d*)$")

SITE_FIELDS = (
    "permit_number",
    "description",
    "site_address",
    "parcel_info",
    "builder_name",
    "builder_address",
    "builder_location",
    "represented_by",
    "architect_name",
    "architect_address",
    "architect_location",
    "site_manager_name",
    "site_manager_address",
    "site_manager_location",
    "gemarkung_label",
    "url",
)

TRANSIENT = (urllib.error.URLError, TimeoutError, json.JSONDecodeError)


def parcel_id(parcel_info: str) -> tuple[str, str, str, str] | None:
    """Split ``… (478), 414, 67/1`` into Gemarkung, Flur, Zaehler, Nenner."""
    match = PARCEL_INFO.match(parcel_info.strip())
    if not match:
        return None
    gemarkung, flur, number = match.groups()
    parts = PARCEL_NUMBER.match(number.strip())
    if not parts:
        return None
    return (
        f"{int(gemarkung):04d}",
        str(int(flur)),
        str(int(parts.group(1))),
        parts.group(2),
    )


def parcel_key(parcel: tuple[str, str, str, str]) -> str:
    """ALKIS Flurstueckskennzeichen: 06 GMK(4) FLN(3) ZAE(5) NEN(4) __.

    A parcel carrying no Nenner pads that field with underscores, not zeros.
    """
    gemarkung, flur, zaehler, nenner = parcel
    nenner_field = f"{int(nenner):04d}" if nenner else "____"
    return f"06{gemarkung}{int(flur):03d}{int(zaehler):05d}{nenner_field}__"


def post(query_body: str) -> list[dict]:
    """POST rather than GET: a few hundred keys overflow the server's URI limit."""
    body = (
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs/2.0"'
        ' xmlns:fes="http://www.opengis.net/fes/2.0" service="WFS" version="2.0.0"'
        ' outputFormat="GEOJSON" srsName="EPSG:4326">'
        f'<wfs:Query typeNames="{TYPE_NAME}">{query_body}</wfs:Query>'
        "</wfs:GetFeature>"
    )
    request = urllib.request.Request(
        WFS, data=body.encode(), headers={"Content-Type": "text/xml"}
    )
    for attempt in range(ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)["features"]
        except TRANSIENT as exc:
            if attempt == ATTEMPTS - 1:
                raise
            delay = BACKOFF * 2**attempt
            print(f"! {exc}; retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)


def equals(field: str, value: str) -> str:
    return (
        f"<fes:PropertyIsEqualTo><fes:ValueReference>{field}</fes:ValueReference>"
        f"<fes:Literal>{value}</fes:Literal></fes:PropertyIsEqualTo>"
    )


def fetch_by_key(keys: list[str]) -> list[dict]:
    clauses = "".join(equals("FSK", key) for key in keys)
    return post(f"<fes:Filter><fes:Or>{clauses}</fes:Or></fes:Filter>")


def fetch_by_number(parcels: list[tuple[str, str, str, str]]) -> list[dict]:
    """Drop the Nenner: the permit register lags ALKIS on parcel splits."""
    clauses = "".join(
        "<fes:And>"
        + equals("GMK", gemarkung)
        + equals("FLN", flur)
        + equals("ZAE", zaehler)
        + "</fes:And>"
        for gemarkung, flur, zaehler, _ in parcels
    )
    return post(f"<fes:Filter><fes:Or>{clauses}</fes:Or></fes:Filter>")


def batched(items: list, size: int = BATCH_SIZE):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def resolve(parcels: list[tuple[str, str, str, str]]) -> dict[tuple, dict]:
    """Raises on a batch that outlasts its retries: that is the service, not one query."""
    by_key = {parcel_key(parcel): parcel for parcel in parcels}
    resolved: dict[tuple, dict] = {}

    for batch in batched(sorted(by_key)):
        for feature in fetch_by_key(batch):
            resolved[by_key[feature["properties"]["FSK"]]] = feature

    retry = [parcel for parcel in parcels if parcel not in resolved]
    by_number = {parcel[:3]: parcel for parcel in retry}
    for batch in batched(retry):
        for feature in fetch_by_number(batch):
            properties = feature["properties"]
            number = (
                properties["GMK"],
                str(int(properties["FLN"])),
                str(int(properties["ZAE"])),
            )
            parcel = by_number.get(number)
            if parcel and parcel not in resolved:
                resolved[parcel] = feature

    print(f"resolved {len(resolved)}/{len(parcels)} parcels ({len(retry)} needed retry)")
    return resolved


def outer_rings(geometry: dict) -> list[list[list[float]]]:
    if geometry["type"] == "MultiPolygon":
        return [polygon[0] for polygon in geometry["coordinates"]]
    return [geometry["coordinates"][0]]


def centroid(geometry: dict) -> tuple[float, float]:
    """Area-weighted centroid over the outer rings of a (Multi)Polygon.

    The shoelace terms are taken about the first vertex. In raw WGS84 a city
    parcel is a handful of metres wide around 8.7E/50.1N, so ``x0*y1 - x1*y0``
    subtracts two numbers agreeing to fifteen digits and keeps almost none of
    them; markers then land hundreds of metres to kilometres off their parcel.
    Subtracting the origin first makes the coordinates small, and the terms
    significant.
    """
    rings = outer_rings(geometry)
    origin_x, origin_y = rings[0][0]
    twice_area = sum_x = sum_y = 0.0

    for ring in rings:
        for (px0, py0), (px1, py1) in pairwise(ring):
            x0, y0 = px0 - origin_x, py0 - origin_y
            x1, y1 = px1 - origin_x, py1 - origin_y
            cross = x0 * y1 - x1 * y0
            twice_area += cross
            sum_x += (x0 + x1) * cross
            sum_y += (y0 + y1) * cross

    if twice_area == 0:
        points = [point for ring in rings for point in ring]
        return (
            sum(p[0] for p in points) / len(points),
            sum(p[1] for p in points) / len(points),
        )
    return (
        sum_x / (3 * twice_area) + origin_x,
        sum_y / (3 * twice_area) + origin_y,
    )


def rounded_rings(geometry: dict) -> list[list[list[float]]]:
    return [
        [[round(x, PRECISION), round(y, PRECISION)] for x, y in ring]
        for ring in outer_rings(geometry)
    ]


def clean(value):
    return value.replace("\xa0", " ").strip() if isinstance(value, str) else value


def main() -> None:
    source = json.loads(SITES.read_text())
    sites = source["sites"]

    keyed: dict[tuple, list[dict]] = {}
    for site in sites:
        parcel = parcel_id(site["parcel_info"])
        if parcel:
            keyed.setdefault(parcel, []).append(site)
        else:
            print(f"! unparseable parcel: {site['parcel_info']}", file=sys.stderr)

    # A payload built without the cadastre carries no parcels at all, and the map
    # it publishes is empty. The one already on disk is a better answer than that,
    # so leave it and fail the run.
    try:
        resolved = resolve(list(keyed))
    except TRANSIENT as exc:
        sys.exit(f"! ALKIS unreachable ({exc}); keeping the payload already on disk")

    if len(resolved) < len(keyed) * MIN_RESOLVED:
        sys.exit(
            f"! only {len(resolved)}/{len(keyed)} parcels resolved; "
            "keeping the payload already on disk"
        )

    records = []
    parcels: dict[str, list] = {}
    unresolved = []

    for parcel, matches in keyed.items():
        feature = resolved.get(parcel)
        if not feature:
            unresolved.append(matches[0]["parcel_info"])
            continue

        key = feature["properties"]["FSK"]
        parcels.setdefault(key, rounded_rings(feature["geometry"]))
        lon, lat = centroid(feature["geometry"])

        for site in matches:
            record = {field: clean(site.get(field)) for field in SITE_FIELDS}
            record = {k: v for k, v in record.items() if v}
            record["lon"] = round(lon, PRECISION)
            record["lat"] = round(lat, PRECISION)
            record["parcel_key"] = key
            area = feature["properties"].get("AFL")
            if area:
                record["parcel_area"] = round(area)
            records.append(record)

    records.sort(key=lambda r: (r["site_address"], r["permit_number"]))

    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated": source["meta"]["last_updated"],
        "count": len(records),
        "sites": records,
    }
    write(OUT / "sites.json", payload)
    write(OUT / "parcels.json", parcels)

    print(f"{len(records)} sites, {len(parcels)} parcels, {len(unresolved)} unresolved")
    if unresolved:
        print("  " + "; ".join(unresolved[:20]))


def write(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1024:.0f} kB)")


if __name__ == "__main__":
    main()
