#!/usr/bin/env python3
"""Live build: BMA sensors via ThaiWater + iTIC. See scripts/fetch_sensors.py."""
import json, os, sys, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import live_patch

from live_patch import status, key_of, ROAD

def main(itic=os.path.join(ROOT, "data", "itic.json"), out=os.path.join(ROOT, "site"),
         sens=os.path.join(ROOT, "data", "sensors.json")):
    base = json.load(open(os.path.join(ROOT, "data", "base.json"), encoding="utf-8"))
    roads, meta = base["roads"], dict(base["meta"])
    known = {e["code"]: r["key"] for r in roads for e in r["ev"] if e.get("src") == "sensor"}
    hist = {e["code"]: e.get("h") for r in roads for e in r["ev"] if e.get("src") == "sensor"}
    if not os.path.exists(sens):
        try:
            import fetch_sensors; fetch_sensors.main(sens)
        except (Exception, SystemExit) as x:
            print("warning: sensor fetch failed (%s), snapshot sensors kept" % x, file=sys.stderr)
    ns = 0
    if os.path.exists(sens):
        sn = json.load(open(sens, encoding="utf-8"))
        for r in roads: r["ev"] = [e for e in r["ev"] if e.get("src") != "sensor"]
        roads = [r for r in roads if r["ev"]]
        idx = {r["key"]: r for r in roads}
        for s in sn["stations"]:
            k, kind = key_of(s, known)
            r = idx.get(k)
            if not r:
                r = {"key": k, "name": k if kind != "road" else ROAD + k, "kind": kind, "d": s["district"], "ev": []}
                roads.append(r); idx[k] = r
            if not r.get("d"): r["d"] = s["district"]
            ev = {"src": "sensor", "conf": "confirmed", "st": status(s["cm"]), "cm": s["cm"], "where": s["where"] or s["name"],
                  "code": s["code"], "d": s["district"], "pt": s["pt"], "t": s["t"]}
            if hist.get(s["code"]): ev["h"] = hist[s["code"]] + [s["cm"]]
            r["ev"].append(ev); ns += 1
        flood_roads = len({key_of(s, known)[0] for s in sn["stations"] if s["cm"] >= 5})
        meta["sensorTs"] = sn["latest"]
        meta["sensorFlood"] = sum(1 for s in sn["stations"] if s["cm"] >= 5)
        meta["snaps"] = meta.get("snaps", []) + [sn["latest"][:16]]
        meta["hist"] = meta.get("hist", []) + [{"iso": sn["latest"][:16], "roads": flood_roads, "n": meta["sensorFlood"]}]
    idx = {r["key"]: r for r in roads}
    ni = 0
    if os.path.exists(itic):
        it = json.load(open(itic, encoding="utf-8"))
        for e in it["events"]:
            r = idx.get(e["key"])
            if not r:
                r = {"key": e["key"], "name": e["name"], "kind": e["kind"], "d": e["district"], "ev": []}
                roads.append(r); idx[e["key"]] = r
            if not r.get("d"): r["d"] = e["district"]
            r["ev"].append({"src": "itic", "conf": "crowd", "st": "caution", "where": e["where"], "n": e["n"], "t": e["t"], "pt": e["pt"]})
            ni += 1
        meta.update({"iticFetched": it["fetchedAt"], "iticLatest": it["latest"], "iticWindow": it["windowMin"],
                     "iticCount": sum(e["n"] for e in it["events"])})
    data = {"roads": roads, "meta": meta, "base": base["base"], "districts": base["districts"]}
    bid = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tpl = live_patch.apply(open(os.path.join(ROOT, "index.template.html"), encoding="utf-8").read())
    html = tpl.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")).replace("__BUILD__", bid)
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(html)
    open(os.path.join(out, "build.txt"), "w").write(bid + "\n")
    open(os.path.join(out, ".nojekyll"), "w").write("")
    print("built %s: %d places, %d live sensors, %d iTIC" % (bid, len(roads), ns, ni), file=sys.stderr)

if __name__ == "__main__":
    main(*sys.argv[1:])
