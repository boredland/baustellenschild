/**
 * A deliberately thin basemap style over basemap.de vector tiles (BKG, CC BY 4.0).
 *
 * The published gray style carries 557 layers of national cartography. This page
 * only needs a cadastral plan to hang parcels on, so the style is written from
 * scratch: paper, hairline streets, flat building blocks, no colour at all —
 * every chromatic pixel on the page belongs to a Bauschild.
 */

const TILES =
  "https://sgx.geodatenzentrum.de/gdz_basemapde_vektor/tiles/v2/bm_web_de_3857/bm_web_de_3857.json";
const GLYPHS =
  "https://sgx.geodatenzentrum.de/gdz_basemapde_vektor/fonts/v2/{fontstack}/{range}.pbf";

const PAPER = "#e9e9e3";
const BLOCK = "#dcdcd4";
const BUILDING = "#cfcfc6";
const WATER = "#d5dbd8";
const GREEN = "#e2e5da";
const HAIRLINE = "#b9bab0";
const INK = "#14140f";

const MAIN_ROADS = [
  "Bundesautobahn",
  "Autobahn",
  "Bundesstraße",
  "Landesstraße, Staatsstraße",
  "Kreisstraße",
];

export const basemap = {
  version: 8,
  name: "Kataster",
  glyphs: GLYPHS,
  sources: {
    bm: {
      type: "vector",
      url: TILES,
      attribution:
        '&copy; <a href="https://basemap.de">basemap.de</a> / BKG (CC BY 4.0) &middot; Flurstücke: Stadtvermessungsamt Frankfurt am Main',
    },
  },
  layers: [
    { id: "paper", type: "background", paint: { "background-color": PAPER } },
    {
      id: "green",
      type: "fill",
      source: "bm",
      "source-layer": "Vegetationsflaeche",
      paint: { "fill-color": GREEN },
    },
    {
      id: "settlement",
      type: "fill",
      source: "bm",
      "source-layer": "Siedlungsflaeche",
      paint: { "fill-color": BLOCK, "fill-opacity": 0.55 },
    },
    {
      id: "water",
      type: "fill",
      source: "bm",
      "source-layer": "Gewaesserflaeche",
      paint: { "fill-color": WATER },
    },
    {
      id: "water-line",
      type: "line",
      source: "bm",
      "source-layer": "Gewaesserlinie",
      paint: { "line-color": WATER, "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.6, 16, 3] },
    },
    {
      id: "rail",
      type: "line",
      source: "bm",
      "source-layer": "Verkehrslinie",
      filter: ["in", "klasse", "Eisenbahn", "S-Bahn", "Gleis", "Straßenbahn", "Stadtbahn"],
      minzoom: 11,
      paint: {
        "line-color": HAIRLINE,
        "line-width": 0.6,
        "line-dasharray": [4, 3],
      },
    },
    {
      id: "street",
      type: "line",
      source: "bm",
      "source-layer": "Verkehrslinie",
      filter: ["!in", "klasse", "Eisenbahn", "S-Bahn", "Gleis", "Straßenbahn", "Stadtbahn", "Fährlinie"],
      minzoom: 12,
      paint: {
        "line-color": "#ffffff",
        "line-width": ["interpolate", ["exponential", 1.6], ["zoom"], 12, 0.8, 15, 3, 18, 14],
      },
    },
    {
      id: "street-casing",
      type: "line",
      source: "bm",
      "source-layer": "Verkehrslinie",
      filter: ["!in", "klasse", "Eisenbahn", "S-Bahn", "Gleis", "Straßenbahn", "Stadtbahn", "Fährlinie"],
      minzoom: 13.5,
      paint: {
        "line-color": HAIRLINE,
        "line-width": 0.5,
        "line-gap-width": ["interpolate", ["exponential", 1.6], ["zoom"], 13.5, 1.6, 18, 14],
        "line-opacity": 0.7,
      },
    },
    {
      id: "trunk",
      type: "line",
      source: "bm",
      "source-layer": "Verkehrslinie",
      filter: ["in", "klasse", ...MAIN_ROADS],
      paint: {
        "line-color": "#ffffff",
        "line-width": ["interpolate", ["exponential", 1.6], ["zoom"], 9, 0.8, 13, 2.6, 18, 18],
      },
    },
    {
      id: "building",
      type: "fill",
      source: "bm",
      "source-layer": "Gebaeudeflaeche",
      minzoom: 14,
      paint: {
        "fill-color": BUILDING,
        "fill-opacity": ["interpolate", ["linear"], ["zoom"], 14, 0, 15.5, 1],
      },
    },
    {
      id: "structure",
      type: "fill",
      source: "bm",
      "source-layer": "Bauwerksflaeche",
      minzoom: 15,
      paint: { "fill-color": BUILDING, "fill-opacity": 0.6 },
    },
    {
      id: "district",
      type: "symbol",
      source: "bm",
      "source-layer": "Name_Punkt",
      filter: ["in", "art", "Stadtteil", "Gemeindeteil", "Wohnplatz"],
      minzoom: 11.5,
      maxzoom: 15,
      layout: {
        "text-field": ["get", "name"],
        "text-font": ["Noto Sans ExtraCondensed Light"],
        "text-size": 11,
        "text-letter-spacing": 0.22,
        "text-transform": "uppercase",
        "text-padding": 14,
      },
      paint: {
        "text-color": INK,
        "text-opacity": 0.5,
        "text-halo-color": PAPER,
        "text-halo-width": 1.4,
      },
    },
    {
      id: "street-label",
      type: "symbol",
      source: "bm",
      "source-layer": "Verkehrslinie",
      filter: ["has", "name"],
      minzoom: 15,
      layout: {
        "text-field": ["get", "name"],
        "text-font": ["Noto Sans ExtraCondensed Light"],
        "symbol-placement": "line",
        "text-size": 10.5,
        "text-letter-spacing": 0.06,
      },
      paint: {
        "text-color": INK,
        "text-opacity": 0.55,
        "text-halo-color": "#ffffff",
        "text-halo-width": 1.6,
      },
    },
  ],
};
