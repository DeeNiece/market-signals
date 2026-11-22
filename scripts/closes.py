#!/usr/bin/env python3
"""Stored daily closes, so a scan needs no big TradingView fetch.

data/closes.json = {"calendar": {"PSEi": [dates], "HSI": [dates]}, "closes": {"PSE:SM": {"2026-11-20": 535.5}}}

Commands
  import-partial <partial.json>              merge a partial file ({"closes": {tv: [47 closes]}, "dates": {market: [47 dates]}})
  add-daily <market> <date> <quotes.json>    quotes.json = {tv: close}; marks <date> as a trading day for <market>
  status [date]                              how many stocks per market have a complete series up to <date> (default: latest)
  make-input <date> <run_at> <out.json> [extras.json]
                                             scan input for scripts/run.py; extras = {tv: {"earnings": ..., "fund": {...}}}
Rules: a stock is complete when it has a close for each of the last 45 calendar dates up to <date>.
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = os.path.join(ROOT, "data", "closes.json")
N, MIN = 47, 45


def load():
    if os.path.exists(F):
        return json.load(open(F))
    return {"calendar": {}, "closes": {}}


def save(d):
    d["calendar"] = {m: sorted(set(v)) for m, v in d["calendar"].items()}
    d["closes"] = {k: dict(sorted(v.items())) for k, v in sorted(d["closes"].items())}
    json.dump(d, open(F, "w"), separators=(",", ":"))


def universe():
    return json.load(open(os.path.join(ROOT, "data", "universe.json")))


def series(d, tv, dates):
    c = d["closes"].get(tv, {})
    return [c.get(x) for x in dates]


def complete(d, tv, dates):
    s = series(d, tv, dates[-MIN:])
    return len(dates) >= MIN and all(v is not None for v in s)


def cal_upto(d, m, date):
    return [x for x in d["calendar"].get(m, []) if x <= date][-N:]


def main(a):
    d = load()
    cmd = a[0]
    if cmd == "import-partial":
        p = json.load(open(a[1]))
        mk = {s["tv"]: m for m, v in universe().items() for s in v["stocks"]}
        for tv, cl in p["closes"].items():
            dates = p["dates"][mk[tv]]
            assert len(cl) == len(dates), tv
            d["closes"].setdefault(tv, {}).update(dict(zip(dates, cl)))
        for m, ds in p["dates"].items():
            d["calendar"].setdefault(m, []).extend(ds)
        save(d); print("imported", len(p["closes"]), "stocks")
    elif cmd == "add-daily":
        m, date, q = a[1], a[2], json.load(open(a[3]))
        for tv, v in q.items():
            d["closes"].setdefault(tv, {})[date] = round(float(v), 4)
        d["calendar"].setdefault(m, []).append(date)
        save(d); print("added", len(q), "closes for", m, date)
    elif cmd == "status":
        for m, v in universe().items():
            cal = d["calendar"].get(m, [])
            date = a[1] if len(a) > 1 else (cal[-1] if cal else "")
            ds = cal_upto(d, m, date)
            ok = sum(complete(d, s["tv"], ds) for s in v["stocks"])
            print(f'{m}: {ok} of {len(v["stocks"])} complete up to {date}')
    elif cmd == "make-input":
        date, run_at, out = a[1], a[2], a[3]
        ex = json.load(open(a[4])) if len(a) > 4 else {}
        inp = {"run_at": run_at, "markets": {}}
        for m, v in universe().items():
            ds = cal_upto(d, m, date)
            st = []
            for s in v["stocks"]:
                if not complete(d, s["tv"], ds):
                    continue
                pairs = [(x, d["closes"][s["tv"]].get(x)) for x in ds]
                pairs = [(x, c) for x, c in pairs if c is not None]
                e = ex.get(s["tv"], {})
                row = {"tv": s["tv"], "symbol": s["symbol"], "name": s["name"], "closes": [c for _, c in pairs],
                       "last_date": ds[-1], "earnings": e.get("earnings")}
                if e.get("fund"):
                    row["fund"] = e["fund"]
                st.append(row)
            n, tot = len(st), len(v["stocks"])
            label = v["label"] if n == tot else f"{m} ({n} of {tot} stocks scanned so far)"
            inp["markets"][m] = {"label": label, "dates": ds, "stocks": st}
        json.dump(inp, open(out, "w"))
        print({m: len(x["stocks"]) for m, x in inp["markets"].items()})
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
