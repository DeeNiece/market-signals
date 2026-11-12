#!/usr/bin/env python3
"""Compute bullish D1 signals and rebuild the site.

Usage: python3 scripts/run.py input.json

input.json format:
{
  "run_at": "2026-11-12T16:30:00+08:00",
  "markets": {
    "PSEi": {
      "label": "PSEi (30 stocks)",
      "stocks": [
        {"tv": "PSE:SM", "symbol": "SM", "name": "SM Investments",
         "closes": [...closed daily closes, oldest first...],
         "last_date": "2026-11-11", "earnings": "2026-11-12" or null}
      ]
    }
  }
}

Rules (all on closed daily candles):
  MA cross   : simple MA 9 crosses above simple MA 26, and 9 is still above 26 now.
  HMA turn   : slope of the 26-period Hull MA flips from <=0 to >0, and is still rising now.
  Fresh      : the signal is in the last 3 candles. Older = 4 to 12 candles ago.
"""
import datetime as dt
import glob
import html
import json
import os
import sys

FAST, SLOW, HMA_N = 9, 26, 26
FRESH, WINDOW = 3, 12
EARNINGS_DAYS = 7
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sma(x, p):
    return [None] * (p - 1) + [sum(x[i - p + 1:i + 1]) / p for i in range(p - 1, len(x))]


def wma(x, p):
    out = [None] * len(x)
    w = p * (p + 1) / 2
    for i in range(p - 1, len(x)):
        s = x[i - p + 1:i + 1]
        if None in s:
            continue
        out[i] = sum((j + 1) * s[j] for j in range(p)) / w
    return out


