import { Map, NavigationControl, GeolocateControl, setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";
import "./style.css";
import { basemap } from "./basemap.js";
import { signImage } from "./sign-icon.js";
import { renderBoard, renderVacantBoard, renderResults } from "./board.js";

setWorkerUrl(workerUrl);

const FRANKFURT = { center: [8.6821, 50.1109], zoom: 11.6 };
const SIGN_ZOOM = 15;

const map = new Map({
  container: "map",
  style: basemap,
  ...FRANKFURT,
  minZoom: 9.5,
  maxZoom: 19,
  maxBounds: [
    [8.24, 49.88],
    [9.05, 50.36],
  ],
  attributionControl: { compact: true },
  dragRotate: false,
  touchPitch: false,
});

map.addControl(new NavigationControl({ showCompass: false }), "top-right");
map.addControl(
  new GeolocateControl({ trackUserLocation: false }),
  "top-right",
);
map.keyboard.enable();

const board = document.getElementById("board");
const boardFace = document.getElementById("board-face");
const results = document.getElementById("results");
const search = document.getElementById("search");
const tally = document.getElementById("tally");

let sites = [];
let parcels = {};
let selected = null;

const collection = (records) => ({
  type: "FeatureCollection",
  features: records.map((site, index) => ({
    type: "Feature",
    id: index,
    geometry: { type: "Point", coordinates: [site.lon, site.lat] },
    properties: { index, address: site.site_address },
  })),
});

async function load() {
  const [siteData, parcelData] = await Promise.all([
    fetch("/data/sites.json").then((response) => response.json()),
    fetch("/data/parcels.json").then((response) => response.json()),
  ]);

  sites = siteData.sites;
  parcels = parcelData;

  const updated = new Date(siteData.updated).toLocaleDateString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
  tally.textContent = `${siteData.count} Bauschilder · Stand ${updated}`;

  renderVacantBoard(boardFace, siteData.count);
  addLayers();
}

function addLayers() {
  map.addImage("bauschild", signImage(), { pixelRatio: 2 });
  map.addImage("bauschild-selected", signImage({ selected: true }), { pixelRatio: 2 });

  map.addSource("sites", {
    type: "geojson",
    data: collection(sites),
  });

  map.addSource("parcel", {
    type: "geojson",
    data: { type: "FeatureCollection", features: [] },
  });

  map.addLayer({
    id: "parcel-fill",
    type: "fill",
    source: "parcel",
    paint: { "fill-color": "#fcbb0a", "fill-opacity": 0.28 },
  });

  map.addLayer({
    id: "parcel-outline",
    type: "line",
    source: "parcel",
    paint: {
      "line-color": "#14140f",
      "line-width": ["interpolate", ["linear"], ["zoom"], 13, 1, 17, 2],
    },
  });

  // Far out a permit is just a cadastral dot; close in you walk up to the sign.
  map.addLayer({
    id: "sites-dot",
    type: "circle",
    source: "sites",
    maxzoom: SIGN_ZOOM,
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 2.6, 14.9, 5],
      "circle-color": "#14140f",
      "circle-stroke-color": "#efefea",
      "circle-stroke-width": 1,
      "circle-opacity": [
        "case",
        ["boolean", ["feature-state", "muted"], false],
        0.12,
        1,
      ],
      "circle-stroke-opacity": [
        "case",
        ["boolean", ["feature-state", "muted"], false],
        0.12,
        1,
      ],
    },
  });

  map.addLayer({
    id: "sites-sign",
    type: "symbol",
    source: "sites",
    minzoom: SIGN_ZOOM,
    layout: {
      "icon-image": "bauschild",
      "icon-size": ["interpolate", ["linear"], ["zoom"], SIGN_ZOOM, 0.62, 18, 1],
      "icon-anchor": "bottom",
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
    },
    paint: {
      "icon-opacity": [
        "case",
        ["boolean", ["feature-state", "muted"], false],
        0.15,
        1,
      ],
    },
  });

  // The selected permit is always drawn as a sign, at any zoom: picking one is
  // what makes it readable, so it stops being an anonymous dot.
  map.addLayer({
    id: "sites-selected",
    type: "symbol",
    source: "sites",
    filter: ["==", ["get", "index"], -1],
    layout: {
      "icon-image": "bauschild-selected",
      "icon-size": ["interpolate", ["linear"], ["zoom"], 11, 0.7, 16, 1.05],
      "icon-anchor": "bottom",
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
    },
  });

  for (const layer of ["sites-dot", "sites-sign"]) {
    map.on("click", layer, (event) =>
      select(event.features[0].properties.index, { from: "map" }),
    );
    map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
  }
}

function select(index, { from = "list" } = {}) {
  const site = sites[index];
  if (!site) return;

  selected = index;
  renderBoard(boardFace, site);
  board.focus({ preventScroll: true });

  map.setFilter("sites-selected", ["==", ["get", "index"], index]);

  const rings = parcels[site.parcel_key];
  map.getSource("parcel").setData({
    type: "FeatureCollection",
    features: rings
      ? [
          {
            type: "Feature",
            geometry: { type: "Polygon", coordinates: rings },
            properties: {},
          },
        ]
      : [],
  });

  if (from === "list") {
    map.easeTo({
      center: [site.lon, site.lat],
      zoom: Math.max(map.getZoom(), 16.5),
      duration: prefersReducedMotion() ? 0 : 900,
    });
  }

  revealBoard(from);
}

const prefersReducedMotion = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const isNarrow = () => window.matchMedia("(max-width: 56rem)").matches;

/**
 * On a phone the sign is taller than the screen, so it cannot be shown without
 * pushing something away. Tapping a sign in the map keeps a strip of map in
 * view — you should still see where you are; picking from the list does not.
 */
function revealBoard(from) {
  const behavior = prefersReducedMotion() ? "auto" : "smooth";

  if (isNarrow() && from === "map") {
    const top = board.getBoundingClientRect().top + window.scrollY;
    window.scrollTo({ top: top - window.innerHeight * 0.32, behavior });
    return;
  }

  board.scrollIntoView({ behavior, block: "start" });
}

/* Search ------------------------------------------------------------------ */

const haystack = (site) =>
  [
    site.site_address,
    site.builder_name,
    site.architect_name,
    site.site_manager_name,
    site.permit_number,
    site.description,
    site.gemarkung_label,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

let index = null;

function filter(term) {
  const query = term.trim().toLowerCase();

  if (!index) index = sites.map(haystack);

  if (!query) {
    results.hidden = true;
    results.innerHTML = "";
    clearMuting();
    return;
  }

  const matches = [];
  for (let i = 0; i < index.length; i += 1) {
    if (index[i].includes(query)) matches.push(i);
  }

  results.hidden = false;
  renderResults(results, matches, sites);
  muteExcept(matches);
}

function muteExcept(matches) {
  const keep = new Set(matches);
  for (let i = 0; i < sites.length; i += 1) {
    map.setFeatureState({ source: "sites", id: i }, { muted: !keep.has(i) });
  }
}

function clearMuting() {
  map.removeFeatureState({ source: "sites" });
}

let debounce;
search.addEventListener("input", (event) => {
  const term = event.target.value;
  clearTimeout(debounce);
  debounce = setTimeout(() => filter(term), 120);
});

results.addEventListener("click", (event) => {
  const button = event.target.closest("[data-index]");
  if (button) select(Number(button.dataset.index));
});

map.on("load", load);
