#!/usr/bin/env python3
"""b4u.fish lake structure maps — generates one SVG per lake.
Shoreline: OpenStreetMap. Levels: live dashboard values. Species: per b4u.fish lake index.
Current waterline: uniform recession fitted to today's surface area
(CAP true acreage for Pleasant; area ~ storage^(2/3) model for SRP/USACE lakes).
All markers are snapped INSIDE the current waterline and verified before writing.
Usage: gen_lake_maps.py <geometry_dir> <levels.json> <out_dir>
levels.json: {"pleasant": {"pct":63,"elev":"1,667.5","below":"34.5","stor_af":552729,"acres":7595}, ...}
"""
import json, math, sys, os
from shapely.geometry import Polygon, Point
from shapely.ops import nearest_points

C = dict(bg="#0a1420", card="#13202e", text="#eaf1f8", muted="#8ea6be",
         accent="#5eb4e7", good="#4fc27a", warn="#f5b44c", bank="#241f19")

CFG = {
 "pleasant": dict(
   title="LAKE PLEASANT", county="MARICOPA CO. ARIZONA", full_elev="1,702",
   cap_af=None,  # true acreage supplied
   dams=[("NEW WADDELL DAM", 33.8425, -112.267)],
   inflows=[("AGUA FRIA", 33.935,-112.208), ("HUMBUG CREEK", 33.951,-112.284)],
   ramps=[("SCORPION BAY MARINA",33.8766,-112.2965),("10-LANE RAMP",33.8554,-112.2898),
          ("PLEASANT HARBOR",33.8524,-112.2573),("CASTLE CREEK RAMP",33.906,-112.3083)],
   zones=[("boil","STRIPER BOILS · SUMMER DAWN",33.860,-112.270),
          ("solid_warn","WHITE BASS · SHAD SCHOOLS",33.941,-112.281),
          ("solid_good","LARGEMOUTH · SPRING COVES",33.905,-112.302),
          ("ring_good","CRAPPIE · BRUSHY BACKS",33.892,-112.221)],
   extras=[("dash","OLD WADDELL DAM · SUBMERGED",33.857,-112.256)]),
 "roosevelt": dict(
   title="ROOSEVELT LAKE", county="GILA CO. ARIZONA", full_elev="2,151",
   cap_af=1653043,
   dams=[("ROOSEVELT DAM", 33.671,-111.1623)],
   inflows=[("SALT RIVER", 33.585,-111.005), ("TONTO CREEK", 33.725,-111.130)],
   ramps=[("WINDY HILL",33.6705,-111.0932),("CHOLLA RAMP",33.6820,-111.2020)],
   zones=[("solid_good","LARGEMOUTH · SPRING COVES",33.615,-111.055),
          ("ring_good","CRAPPIE · SUBMERGED TIMBER",33.718,-111.152),
          ("solid_warn","SMALLMOUTH · ROCKY POINTS",33.655,-111.190)],
   extras=[]),
 "apache": dict(
   title="APACHE LAKE", county="MARICOPA CO. ARIZONA", full_elev="1,914",
   cap_af=245138,
   dams=[("HORSE MESA DAM", 33.5904,-111.3443)],
   inflows=[("SALT RIVER", 33.615,-111.225)],
   ramps=[("APACHE LAKE MARINA",33.5798,-111.2512),("BURNT CORRAL",33.5720,-111.2380)],
   zones=[("solid_good","LARGEMOUTH · COVES",33.576,-111.283),
          ("ring_acc","WALLEYE · DEEP CHANNEL",33.586,-111.320),
          ("solid_warn","YELLOW BASS · SCHOOLS",33.579,-111.260)],
   extras=[]),
 "canyon": dict(
   title="CANYON LAKE", county="MARICOPA CO. ARIZONA", full_elev="1,660",
   cap_af=57852,
   dams=[("MORMON FLAT DAM", 33.5533,-111.4433)],
   inflows=[("SALT RIVER", 33.545,-111.395)],
   ramps=[("PALO VERDE RAMP",33.5376,-111.4291),("CANYON LAKE MARINA",33.5353,-111.4243)],
   zones=[("ring_acc","WALLEYE · DEEP CHANNEL",33.543,-111.432),
          ("solid_good","LARGEMOUTH · COVES",33.546,-111.410),
          ("solid_warn","TROUT · WINTER STOCKED",33.537,-111.422)],
   extras=[]),
 "saguaro": dict(
   title="SAGUARO LAKE", county="MARICOPA CO. ARIZONA", full_elev="1,529",
   cap_af=69765,
   dams=[("STEWART MOUNTAIN DAM", 33.5662,-111.5356)],
   inflows=[("SALT RIVER", 33.560,-111.470)],
   ramps=[("SAGUARO LAKE MARINA",33.5723,-111.5374)],
   zones=[("solid_warn","YELLOW BASS · SCHOOLS",33.570,-111.520),
          ("solid_good","LARGEMOUTH · COVES",33.562,-111.490),
          ("ring_good","CRAPPIE · BRUSH",33.567,-111.505)],
   extras=[]),
 "bartlett": dict(
   title="BARTLETT LAKE", county="MARICOPA CO. ARIZONA", full_elev="1,798",
   cap_af=178186,
   dams=[("BARTLETT DAM", 33.8186,-111.6319)],
   inflows=[("VERDE RIVER", 33.912,-111.593)],
   ramps=[("JOJOBA RAMP",33.8379,-111.6362),("RATTLESNAKE COVE",33.8626,-111.6320)],
   zones=[("solid_good","LARGEMOUTH · SPRING COVES",33.842,-111.643),
          ("ring_good","CRAPPIE · BRUSH · VERDE INFLOW",33.895,-111.598),
          ("solid_warn","CATFISH · RIVER CHANNEL",33.870,-111.615)],
   extras=[]),
 "alamo": dict(
   title="ALAMO LAKE", county="LA PAZ CO. ARIZONA", full_elev="1,125",
   cap_af=138979,
   dams=[("ALAMO DAM", 34.232,-113.6023)],
   inflows=[("SANTA MARIA / BIG SANDY", 34.290,-113.485)],
   ramps=[("STATE PARK RAMPS",34.235,-113.575)],
   zones=[("solid_good","LARGEMOUTH · FLOODED BRUSH",34.262,-113.535),
          ("ring_good","CRAPPIE · TIMBER",34.276,-113.505),
          ("solid_warn","CATFISH · CHANNEL",34.250,-113.560)],
   extras=[]),
}