def hma(x, p):
    a, b = wma(x, p // 2), wma(x, p)
    raw = [2 * a[i] - b[i] if a[i] is not None and b[i] is not None else None for i in range(len(x))]
    return wma(raw, int(p ** 0.5))


def analyse(closes):
    n = len(closes)
    if n < 45:
        return None
    f, s, h = sma(closes, FAST), sma(closes, SLOW), hma(closes, HMA_N)
    cross = None
    for i in range(SLOW, n):
        a, b = f[i - 1] - s[i - 1], f[i] - s[i]
        if a <= 0 < b:
            cross = n - 1 - i
    slope = [None] * n
    for i in range(1, n):
        if h[i] is not None and h[i - 1] is not None:
            slope[i] = h[i] - h[i - 1]
    turn = None
    for i in range(2, n):
        if slope[i] is not None and slope[i - 1] is not None and slope[i - 1] <= 0 < slope[i]:
            turn = n - 1 - i
    ma_bull_now = f[-1] > s[-1]
    hma_up_now = slope[-1] is not None and slope[-1] > 0
    signals = []
    if cross is not None and cross < WINDOW and ma_bull_now:
        signals.append({"type": "MA cross", "bars_ago": cross})
    if turn is not None and turn < WINDOW and hma_up_now:
        signals.append({"type": "HMA turn", "bars_ago": turn})
    return {
        "signals": signals,
        "ma_bull_now": ma_bull_now,
        "hma_up_now": hma_up_now,
        "above_hma": closes[-1] > h[-1],
        "gap_pct": round((f[-1] / s[-1] - 1) * 100, 2),
        "close": closes[-1],
    }


def run_scan(inp):
    scan_date = max(st["last_date"] for m in inp["markets"].values() for st in m["stocks"])
    d0 = dt.date.fromisoformat(scan_date)
    out = {"scan_date": scan_date, "run_at": inp.get("run_at", ""), "markets": {}}
    for name, m in inp["markets"].items():
        rows, ma_bull, hma_up, total = [], 0, 0, 0
        for st in m["stocks"]:
            r = analyse(st["closes"])
            if r is None:
                continue
            total += 1
            ma_bull += r["ma_bull_now"]
            hma_up += r["hma_up_now"]
            if not r["signals"]:
                continue
            e = st.get("earnings")
            soon = False
            if e:
                days = (dt.date.fromisoformat(e) - d0).days
                soon = 0 <= days <= EARNINGS_DAYS
            best = min(x["bars_ago"] for x in r["signals"])
            rows.append({
                "tv": st["tv"], "symbol": st["symbol"], "name": st["name"],
                "close": r["close"], "signals": r["signals"], "best": best,
                "fresh": best < FRESH, "above_hma": r["above_hma"], "gap_pct": r["gap_pct"],
                "earnings": e if soon else None,
            })
        rows.sort(key=lambda x: (x["best"], -len(x["signals"]), x["symbol"]))
        out["markets"][name] = {
            "label": m.get("label", name), "total": total,
            "ma_bull": ma_bull, "hma_up": hma_up, "rows": rows,
        }
    return out


# ---------------------------------------------------------------- site
CSS = """
:root{--bg:#fff;--fg:#1a1d21;--mut:#5b6470;--line:#e3e6ea;--card:#f6f8fa;--acc:#0b6b4f;--warn:#9a5b00}
@media(prefers-color-scheme:dark){:root{--bg:#0f1317;--fg:#e8ebee;--mut:#9aa4af;--line:#262d35;--card:#171d23;--acc:#4cc59b;--warn:#e0a84a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:960px;margin:0 auto;padding:28px 18px 60px}
h1{font-size:1.6rem;margin:0 0 4px}h2{font-size:1.25rem;margin:34px 0 6px}h3{font-size:1rem;margin:20px 0 6px}
p{margin:6px 0}.mut{color:var(--mut)}.small{font-size:.88rem}
.box{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:14px 0}
table{width:100%;border-collapse:collapse;margin:6px 0 4px;font-size:.95rem}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:600;color:var(--mut);font-size:.82rem;text-transform:uppercase;letter-spacing:.03em}
a{color:var(--acc)}.tag{display:inline-block;border:1px solid var(--line);border-radius:6px;padding:1px 7px;margin:1px 4px 1px 0;font-size:.85rem}
.up{color:var(--acc)}.warn{color:var(--warn)}
.wrap{overflow-x:auto}
.tabs{display:flex;gap:8px;margin:18px 0 4px;position:sticky;top:0;z-index:5;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line)}
.tabs button{flex:1;font:inherit;font-weight:600;color:var(--fg);background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;cursor:pointer;min-height:44px}
.tabs button[aria-selected=true]{background:var(--acc);border-color:var(--acc);color:var(--bg)}
.tabs .n{font-weight:400;font-size:.85rem;opacity:.85;display:block}
.js .panel{display:none}.js .panel.on{display:block}
@media(max-width:640px){
main{padding:16px 12px 48px}h1{font-size:1.35rem}h2{font-size:1.1rem}
table,tbody,tr,td{display:block;width:100%}
table tr:first-child{display:none}
tr{border:1px solid var(--line);border-radius:10px;background:var(--card);padding:8px 12px;margin:10px 0}
td{border:0;padding:3px 0;display:flex;justify-content:space-between;gap:12px;align-items:baseline}
td:first-child{display:block;font-size:1.05rem;font-weight:600;padding-bottom:6px}
td[data-l]::before{content:attr(data-l);color:var(--mut);font-size:.8rem;text-transform:uppercase;letter-spacing:.03em;flex:none}
td.sg{display:block}td.sg::before{display:block;margin-bottom:2px}
}
"""


TABJS = """<script>
(function(){var d=document.documentElement;d.className+=' js';
var b=document.querySelectorAll('.tabs button'),p=document.querySelectorAll('.panel');
function show(i){for(var k=0;k<b.length;k++){var on=k==i;b[k].setAttribute('aria-selected',on);p[k].className='panel'+(on?' on':'');}
try{history.replaceState(null,'','#'+b[i].textContent.split(/\\d/)[0].trim().toLowerCase())}catch(e){}}
for(var k=0;k<b.length;k++)(function(k){b[k].onclick=function(){show(k)}})(k);
var h=location.hash.slice(1).toLowerCase();
for(var k=0;k<b.length;k++){if(b[k].textContent.toLowerCase().indexOf(h)==0&&h){show(k);break}}
})();
</script>"""


def bars_txt(n):
    return "latest candle" if n == 0 else ("1 candle ago" if n == 1 else f"{n} candles ago")


def fmt_date(s):
    return dt.date.fromisoformat(s).strftime("%a %d %b %Y")


def table(rows):
    if not rows:
        return '<p class="mut">None.</p>'
    t = ['<div class="wrap"><table><tr><th>Stock</th><th>Signals</th><th>Price vs HMA 26</th><th>9 vs 26 SMA</th><th>Earnings</th></tr>']
    for r in rows:
        link = "https://www.tradingview.com/chart/?symbol=" + r["tv"].replace(":", "%3A")
        sig = "".join(f'<span class="tag">{html.escape(s["type"])} &middot; {bars_txt(s["bars_ago"])}</span>' for s in r["signals"])
        vs = '<span class="up">Above</span>' if r["above_hma"] else "Below"
        e = f'<span class="warn">{html.escape(r["earnings"])}</span>' if r["earnings"] else "&ndash;"
        t.append(
            f'<tr><td><a href="{link}" target="_blank" rel="noopener">{html.escape(r["symbol"])}</a>'
            f'<br><span class="mut small">{html.escape(r["name"])}</span></td>'
            f"<td class=\"sg\" data-l=\"Signals\">{sig}</td><td data-l=\"Price vs HMA 26\">{vs}</td>"
            f"<td data-l=\"9 vs 26 SMA\">{r['gap_pct']:+.2f}%</td><td data-l=\"Earnings\">{e}</td></tr>")
    t.append("</table></div>")
    return "".join(t)


def page(scan, past, depth):
    up = "../" * depth
    parts = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
             f"<title>Market Signals: PSEi and HSI</title><style>{CSS}</style></head><body><main>"]
    parts.append("<h1>Market Signals: PSEi and HSI</h1>")
    parts.append('<p class="mut">Bullish signals on the daily (D1) chart, from closed candles only. Scanned every Tuesday and Friday after the close.</p>')
    parts.append(f'<div class="box"><b>Scan date: {fmt_date(scan["scan_date"])}</b> (data through that day\'s close)'
                 f'<br><span class="mut small">Generated {html.escape(scan.get("run_at", ""))}</span></div>')
    mk = list(scan["markets"].items())
    parts.append('<div class="tabs" role="tablist">' + "".join(
        f'<button role="tab" id="t{i}" data-t="{i}" aria-selected="{"true" if i == 0 else "false"}">{html.escape(name)}'
        f'<span class="n">{sum(1 for r in m["rows"] if r["fresh"])} fresh &middot; {len(m["rows"])} total</span></button>'
        for i, (name, m) in enumerate(mk)) + "</div>")
    for i, (name, m) in enumerate(mk):
        fresh = [r for r in m["rows"] if r["fresh"]]
        older = [r for r in m["rows"] if not r["fresh"]]
        parts.append(f'<section class="panel{" on" if i == 0 else ""}" id="p{i}" role="tabpanel">')
        parts.append(f"<h2>{html.escape(m['label'])}</h2>")
        parts.append(f'<p class="mut">Market breadth: {m["ma_bull"]} of {m["total"]} stocks have the 9 SMA above the 26 SMA. '
                     f'{m["hma_up"]} of {m["total"]} have a rising Hull MA 26.</p>')
        parts.append(f"<h3>Fresh signals (last {FRESH} candles)</h3>" + table(fresh))
        parts.append(f"<h3>Earlier signals ({FRESH + 1} to {WINDOW} candles ago)</h3>" + table(older))
        parts.append("</section>")
    parts.append('<h2>How the signals work</h2><div class="box small">'
                 "<p><b>MA cross:</b> the simple 9-period average closes above the simple 26-period average, and is still above it at the latest close.</p>"
                 "<p><b>HMA turn:</b> the 26-period Hull MA stops falling and starts rising, and is still rising at the latest close. "
                 "No minimum size is applied, so a turn on a flat line can be weak.</p>"
                 "<p><b>Price vs HMA 26:</b> whether the latest close is above the Hull MA. <b>9 vs 26 SMA:</b> the gap between the two averages.</p>"
                 "<p><b>Earnings:</b> shown only when results are due within 7 days of the scan date, because signals around earnings are less reliable.</p>"
                 "<p>Averages are calculated from TradingView daily closes. TradingView's own indicators may differ slightly. "
                 "This page is a signal list for reference, not investment advice.</p></div>")
    parts.append("<h2>Past scans</h2><p>")
    links = [f'<a href="{up}archive/{s["scan_date"]}.html">{fmt_date(s["scan_date"])}</a>' for s in past]
    parts.append(" &middot; ".join(links) if links else "<span class='mut'>None yet.</span>")
    parts.append("</p></main>" + TABJS + "</body></html>")
    return "".join(parts)


def build_site():
    scans = []
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "scans", "*.json")), reverse=True):
        with open(p) as fh:
            scans.append(json.load(fh))
    if not scans:
        return
    os.makedirs(os.path.join(ROOT, "archive"), exist_ok=True)
    with open(os.path.join(ROOT, "index.html"), "w") as fh:
        fh.write(page(scans[0], scans, 0))
    for s in scans:
        with open(os.path.join(ROOT, "archive", f'{s["scan_date"]}.html'), "w") as fh:
            fh.write(page(s, scans, 1))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    with open(sys.argv[1]) as fh:
        inp = json.load(fh)
    scan = run_scan(inp)
    os.makedirs(os.path.join(ROOT, "data", "scans"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "scans", f'{scan["scan_date"]}.json'), "w") as fh:
        json.dump(scan, fh, indent=1)
    build_site()
    for name, m in scan["markets"].items():
        print(name, "stocks:", m["total"], "signals:", len(m["rows"]), "fresh:", sum(r["fresh"] for r in m["rows"]))


if __name__ == "__main__":
    main()
