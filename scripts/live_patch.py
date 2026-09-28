"""Small, idempotent patches applied to index.template.html at build time for live sensors.
Each patch is (old, new). Already-applied or missing patches are skipped with a warning."""
import re, sys

DIG = str.maketrans("\u0e50\u0e51\u0e52\u0e53\u0e54\u0e55\u0e56\u0e57\u0e58\u0e59", "0123456789")
ALIAS = {"\u0e27\u0e34\u0e20\u0e32\u0e27\u0e14\u0e35\u0e02\u0e32\u0e2d\u0e2d\u0e01": "\u0e27\u0e34\u0e20\u0e32\u0e27\u0e14\u0e35",
         "\u0e40\u0e2a\u0e19\u0e32\u0e19\u0e34\u0e04\u0e21": "\u0e40\u0e2a\u0e19\u0e32\u0e19\u0e34\u0e04\u0e21 1"}
ROAD, SOI, TUN = "\u0e16.", "\u0e0b.", "\u0e2d."

def status(cm): return "avoid" if cm > 15 else "caution" if cm > 5 else "pass"

def key_of(s, known):
    if s["code"] in known: return known[s["code"]], "road"
    h = s["road"].translate(DIG).strip()
    h = re.sub("^(\u0e1e\u0e23\u0e30\u0e23\u0e32\u0e21)\\s*(\u0e17\u0e35\u0e48)?\\s*(\\d+)$", r"\1 \3", h)
    h = ALIAS.get(h, h)
    if s["prefix"] == SOI: return SOI + h, "soi"
    if s["prefix"] == TUN: return "\u0e2d\u0e38\u0e42\u0e21\u0e07\u0e04\u0e4c" + h, "tunnel"
    return h, "road"


PATCHES = [
    # sensors without history: no sparkline
    ('e.src==="sensor"?spark(e.h)+', 'e.src==="sensor"&&e.h?spark(e.h)+'),
    # trend ignores sensors without history
    ('const t = r.ev.filter(e=>e.src==="sensor").map(evTrend);',
     'const t = r.ev.filter(e=>e.src==="sensor").map(evTrend).filter(k=>k!=="na");'),
    ('trendTag("na","\u0e23\u0e32\u0e22\u0e07\u0e32\u0e19\u0e40\u0e02\u0e15\u0e21\u0e35\u0e23\u0e2d\u0e1a\u0e40\u0e14\u0e35\u0e22\u0e27 \u0e22\u0e31\u0e07\u0e40\u0e17\u0e35\u0e22\u0e1a\u0e44\u0e21\u0e48\u0e44\u0e14\u0e49")',
     'trendTag("na","\u0e44\u0e21\u0e48\u0e21\u0e35\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e22\u0e49\u0e2d\u0e19\u0e2b\u0e25\u0e31\u0e07\u0e43\u0e2b\u0e49\u0e40\u0e17\u0e35\u0e22\u0e1a")'),
    # per-station timestamps
    ('function ageMin(e){ const t = e.src==="sensor"?T_SENSOR : e.src==="report"?T_REPORT : new Date(e.t);',
     'function ageMin(e){ const t = e.t ? new Date(e.t) : e.src==="sensor"?T_SENSOR : T_REPORT;'),
    ('function expired(e){ return e.src==="itic" && ageMin(e) > ITIC_EXPIRE; }',
     'function expired(e){ return (e.src==="itic" || (e.src==="sensor" && e.t)) && ageMin(e) > ITIC_EXPIRE; }'),
    ('function evTime(e){ return e.src==="sensor" ? hhmm(T_SENSOR) : e.src==="report" ? hhmm(T_REPORT) : hhmm(new Date(e.t)); }',
     'function evTime(e){ return e.t ? hhmm(new Date(e.t)) : e.src==="sensor" ? hhmm(T_SENSOR) : hhmm(T_REPORT); }'),
    ('function evStale(e){ return e.src==="sensor" ? fs.s : e.src==="report" ? fs.r : level(ageMin(e),60,120); }',
     'function evStale(e){ return e.t ? level(ageMin(e),60,120) : e.src==="sensor" ? fs.s : fs.r; }'),
    ('(snapshot 09:40)', '(live via ThaiWater)'),
]

def apply(tpl):
    for old, new in PATCHES:
        if tpl.count(old) == 1:
            tpl = tpl.replace(old, new)
        elif new in tpl:
            pass
        else:
            print("warning: patch target not found: " + old[:50], file=sys.stderr)
    return tpl
