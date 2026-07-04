---
name: lake-report-v2
description: Twice-daily Phoenix fishing dashboard refresh at b4u.fish (6 AM and 5 PM Phoenix). Pulls SRP/DWR, NWS Phoenix, USNO solunar, KPHX METAR, and CAP Lake Pleasant; pushes index.html to Tjone7306/fishing-dashboard main; Netlify auto-deploys.
---

Refresh the Phoenix fishing dashboard hosted at https://b4u.fish.

**Hosting:** Netlify project `b4u-fish` (team `AZWEB`). Push commits to GitHub `main`; Netlify auto-deploys within ~30 seconds. Do NOT touch GitHub Pages settings; the custom-domain CNAME file was intentionally removed during the migration.

Source of truth: GitHub repo `Tjone7306/fishing-dashboard`, branch `main`, file `index.html`.

**HARD RULE — NEVER FABRICATE.** If a data point cannot be retrieved, write `null` (or `NA` for visible UI fields). Never guess, never use stale values, never invent numbers. Missing-ness is information — preserve it.

**Authentication (already set up, headless):**
`GITHUB_TOKEN=[REDACTED in this copy — live fine-grained PAT; see the original at ~/Documents/Claude/Scheduled/lake-report-v2/SKILL.md]`

This is a fine-grained PAT scoped to `Tjone7306/fishing-dashboard` only (Contents: Read/Write, Metadata: Read). Check expiration at https://github.com/settings/personal-access-tokens and rotate before then. If you get 401 "Bad credentials", the token has expired and Tim needs to generate a new one.

---

## Step 1 — Pull the current index.html from GitHub

```bash
SESSION_DIR="$(ls -d /sessions/*/mnt/outputs 2>/dev/null | head -1)"
[ -z "$SESSION_DIR" ] && SESSION_DIR="/tmp"
mkdir -p "$SESSION_DIR/work/raw"

RESP=$(curl -sS \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/Tjone7306/fishing-dashboard/contents/index.html?ref=main")

echo "$RESP" | python3 -c "
import sys, json, base64, pathlib
d = json.load(sys.stdin)
pathlib.Path('$SESSION_DIR/work/index.html').write_bytes(base64.b64decode(d['content']))
pathlib.Path('$SESSION_DIR/work/.sha').write_text(d['sha'])
print('sha:', d['sha'], 'bytes:', len(base64.b64decode(d['content'])))
"
```

---

## Step 2 — Gather live data

Phoenix is MST year-round (UTC-7, no DST).

### 2a. SRP lake levels and river flows
Source: `https://streamflow.watershedconnection.com/dwr`

For each reservoir (Roosevelt, Apache, Canyon, Saguaro, Bartlett, Horseshoe), parse:
- `% full`, `elevation (ft)`, `storage (acre-ft)`, `below full (ft)`, change vs yesterday (AF)

Streamflow rows: Salt River at Roosevelt, Tonto Creek, Verde at Tangle, Bartlett release, Saguaro release, Horseshoe release (all cfs).

**ALSO PARSE THE REPORT DATE.** The HTML contains `var reportDate = 'MM DD, YYYY'`. Capture this — you'll need it in Step 3 to stamp the SRP lake cards with their data freshness.

If today shows `n/r` across the board, fall back to the most recent reported day and note the date. If a single field is `n/r` but others aren't, write `NA` for that field only. SRP data often isn't published for the current day before ~4 PM MST — the 6 AM run will usually fall back to the previous day.

### 2b. Lake Pleasant (CAP — separate system)
Source: `https://azr-prod-rsg-dmz-app-waterqualityweb.azurewebsites.net/api/opslakepleasant`

Returns JSON with `LP_Elev`, `LP_Volume` (AF), `LP_PercentFull`, `LP_SurfaceArea` (acres), `PP_Flow` (canal pump flow into the lake, cfs), `RiverOutletFlow` (Agua Fria release, cfs), `RecordTime` (ISO 8601, Phoenix local time, no offset — treat as MST). Updated every ~15 minutes. Full pool elevation is 1,702 ft.

**Capture `RecordTime`** — you'll stamp the Pleasant lake card with this in Step 3.

