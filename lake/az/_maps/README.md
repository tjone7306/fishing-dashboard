# Lake map generator

Run: `python3 gen_lake_maps.py geo levels.json <outdir>` (needs `pip install shapely`).
levels.json is built by the lake-report-v2 scheduled task from live CAP/SRP/USACE values.
Each lake's map.svg is written to lake/az/<lake>/map.svg. Markers are verified to sit inside the current waterline.
nws_grids.json holds each lake's NWS gridpoint for localized forecasts.
