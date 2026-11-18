# Antarctic-Ice-Melt
Quick interactive map on Antarctic ice melting.

### 🌍 [Open the live map](https://ajdur96.github.io/Antarctic-Ice-Melt/)

One slider melts the Antarctic ice sheet and shows two things at once: how Antarctica's coastline redraws itself, and how the rising sea floods the Washington, DC metro area.

On a desktop browser the two maps sit side by side; on phones they appear as tabs.

---

## Features

### Antarctica map
- **Melt slider and Play button** – drag from 0 to 100% of the ice volume melted, or press Play to loop through the whole melt with a short pause at the end.
- **Staggered thaw order** – the ice doesn't vanish all at once. Floating ice shelves go first, then low-lying, marine-based and more northerly ice (West Antarctica, the Peninsula, the coasts). The high East Antarctic plateau goes last. Some smooth random variation keeps the melt front natural looking.
- **Land cover tinted by elevation** – grounded ice, floating shelves, exposed rock, newly exposed land, newly flooded areas and ocean depth, all shaded by height or depth with a hillshade.
- **See-through ice** – thinning ice fades so the land or seafloor underneath shows through gradually.
- **Coastlines** – the current coastline in black and today's coastline in orange for comparison.
- **Isostatic rebound** (on by default) – bedrock rises as the weight of the ice is removed.
- **Live stats** – global sea level rise, ice volume remaining, ice-free land, and land and ice now under the sea.
- **Tap or hover anywhere** for latitude/longitude, surface elevation, ice thickness and bedrock height.

### Washington, DC map
- **Driven by the same slider** – Antarctic melt is converted to sea level rise in DC.
- **Gravitational fingerprint** (on by default) – DC gets about 1.25× the global rise, because losing Antarctica's gravitational pull pushes ocean water toward the Northern Hemisphere. Full melt gives about 57 m globally and about 71 m in DC.
- **Connected flooding** – water only spreads into ground connected to the tidal Potomac, the Anacostia or the map edge, so enclosed low spots stay dry until water tops their rim.
- **417,042 building footprints** – each building turns orange, then red, as water climbs its walls and disappears once it is fully submerged. Zoomed out, buildings show as a texture; zoom in to see individual footprints.
- **Flood stats** – land flooded, buildings with water at the walls, buildings fully submerged, developed land lost, forest and wetland lost, plus the top land cover classes under water and submerged buildings by use.
- **Boundaries for orientation** – DC, Maryland and Virginia state lines, plus Arlington, Fairfax, Montgomery and Prince George's counties and the cities of Alexandria, Falls Church and Fairfax.
- **Tap anywhere** to see the water level that floods that spot and the matching percentage of Antarctic ice melted.
- **Lighter mode on phones** – a lower-resolution base image and coarser layers to stay within mobile memory limits.

---

## How it works

**Sea level rise.** Each cell's ice volume above flotation is tracked as it thins. The volume lost is converted to water and spread over the world ocean (3.618 × 10⁸ km²).

**Floating vs. grounded ice.** Ice floats wherever it is too thin to stay grounded below the new sea level.

**Thaw order.** Every 5 km cell gets a score from surface elevation (45%), distance from the South Pole (30%), whether its bed is below sea level (15%) and smooth random noise (8%). Ice shelves are moved to the front of the line. Each cell then thins over its own window covering 35% of the slider.

**Rebound.** Uses full equilibrium rebound (ρ<sub>ice</sub> / ρ<sub>mantle</sub> ≈ 0.28), which in reality takes thousands of years.

**DC flooding.** A "bathtub" model with hydrologic connectivity: for every 10 m cell, the script calculates the lowest water level that can reach it from tidal water or the map edge. A building gets water at its walls when the water reaches its lowest corner, and is fully submerged when water passes its roof (highest ground + FEMA height; 6 m if the height is unknown).

---

## Simplifications

This map is built for show, not as a climate projection.

- The thaw order is an illustrative score, not output from an ice-sheet model.
- Only Antarctic ice is included: no Greenland, mountain glaciers or thermal expansion.
- Ocean density changes and the effect of rebound on sea level are ignored.
- The DC map has no tides, storm surge, erosion or land subsidence. Elevations are NAVD88, roughly today's mean sea level.

---

## Data sources

| Data | Source | Used for |
|---|---|---|
| Bed, surface, ice thickness, ice mask | **Bedmap2** (Fretwell et al., 2013, *The Cryosphere* 7, 375–393), 1 km resampled to 5 km | Antarctica map |
| Elevation | **USGS 3DEP** 1/3 arc-second DEM, 10 m | DC map |
| Land cover | **NLCD 2021**, 30 m (MRLC) | DC map |
| Building footprints | **FEMA / ORNL USA Structures** (Region 3) | DC map |
| State and county boundaries | **US Census TIGER 2010** | DC map |
| Sea-level fingerprint | Mitrovica et al., 2009, *Science* | DC map |

Projections: Antarctic Polar Stereographic (EPSG:3031) for Antarctica, UTM zone 18N (EPSG:26918) for DC.

---

## Repository layout

```
index.html                  The full page (Antarctica data is embedded)
dc/                         DC map data, loaded by index.html
  dc_base.webp              Shaded land-cover base map (10 m)
  dc_base_lite.webp         Same, 20 m, for phones
  dc_flood.txt              Flood level for every 20 m cell (gzip + base64)
  dc_buildings.txt          Packed building footprints (gzip + base64)
  dc_meta.json              Stats tables, boundaries and labels
scripts/
  1_sea_level_curve.py      Antarctica: sea level curve from the 1 km Bedmap2 grids
  2_downsample.py           Antarctica: resample to 5 km and classify cells
  3_thaw_order.py           Antarctica: per-cell thaw order
  4_build_html.py           Build index.html from template.html
  template.html             Page template
  dc/1_flood_levels.py      DC: land cover reprojection and connected flood levels
  dc/2_pack_web_data.py     DC: base images, flood grid, stats and buildings
  dc/3_county_boundaries.py DC: county and city boundaries and labels
  dc/dc_module.js           DC map code inserted into the page
```

## Running it locally

The DC map loads its data from the `dc/` folder, which browsers block when you double-click `index.html`. Serve the folder instead:

```bash
python -m http.server 8000
```

Then open <http://localhost:8000>.

## Rebuilding the data

1. **Antarctica:** download the Bedmap2 binary grids (`bedmap2_bin`) and run `scripts/1_sea_level_curve.py`, `2_downsample.py` and `3_thaw_order.py` in order.
2. **DC:** download the 3DEP DEM, NLCD 2021 and FEMA USA Structures for the area, then run the scripts in `scripts/dc/` in order.
3. Run `scripts/4_build_html.py` to rebuild `index.html`.

Requires Python with `numpy`, `scipy`, `scikit-image`, `rasterio`, `pyproj`, `shapely` and `Pillow`.
