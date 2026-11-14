# market-signals

Twice-weekly bullish signal scan of PSEi and HSI stocks on the D1 chart. Published with GitHub Pages.

- Signals: simple MA 9/26 bullish cross, and bullish turn of the 26-period Hull MA.
- Candles: closed daily candles only.
- Schedule: Tuesday and Friday after the close.
- `scripts/run.py` computes the signals from an input file and rebuilds `index.html` and `archive/`.
- `data/scans/` keeps the result of every scan.

This is a signal list for reference, not investment advice.

## Scan procedure (for the scheduled run)

1. Read `data/universe.json` (PSEi 30 stocks, HSI top 50 by trading value).
2. For each stock, pull about 47 daily bars from TradingView (interval 1D, format columns). Drop the last bar if it is dated today and the market has not closed (PSE closes 15:30, HKEX 16:00, Hong Kong time).
3. Get earnings dates from the TradingView earnings calendar for the next 14 days.
3b. Fundamentals: call `mcp-tv-get-symbol-data-batch` (up to 50 symbols per call, so 2 calls for 80 stocks) with the columns `price_earnings_ttm, earnings_per_share_diluted_yoy_growth_ttm, total_revenue_yoy_growth_ttm, net_margin_ttm, dividends_yield_current, earnings_release_date, earnings_release_next_date, eps_surprise_percent_fq, revenue_surprise_percent_fq, sector`. Put each stock's returned values in its input entry as `"fund": {column: value, ...}` (raw values, null when missing). `run.py` formats them.
4. Write an input file in the format described at the top of `scripts/run.py` and run `python3 scripts/run.py <input.json>`.
5. Commit `index.html`, `archive/`, `data/` and push to `main`.

## Track record tab
run.py builds a third tab from data/scans/*.json. Each scan file stores the last close of every stock (markets.<name>.prices), taken from the closes in the input, so no extra data calls are needed. A fresh signal is counted once, on the first scan where the stock is fresh. Returns are taken at the first later scan at least 7, 14 and 28 days after entry, and compared with the equal-weight average of all stocks in that market over the same dates. Do not delete old scan files.

## Analysis tab
run.py also builds a fourth tab, Analysis, with plain SVG charts (no libraries): win ratio, performance vs market, return by holding time, market breadth over time, fresh signals per scan, stocks with a signal, signal types and sectors. All charts come from data/scans/*.json, so they fill in as scans are added. Colours: blue = PSEi, orange = HSI, gray = market average.