def stitch(elements):
    segs=[]
    for e in elements:
        if e["type"]=="way" and e.get("geometry"):
            segs.append([(p["lon"],p["lat"]) for p in e["geometry"]])
        elif e["type"]=="relation":
            for m in e.get("members",[]):
                if m.get("role")=="outer" and m.get("geometry"):
                    segs.append([(p["lon"],p["lat"]) for p in m["geometry"]])
    rings=[]; pool=segs[:]
    while pool:
        ring=pool.pop(0); changed=True
        while changed and ring[0]!=ring[-1]:
            changed=False
            for i,s in enumerate(pool):
                if s[0]==ring[-1]: ring+=s[1:]; pool.pop(i); changed=True; break
                if s[-1]==ring[-1]: ring+=s[::-1][1:]; pool.pop(i); changed=True; break
                if s[-1]==ring[0]: ring=s[:-1]+ring; pool.pop(i); changed=True; break
                if s[0]==ring[0]: ring=s[::-1][:-1]+ring; pool.pop(i); changed=True; break
        if len(ring)>3: rings.append(ring)
    return max(rings, key=len)

ZSTYLE={"boil":None,"solid_good":("fill",C["good"]),"ring_good":("ring",C["good"]),
        "solid_warn":("fill",C["warn"]),"ring_acc":("ring",C["accent"])}

