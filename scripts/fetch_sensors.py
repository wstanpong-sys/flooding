#!/usr/bin/env python3
"""Fetch BMA road flood sensors via ThaiWater (relayed from the BMA drainage department).

Why ThaiWater: floodbangkok.bangkok.go.th only answers Thai networks, so GitHub Actions
cannot reach it. ThaiWater republishes the same 262 stations (same FL.* codes).

Output: sensors.json -> {"fetchedAt", "latest", "stations": [...], "offline": n}
Each station: code, name, road, where, district, pt [lat, lng], cm, t (ISO +07:00)

Rules (explicit, no magic):
- Only stations in Bangkok with a reading; readings older than STALE_MIN are counted as offline.
- Values are centimetres as published; no smoothing or correction.
- Road name is parsed from the station name; the page decides status, not this script.
"""
import json, re, sys, urllib.request, datetime

URL = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/flood_road"
STALE_MIN = 180
TZ = datetime.timezone(datetime.timedelta(hours=7))
SPLIT = re.compile(r"\s*(?:\(|\s(?:ช่วง|หน้า|แยก|ตลาด|ซอย|ซ\.|ตรงข้าม|บริเวณ|ปาก|ใกล้|ถนน))")

def parse_name(raw):
    name = re.sub(r"\s*\*\s*$", "", raw).strip()
    name = re.sub(r"\s{2,}", " ", name)
    m = re.match(r"^(ถ\.|ซ\.|อ\.)\s*(.+)$", name)
    prefix, rest = (m.group(1), m.group(2)) if m else ("", name)
    parts = SPLIT.split(rest, maxsplit=1)
    head = parts[0].strip()
    where = rest[len(parts[0]):].strip() if len(parts) > 1 else ""
    where = re.sub(r"^\((.*)\)$", r"\1", where).strip()
    return name, prefix, head, where

def main(out_path="sensors.json", src=None):
    if src:
        raw = json.load(open(src, encoding="utf-8"))
    else:
        req = urllib.request.Request(URL, headers={"Referer": "https://www.thaiwater.net/",
                                                   "User-Agent": "flooding-page/0.4 (github.com/wstanpong-sys/flooding)"})
        raw = json.load(urllib.request.urlopen(req, timeout=60))
    rows = raw.get("data") or []
    now = datetime.datetime.now(TZ)
    stations, offline = [], 0
    for x in rows:
        st = x.get("station") or {}
        geo = x.get("geocode") or {}
        if ((geo.get("province_name") or {}).get("th") or "") != "กรุงเทพมหานคร":
            continue
        ts, val = x.get("floodroad_datetime"), x.get("floodroad_value")
        if not ts or val is None:
            offline += 1; continue
        t = datetime.datetime.strptime(ts[:16], "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
        if (now - t).total_seconds() > STALE_MIN * 60:
            offline += 1; continue
        name, prefix, head, where = parse_name(((st.get("floodroad_name") or {}).get("th")) or "")
        stations.append({
            "code": st.get("floodroad_oldcode") or str(st.get("id")),
            "name": name, "prefix": prefix, "road": head, "where": where,
            "district": ((geo.get("amphoe_name") or {}).get("th") or "").replace("เขต", ""),
            "pt": [round(float(st["floodroad_lat"]), 5), round(float(st["floodroad_long"]), 5)],
            "cm": round(float(val), 1), "t": t.isoformat(),
        })
    if not stations:
        sys.exit("no live stations: keep previous data")
    out = {"fetchedAt": now.isoformat(timespec="seconds"), "latest": max(s["t"] for s in stations),
           "staleMin": STALE_MIN, "stations": stations, "offline": offline, "source": URL}
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    flooded = sum(1 for s in stations if s["cm"] >= 5)
    print(f"{len(stations)} live stations ({flooded} at 5 cm or more), {offline} offline, latest {out['latest']}", file=sys.stderr)

if __name__ == "__main__":
    main(*sys.argv[1:])
