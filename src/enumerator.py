from typing import Iterator

GEMARKUNGEN = list(range(460, 519))


def enumerate_all_parcels() -> Iterator[tuple[int, str, str]]:
    """Enumerate parcels by brute-force POST to liegenschaft form.

    Most combinations won't have a Bauschild, but the ones that do will be returned.
    This is faster than trying to use the autocomplete API which requires session state.
    Ranges are tuned to cover likely parcels while keeping the crawl duration manageable.
    """
    for gemark in GEMARKUNGEN:
        for flur in range(1, 70):
            for flst_num in range(1, 300):
                for flst_den in range(1, 8):
                    flurstueck = f"{flst_num}/{flst_den}"
                    yield (gemark, str(flur), flurstueck)


def enumerate_test() -> Iterator[tuple[int, str, str]]:
    """Quick test: just Gemarkung 460, limited ranges."""
    gemark = 460
    for flur in range(1, 6):
        for flst_num in range(1, 30):
            for flst_den in range(1, 4):
                flurstueck = f"{flst_num}/{flst_den}"
                yield (gemark, str(flur), flurstueck)