def gen(key, ring, lv, outpath):
    cfg=CFG[key]
    poly=Polygon(ring)
    c=poly.centroid; k=math.cos(math.radians(c.y))
    prj=lambda lon,lat: ((lon-c.x)*111320*k,(lat-c.y)*110540)
    P=Polygon([prj(x,y) for x,y in poly.exterior.coords]).simplify(30)
    if not P.is_valid: P=P.buffer(0)
    A=P.area; L=math.sqrt(A)
    # target area for current waterline
    if lv.get("acres"):
        target=lv["acres"]*4046.86
    else:
        ratio=max(0.35,min(0.995,(lv["stor_af"]/cfg["cap_af"])**(2/3)))
        target=A*ratio
    lo,hi=0.0,0.35*L
    for _ in range(40):
        mid=(lo+hi)/2
        if P.buffer(-mid).area>target: lo=mid
        else: hi=mid
    curU=P.buffer(-(lo+hi)/2)          # may be multi-part: arms pinch into separate pools
    cur_parts=[g for g in (curU.geoms if curU.geom_type!="Polygon" else [curU]) if g.area>0.002*A]
    inner=curU.buffer(-0.02*L)
    if inner.is_empty: inner=curU.buffer(-1)
    minx,miny,maxx,maxy=P.bounds
    W,H=maxx-minx,maxy-miny
    PAD_L,PAD_R,PAD_T=70,70,150
    LEG_H=170
    mapw=900-PAD_L-PAD_R
    s=mapw/W; maph=H*s
    if maph>760: s=760/H; maph=760; mapw=W*s
    xoff=PAD_L+(900-PAD_L-PAD_R-W*s)/2
    CH=int(PAD_T+maph+40+LEG_H)
    to=lambda x,y:(xoff+(x-minx)*s, PAD_T+(maxy-y)*s)
    def pth(g,simp=None):
        g=g.simplify(simp if simp else 0.006*L)
        return "M "+" L ".join(f"{a:.1f},{b:.1f}" for a,b in [to(x,y) for x,y in g.exterior.coords])+" Z"
    def snap(lat,lon):
        pt=Point(*prj(lon,lat))
        if not inner.contains(pt): pt=nearest_points(inner,pt)[0]
        return to(pt.x,pt.y)
    def shoresnap(lat,lon):
        pt=Point(*prj(lon,lat)); q=nearest_points(P.exterior,pt)[0]; return to(q.x,q.y)
    ctr=to(*(P.centroid.coords[0]))
    placed=[]  # (x0,x1,y) of placed label boxes
    def place(x,y,label,prefer=None):
        """pick side + y offset avoiding edge clipping and collisions"""
        w=7.6*len(label)
        opts=[]
        base = prefer or (("end") if x<ctr[0] else ("start"))
        order=[base, "start" if base=="end" else "end"]
        for anc in order:
            for dy in (0,-18,18,-36,36):
                x0 = x-14-w if anc=="end" else x+14
                x1 = x0+w
                if x0<8 or x1>892: continue
                yy=y+dy
                if any(abs(yy-py)<15 and not(x1<px0 or x0>px1) for px0,px1,py in placed): continue
                placed.append((x0,x1,yy))
                return anc,(-14 if anc=="end" else 14),dy
        placed.append((x-w/2,x+w/2,y-18))
        return ("middle",0,-18)
    water="".join(f'<path d="{pth(g)}" fill="url(#wg)" stroke="{C["accent"]}" stroke-opacity="0.9" stroke-width="1.6"/>' for g in cur_parts)
    conts=""
    for f,frac,op in (("#0e2233",0.035,0.22),("#0c1e2e",0.09,0.15),("#0a1a29",0.16,0.10)):
        b=curU.buffer(-frac*L)
        gs=[b] if b.geom_type=="Polygon" else (list(b.geoms) if not b.is_empty else [])
        conts+="".join(f'<path d="{pth(g)}" fill="{f}" stroke="{C["accent"]}" stroke-opacity="{op}" stroke-width="1"/>' for g in gs if g.area>0.002*A)
    body=[]
    for name,lat,lon in cfg["inflows"]:
        x,y=shoresnap(lat,lon)
        y2 = y-16 if y<ctr[1] else y+24
        body.append(f'<text x="{x:.0f}" y="{y2:.0f}" fill="{C["muted"]}" font-size="11.5" letter-spacing="1.6" text-anchor="middle">{name}</text>')
    for name,lat,lon in cfg["dams"]:
        x,y=shoresnap(lat,lon)
        dy = 40 if y>ctr[1] else -30
        body.append(f'<line x1="{x-60:.0f}" y1="{y+(8 if dy>0 else -8):.0f}" x2="{x+60:.0f}" y2="{y+(8 if dy>0 else -8):.0f}" stroke="{C["muted"]}" stroke-width="3" stroke-opacity="0.8"/>')
        body.append(f'<text x="{x:.0f}" y="{y+dy:.0f}" fill="{C["muted"]}" font-size="11.5" letter-spacing="3" text-anchor="middle">{name}</text>')
    for name,lat,lon in cfg["ramps"]:
        x,y=shoresnap(lat,lon)
        anc,dx,dy=place(x,y,name)
        body.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="6" fill="{C["text"]}" stroke="{C["accent"]}" stroke-width="2"/>')
        body.append(f'<text x="{x+dx:.0f}" y="{y+4+dy:.0f}" fill="{C["text"]}" font-size="10.5" letter-spacing="1.2" text-anchor="{anc}">{name}</text>')
    marks=[]
    for zt,label,lat,lon in cfg["zones"]:
        x,y=snap(lat,lon); marks.append((label,x,y))
        if zt=="boil":
            body.append(f'<g stroke="{C["accent"]}" fill="none" filter="url(#glow)"><circle cx="{x:.0f}" cy="{y:.0f}" r="9" stroke-opacity="0.9"/><circle cx="{x:.0f}" cy="{y:.0f}" r="19" stroke-opacity="0.45"/><circle cx="{x:.0f}" cy="{y:.0f}" r="30" stroke-opacity="0.2"/></g>')
            body.append(f'<text x="{x:.0f}" y="{y-46:.0f}" fill="{C["accent"]}" font-size="10.5" letter-spacing="1.2" text-anchor="middle">{label}</text>')
            continue
        kind,col=ZSTYLE[zt]
        anc,dx,dy=place(x,y,label)
        if kind=="fill": body.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="5" fill="{col}" filter="url(#glow)"/>')
        else: body.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="5" fill="none" stroke="{col}" stroke-width="1.6" filter="url(#glow)"/>')
        body.append(f'<text x="{x+dx:.0f}" y="{y+4+dy:.0f}" fill="{col}" font-size="10.5" letter-spacing="1.2" text-anchor="{anc}">{label}</text>')
    for zt,label,lat,lon in cfg["extras"]:
        x,y=snap(lat,lon); marks.append((label,x,y))
        body.append(f'<line x1="{x-40:.0f}" y1="{y:.0f}" x2="{x+40:.0f}" y2="{y:.0f}" stroke="{C["accent"]}" stroke-width="2" stroke-dasharray="7 6" stroke-opacity="0.9" filter="url(#glow)"/>')
        body.append(f'<text x="{x+52:.0f}" y="{y+4:.0f}" fill="{C["accent"]}" font-size="10.5" letter-spacing="1.2">{label}</text>')
    meth = "CAP LIVE ACREAGE" if lv.get("acres") else "MODELED FROM STORAGE"
    LY=CH-LEG_H+10
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 {CH}" font-family="Helvetica,Arial,sans-serif">
<defs>
 <radialGradient id="wg" cx="45%" cy="60%" r="80%"><stop offset="0%" stop-color="#0c1f31"/><stop offset="55%" stop-color="#102639"/><stop offset="100%" stop-color="#13293c"/></radialGradient>
 <filter id="glow"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<rect width="900" height="{CH}" fill="{C["bg"]}"/>
