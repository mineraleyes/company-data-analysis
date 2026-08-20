# Stage 2 — Looking broader

*Notes only. Nothing fetched yet. Revised after the TMX mining properties file closed two gaps.*

## What Stage 1 already closed

**Commodity classification is done, and it cost nothing.**

The TMX mining properties file supplied commodity for 92% of companies and asset jurisdiction for 94%. That removes the largest and most expensive item this list previously carried — manual classification of 1,079 names, or a commercial data licence.

Asset location is solved too, at province and state granularity.

## Historical TMX files

**The only route to attrition, and the cheapest thing on this list.**

Prior months of both the issuer list and the properties list are obtainable and parse identically to what's already built. Confirmed rather than assumed: the June and July files already differ by 10 departures, 5 arrivals and 1 board change in a single month.

Could produce:

- **Survival curve** — share of each listing cohort still listed after 1, 3, 5, 10 years, split by size band or listing route. Nothing else can produce this.
- **New listings per year by commodity** — the hype cycle made visible; the lithium wave and the uranium wave before it.
- **Commodity pivot flow** — companies that changed commodity between files, old → new. Quantifies how much of the sector is chasing rather than mining.
- **Dilution rate** — median annual share-count growth, juniors versus producers.

## TMX Market Intelligence (MiG) report

**Financings are the missing half of "where the money goes".**

TMX publishes year-to-date financings by sector alongside listings and trading activity. That is primary-market money — capital actually raised — rather than shares changing hands between investors. Same publisher as the files already in use, so the format is likely familiar.

Could produce:

- **Capital raised per year by sector** — the funding cycle, which is the real junior heartbeat.
- **Raised versus traded** — primary money against secondary money, side by side.
- **Raise size distribution** — typical financing on TSXV versus TSX.
- **Capital absorbed per dollar of market cap, by commodity.**

## SEDAR+ financials

**Fixes the funded-versus-failing distinction — the sharpest remaining cut in the junior space.**

Free and public. Cash, burn, working capital. Unstructured PDFs at high volume, so scope it to a subset rather than all 896 juniors.

Could produce:

- **Runway histogram** — months of cash remaining. Probably the single most useful chart on this list: *"X% of TSXV juniors have under 12 months of cash."*
- **Cash as a share of market cap** — surfaces companies trading below their bank balance.
- **Runway versus % traded** — is attention going to the funded companies or the doomed ones?

## Commodity price series

**Previously blocked behind commodity tagging; now joins straight onto the commodity flags.**

Gold, copper, lithium, uranium spot and futures. Widely available free.

Could produce:

- **Listings against price, lagged** — does a rising price drive new listings, and by how many months?
- **Correlation by commodity** — do gold companies actually track gold? Producers likely will; juniors likely won't.

## Fraser Institute Mining Survey

**Adds a policy-risk dimension to every company in one merge.**

Free, annual jurisdiction attractiveness scores. Joins directly to `property_jurisdictions` at province and state level.

Could produce:

- **Jurisdiction risk score per company**, weighted across its properties — a new sortable column.
- **Market cap by risk quartile** — does the market discount bad jurisdictions, and by how much?
- **Sector exposure to bottom-quartile jurisdictions** — one number for the whole board.

## US-side trading data

**May invalidate part of the current dormancy read.**

141 companies are interlisted and 414 trade on OTCQX/QB. Canadian turnover could badly understate real activity — a company that looks dead on the TSXV might be trading normally on Nasdaq.

Could produce:

- **Where it really trades** — share of volume on the Canadian board versus abroad.
- **Re-scored turnover** including foreign volume — how many "dormant" companies aren't.

## Venture 50 / TSX30 history

**A cheap test of whether the accolade means anything.**

Published annually, free, several years deep.

Could produce:

- **What happened next** — market cap change 1, 2 and 3 years after being named.
- **Repeat appearances** and **survival rate** of past honourees.

## Smaller sources

**SEDI insider filings** — insider buying-to-selling ratio by commodity and size band.

**Provincial claim registries** (BC MTO, Ontario MLAS) — hectares held per company, an asset-size measure completely independent of market cap. Market cap per hectare by jurisdiction would be a genuinely novel cut.

## The remaining gap

**Stage — explorer, developer or producer — is now the most valuable missing field.**

It changes the meaning of every other number: a producer with 14% turnover is a different animal to an explorer with 14%. It is also a filter on charts that already exist rather than a set of new ones — turnover by stage, size by stage, commodity mix by stage. **Producers versus explorers by commodity** would be revealing; lithium especially.

Two routes, very different in cost:

- **Revenue as a proxy.** A company with meaningful revenue is a producer; one without is not. Reduces the problem to a single financial field, obtainable with the SEDAR+ work above.
- **NI 43-101 technical reports.** Resource and reserve estimates, grades, tonnage, named projects. Worth less than it was — commodity and location no longer need it — while remaining the heaviest extraction job here. Only justified if project-level detail is genuinely required.

## Open questions

1. **Primary or secondary money?** Capital raised, or trading activity? Decides whether the MiG report and SEDAR financings matter at all.
2. **Is a time dimension wanted?** If yes, scope the TMX backfill — cheapest route, and the only one that recovers attrition.
3. **Company or project as the unit of analysis?** Project-level still looks too large for a one-off.
4. **Commercial data budget?** Much less pressing now the expensive item arrived free.
