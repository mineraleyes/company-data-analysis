# Listed Mining — TSX / TSXV and ASX

Exploratory analysis of listed mining companies on two markets:

- **1,079** on the Toronto Stock Exchange and TSX Venture Exchange, as at 30 June 2026
- **726** on the Australian Securities Exchange, as at 26 August 2026

One-off analysis — no recurring pipeline.

## The output

`outputs/report.html` — a single self-contained page. A market toggle at the top
right switches between the two, seven tabs in total:

| Market | Tab | What's in it |
|---|---|---|
| TSX / TSXV | Stage 1 · Dataset | what the source files contain, coverage, what's missing |
| | Stage 1 · Numbers | the findings, with charts inline |
| | Stage 1 · Charts | nine interactive charts, filterable by board |
| | Stage 2 | candidate external datasets and what each would produce |
| ASX | Dataset | how the population, stage and commodity flags were derived |
| | Numbers | the findings, with charts inline |
| | Charts | seven interactive charts, filterable by stage |

Open it in a browser. Nothing to install, no network calls.

## The central asymmetry

**The two markets did not arrive the same way, and every comparison should be read
through that.** The TMX exports come pre-filtered to mining, with commodity flags
and a property register already in them — official data, published by the exchange.
The ASX export is five columns: code, name, GICS industry group, listing date,
market cap. Population, commodity, geography and stage are all *derived* on the ASX
side, from business summaries and financial statements pulled from a free,
unofficial API.

The one place the two are honestly like for like is post-listing returns: same
script, same milestones, same base, and a return is a ratio, so the currencies
never meet. That comparison is drawn explicitly on the ASX Charts tab.

## Sources