<g stroke="#ffffff" stroke-opacity="0.025">{''.join(f'<line x1="{x}" y1="0" x2="{x}" y2="{CH}"/>' for x in range(60,900,60))}{''.join(f'<line x1="0" y1="{y}" x2="900" y2="{y}"/>' for y in range(60,CH,60))}</g>
<path d="{pth(P)}" fill="{C["bank"]}" fill-opacity="0.9" stroke="{C["muted"]}" stroke-opacity="0.5" stroke-width="1.2" stroke-dasharray="5 4"/>
{water}
{conts}
{''.join(body)}
<text x="56" y="64" fill="{C["text"]}" font-size="30" letter-spacing="6" font-weight="300">{cfg["title"]}</text>
<text x="56" y="88" fill="{C["muted"]}" font-size="11.5" letter-spacing="3">STRUCTURE &amp; SEASONAL MAP · {cfg["county"]}</text>
<line x1="56" y1="102" x2="248" y2="102" stroke="{C["accent"]}" stroke-width="2"/>
<text x="56" y="122" fill="{C["muted"]}" font-size="10" letter-spacing="1.5" opacity="0.85">SHORELINE: OPENSTREETMAP · SPECIES PER B4U.FISH LAKE GUIDE · ZONES GENERALIZED</text>
<g>
 <rect x="640" y="30" width="204" height="86" rx="10" fill="{C["card"]}" stroke="{C["accent"]}" stroke-opacity="0.35"/>
 <text x="742" y="52" fill="{C["muted"]}" font-size="10" letter-spacing="2" text-anchor="middle">WATER LEVEL TODAY</text>
 <text x="742" y="78" fill="{C["text"]}" font-size="21" letter-spacing="1" text-anchor="middle" font-weight="600">{lv["elev"]} FT · {lv["pct"]}%</text>
 <text x="742" y="100" fill="{C["warn"]}" font-size="10.5" letter-spacing="1.2" text-anchor="middle">−{lv["below"]} FT BELOW FULL ({cfg["full_elev"]} FT)</text>