### 2c. Weather (NWS gridpoint forecast, Phoenix)
- Office: `PSR`, grid: `165,59`
- Daily: `https://api.weather.gov/gridpoints/PSR/165,59/forecast`
- Hourly: `https://api.weather.gov/gridpoints/PSR/165,59/forecast/hourly`
- Raw grid (for cloud cover): `https://api.weather.gov/gridpoints/PSR/165,59` — read `skyCover` for cloud %
- For hours of today already in the past, prefer KPHX METAR observations for temp/wind over carrying forward NWS forecast values

### 2d. Moon + solunar (USNO)
Fetch 7 days — TODAY + 6 forward days:

```
https://aa.usno.navy.mil/api/rstt/oneday?date=YYYY-MM-DD&coords=33.45,-112.07&tz=-7
```

Record per day: `sunrise`, `sunset`, `moonrise`, `moonset`, `upper_transit`, `lower_transit`, `phase`, `illum_pct`. If a day's Upper Transit is missing (happens monthly when transit falls on a day boundary), derive `lower_transit` from neighbor days ± 12 h.

### 2e. Barometric pressure (KPHX METAR, 30 h history)
`https://aviationweather.gov/api/data/metar?ids=KPHX&format=raw&hours=30`

- `now_inhg` = altimeter from most recent METAR (`A2995` → `29.95`)
- `trend_6h_inhg` = `now_inhg` − altimeter ~6 h ago
- `trend_24h_inhg` = same vs ~24 h ago
- `trend_label`: `falling-fast` (≤−0.05), `falling` (−0.05..−0.01), `stable` (−0.01..0.01), `rising` (0.01..0.05), `rising-fast` (>0.05)

### 2f. Local tournaments (per-lake `🏆` badges)

Scrape three Arizona bass-club calendars and extract every 2026 tournament held on one of the six dashboard lakes (Pleasant, Roosevelt, Apache, Canyon, Saguaro, Bartlett). These feed the per-lake `🏆` badge on each lake card and update via this task. All three are server-rendered HTML — plain `curl` works; save raw responses to `raw/`.

