# ASX — The dataset

*726 mining companies, derived from a five-column exchange export plus Yahoo Finance.*

## What arrived

| File | Source | As at | Rows | Cols |
|---|---|---|---|---|
| ASX listed companies | ASX company directory export | 26 Aug 2026 | 1,843 | 5 |
| Company data | Yahoo Finance via `yfinance` | 30 Aug 2026 | 775 | 57 |
| Price history | Yahoo Finance via `yfinance` | to 2 Sep 2026 | 726 | 41 |

The ASX export is five columns: **code, company name, GICS industry group, listing date, market cap.** Everything else on the Numbers tab is derived from Yahoo.

**This is the central asymmetry with the TSX side and it should be read into every comparison.** The TMX exports arrive pre-filtered to mining, with commodity flags and a property register already in them — official data, published by the exchange. Here the exchange gave a list and a market cap, and commodity, geography and stage are all inferred from a business summary and a set of financial statements sourced from a free, unofficial API.

## What that bought

| | TSX / TSXV | ASX |
|---|---|---|
| Company count, size, concentration | ✓ | ✓ |
| Listings by year | ✓ | ✓ |
| Commodity | TMX register | inferred from prose |
| Where the assets are | TMX register | inferred from prose |
| Producer / explorer | ✓ | ✓ |
| **Developer** | not possible | **✓ balance sheet** |
| Turnover | TMX, dollars traded | estimated from volume |
| Post-listing returns | ✓ 595 of 1,079 | ✓ **611 of 726** |

Nine of nine, where before there were four of ten. Two of them came out *better* than the Canadian side:

**Developer.** The TSX had to give it up because "feasibility" appears once across 1,079 business summaries; here construction in progress on the balance sheet answers it directly.

**Returns coverage.** 84% of ASX miners can be anchored to their listing date against 55% on the TSX, because every ASX company has a listing date in the export and 224 TSXV companies do not.

## Who counts as a miner

**There is no mining flag in either source**, so the population is a judgement made in `enrich_asx_dataset.py` and re-runnable by editing it.

Two rules, in order:

1. **Yahoo's `industry` is authoritative when it names a mining industry** — Gold, Copper, Silver, Aluminum, Uranium, Coking Coal, Thermal Coal, and the two "Other … Metals & Mining" buckets. 704 companies.
2. **Otherwise the business summary has to say something only a miner says** — that it explores *for* something, or holds deposits, ore bodies, tenements or mineral properties. 672 companies, overlapping heavily with the first rule.

| | Companies | Market cap |
|---|---|---|
| GICS Materials, fetched | 775 | A$1,180B |
| **Mining population** | **726** | **A$1,079B** |
| Excluded | 49 | A$100B |

### Why positive evidence, not an exclusion list

The first attempt used a list of manufacturing words to knock out non-miners. It got **BCI Minerals** wrong — a salt and potash developer whose summary mentions food and fertiliser — while a hand-written list of the big names would never have caught the fifty small non-miners underneath them.

What actually separates a miner from its suppliers is that a miner explores *for* something and holds ground. Suppliers talk about products, services and solutions. On that test:

- **Excluded correctly:** Amcor (packaging), James Hardie (building materials), BlueScope (steel products), Orica and Dyno Nobel (explosives), Sims (recycling), Imdex — *"a mining-tech company, provides drilling products"* — and Vysarn (drilling services).
- **Kept correctly:** Champion Iron, MGX, Fenix, Grange, Brockman and GWR, all iron ore miners that **Yahoo files under "Steel"** alongside BlueScope. Excluding the Steel industry wholesale would have thrown away eleven miners to remove two manufacturers.
- Also kept: Silver Mines Limited, which Yahoo classifies as **Farm Products**.

22 spot checks, all correct.

## Stage — how Producer, Developer and Explorer are decided

**No exchange publishes a lifecycle stage.** There is no such field in the ASX export, none in the TMX files, and none in Yahoo. Every stage label in this report is assigned by `classify_stage()` in `enrich_asx_dataset.py`, from financial statements. It can be re-run with different thresholds by editing that function.

The rules are applied **in order, first match wins**. Order matters: a royalty company has revenue, so it would be labelled a producer if the revenue test ran first.

| # | Test | Result | n |
|---|---|---|---|
| 1 | Summary names royalties or streaming | Royalty / Streamer | 3 |
| 2 | Revenue ≥ A$1M **and** a cost-of-revenue line exists | Producer | 103 |
| 3 | Revenue ≥ A$10M with no cost line | Producer | 12 |
| 4 | Construction in progress, and it is material | Developer | 15 |
| 5 | Financial statements exist, but no revenue | Explorer | 576 |
| 6 | Nothing returned | Unknown | 17 |

### Why each test is shaped that way

**Producer is revenue — but revenue from what?** A junior showing A$1.0M of revenue and A$1.0M of gross profit has no cost of revenue at all. That is not metal; it is interest on the placement money, or a one-off tenement sale. Battery Age was the case that exposed it. But *requiring* a cost line is too strict, because Yahoo simply omits it for IGO (A$512M) and Catalyst (A$317M) — real producers with real mines. Hence the two-level floor: **A$1M when a cost line proves something was sold, A$10M when it has to stand on size alone.** The lowest-revenue company that qualifies is at A$1.05M. Tightening this moved producers from 162 to 115.

