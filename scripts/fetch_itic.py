#!/usr/bin/env python3
"""Fetch iTIC / Longdo traffic events and normalize Bangkok flood reports.

Output: itic.json -> {"fetchedAt", "latest", "events": [...]}
Each event: key, kind, name, where, district, pt [lat, lng], n (merged reports), t (latest ISO +07:00)

Rules (explicit, no magic):
- Only type 6 (flood) inside Bangkok (description mentions กรุงเทพ).
- Only reports that started within WINDOW_MIN minutes of fetch time.
- Titles phrased as questions (ไหม, ?) are excluded: they ask, they do not report.
- Reporter names are dropped (privacy).
- Reports with the same key within MERGE_M metres are merged into one evidence.
- No depth is given by the feed, so status is decided by the page, not here.
"""
import json, math, re, sys, urllib.request, datetime

FEED = "https://event.longdo.com/feed/json"
WINDOW_MIN = 180
MERGE_M = 500
TZ = datetime.timezone(datetime.timedelta(hours=7))

def parse_t(s):
    return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)

def dist_m(a, b):
    k = math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot((a[0] - b[0]) * 111320, (a[1] - b[1]) * 111320 * k)

def classify(title):
    t = re.sub(r"^น้ำท่วม\s*", "", title).strip()
    t = re.sub(r"\s*\(.*?\)\s*$", "", t).strip()
    m = re.match(r"^ถนน(.+)$", t)
    if m: return m.group(1).strip(), "road", "ถ." + m.group(1).strip()
    m = re.match(r"^ซอย(.+)$", t)
    if m: return "ซ." + m.group(1).strip(), "soi", "ซ." + m.group(1).strip()
    m = re.match(r"^(\S+) (\d+(?:/\d+)?)$", t)          # e.g. ร่มเกล้า 27 -> soi
    if m: k = "ซ." + m.group(1) + " " + m.group(2); return k, "soi", k
    m = re.match(r"^แขวง(.+)$", t)
    if m: return "แขวง" + m.group(1).strip(), "area", "แขวง" + m.group(1).strip()
    return t, "place", t

def district(desc):
    m = re.search(r"เขต(\S+)", desc or "")
    return m.group(1) if m else ""

def main(out_path="itic.json", src=None):
    if src:
        raw = json.load(open(src, encoding="utf-8"))
    else:
        req = urllib.request.Request(FEED, headers={"User-Agent": "flood-decision-mockup/0.3"})
        raw = json.load(urllib.request.urlopen(req, timeout=30))
    now = datetime.datetime.now(TZ)
    evs, skipped = [], {"old": 0, "outside": 0, "question": 0}
    for x in raw:
        if str(x.get("type")) != "6": continue
        if "กรุงเทพ" not in (x.get("description") or ""): skipped["outside"] += 1; continue
        t = parse_t(x["start"])
        if (now - t).total_seconds() > WINDOW_MIN * 60 or t > now + datetime.timedelta(minutes=5): skipped["old"] += 1; continue
        title = x.get("title") or ""
        if re.search(r"ไหม|\?", title): skipped["question"] += 1; continue
        key, kind, name = classify(title)
        pt = [round(float(x["latitude"]), 5), round(float(x["longitude"]), 5)]
        where = re.sub(r"^น้ำท่วม\s*", "", title).strip()
        hit = next((e for e in evs if e["key"] == key and dist_m(e["pt"], pt) <= MERGE_M), None)
        if hit:
            hit["n"] += 1
            if t.isoformat() > hit["t"]: hit["t"] = t.isoformat()
        else:
            evs.append({"key": key, "kind": kind, "name": name, "where": where,
                        "district": district(x.get("description")), "pt": pt, "n": 1, "t": t.isoformat()})
    evs.sort(key=lambda e: e["t"], reverse=True)
    out = {"fetchedAt": now.isoformat(timespec="seconds"), "latest": evs[0]["t"] if evs else None,
           "windowMin": WINDOW_MIN, "events": evs, "skipped": skipped, "source": FEED}
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(evs)} evidence from {sum(e['n'] for e in evs)} reports, skipped {skipped}", file=sys.stderr)

if __name__ == "__main__":
    main(*sys.argv[1:])