| File | Source | As at |
|---|---|---|
| `data/raw/tmx_issuers_2026-06-30.xlsx` | [TMX Current Market Statistics](https://www.tsx.com/en/listings/current-market-statistics) | 30 Jun 2026 |
| `data/raw/tmx_mining_properties_2026-07-31.xlsx` | [TMX Mining sector profile](https://www.tsx.com/en/listings/listing-with-us/sector-and-product-profiles/mining) | 31 Jul 2026 |
| `data/raw/ASX_Listed_Companies_*.csv` | [ASX company directory](https://www.asx.com.au/markets/trade-our-cash-market/directory) | 26 Aug 2026 |
| price history, both markets | Yahoo Finance via `yfinance` | to 2 Sep 2026 |
| company data, both markets | Yahoo Finance via `yfinance` | Aug–Sep 2026 |

`yfinance` is a community package reading Yahoo's undocumented endpoints. There is
no official Yahoo API — it was retired in 2017 — so every Yahoo-derived column is
unofficial and can change or vanish without notice.

## Rebuilding

```bash
pip install -r requirements.txt
```

**TSX / TSXV**

```bash
python src/build_mining_dataset.py     # raw xlsx -> mining_clean.csv
python src/enrich_mining_dataset.py    # + commodity, geography, derived metrics
python src/fetch_prices.py             # Yahoo prices -> price_milestones.csv   (internet)
python src/fetch_fundamentals.py       # + revenue and stage, in place          (internet)
```

**ASX**

```bash
python src/build_asx_dataset.py        # raw csv -> asx_clean.csv
python src/fetch_asx_yahoo.py          # Yahoo company data -> asx_yahoo.csv    (internet, ~25 min)
python src/enrich_asx_dataset.py       # -> asx_enriched.csv: population, stage, commodity
python src/fetch_asx_prices.py         # Yahoo prices -> asx_price_milestones.csv (internet, ~25 min)
```

**Both**

```bash
python src/build_report.py             # notes + data -> outputs/report.html
```

Run each market's scripts in the order given. `build_report.py` is the only one you
need after editing the notes — the markdown files are the source of truth for the
written tabs, and the charts read the processed CSVs.

Both fetch steps are **resumable**: they append to a cache as they go and skip what
is already in it, so a run that dies partway can simply be re-run. `--rebuild`
re-derives the extract from cache with no network at all.

## Layout

    data/raw/          source files as received — do not edit
    data/processed/    cleaned and derived datasets
    notes/             the written sections, one markdown file per tab
    outputs/           report.html
    src/               the nine scripts above, plus charts.py and asx_charts.py
    explore/           standalone scratch — what yfinance and EODHD return for one ticker

The two price caches (`data/raw/*price_history.csv`, 295 MB combined) are
gitignored. They are reproducible from the fetch scripts.

## Key datasets

| File | Rows | Cols | One row per |
|---|---|---|---|
| `data/processed/mining_enriched.csv` | 1,079 | 94 | TSX/TSXV mining company |
| `data/processed/price_milestones.csv` | 1,079 | 43 | the same, 595 of them priced |
| `data/processed/asx_enriched.csv` | 775 | 120 | ASX Materials company, 726 flagged as miners |
| `data/processed/asx_price_milestones.csv` | 726 | 45 | ASX miner, 611 of them usable |

| Column group | TSX | ASX |
|---|---|---|
| Join keys | `co_id`, `ticker_full` | `ticker`, `ticker_full` |
| Commodity | `commodities`, 20 `comm_*` booleans | `commodities`, 28 `comm_*` booleans |
| Geography | `hq_country`, `property_countries`, 8 `prop_*` | `hq_country`, 8 `prop_*` |
| Market | `mcap`, `turnover`, `size_band` | `mcap`, `turnover_est`, `size_band` |
| Stage | `stage`, `stage_basis`, `revenue` | `stage`, `stage_basis`, `revenue_stmt`, `construction_in_progress` |
| Returns | `px_base`, 11 `px_d*`, 11 `ret_d*` | the same, plus `price_predates_listing` |

**`turnover` and `turnover_est` are not the same measure.** TMX reports dollars
actually traded; the ASX export carries no trading data, so its figure is estimated
from average daily volume × price × 126 trading days ÷ market cap. Same quantity,
different construction. They never share an axis, and the ASX label always says
"est".

## How stage is decided

**No exchange publishes a lifecycle stage.** Every stage label in this project is
derived, and the two markets are derived differently.

**TSX** — `Producer` is reported revenue above C$1M, `Royalty/Streamer` comes from
TMX's own flag, `Shell` means no commodity and no property, and `Explorer` is the
residual. There is no `Developer`: Yahoo's business summaries name the commodity but
not the project stage, and "feasibility" appears once across 1,079 of them.

**ASX** — rules applied in order, first match wins, in `classify_stage()`:

| # | Test | Result | n |
|---|---|---|---|
| 1 | Summary names royalties or streaming | Royalty / Streamer | 3 |
| 2 | Revenue ≥ A$1M **and** a cost-of-revenue line exists | Producer | 103 |
| 3 | Revenue ≥ A$10M with no cost line | Producer | 12 |
| 4 | Construction in progress, and it is material | Developer | 15 |
| 5 | Statements exist, but no revenue | Explorer | 576 |
| 6 | Nothing returned | Unknown | 17 |

`Developer` exists here and not on the TSX because the balance sheet answered a
question the prose could not. **A capex test was tried first and thrown out**: under
AASB 6 Australian explorers capitalise exploration expenditure, so drilling arrives
as capex and the rule labelled 226 companies as developers, including a A$3.3B
explorer and a A$1.9M shell. `Construction In Progress` is the account for assets
being built and not yet commissioned, which is the actual question.

`stage_basis` records which test decided each row. The full reasoning is on the ASX
Dataset tab.

## Who counts as an ASX miner

There is no mining flag in the ASX export, so the population is a judgement made in
`enrich_asx_dataset.py`: Yahoo's `industry` is authoritative where it names a mining
industry, and otherwise the business summary has to say something only a miner says.
726 of 775, A$1,079B of A$1,180B.

Name-matching was rejected outright — it discards BHP, Newmont, Fortescue, South32,
Alcoa, PLS and IGO, which is A$797B of the sector. An exclusion list was rejected
too, after it wrongly dropped a salt and potash developer whose summary mentions
food and fertiliser.

## Known limits

Both markets:

- **Survivorship** — only companies listed at the snapshot date appear anywhere, so
  every listing-year count and every return is of a survivor. Nothing here recovers
  a delisted company
- **No share counts over time** — dilution and capital raised are unmeasurable. This
  is now the largest remaining gap, since 31% of priced ASX miners have consolidated
- **Stage is today's stage, applied to all of history** — a company that floated as
  an explorer and became a producer counts as a producer across its whole price
  series, so returns split by stage describe outcomes, not strategies
- **Yahoo prices are free and unreliable on thin juniors.** Adjusted closes that
  back-adjust below zero are dropped rather than repaired — 5 companies on the TSX,
  7 on the ASX, one of them negative for twenty-one years

TSX only:

- **224 TSXV companies have no listing date**, so cannot be anchored in time
- **Two source dates** — commodity and property are 31 July, everything financial is
  30 June
- **No developer stage**; within non-producers only market cap distinguishes an
  advanced project from a shell

ASX only:

- **Population, commodity, geography and stage are all inferred**, mostly from prose
  that names the flagship project and stops. Offshore counts are a floor, not a count
- **Coal and uranium are partly excluded** — dropping the Energy sector removed
  Yancoal and Whitehaven but left 13 coal and uranium miners filed under Materials.
  The TMX population carries both in full, so the two are not defined the same way
- **99 companies have no price history reaching their listing**, 73 of them listed
  before 2000 — Yahoo has no 1980s or 1990s ASX data
- **16 companies are excluded as suspected backdoor listings**, where the price
  series predates the stated listing date and so belongs to a shell. The TSX side's
  `covers_listing` flag cannot detect this; `days_price_before_listing` can
- **Australian dollars, never converted.** An A$ size band is not the C$ band with
  the same label