**Developer is construction in progress, and only that.** A capex test was tried first and had to be thrown out. Under AASB 6, Australian explorers *capitalise exploration expenditure* — drilling arrives on the cash flow statement as capex, indistinguishable from mine building. The rule "capex above 10% of assets" labelled **226 companies as developers**, including Southern Cross Gold, a A$3.3B explorer, and Vita Resources, a A$1.9M shell whose entire capex was a single drill programme. Any capex rule measures how hard a company is drilling, not whether it is building a mine.

`Construction In Progress` is a different line: it is the balance-sheet account for assets being built and not yet commissioned. Material means **A$5M or 5% of total assets**, which stops a A$50,000 workshop counting. That gives 15 companies, from Vertex at A$2.5M to Alpha HPA at A$213M — Core Lithium, Galan, Talga, Hastings, Cyprium and nine others, all genuinely mid-build.

**Royalty and streaming come out first** because they break the revenue test by construction: they have revenue and no cost of revenue, because they operate nothing. Deterra collects A$242M against Australian iron ore without owning a mine.

**Explorer is a residual, and that is the honest description of it.** It means "has financial statements, has no revenue, is not building anything" — 576 companies, 79% of the population. It bundles a A$3.3B explorer with a A$1M shell that has not drilled in three years. Nothing in Yahoo separates those, because the distinction lives in drill results and JORC resource statements, which are announcements rather than data.

### What this cannot see

**Stage is today's stage, applied to all of history.** Nothing dates the transition, so a company that floated as an explorer and poured its first gold in 2019 counts as a producer for its entire price series. Every return split by stage on the Charts tab is therefore a statement about outcomes, not about strategies.

**"Feasibility" is not detectable in prose.** It appears twice across 775 ASX business summaries and once across 1,079 Canadian ones. This is why the TSX side has no developer category at all — the balance sheet answered a question the text could not, and only because AASB and IFRS require the line.

**The stage is as stale as the last filing.** A company that started construction after its most recent annual report reads as an explorer here.

## Coverage

What Yahoo actually returned, across 775 companies:

| Field | Coverage | Used for |
|---|---|---|
| `summary` | 99.7% | commodity, geography, miner test |
| `industry` | 99.7% | primary commodity, miner test |
| `total_assets` | 97.8% | statements exist at all |
| `capex` | 95.4% | — rejected, see above |
| `revenue_stmt` | 35.6% | producer test |
| `construction_in_progress` | 16.6% | developer test |

The low figures on the last two are **not** coverage failures. 35.6% having a revenue line *is* the producer/explorer split, and most companies genuinely have nothing under construction.

## Handling notes

- **21 companies show no market cap** in the ASX export — suspended lines, read as blank rather than zero.
- **Australian dollars, never converted.** Size bands use the same numeric thresholds as the TSX chart so the shapes compare, but the currencies do not.
- **Listing dates are DD/MM/YYYY**, confirmed by day values above 12. All rows have one — no ASX equivalent of the 224 TSXV companies with no listing date.
- **Coal and uranium partly excluded.** Dropping the Energy sector removed Yancoal and Whitehaven but left 13 coal and uranium miners filed under Materials. The TMX population carries both in full.
- **Survivorship**, as everywhere: only companies listed on 26 August 2026 appear.

## Prices

`fetch_asx_prices.py` is the ASX twin of `fetch_prices.py` — separate script, separate cache, identical milestones — so the two return curves line up column for column. 706 tickers fetched, none failed. Returns are measured against the mean of a company's first five trading days rather than its opening print, because day zero on a junior is thin, wide and often just the placement price.

Three things had to be handled, and each one changes a number:

**99 companies have no price near their listing.** 73 of them listed before 2000. Yahoo has no 1980s or 1990s ASX data, so the oldest cohort is largely unanchorable — the same shape of gap as the TSX's 224 missing listing dates, arriving for a different reason.

**16 companies are excluded as suspected backdoor listings.** Antilles Gold states a 1993 listing; the price series starts January 1988. A mining company reversing into a dormant shell inherits its ticker and its history, so the anchor belongs to the shell. `covers_listing`, the flag the TSX side uses, reads `True` for exactly these cases — a series that starts early certainly covers the listing. The flag that works is `days_price_before_listing`, and anything over 90 days is dropped from the returns.

**Seven companies have a negative adjusted close.** Yahoo back-adjusts distributions, so when a company returns more capital per share than the share was then worth, the adjusted series runs through zero. AIC Mines is negative for the twenty-one years from 1993 to 2014. Substituting the unadjusted close would recover the row, but only by turning a total return into a price return for that one company, so the quotes are dropped and the loss is reported instead. This is the same fault that produced a −100.8% return on the TSX side before it was caught.

## What is still missing

1. **A property register.** Geography is inferred from prose that names the flagship and stops, so offshore counts are a floor, not a count.
2. **Dilution.** `get_shares_full` would give shares outstanding as a time series; the collection script has a `--shares` flag for it, not yet run. This is now the largest remaining gap, because a share price return says nothing about how much stock was issued to get there — and 31% of these companies have consolidated.
3. **Stage at listing.** Stage is what a company is today. Every return split by stage therefore describes outcomes, not strategies, and nothing in either source dates the transition.
4. **Delisted companies.** Nothing here recovers them, so survivorship stands on both markets.
