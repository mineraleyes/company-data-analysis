# TSX / TSXV Mining Analysis

Analysis of the 1,079 mining companies listed on the Toronto Stock Exchange (TSX)
and TSX Venture Exchange (TSXV), as at 30 June 2026.

One-off analysis — no recurring pipeline.

## The output

`outputs/report.html` — a single self-contained page, four tabs:

| Tab | What's in it |
|---|---|
| Stage 1 · Dataset | what the source files contain, coverage, what's missing |
| Stage 1 · Numbers | the findings, with charts inline |
| Stage 1 · Charts | six interactive charts, filterable by board |
| Stage 2 | candidate external datasets and what each would produce |

Open it in a browser. Nothing to install, no network calls.

## Sources

| File | Source | As at |
|---|---|---|
| `data/raw/tmx_issuers_2026-06-30.xlsx` | [TMX Current Market Statistics](https://www.tsx.com/en/listings/current-market-statistics) | 30 Jun 2026 |
| `data/raw/tmx_mining_properties_2026-07-31.xlsx` | [TMX Mining sector profile](https://www.tsx.com/en/listings/listing-with-us/sector-and-product-profiles/mining) | 31 Jul 2026 |
| price history | Yahoo Finance via `yfinance` | to Aug 2026 |
| revenue and business summaries | Yahoo Finance via `yfinance` | Aug 2026 |

The issuer list gives size and trading; the mining list gives commodity and asset
location. Both are free from TMX, and the issuer page also hosts archived monthly
versions — the route to any historical work.

## Rebuilding

```bash
pip install -r requirements.txt

python src/build_mining_dataset.py     # raw xlsx  -> mining_clean.csv
python src/enrich_mining_dataset.py    # + commodity, geography, derived metrics
python src/fetch_prices.py             # Yahoo prices -> price_milestones.csv  (needs internet)
python src/fetch_fundamentals.py       # + revenue and stage, in place             (needs internet)
python src/build_report.py             # notes + data -> outputs/report.html
```

Run them in that order. `build_report.py` is the only one you need after editing
the notes — the markdown files are the source of truth for the written tabs, and
the charts read the processed CSVs.

## Layout

    data/raw/          source files as received — do not edit
    data/processed/    cleaned and derived datasets
    notes/             the written sections, one markdown file per tab
    outputs/           report.html
    src/               the five scripts above

## Key datasets

`data/processed/mining_enriched.csv` — 1,079 rows, 94 columns. One row per company.

| Column group | Examples |
|---|---|
| Join keys | `co_id`, `ticker_full`, `name_normalised` |
| Commodity | `commodities` (fixed-order set), 20 `comm_*` booleans |
| Geography | `hq_country`, `property_countries`, 8 `prop_*` booleans |
| Market | `mcap`, `turnover`, `attention_ratio`, `size_band` |
| Stage | `stage`, `stage_basis`, `revenue` |
| Flags | `consolidated`, `shell_like`, `is_royalty_streamer` |

`data/processed/price_milestones.csv` — 595 priced companies, with prices and
returns at 11 points measured from each company's own listing date.

`stage` is derived, not disclosed: `Producer` means reported revenue above C$1M,
`Royalty/Streamer` comes from TMX's flag, `Shell` means no commodity and no
property, and `Explorer` is the residual. `stage_basis` records which of those
decided each row.

## Known limits

- **No share counts over time** — dilution and capital raised are unmeasurable
- **Survivorship** — only companies still listed at 30 June 2026 appear anywhere
- **224 TSXV companies have no listing date**, so cannot be anchored in time
- **Two source dates** — commodity and property are 31 July, everything financial is 30 June
- **No developer stage** — Yahoo's business summaries name the commodity but not the
  project stage, so the dataset separates producing from not-producing and nothing
  finer. Within non-producers only market cap distinguishes an advanced project
  from a shell
- Prices are Yahoo Finance: free, and unreliable on thinly traded juniors. Quotes
  that back-adjust below zero (5 companies with large distributions) are dropped
