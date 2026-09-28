#!/usr/bin/env python3
"""Merge the static snapshot (data/base.json) with live iTIC reports (data/itic.json)
and render the page into site/. The page embeds its data, so each run is one self-contained build.

Usage: python3 scripts/build.py [itic.json path] [output dir]
"""
import json, os, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main(itic_path=os.path.join(ROOT, "data", "itic.json"), out_dir=os.path.join(ROOT, "site")):
    base = json.load(open(os.path.join(ROOT, "data", "base.json"), encoding="utf-8"))
    roads, meta = base["roads"], dict(base["meta"])
    idx = {r["key"]: r for r in roads}
    n_ev = 0
    if os.path.exists(itic_path):
        it = json.load(open(itic_path, encoding="utf-8"))
        for e in it["events"]:
            r = idx.get(e["key"])
            if not r:
                r = {"key": e["key"], "name": e["name"], "kind": e["kind"], "d": e["district"], "ev": []}
                roads.append(r); idx[e["key"]] = r
            if not r.get("d"): r["d"] = e["district"]
            r["ev"].append({"src": "itic", "conf": "crowd", "st": "caution", "where": e["where"],
                            "n": e["n"], "t": e["t"], "pt": e["pt"]})
            n_ev += 1
        meta.update({"iticFetched": it["fetchedAt"], "iticLatest": it["latest"],
                     "iticWindow": it["windowMin"], "iticCount": sum(e["n"] for e in it["events"])})
    else:
        print("warning: no iTIC file, building snapshot only", file=sys.stderr)
    data = {"roads": roads, "meta": meta, "base": base["base"], "districts": base["districts"]}
    build_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tpl = open(os.path.join(ROOT, "index.template.html"), encoding="utf-8").read()
    for token in ("__DATA__", "__BUILD__"):
        if tpl.count(token) != 1: sys.exit(f"template must contain {token} exactly once")
    html = tpl.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    html = html.replace("__BUILD__", build_id)
    os.makedirs(out_dir, exist_ok=True)
    open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8").write(html)
    open(os.path.join(out_dir, "build.txt"), "w").write(build_id + "\n")
    open(os.path.join(out_dir, ".nojekyll"), "w").write("")
    print(f"built {build_id}: {len(roads)} places, {n_ev} iTIC evidence, {len(html)//1024} KB", file=sys.stderr)

if __name__ == "__main__":
    main(*sys.argv[1:])