</g>
<g font-size="10.5" letter-spacing="1.1">
 <rect x="56" y="{LY}" width="788" height="{LEG_H-30}" rx="10" fill="{C["card"]}" stroke="#ffffff" stroke-opacity="0.08"/>
 <circle cx="80" cy="{LY+26}" r="5" fill="{C["text"]}" stroke="{C["accent"]}" stroke-width="1.6"/><text x="96" y="{LY+30}" fill="{C["muted"]}">BOAT RAMP / MARINA</text>
 <circle cx="80" cy="{LY+52}" r="4.5" fill="{C["good"]}"/><text x="96" y="{LY+56}" fill="{C["muted"]}">SOLID = PRIMARY ZONE</text>
 <circle cx="80" cy="{LY+78}" r="4.5" fill="none" stroke="{C["good"]}"/><text x="96" y="{LY+82}" fill="{C["muted"]}">RING = STRUCTURE / SCHOOLING</text>
 <line x1="330" y1="{LY+22}" x2="350" y2="{LY+22}" stroke="{C["accent"]}" stroke-opacity="0.9" stroke-width="2"/><text x="360" y="{LY+26}" fill="{C["muted"]}">CURRENT WATERLINE · {lv["pct"]}%</text>
 <line x1="330" y1="{LY+48}" x2="350" y2="{LY+48}" stroke="{C["muted"]}" stroke-opacity="0.5" stroke-dasharray="5 4"/><text x="360" y="{LY+52}" fill="{C["muted"]}">FULL POOL {cfg["full_elev"]} FT</text>
 <rect x="330" y="{LY+68}" width="20" height="9" fill="{C["bank"]}"/><text x="360" y="{LY+78}" fill="{C["muted"]}">EXPOSED BANK</text>
 <text x="620" y="{LY+26}" fill="{C["muted"]}">DEPTH CONTOURS = RELATIVE</text>
 <text x="620" y="{LY+52}" fill="{C["muted"]}">WATERLINE: {meth}</text>
 <text x="620" y="{LY+78}" fill="{C["muted"]}">LOCAL BANKS VARY</text>
</g>
<text x="844" y="{CH-14}" fill="{C["muted"]}" font-size="10" letter-spacing="1.5" text-anchor="end" opacity="0.8">STYLIZED — NOT FOR NAVIGATION · b4u.fish</text>
<g transform="translate(862,158)" stroke="{C["muted"]}" fill="{C["muted"]}"><line x1="0" y1="14" x2="0" y2="-14" stroke-width="1.2"/><path d="M 0,-14 l 5,9 h -10 z" stroke="none"/><text x="0" y="-20" font-size="10" text-anchor="middle" stroke="none">N</text></g>
</svg>'''
    inv=lambda xs,ys:(minx+(xs-xoff)/s, maxy-(ys-PAD_T)/s)
    bad=[lbl for lbl,x,y in marks if not curU.contains(Point(*inv(x,y)))]
    if bad: raise SystemExit(f"{key}: markers OUTSIDE water: {bad}")
    open(outpath,"w").write(svg)
    return f"{key}: ok ({curU.area/4046.86:.0f} ac water in {len(cur_parts)} pool(s), target {target/4046.86:.0f})"

if __name__=="__main__":
    geo_dir, levels_file, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    levels=json.load(open(levels_file))
    for key in CFG:
        d=json.load(open(os.path.join(geo_dir,f"{key}.json")))
        ring=d if isinstance(d,list) else stitch(d["elements"])
        print(gen(key, ring, levels[key], os.path.join(out_dir,f"{key}.svg")))