- **Midweek Bass Anglers** (Tim's club) — `https://midweekbassaz.com/midweek-bass-club-tournament-schedule-2026` — rows like `June 17, Pleasant SL to 11:00 a.m.` → format `Month D, Lake SL to <end>`. Series label `Midweek Bass`.
- **Roostertales Bass Club** — `https://roostertalesbassclub.com/my-calendar/` — rows like `Bartlett Lake June 20th 2026 (4am-11am)` → format `Lake … Month Dth 2026 (window)`. Series `Roostertales`.
- **Weekend Warrior** (SW Custom Tackle) — `https://swctackle.com/ww-arizona-region` — rows like `06 / 20 / 26- Bartlett Lake` → format `MM / DD / YY- Lake`. A `TBD` on the row → set `"tbd": true`. Series `Weekend Warrior`.

Parsing rules:
- Match ONLY the six dashboard lakes; ignore Havasu, Alamo, Martinez, Parker, Mead, Mohave, Powell, etc.
- Convert every date to ISO `YYYY-MM-DD`. Multi-day events (e.g. `Apache Nov 17 & 18`) → use the first day and set `"multiday":"17–18"` (U+2013 en dash).
- Capture an end time if present as `"end"` (e.g. `11:00a`, `3:00p`).
- Keep only events with `date >= today` (Phoenix). De-dupe identical (lake, date, series).
- **NEVER FABRICATE.** If a source is unreachable or yields no parseable rows, SKIP it and keep whatever the other sources returned. If ALL THREE fail, leave the existing `tournaments-data` block in `index.html` unchanged (re-use the current one).
- AKBA (kayak) events are not scraped (no stable calendar page); if a known AKBA event already sits in the current block and is still future, preserve it.

Group by lake into the Step 3d schema. The page JS auto-selects the next upcoming event per lake and flags any within 7 days as `soon` — no per-card HTML edits needed beyond writing the data block.

Save every raw API response to `$SESSION_DIR/work/raw/` for debugging.

### 2g. Copperstate Tackle sale bubble (`copperstate-sale.json`)

Detect whether Copperstate Tackle (a local Chandler, AZ shop) is currently running a **store-wide percent-off sale**, and keep `copperstate-sale.json` in this repo in sync. A shared widget (`cst-sale-bubble.js`) on b4u.fish and b4ufish.com reads that JSON and shows a small badge only while a sale is live.

**Manual-override check FIRST.** Fetch the current `copperstate-sale.json` from the repo.
- If it has `"manual": true` AND today (Phoenix) is on/before its `end` date → Tim set it by hand for a known sale; **leave it unchanged** (skip the rest of 2g and Step 4b).
- If it has `"manual": true` AND today is **past** `end` → the manual sale is over: write `{"active": false, ...}` WITHOUT the `manual` flag (this hands control back to auto-detection) and continue.
- Otherwise (`manual` absent/false) → auto-detect as below.

**The sale is posted as a banner IMAGE, not text.** Copperstate's homepage hero is a Shopify slideshow; their holiday sale (e.g. "4TH OF JULY SALE 20% OFF, JUNE 29 – JULY 6") is a slide *image* with no readable alt text or price in the HTML. A plain `curl` text grep CANNOT see it. You must look at the actual slide images:

1. Open `https://copperstatetackle.com/` in the browser tools (Claude-in-Chrome). A "10% off / Limited Time" email-signup popup appears on top — close it (click its ✕) so it isn't covering the hero. (The 10%-off popup is a permanent email-capture offer — it is NOT a sale and must never trigger the badge.)
2. Enumerate the hero slideshow slide image URLs, e.g. run in the page:
   ```js
   Array.from(document.querySelectorAll('[class*="slideshow"] img,[class*="slider"] img,[class*="banner"] img'))
     .map(i=>(i.currentSrc||i.src).split('?')[0]).filter((v,j,a)=>a.indexOf(v)===j)
   ```
3. **View each slide image** (navigate the tab to the image URL and screenshot, or otherwise inspect it visually). Look for a promotional graphic advertising a store-wide percent-off sale.

   *Browser-free fallback:* the slideshow `<img>` tags are in the server HTML too, so if Chrome isn't available you can still get the slide image URLs with `curl -sSL https://copperstatetackle.com/ | grep -oE 'cdn/shop/files/[^"?]+\.(png|jpg|webp)'`, then view those images directly with your own vision. Either path works — the point is you must *look at the image*, not grep text.

Decide:

- **`active`** — `true` ONLY if there is a clear **store-wide / sitewide percent-off promotion** (e.g. "20% OFF EVERYTHING", "SITEWIDE 20% OFF — JULY 4TH", a discount code like "JULY20"). Do NOT trigger on: free-shipping offers, "World's Largest 6th Sense Dealer", individual product sale prices, or a single brand/category markdown. When in doubt, `active=false`.
- **`percent`** — the integer percent off (e.g. `20`). Null if active but no percent is stated.
- **`headline`** — short occasion label for the badge, e.g. `"Fourth of July Sale"`, `"Memorial Day Sale"`, `"Labor Day Sale"`. Keep it under ~28 chars. Null if none.
- **`end`** — sale end date as `YYYY-MM-DD` (Phoenix local). Read it off the banner graphic if a range is shown (e.g. "JUNE 29 – JULY 6" → end `2026-07-06`; use the LATER date). Note their banners sometimes have a typo in the start month — trust the end date and the holiday. If no end is shown, infer the holiday weekend (e.g. through the Sunday/Monday after the 4th) or set `null` (then the bubble stays up on a presence basis and clears the next run after the sale slide is gone).
- **`updated`** — today's Phoenix date `YYYY-MM-DD`.
- **`url`** — keep `"https://copperstatetackle.com"`.

**HARD RULE — same as the rest of this task: never fabricate.** Base the decision only on what you actually see on their site this run. If the browser tools are unavailable or the page won't load, leave `copperstate-sale.json` UNCHANGED (skip the push) — never invent a sale, and never turn off an existing sale just because you couldn't check. Only set `active:false` when you have actually looked and confirmed no sale graphic is present.

Write the result to `$SESSION_DIR/work/copperstate-sale.json`, e.g. an active example:

```json
{ "active": true, "percent": 20, "headline": "Fourth of July Sale", "holiday": "Fourth of July",
  "end": "2026-07-07", "url": "https://copperstatetackle.com", "updated": "2026-07-02" }
```

…or inactive: `{ "active": false, "percent": null, "headline": null, "holiday": null, "end": null, "url": "https://copperstatetackle.com", "updated": "<today>" }`

This file is pushed in Step 4b. It is independent of `index.html` — a failure here must NEVER block the dashboard refresh.

---

## Step 3 — Apply edits to the working index.html

Open `$SESSION_DIR/work/index.html` and replace:

1. **Date pill** (`id="date-badge"`): `<Day>, <Month> <D>, <YYYY>` in Phoenix local time.
2. **"Last updated"** (`<div class="updated">` block): `<Day>, <Month> <D>, <YYYY> at <H:MM> AM/PM MST`.
3. **Lake cards** (`<details data-lake="pleasant|roosevelt|apache|canyon|saguaro|bartlett">`):
   - `<span class="lk-pct ...">XX%</span>` — % full + tier class (`good` / `warn` / `bad` / `na`)
   - `<span class="lk-elev"><b>X,XXX.XX</b> ft · −Y.YY</span>` — use U+2212 minus
   - `<div class="bar"><i class="..." style="width:XX%"></i></div>`
   - `<div class="row"><span class="k">Storage</span><span class="v">XXX,XXX AF</span></div>`
   - Inflow `<span data-snap-cfs-in>NN</span>` (`class="sf-na">NA</span>` for unknown; `SRP` for managed; for Pleasant, `PP_Flow`)
   - Outflow `<span data-snap-cfs-out>NN</span>` (for Pleasant, `RiverOutletFlow`)
   - `data-surface="X,XXX.XX"` (matches elev)
   - **DATA FRESHNESS BADGE** — see Step 3a below
4. **Watershed schematic SVG** — viewBox `0 0 750 620` with three columns: Salt (x=120), Verde (x=375), CAP/Pleasant (x=630). Each tank has a `<text class="reservoir-label" y="-6">` with the lake's name. Update pct/sub/flow labels. Recompute tank fill: rim height H → fill `y = H*(1-pct/100)`, `height = H*pct/100`. Fill class: `waterFill` (pct≥70), `waterFillWarn` (50-69), `waterFillBad` (<50).
5. **Watershed system summary stats** (`.ws-summary`): system storage + delta, % fill + delta vs year-ago, total inflow + delta vs yesterday, total release + delta vs yesterday.
6. **Hourly summary chips** (`.hour-summary`): today's `Hi`, `Lo`, `Wind`, cloud %.
7. **SVG hourly graph** (`svg.hour-graph`, now inside the hero at `id="hero-hourly"` — there is NO standalone "Today's Hourly" card anymore). Regenerate the temp curve path/polyline, the y-axis labels, and BOTH callouts. **Preserve the callout styling — do NOT revert it:** the high-temp dot+label must keep `class="hg-dot hg-hi"` / `class="hg-lbl hg-hi-t"` (red, via CSS) and the low dot+label `class="hg-dot hg-lo"` / `class="hg-lbl hg-lo-t"` (blue, via CSS). Colors and the `hgthump` heartbeat animation live in CSS classes — only update the numbers (`109° · 5 PM`, `Lo 93°`), the x/y coordinates, and font sizes (high label `font-size="25"`, low label `font-size="21"`). Never put inline `fill="#ffffff"` back on these — that removes the red/blue convention.
8. **"Best fishing times" 4 tiles** (`.sol-card .sol-grid`): two Major (overhead/underfoot, ±1h) and two Minor (moonrise/moonset, ±1h).
9. **Bite Score data block** (`<script id="bs-data" type="application/json">`) — see 3b.
10. **Tournaments data block** (`<script id="tournaments-data" type="application/json">`) — see 3d. Replace the JSON between the script tags with freshly scraped events from Step 2f. The injector JS (already in the page) renders the per-lake badges from it; do not edit individual lake cards for this.

### Step 3a — Lake data freshness badges (per-card)

Each lake card's `<summary>` contains a span like:
```html
<span class="lk-name">Roosevelt <span class="pill bad">Low</span> <span class="lk-asof CLASS" data-asof-source="srp">TEXT</span><span class="dist" data-dist></span></span>
```

You MUST update `CLASS` and `TEXT` to reflect the freshness of THIS lake's data.

**For SRP lakes** (Roosevelt, Apache, Canyon, Saguaro, Bartlett, Horseshoe):
- Compare DWR `reportDate` (parsed in Step 2a) to today's Phoenix date.
- `data-asof-source="srp"`
- TEXT format: `data M/D · Nd old` (or `· today`, `· 1d old`)
- CLASS by age:
  - 0 days old → `fresh`
  - 1 day old → `ok` (normal — SRP is typically day-delayed)
  - 2 days old → `warn`
  - 3+ days old → `bad`

**For Pleasant**:
- Use CAP `RecordTime` minus current time.
- `data-asof-source="cap"`
- TEXT format:
  - <30 min old → `live H:MM AM/PM`
  - <2 h old → `updated H:MM AM/PM`
  - <24 h old → `Nh old · H:MM AM/PM`
  - ≥24 h old → `Nd old · H:MM AM/PM`
- CLASS by age:
  - <30 min → `fresh`
  - <2 h → `ok`
  - <24 h → `warn`
  - ≥24 h → `bad`

If an `<span class="lk-asof ...">` element does not yet exist in a lake card (rare — only if the file was hand-edited), inject one immediately before the `<span class="dist" data-dist>` span inside `<span class="lk-name">`.

CSS for these badges is already in the file (`.lk-asof`, `.lk-asof.fresh|.ok|.warn|.bad`). Do not modify the CSS unless adding new states.

### Step 3b — Bite Score data block schema (v2)

```json
{
  "generated": "<ISO 8601 with -07:00 offset>",
  "version": 2,
  "today_date": "YYYY-MM-DD",
  "baro_now": {
    "now_inhg": 29.84,
    "trend_6h_inhg": -0.05,
    "trend_24h_inhg": 0.07,
    "trend_label": "falling-fast"
  },
  "today_hourly": [
    { "h": 6, "temp": 60, "wind_mph": 3, "wind_dir": "WSW", "cloud_pct": 30 },
    ... 18 entries (h = 6..23) ...
  ],
  "by_day": [
    {
      "date": "YYYY-MM-DD", "label": "Sun", "is_today": true,
      "high_f": 78, "low_f": 54, "wind_dir": "WSW", "wind_mph": 10,
      "cloud_pct_avg": 40, "narrative": "Sunny then partly cloudy",
      "moon_phase": "Waxing Gibbous", "moon_illum_pct": 77,
      "moon_upper": "21:10", "moon_lower": "09:10",
      "moonrise": "14:41", "moonset": "03:04",
      "sunrise": "05:45", "sunset": "19:07",
      "press_label": "falling-moderate",
      "press_context": "falling, no front yet",
      "front_phase": "stable",
      "score": 76, "tier": "good", "verdict": "Solid bite",
      "best_window": "7:00 PM – 10:00 PM",
      "reason": "Falling pressure + dusk overhead transit"
    },
    ... 6 more entries (today + 6) ...
  ]
}
```

- All times Phoenix local (24-hour, MST).
- `by_day` is TODAY + 6 forward days.
- `cloud_pct` uses NWS raw-grid `skyCover` (not `probabilityOfPrecipitation`).
- For past hours of today, prefer KPHX METAR for `temp` and `wind_mph`.

### Step 3c — Bite Score algorithm (5 factors, cap at 100)

Tiers: 85+ peak, 70+ good, 55+ fair, 35+ tough, < 35 skip.

| Factor | Weight | Rule |
|---|---|---|
| Pressure (trend + front) | 25 | Trend 6h: ≤−0.05 = 18; <−0.01 = 15; ±0.005 = 9; ≤+0.05 = 5; >+0.05 = 0. Front: pre-front = +7; stable >48h = +3; day-of-front = 0; post-front +1d = −5; +2d = −2. |
| Moon & solunar | 20 | Phase: ±2d New/Full = 10; ±4d = 8; quarter ±2d = 4; else = 6. Transit: 1 fishable (5 AM–10 PM) = +6; both + dawn/dusk = +10; neither = +2. |
| Wind | 15 | Dir: WSW/SW/SSW/W/S = +6; SE/NW = +4; N = +2; NE/E/ESE = −1. Speed: 6–15 = +9; 4–5 or 16–20 = +6; 0–3 = +3; >20 = 0. |
| Cloud cover | 15 | 60–100% = 9; 30–60% = 7; 10–30% = 5; 0–10% = 3. + dawn/dusk window (±90 min of sunrise/sunset) = +5. |
| Water-temp species fit | 15 | Surface ≈ air − 8 °F. Largemouth: 65–78 = 12; 55–65 or 78–85 = 9; 45–55 or 85–90 = 5; <45 or >90 = 2. Spring/Fall = +3; summer/winter = −1. |
| Stability | 10 | Stable 48h+ = 7; stable + light rain in last 24h = 10; one swing in last 24h = 5; big swing/front passage = 2. |

Verdicts: peak `Drop everything`, good `Solid bite`, fair `Workable`, tough `Tough day`, skip `Save the gas`.

### Step 3d — Tournaments data block schema

```json
{
  "generated": "<ISO 8601 with -07:00 offset>",
  "today": "YYYY-MM-DD",
  "sources": ["midweekbassaz.com", "roostertalesbassclub.com", "swctackle.com (Weekend Warrior)", "Arizona Kayak Bass Anglers"],
  "by_lake": {
    "pleasant":  [ { "date": "YYYY-MM-DD", "series": "Midweek Bass", "end": "11:00a" }, ... ],
    "roosevelt": [ ... ],
    "apache":    [ ... ],
    "canyon":    [ ... ],
    "saguaro":   [ ... ],
    "bartlett":  [ ... ]
  }
}
```

- All six lake keys MUST be present (use `[]` for a lake with no upcoming events).
- Per event: `date` (ISO, required), `series` (required). Optional: `end` (end time), `multiday` (e.g. `"17–18"`), `tbd` (true if date/permit pending).
- Sort within each lake is not required — the page JS sorts and picks the soonest `date >= today`, then styles events within 7 days as `soon`.
- Replace ONLY the JSON between `<script id="tournaments-data" type="application/json">` and its closing `</script>`. Do not touch the injector `<script>` that follows it.

**Integrity checks (MUST pass before pushing):**
- Exactly 1 `<!DOCTYPE` and exactly 1 `</html>`
- File size 100,000–180,000 bytes (current ~153 KB)
- No `NaN`, `undefined`, or Python `None` in rendered output (matches inside `<script>` blocks fine)
- No leftover `{{...}}` or `XX:XX` placeholders
- `bs-data` JSON parses cleanly
- Bite Score markers present: `id="bs-data"`, `function gaugeSvg`, `function decorateOutlookTiles`
- `tournaments-data` JSON parses cleanly AND contains all six lake keys; tournament badge marker `class="lk-tourney"` (CSS) and `id="tournaments-data"` both present
- **Each of the 6 lake cards has exactly one `<span class="lk-asof ...">` populated with a non-empty `TEXT`** (this is the freshness badge — leaving any empty defeats the whole point)

If any check fails, STOP. Write the failure reason to `$SESSION_DIR/work/ABORT.txt` and exit.

---

## Step 4 — Push to GitHub

```bash
SHA=$(cat "$SESSION_DIR/work/.sha")

python3 <<EOF
import json, base64, pathlib, datetime, zoneinfo
session_dir = '$SESSION_DIR/work'
content_b64 = base64.b64encode(pathlib.Path(f'{session_dir}/index.html').read_bytes()).decode()
sha = pathlib.Path(f'{session_dir}/.sha').read_text().strip()
mst = zoneinfo.ZoneInfo('America/Phoenix')
stamp = datetime.datetime.now(mst).strftime('%Y-%m-%d %H:%M MST')
payload = {
    'message': f'daily refresh {stamp}',
    'content': content_b64,
    'sha':     sha,
    'branch':  'main',
}
pathlib.Path(f'{session_dir}/payload.json').write_text(json.dumps(payload))
EOF

HTTP=$(curl -sS -o "$SESSION_DIR/work/push_resp.json" -w "%{http_code}" \
  -X PUT \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  --data-binary @"$SESSION_DIR/work/payload.json" \
  "https://api.github.com/repos/Tjone7306/fishing-dashboard/contents/index.html")

echo "push status: $HTTP"
[ "$HTTP" = "200" ] || [ "$HTTP" = "201" ] || { cat "$SESSION_DIR/work/push_resp.json"; exit 1; }
```

A `200` means the commit landed on `main`. Netlify auto-deploys within ~30 seconds.

Do NOT add or edit a `CNAME` file in the repo.

---

## Step 4b — Push the Copperstate sale status (independent of index.html)

Push `copperstate-sale.json` from Step 2g. This is a separate Contents-API PUT and must not be gated on the dashboard push succeeding (and vice-versa). Fetch the current file's sha, then PUT the new content:

```bash
python3 <<'EOF'
import json, base64, pathlib, urllib.request
TOKEN="<same GITHUB_TOKEN as above>"
REPO="Tjone7306/fishing-dashboard"; PATH="copperstate-sale.json"
SESSION_DIR=pathlib.Path("$SESSION_DIR/work")  # substitute the real dir
api="https://api.github.com/repos/%s/contents/%s"%(REPO,PATH)
def req(method,data=None):
    r=urllib.request.Request(api,method=method,headers={"Authorization":"Bearer "+TOKEN,
        "Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"})
    if data is not None: r.data=json.dumps(data).encode(); r.add_header("Content-Type","application/json")
    return urllib.request.urlopen(r)
new=(SESSION_DIR/"copperstate-sale.json").read_bytes()
import json as _j
cur=_j.load(req("GET")); sha=cur["sha"]
# Optional: skip the push if content is byte-identical to avoid empty commits.
if base64.b64decode(cur["content"])==new:
    print("copperstate-sale.json unchanged; skip"); raise SystemExit
req("PUT",{"message":"copperstate sale status refresh","content":base64.b64encode(new).decode(),
          "sha":sha,"branch":"main"})
print("copperstate-sale.json pushed")
EOF
```

Netlify serves it at `https://b4u.fish/copperstate-sale.json` with `Access-Control-Allow-Origin: *` (configured in `netlify.toml`), so both b4u.fish and b4ufish.com can read it cross-origin.

---

## Step 5 — Verify deployment

```bash
sleep 45
curl -sSL https://b4u.fish/index.html | grep -o 'Last updated[^<]*' | head -1
```

Confirm the stamp matches what you just pushed. Fallback if DNS hiccups: `https://b4u-fish.netlify.app/`.

---

## Notes

- The PAT is scoped to Contents on this repo only. Check expiration at https://github.com/settings/personal-access-tokens.
- 401 = token revoked/expired → rotate. 409 = sha stale → re-fetch and retry. 422 = payload malformed → check base64 has no newlines (`base64 -w0`).
- SRP data often isn't published for current day before ~4 PM MST — that's why we stamp the report date on each lake card.
- **Hosting:** Netlify project `b4u-fish` (team AZWEB). Custom domain `b4u.fish` + `www.b4u.fish`. No GitHub Pages CNAME file.
- **DNS (GoDaddy):** apex A `@ → 75.2.60.5`, `www` CNAME → `b4u-fish.netlify.app`.
- **Lake Pleasant:** separate CAP/Colorado-River column on the right of the schematic, with live data from the CAP aquaportal feed. Pleasant card "In" = canal pump rate; "Out" = Agua Fria release.
- **Freshness badges:** every lake card carries a `.lk-asof` span in its summary line. SRP lakes show `data M/D · Nd old`; Pleasant shows `live H:MM AM/PM`. Color states: `fresh` (green) / `ok` (muted) / `warn` (amber) / `bad` (red).
- **Schedule:** twice daily at 6:00 AM and 5:00 PM Phoenix time. Cowork must be running for the scheduler to fire.
