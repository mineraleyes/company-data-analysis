"""
What can yfinance and EODHD each give you for one company?

    python explore/provider_explore.py                     # both, default tickers
    python explore/provider_explore.py --yf-only
    python explore/provider_explore.py --eodhd-only
    python explore/provider_explore.py --offline           # catalogues only
    python explore/provider_explore.py --yf CVE.TO --eodhd CVE.TO

Out: explore/provider_report.html   — three tabs, side nav, live sample data

API KEY
Read from, in order: --key, $EODHD_API_KEY, explore/.eodhd_key, then "demo".
Never hardcoded and never written to a tracked file — this repo is a client's,
and .eodhd_key is in .gitignore. Check with: git check-ignore -v explore/.eodhd_key

WHY THE EODHD SIDE PROBES APPLE
EODHD's free trial key returns almost nothing: the endpoints answer, the payloads
come back thin, and you learn about the trial rather than about the product. Its
"demo" key is the opposite — it serves EVERY data type without limitation, but
only for six symbols: AAPL.US, TSLA.US, VTI.US, AMZN.US, BTC-USD.CC and
EURUSD.FOREX. Apple is the fullest of them, so it is the default here.

That trade has to be read honestly. Apple is a US mega-cap: the best-covered
security on the best-covered exchange, and the exact opposite of a C$3M shell on
the TSX Venture exchange. What this probe shows is the SCHEMA at full fill —
which sections exist, how deep they go, what a populated General block actually
contains. It is evidence about structure. It is no evidence at all about whether
a junior miner would return any of it.

WHY THIS EXISTS
Standalone scratch work — nothing else in this repo imports it. The mining
analysis leans on yfinance for prices, revenue and a business summary, which is
a small corner of one provider. This walks every surface of both, says what each
one is, shows what actually came back for the same company, and then argues out
what a mining dataset could be built from each.

WHY BOTH ARE PROBED THE SAME WAY
The interesting comparison is not "who has more fields" — it is which provider
gives a fact as a STRUCTURED field rather than as prose you have to parse.
Yahoo makes you read a paragraph to learn what a company mines. EODHD has a
four-level GICS classification. That difference is worth more than any count.

SYMBOL FORMATS DIFFER
Yahoo says BHP.AX for the ASX; EODHD says BHP.AU. Yahoo and EODHD agree on .TO
for Toronto and .V for the Venture exchange. Any pipeline using both needs a
mapping table, which is itself a reason to pick one.
"""

import argparse
import datetime as dt
import html
import json
import os
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
OUT = HERE / "provider_report.html"
KEYFILE = HERE / ".eodhd_key"

YF_DEFAULT = "BHP.AX"
EODHD_DEFAULT = "AAPL.US"
EODHD_BASE = "https://eodhd.com/api"

# The demo key serves every data type without limitation for exactly these six.
# A free trial key does not, so when the symbol is one of them and no key was
# named explicitly, demo is strictly the better choice.
DEMO_TICKERS = {"AAPL.US", "TSLA.US", "VTI.US", "AMZN.US",
                "BTC-USD.CC", "EURUSD.FOREX"}

# ═════════════════════════════════════════════════════════════════════════════
# YFINANCE CATALOGUE
#   kind: "prop" plain attribute · "param" needs arguments
# ═════════════════════════════════════════════════════════════════════════════

YF_CATALOGUE = [
    ("Prices and corporate actions", [
        ("history", "param",
         "The OHLCV table. Open/High/Low/Close/Volume, plus Dividends and Stock "
         "Splits when actions=True. Close is ALREADY split-adjusted; Adj Close is "
         "split- and dividend-adjusted. Their ratio measures dividends, not "
         "consolidations."),
        ("history_metadata", "prop",
         "Non-pricing facts riding along with the price request: currency, "
         "exchange name and timezone, instrument type, first trade date, price "
         "hint, and the ranges and granularities Yahoo will serve."),
        ("actions", "prop",
         "Dividends and splits as one DataFrame. The only reliable way to see a "
         "consolidation, since it is invisible in the adjusted price."),
        ("dividends", "prop",
         "Dividend per share, dated. Includes returns of capital and spin-out "
         "distributions, which are not earnings."),
        ("splits", "prop",
         "Split factor, dated. Below 1 is a consolidation — 0.1 is a 10:1 rollback."),
        ("capital_gains", "prop",
         "Capital gains distributions. Funds and trusts only."),
    ]),
    ("Identity and description", [
        ("info", "prop",
         "A dict of 100+ keys: identity, business description, market data, "
         "valuation, ratios, dividends, share counts, analyst targets and "
         "governance risk. Broken out by theme in its own section."),
        ("fast_info", "prop",
         "A small, fast subset of info. Use when you only need a quote — it avoids "
         "the slow full info request."),
        ("isin", "prop", "ISIN. Often empty for non-US listings."),
        ("sec_filings", "prop",
         "Filing type, date and link. US registrants only — an ASX or TSX company "
         "will be empty."),
    ]),
    ("Financial statements", [
        ("income_stmt", "prop",
         "Annual income statement, 4-5 years. Revenue, cost of revenue, gross "
         "profit, operating income, net income."),
        ("quarterly_income_stmt", "prop", "The same, by quarter."),
        ("ttm_income_stmt", "prop", "Trailing twelve months. Newer yfinance only."),
        ("balance_sheet", "prop",
         "Annual balance sheet — and for a miner the capitalised property, Net PPE "
         "and Construction In Progress that betray a mine being built."),
        ("quarterly_balance_sheet", "prop", "The same, by quarter."),
        ("cashflow", "prop",
         "Annual cash flow. Capital Expenditure and Issuance Of Capital Stock both "
         "sit here — a mine build and the raise that paid for it."),
        ("quarterly_cashflow", "prop",
         "The same, by quarter. The one that gives a current burn rate."),
        ("ttm_cashflow", "prop", "Trailing twelve months. Newer yfinance only."),
        ("earnings", "prop", "Legacy. Deprecated — income_stmt replaces it."),
        ("quarterly_earnings", "prop", "Legacy quarterly. Also deprecated."),
    ]),
    ("Share count and ownership", [
        ("get_shares_full", "param",
         "Shares outstanding as a TIME SERIES. The field the mining analysis was "
         "missing: with it, dilution becomes measurable."),
        ("major_holders", "prop", "Insider and institutional percentages."),
        ("institutional_holders", "prop",
         "Named institutions, shares held, value, percentage."),
        ("mutualfund_holders", "prop", "The same for mutual funds."),
        ("insider_purchases", "prop", "Insider buying and selling, six months, netted."),
        ("insider_transactions", "prop", "Individual insider trades."),
        ("insider_roster_holders", "prop", "Named insiders and current holdings."),
    ]),
    ("Analyst coverage and estimates", [
        ("recommendations", "prop", "Ratings distribution over recent months."),
        ("recommendations_summary", "prop", "The same, summarised."),
        ("upgrades_downgrades", "prop", "Rating changes with firm, date, from/to."),
        ("analyst_price_targets", "prop",
         "Current, high, low, mean, median targets. Newer yfinance only."),
        ("earnings_estimate", "prop", "Consensus EPS by period."),
        ("revenue_estimate", "prop", "Consensus revenue by period."),
        ("earnings_history", "prop", "Estimated versus actual EPS — the surprise history."),
        ("eps_trend", "prop", "How consensus EPS has moved."),
        ("eps_revisions", "prop", "Upward and downward revision counts."),
        ("growth_estimates", "prop", "Company, sector and index growth."),
        ("earnings_dates", "prop", "Past and upcoming earnings dates."),
        ("calendar", "prop", "Next earnings, ex-dividend and dividend dates."),
    ]),
    ("Sustainability and governance", [
        ("sustainability", "prop",
         "ESG risk scores plus controversy flags and involvement categories "
         "including thermal coal. Sparse outside large caps."),
    ]),
    ("News and options", [
        ("news", "prop", "Recent headlines with publisher, link and timestamp."),
        ("options", "prop", "Tuple of option expiry dates."),
        ("option_chain", "param", "Calls and puts for one expiry."),
    ]),
    ("Funds and ETFs", [
        ("funds_data", "prop", "Holdings, sector weights, allocation, fees."),
    ]),
]

INFO_GROUPS = [
    ("Identity", ["symbol", "shortName", "longName", "exchange",
                  "fullExchangeName", "quoteType", "currency",
                  "financialCurrency", "market", "region"]),
    ("Business", ["sector", "sectorKey", "industry", "industryKey",
                  "fullTimeEmployees", "website", "irWebsite", "phone",
                  "address1", "city", "state", "zip", "country",
                  "longBusinessSummary"]),
    ("Market data", ["currentPrice", "regularMarketPrice", "previousClose",
                     "open", "dayLow", "dayHigh", "volume", "averageVolume",
                     "averageVolume10days", "bid", "ask", "bidSize", "askSize",
                     "marketCap", "fiftyTwoWeekLow", "fiftyTwoWeekHigh",
                     "fiftyDayAverage", "twoHundredDayAverage", "beta",
                     "52WeekChange"]),
    ("Share count and short interest",
     ["sharesOutstanding", "floatShares", "impliedSharesOutstanding",
      "sharesShort", "sharesShortPriorMonth", "shortRatio",
      "shortPercentOfFloat", "heldPercentInsiders", "heldPercentInstitutions"]),
    ("Valuation", ["trailingPE", "forwardPE", "priceToBook",
                   "priceToSalesTrailing12Months", "enterpriseValue",
                   "enterpriseToRevenue", "enterpriseToEbitda", "bookValue",
                   "pegRatio", "trailingPegRatio"]),
    ("Income and margins", ["totalRevenue", "revenuePerShare", "revenueGrowth",
                            "grossProfits", "grossMargins", "ebitda",
                            "ebitdaMargins", "operatingMargins", "profitMargins",
                            "netIncomeToCommon", "trailingEps", "forwardEps",
                            "earningsGrowth", "earningsQuarterlyGrowth"]),
    ("Balance sheet and returns", ["totalCash", "totalCashPerShare", "totalDebt",
                                   "debtToEquity", "currentRatio", "quickRatio",
                                   "returnOnAssets", "returnOnEquity",
                                   "freeCashflow", "operatingCashflow"]),
    ("Dividends", ["dividendRate", "dividendYield", "trailingAnnualDividendRate",
                   "trailingAnnualDividendYield", "fiveYearAvgDividendYield",
                   "payoutRatio", "exDividendDate", "lastDividendValue",
                   "lastDividendDate"]),
    ("Analyst view", ["targetHighPrice", "targetLowPrice", "targetMeanPrice",
                      "targetMedianPrice", "recommendationMean",
                      "recommendationKey", "numberOfAnalystOpinions"]),
    ("Governance risk", ["auditRisk", "boardRisk", "compensationRisk",
                         "shareHolderRightsRisk", "overallRisk",
                         "governanceEpochDate"]),
]

MODULE_LEVEL = [
    ("yf.download(tickers, ...)",
     "Many tickers at once, one combined frame. Far faster than looping."),
    ("yf.Tickers('A B C')", "A bundle sharing one session."),
    ("yf.Search(query) / yf.Lookup(query)", "Symbol lookup by name."),
    ("yf.Sector(key) / yf.Industry(key)",
     "yf.Industry('gold') returns Yahoo's own list of gold miners — a free "
     "cross-check on any commodity classification you build."),
    ("yf.Screener() / yf.EquityQuery",
     "Server-side screening without downloading the universe."),
]

# ═════════════════════════════════════════════════════════════════════════════
# EODHD CATALOGUE
#   (label, path template, cost_in_api_calls, description)
#   {s} = symbol, {k} = api key
# ═════════════════════════════════════════════════════════════════════════════

EODHD_ENDPOINTS = [
    ("Account and coverage", [
        ("user", "/user?api_token={k}&fmt=json", 0,
         "Your plan, daily call limit and calls used today. Free — call it first "
         "and last, and the difference tells you what this script cost."),
        ("exchanges-list", "/exchanges-list/?api_token={k}&fmt=json", 1,
         "Every exchange EODHD covers, with country and currency. <strong>The "
         "endpoint that would settle the question the marketing pages will not: "
         "whether the ASX and the TSX Venture exchange are actually in the "
         "70+.</strong> Exchange-wide endpoints are outside what the demo key "
         "serves, so a refusal here is a fact about the key, not about coverage — "
         "and it means the coverage question stays open until someone pays."),
        ("exchange-symbol-list AU", "/exchange-symbol-list/AU?api_token={k}&fmt=json", 1,
         "Every listed security on the ASX. Compare the count to the 1,843 rows in "
         "your own ASX export — and note it carries Type and Isin per row, which "
         "your export does not."),
        ("exchange-symbol-list TO", "/exchange-symbol-list/TO?api_token={k}&fmt=json", 1,
         "Every listed security on the TSX."),
        ("exchange-symbol-list V", "/exchange-symbol-list/V?api_token={k}&fmt=json", 1,
         "Every listed security on the TSX Venture exchange — the board that is "
         "80% of your mining population."),
        ("exchange-symbol-list V (delisted)",
         "/exchange-symbol-list/V?api_token={k}&fmt=json&delisted=1", 1,
         "<strong>The survivorship fix.</strong> Companies that have LEFT the "
         "Venture exchange. Every number in the mining report is survivor-only "
         "because TMX publishes no delisted list; this is that list, as a "
         "parameter."),
    ]),
    ("The company", [
        ("fundamentals", "/fundamentals/{s}?api_token={k}&fmt=json", 10,
         "One request, one deep nested JSON: General, Highlights, Valuation, "
         "SharesStats, Technicals, SplitsDividends, AnalystRatings, Holders, "
         "InsiderTransactions, ESGScores, outstandingShares, Earnings and three "
         "financial statements. The structural opposite of yfinance, where each of "
         "those is a separate attribute and a separate round trip. Costs 10 calls."),
    ]),
    ("Prices and actions", [
        ("eod", "/eod/{s}?api_token={k}&fmt=json&period=d&from=2026-06-01", 1,
         "End-of-day OHLCV with adjusted_close. Same content as yfinance history, "
         "but you choose the date range in the request rather than filtering after."),
        ("real-time", "/real-time/{s}?api_token={k}&fmt=json", 1,
         "Delayed quote — price, change, volume, previous close."),
        ("div", "/div/{s}?api_token={k}&fmt=json&from=2015-01-01", 1,
         "Dividend history with declaration, record, payment and period."),
        ("splits", "/splits/{s}?api_token={k}&fmt=json&from=2000-01-01", 1,
         "Split history as a ratio string. The consolidation signal."),
    ]),
    ("Everything else", [
        ("news", "/news?api_token={k}&s={s}&limit=5&fmt=json", 1,
         "Headlines with content, sentiment polarity, and tagged symbols. Yahoo "
         "gives headlines; this adds a sentiment score."),
        ("insider-transactions",
         "/insider-transactions?api_token={k}&code={s}&limit=5&fmt=json", 1,
         "Insider trades. US-heavy in practice."),
        ("calendar/ipos", "/calendar/ipos?api_token={k}&fmt=json&limit=5", 1,
         "Upcoming and recent listings — a forward view your snapshot cannot have."),
        ("screener",
         "/screener?api_token={k}&fmt=json&limit=5"
         "&filters=%5B%5B%22exchange%22%2C%22%3D%22%2C%22V%22%5D%5D", 1,
         "Server-side screening by exchange, sector, market cap. Filters here "
         "select TSXV listings — the whole population without downloading it."),
    ]),
]

# Sections of the fundamentals JSON worth calling out by name.
FUND_SECTIONS = {
    "General": "Identity, classification and the description. Where GicSector, "
               "GicGroup, GicIndustry, GicSubIndustry, Officers, Listings, "
               "IsDelisted and IPODate live.",
    "Highlights": "Headline financials — market cap, EBITDA, PE, EPS, margins, "
                  "ROE, revenue, book value, dividend.",
    "Valuation": "Trailing and forward PE, price/sales, price/book, EV multiples.",
    "SharesStats": "Shares outstanding and float, insider and institutional "
                   "percentages, short interest.",
    "Technicals": "Beta, 52-week range, moving averages, short ratio.",
    "SplitsDividends": "Forward yield, payout ratio, dividend dates, split history.",
    "AnalystRatings": "Rating, target price, and the buy/hold/sell distribution.",
    "Holders": "Institutions and funds, named, with share counts.",
    "InsiderTransactions": "Individual insider trades.",
    "ESGScores": "Environmental, social and governance scores plus controversy flags.",
    "outstandingShares": "Shares outstanding BY YEAR AND QUARTER — the dilution "
                         "series, delivered as part of the same request rather "
                         "than a separate call.",
    "Earnings": "History, trend and annual earnings with estimates and surprises.",
    "Financials": "Balance_Sheet, Cash_Flow and Income_Statement, each yearly and "
                  "quarterly, in one payload.",
}

# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — deriving mining data, now from either provider
# ═════════════════════════════════════════════════════════════════════════════

MINING = [
    {
        "id": "m-commodity",
        "title": "What commodities they work with",
        "verdict": "Solvable from both — but EODHD gives it as a field and Yahoo "
                   "makes you parse a paragraph.",
        "rows": [
            {"src": "EODHD",
             "fields": ["General.GicSector", "General.GicGroup",
                        "General.GicIndustry", "General.GicSubIndustry"],
             "how": "The full four-level GICS tree. Sub-industry splits Metals "
                    "&amp; Mining into Gold, Copper, Diversified Metals &amp; "
                    "Mining, Aluminum, Steel, Precious Metals &amp; Minerals, Coal "
                    "&amp; Consumable Fuels. <strong>This is the fix for the ASX "
                    "problem.</strong> Your ASX export carries only the industry "
                    "<em>group</em> — 'Materials', 775 companies, roughly A$92B of "
                    "packaging, steel and chemicals mixed in, and coal and uranium "
                    "miners exiled to Energy. Sub-industry defines the mining "
                    "population properly, on one taxonomy, for both markets.",
             "limit": "Still one label per company, so a polymetallic miner is "
                      "reduced to its headline metal. 'Diversified Metals &amp; "
                      "Mining' will absorb a lot of the juniors."},
            {"src": "Yahoo",
             "fields": [".info['industry']", ".info['industryKey']"],
             "how": "One industry from a fixed mining list — Gold, Silver, Copper, "
                    "Aluminum, Steel, Uranium, Coking Coal, Thermal Coal, and two "
                    "'Other … Metals &amp; Mining' buckets. A free primary label, "
                    "which is the thing the TMX export could not give: there we had "
                    "twenty overlapping flags and refused to derive a primary, "
                    "because every precedence rule made Agnico Eagle a copper "
                    "company.",
             "limit": "The two 'Other' buckets are broad — lithium, rare earths, "
                      "nickel, cobalt and zinc all land in them, unsplit."},
            {"src": "Both",
             "fields": [".info['longBusinessSummary']", "General.Description"],
             "how": "Both carry prose that names commodities in the open: 'explores "
                    "for gold, silver, copper, lead, zinc, molybdenum, nickel, and "
                    "cobalt deposits'. Keyword-match against a vocabulary and you "
                    "recover the full <em>set</em>, which is what the TMX comm_* "
                    "booleans encode. Classification gives the primary; prose gives "
                    "the set.",
             "limit": "Unstructured, and it says what a company claims to explore "
                      "for rather than what it holds. Descriptions go stale — a "
                      "2023 pivot to lithium may still read as gold. EODHD does not "
                      "document where its Description text comes from, so assume "
                      "the same aggregated-blurb genus as Yahoo until you have read "
                      "twenty of them side by side."},
        ],
        "verdict_note": "Use GICS sub-industry as the primary if you have EODHD, "
                        "Yahoo industry if you do not, and keyword-match either "
                        "description for the set.",
    },
    {
        "id": "m-stage",
        "title": "Producer, developer or explorer",
        "verdict": "Producer is a fact from either. Developer needs the balance "
                   "sheet — and neither provider's prose will give it to you.",
        "rows": [
            {"src": "Both",
             "fields": [".info['totalRevenue']", "Highlights.Revenue",
                        "income_stmt → Total Revenue",
                        "Financials.Income_Statement"],
             "how": "Revenue above a floor means the company sells metal. The only "
                    "part of stage that is a fact rather than a judgement, which is "
                    "why the classifier decides it first. A floor near C$1M keeps "
                    "treasury interest from reading as production.",
             "limit": "Statement coverage thins badly on microcaps in both. Absence "
                      "of revenue data is not evidence of no revenue — and the "
                      "smallest companies are most of this population."},
            {"src": "Both",
             "fields": ["balance_sheet → Construction In Progress, Net PPE",
                        "cashflow → Capital Expenditure",
                        "Financials.Balance_Sheet", "Financials.Cash_Flow"],
             "how": "<strong>The developer signal, and the reason to want financial "
                    "statements at all.</strong> No revenue, large and rising "
                    "Construction In Progress, and a capex spike means a mine is "
                    "being built. That is a balance-sheet fact, not a keyword — the "
                    "way around the finding that killed the first attempt, where "
                    "'feasibility' appeared once across 1,079 business summaries. "
                    "Text can never separate Seabridge from a shell; a construction "
                    "line can.",
             "limit": "Under IFRS, Canadian and Australian juniors capitalise "
                      "exploration into PP&amp;E too, so PP&amp;E alone is noisy. "
                      "Construction In Progress is sharper but neither provider "
                      "populates it universally. Expect it to work on the large "
                      "half of non-producers and fail quietly on the small half."},
            {"src": "Yahoo",
             "fields": [".info['fullTimeEmployees']"],
             "how": "Crude and surprisingly discriminating: an explorer runs on "
                    "fifteen people, a producing mine employs thousands. EODHD "
                    "carries FullTimeEmployees in General too.",
             "limit": "Often missing, and contractor-heavy operations understate. "
                      "Corroborate, never decide."},
        ],
        "verdict_note": "Revenue decides producer. Construction In Progress plus "
                        "capex, on no revenue, decides developer. The rest are "
                        "explorers — with the caveat that for the smallest "
                        "companies the label means 'no statements available' rather "
                        "than 'does nothing'.",
    },
    {
        "id": "m-geography",
        "title": "Where they operate",
        "verdict": "Weak from both, and weaker than the TMX property file. Neither "
                   "has a project register.",
        "rows": [
            {"src": "Both",
             "fields": [".info['longBusinessSummary']", "General.Description"],
             "how": "The prose names countries and projects — 'in Argentina, Côte "
                    "d'Ivoire, Mexico, Peru, and Senegal', or 'the Eskay Creek "
                    "project … in British Columbia'. Match against a gazetteer for "
                    "an operating-location set, often with named projects as a "
                    "bonus.",
             "limit": "Usually names the flagship and stops. A company with ground "
                      "in six countries may yield two, with no completeness "
                      "guarantee of any kind — unlike the TMX property file, which "
                      "is a register."},
            {"src": "EODHD",
             "fields": ["General.CountryName", "General.CountryISO",
                        "General.AddressData", "General.Listings"],
             "how": "Domicile as structured fields rather than a string to parse, "
                    "plus <em>Listings</em> — the company's other quotes. A TSX "
                    "miner also on the ASX resolves to one entity instead of two, "
                    "which your two-market report currently cannot do.",
             "limit": "Domicile is the office, not the ground. The whole "
                      "domicile-versus-operations heatmap exists to show how often "
                      "those differ."},
            {"src": "Yahoo",
             "fields": [".info['financialCurrency']", ".info['currency']"],
             "how": "Reporting currency against trading currency. A TSX company "
                    "reporting in USD usually earns outside Canada. Weak, but free "
                    "where the description says nothing.",
             "limit": "Inference. Plenty of domestic producers report in USD "
                      "because metal is priced in it."},
        ],
        "verdict_note": "Good enough for a country-level map with explicit gaps. "
                        "Any count built from prose undercounts by construction.",
    },
    {
        "id": "m-other",
        "title": "The things worth more than any of the above",
        "verdict": "Two of these close caveats that run through every number in "
                   "the current report.",
        "rows": [
            {"src": "EODHD",
             "fields": ["/exchange-symbol-list/{EXCH}?delisted=1",
                        "General.IsDelisted", "General.DelistedDate"],
             "how": "<strong>Survivorship.</strong> The single biggest caveat in "
                    "the mining report — every figure covers only companies still "
                    "listed, so the real distribution of outcomes is worse than "
                    "anything shown. Recovering the dead from the TMX MiG archives "
                    "was judged too heavy to be worth it. Here it is a query "
                    "parameter and a boolean.",
             "limit": "Depth of delisted history is unverified — check how far back "
                      "the Venture list actually goes before believing a "
                      "survivorship correction built on it."},
            {"src": "Both",
             "fields": ["get_shares_full(start=…)", "outstandingShares"],
             "how": "<strong>Dilution.</strong> Shares outstanding as a time "
                    "series. A junior funds itself by issuing stock, so share-count "
                    "growth is the truest measure of what exploration cost "
                    "shareholders — and it closes gap #1 on the Stage 1 Dataset "
                    "tab, where dilution is currently listed as unmeasurable. With "
                    "price it also reconstructs market cap historically, turning a "
                    "snapshot into a time series. EODHD ships it inside the same "
                    "fundamentals request; Yahoo needs a separate call.",
             "limit": "History depth varies by company and thins on small listings."},
            {"src": "Both",
             "fields": ["cashflow → Issuance Of Capital Stock",
                        "Financials.Cash_Flow"],
             "how": "<strong>Financing cadence.</strong> How much was raised and "
                    "how often — the private-placement history that otherwise needs "
                    "SEDAR+, arriving already annualised.",
             "limit": "Annual granularity merges individual placements."},
            {"src": "Both",
             "fields": [".info['totalCash']", "quarterly_cashflow",
                        "Highlights", "Financials.Cash_Flow"],
             "how": "<strong>Cash runway.</strong> Cash over quarterly burn gives "
                    "quarters until the next raise — for a junior the most "
                    "actionable number available, and it answers the Stage 2 "
                    "question 'who is about to need money' with no new source.",
             "limit": "Ignores committed spend and undrawn facilities. A prompt to "
                      "look, not a conclusion."},
            {"src": "EODHD",
             "fields": ["General.ISIN", "General.CUSIP", "General.LEI",
                        "General.OpenFigi", "General.PrimaryTicker"],
             "how": "<strong>Real join keys.</strong> You currently join TMX on "
                    "Co_ID and Yahoo on ticker, which is exactly what broke on "
                    "Teck's dual-class root symbol. ISIN and LEI are stable across "
                    "rebrands, consolidations and cross-listings.",
             "limit": "Coverage of LEI and CUSIP on small non-US names is uneven."},
            {"src": "EODHD",
             "fields": ["General.Officers"],
             "how": "The management list. In a sector where the same directors "
                    "appear across dozens of shells, this is joinable — and a "
                    "genuinely novel cut nothing else here supports.",
             "limit": "Depth outside large caps is unproven."},
            {"src": "EODHD",
             "fields": ["General.IPODate"],
             "how": "Listing date. 224 of your TSXV companies have none in the TMX "
                    "file, which is why a quarter of the cohort analysis is "
                    "unanchored and 222 rows have no return at all.",
             "limit": "May record the current listing rather than an original "
                      "float — the same QT and RTO problem the TMX date has."},
        ],
        "verdict_note": "Delisted companies and the dilution series are the two "
                        "that change what the analysis can claim. Neither is in "
                        "either exchange export.",
    },
]

MINING_CLOSING = (
    "The honest summary: Yahoo is free and unofficial, and its coverage is "
    "thinnest exactly where this sector is thickest — sub-C$25M companies on the "
    "TSXV and ASX. EODHD is paid and contractual and gives structure where Yahoo "
    "gives prose, but its microcap depth is the open question and no marketing "
    "page will answer it. Before spending anything, take twenty real tickers from "
    "the file — TSXV shells under C$5M and ASX small caps — and run them through "
    "the trial. The tail is where every vendor quietly fails, and it is most of "
    "this population."
)

# ═════════════════════════════════════════════════════════════════════════════
# PROBE HELPERS
# ═════════════════════════════════════════════════════════════════════════════

MAX_ROWS = 4
MAX_CELL = 120


def _flat(v):
    return " ".join(str(v).split())


def _short(v):
    s = _flat(v)
    return s if len(s) <= MAX_CELL else s[:MAX_CELL - 1] + "…"


def _kv_table(pairs, extra=0):
    rows = "".join(f"<tr><th>{html.escape(_short(k))}</th>"
                   f"<td>{html.escape(_short(v))}</td></tr>" for k, v in pairs)
    more = f"<p class='more'>+{extra} more</p>" if extra > 0 else ""
    return f"<table class='prev'>{rows}</table>{more}"


def describe(value):
    """(status, shape, preview_html) for a Python object."""
    import pandas as pd

    if value is None:
        return "empty", "None", ""

    if isinstance(value, pd.DataFrame):
        if value.empty:
            return "empty", "empty DataFrame", ""
        head = value.head(MAX_ROWS)
        rows = ["<tr><th></th>" + "".join(
            f"<th>{html.escape(_short(c))}</th>" for c in head.columns) + "</tr>"]
        for idx, row in head.iterrows():
            rows.append(f"<tr><th>{html.escape(_short(idx))}</th>"
                        + "".join(f"<td>{html.escape(_short(x))}</td>"
                                  for x in row) + "</tr>")
        more = (f"<p class='more'>+{value.shape[0] - MAX_ROWS} more rows</p>"
                if value.shape[0] > MAX_ROWS else "")
        return ("ok", f"DataFrame {value.shape[0]}×{value.shape[1]}",
                f"<table class='prev'>{''.join(rows)}</table>{more}")

    if isinstance(value, pd.Series):
        if value.empty:
            return "empty", "empty Series", ""
        return ("ok", f"Series, {len(value)} values",
                _kv_table(list(value.head(MAX_ROWS).items()),
                          len(value) - MAX_ROWS))

    if isinstance(value, dict):
        if not value:
            return "empty", "empty dict", ""
        keys = list(value)
        return ("ok", f"dict, {len(keys)} keys",
                _kv_table([(k, value[k]) for k in keys[:MAX_ROWS]],
                          len(keys) - MAX_ROWS))

    if isinstance(value, (list, tuple)):
        if not len(value):
            return "empty", f"empty {type(value).__name__}", ""
        first = value[0]
        if isinstance(first, dict):
            body = ", ".join(f"<code>{html.escape(str(k))}</code>"
                             for k in list(first)[:14])
            prev = f"<p class='more'>keys of first item</p><p class='wrap'>{body}</p>"
        else:
            prev = ("<p class='wrap'>"
                    + ", ".join(html.escape(_short(x)) for x in value[:10]) + "</p>")
        return "ok", f"{type(value).__name__}, {len(value)} items", prev

    return "ok", type(value).__name__, f"<p class='wrap'>{html.escape(_flat(value))}</p>"


def probe_yf(tk, name, kind):
    t0 = time.perf_counter()
    try:
        if not hasattr(tk, name):
            return {"status": "absent", "shape": "not in this yfinance version",
                    "preview": "", "ms": 0}
        attr = getattr(tk, name)
        if kind == "param":
            if name == "history":
                attr = attr(period="1mo", auto_adjust=False, actions=True)
            elif name == "get_shares_full":
                attr = attr(start=dt.date.today() - dt.timedelta(days=730))
            elif name == "option_chain":
                exps = getattr(tk, "options", ())
                if not exps:
                    return {"status": "empty", "shape": "no expiries listed",
                            "preview": "", "ms": 0}
                attr = attr(exps[0]).calls
            else:
                attr = attr()
        status, shape, preview = describe(attr)
        return {"status": status, "shape": shape, "preview": preview,
                "ms": (time.perf_counter() - t0) * 1000}
    except Exception as e:
        return {"status": "error", "shape": f"{type(e).__name__}: {_short(e)}",
                "preview": "", "ms": (time.perf_counter() - t0) * 1000}


def probe_eodhd(path, symbol, key):
    """One EODHD GET. Never raises."""
    import requests
    url = EODHD_BASE + path.format(s=symbol, k=key)
    t0 = time.perf_counter()
    try:
        r = requests.get(url, timeout=45)
        ms = (time.perf_counter() - t0) * 1000
        if r.status_code != 200:
            return {"status": "error", "shape": f"HTTP {r.status_code}",
                    "preview": f"<p class='wrap'>{html.escape(_short(r.text))}</p>",
                    "ms": ms, "data": None}
        try:
            data = r.json()
        except ValueError:
            return {"status": "ok", "shape": f"text, {len(r.text)} chars",
                    "preview": f"<p class='wrap'>{html.escape(_short(r.text))}</p>",
                    "ms": ms, "data": None}

        if data in (None, {}, []):
            return {"status": "empty", "shape": "no rows", "preview": "",
                    "ms": ms, "data": data}
        if isinstance(data, list):
            first = data[0]
            if isinstance(first, dict):
                prev = ("<p class='more'>keys of first row</p><p class='wrap'>"
                        + ", ".join(f"<code>{html.escape(str(k))}</code>"
                                    for k in list(first)[:16]) + "</p>"
                        + _kv_table(list(first.items())[:MAX_ROWS],
                                    max(0, len(first) - MAX_ROWS)))
            else:
                prev = ("<p class='wrap'>"
                        + ", ".join(html.escape(_short(x)) for x in data[:10]) + "</p>")
            return {"status": "ok", "shape": f"list, {len(data):,} rows",
                    "preview": prev, "ms": ms, "data": data}
        if isinstance(data, dict):
            return {"status": "ok", "shape": f"dict, {len(data)} keys",
                    "preview": _kv_table(list(data.items())[:MAX_ROWS],
                                         max(0, len(data) - MAX_ROWS)),
                    "ms": ms, "data": data}
        return {"status": "ok", "shape": type(data).__name__,
                "preview": f"<p class='wrap'>{html.escape(_short(data))}</p>",
                "ms": ms, "data": data}
    except Exception as e:
        return {"status": "error", "shape": f"{type(e).__name__}: {_short(e)}",
                "preview": "", "ms": (time.perf_counter() - t0) * 1000, "data": None}


def find_key(cli_key, symbol, force_demo=False):
    """Explicit key wins. Otherwise prefer demo on the six symbols it fully
    serves, since a trial key on those returns strictly less."""
    if force_demo:
        return "demo", "demo (forced)"
    if cli_key:
        return cli_key, "--key"
    if symbol in DEMO_TICKERS:
        return "demo", "demo (full data on this symbol)"
    if os.environ.get("EODHD_API_KEY"):
        return os.environ["EODHD_API_KEY"], "$EODHD_API_KEY"
    if KEYFILE.exists():
        return KEYFILE.read_text(encoding="utf-8").strip(), str(KEYFILE.name)
    return "demo", "demo (no key found)"


# ═════════════════════════════════════════════════════════════════════════════
# RENDER
# ═════════════════════════════════════════════════════════════════════════════

CSS = """
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:#fcfcfb;color:#1a1a1a;
  font:15px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
header{position:sticky;top:0;z-index:20;background:#fafaf9;
  border-bottom:1px solid #e4e4e4;padding:14px 28px 0}
.hin{max-width:1180px;margin:0 auto}
h1{font-size:19px;margin:0;letter-spacing:-.01em}
.sub{color:#7a7a7a;font-size:12.5px;margin:3px 0 0}
nav.tabs{display:flex;gap:2px;margin:12px 0 0}
nav.tabs button{appearance:none;font:inherit;font-size:13.5px;cursor:pointer;
  background:none;border:0;border-bottom:2px solid transparent;padding:8px 14px;
  color:#6a6a6a}
nav.tabs button:hover{color:#1a1a1a}
nav.tabs button[aria-selected=true]{color:#1a1a1a;font-weight:600;
  border-bottom-color:#1a1a1a}
.layout{max-width:1180px;margin:0 auto;padding:0 28px;display:grid;
  grid-template-columns:224px 1fr;gap:40px;align-items:start}
aside{position:sticky;top:112px;max-height:calc(100vh - 134px);overflow-y:auto;
  padding:26px 0 40px}
aside .navgroup{font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;
  color:#a0a0a0;margin:18px 0 7px}
aside a{display:block;font-size:12.5px;line-height:1.35;color:#5a5a5a;
  text-decoration:none;padding:5px 10px;border-left:2px solid #ececec;margin-left:1px}
aside a:hover{color:#1a1a1a;background:#f4f4f2}
aside a.on{color:#1a1a1a;font-weight:600;border-left-color:#1a1a1a;background:#f4f4f2}
main{padding:26px 0 120px;min-width:0}
h2{font-size:17px;margin:40px 0 4px;padding-bottom:8px;border-bottom:1px solid #e4e4e4;
  scroll-margin-top:124px}
h2:first-child{margin-top:4px}
h2 .count{float:right;font-weight:400;font-size:12px;color:#9a9a9a;padding-top:5px}
h3{font-size:13.5px;margin:24px 0 8px;color:#2a2a2a;scroll-margin-top:124px}
.lede{color:#5a5a5a;font-size:13.5px;margin:14px 0 24px;max-width:74ch}
.item{padding:16px 0;border-bottom:1px solid #f0f0f0}
.head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
code.attr{font:600 13px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;
  background:#f2f2f0;padding:2px 7px;border-radius:4px}
.kind{font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;color:#a0a0a0}
.cost{font-size:11px;color:#8a5a2a;background:#fdf6ec;padding:2px 7px;border-radius:4px}
.pill{font-size:11px;padding:2px 8px;border-radius:20px;font-weight:550}
.ok{background:#e2f5ec;color:#12674a}
.empty{background:#f3f3f3;color:#7a7a7a}
.error{background:#fdecea;color:#a3271c}
.absent{background:#f4f0fb;color:#5b46a8}
.shape{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#8a8a8a}
.desc{margin:8px 0 0;color:#3a3a3a;font-size:13.5px;max-width:78ch}
.prevwrap{margin-top:12px;overflow-x:auto}
table.prev{border-collapse:collapse;font:12px ui-monospace,SFMono-Regular,Menlo,monospace}
table.prev th,table.prev td{border:1px solid #ececec;padding:3px 8px;text-align:left;
  white-space:nowrap;color:#4a4a4a}
table.prev th{background:#fafaf9;font-weight:600;color:#2a2a2a}
.more{font-size:11.5px;color:#9a9a9a;margin:6px 0 0}
p.wrap{font-size:12.5px;color:#4a4a4a;margin:6px 0 0;overflow-wrap:anywhere;max-width:82ch}
.info-grid{display:grid;grid-template-columns:minmax(180px,230px) 1fr;gap:1px;
  background:#ececec;border:1px solid #ececec;margin:8px 0 22px;font-size:13px}
.info-grid>div{background:#fff;padding:7px 11px;min-width:0}
.info-grid .k{font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:#5a5a5a;
  overflow-wrap:anywhere}
.info-grid .v{overflow-wrap:anywhere;white-space:pre-wrap;color:#2a2a2a}
.info-grid .missing{color:#b8b8b8;font-style:italic}
.q{border:1px solid #e8e8e6;border-radius:8px;padding:22px 24px;margin:0 0 26px;background:#fff}
.q h2{margin:0 0 6px;border:0;padding:0}
.verdict{font-size:13.5px;color:#12674a;background:#e9f6f0;display:inline-block;
  padding:5px 11px;border-radius:5px;margin:0 0 18px;max-width:78ch}
.route{border-top:1px solid #f0f0f0;padding:15px 0 3px}
.fields{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 9px;align-items:center}
.fields code{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;background:#f2f2f0;
  padding:2px 7px;border-radius:4px;color:#2a2a2a}
.src{font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;font-weight:650;
  padding:3px 8px;border-radius:4px}
.src-Yahoo{background:#eef3fd;color:#24518f}
.src-EODHD{background:#f1eefb;color:#4a3aa7}
.src-Both{background:#eef7f2;color:#12674a}
.how{margin:0;font-size:13.5px;color:#2a2a2a;max-width:80ch}
.limit{margin:9px 0 0;font-size:12.5px;color:#8a5a2a;background:#fdf6ec;padding:8px 11px;
  border-radius:5px;max-width:80ch}
.limit b{color:#7a4a1a}
.close{margin:26px 0 0;font-size:13.5px;color:#3a3a3a;background:#f6f6f4;padding:16px 18px;
  border-radius:8px;max-width:82ch}
.warn{background:#fdf6ec;border:1px solid #f0e0c4;padding:14px 16px;border-radius:8px;
  font-size:13.5px;color:#6a4a1a;margin:0 0 22px;max-width:82ch}
footer{max-width:1180px;margin:0 auto;padding:20px 28px 70px;font-size:12px;color:#9a9a9a;
  border-top:1px solid #e4e4e4}
@media(max-width:880px){.layout{grid-template-columns:1fr;gap:0}
  aside{position:static;max-height:none;padding:16px 0 0}}
"""

JS = """
const tabs=[...document.querySelectorAll('nav.tabs button')];
function pick(t){
  tabs.forEach(b=>b.setAttribute('aria-selected',b.dataset.tab===t));
  document.querySelectorAll('[data-tab]').forEach(el=>{
    if(el.tagName==='BUTTON')return; el.hidden=el.dataset.tab!==t;});
  window.scrollTo(0,0);
}
tabs.forEach(b=>b.addEventListener('click',()=>pick(b.dataset.tab)));
const links=[...document.querySelectorAll('aside a')];
const byId={};links.forEach(a=>byId[a.getAttribute('href').slice(1)]=a);
const io=new IntersectionObserver(es=>{es.forEach(e=>{const a=byId[e.target.id];
  if(a&&e.isIntersecting){links.forEach(l=>l.classList.remove('on'));a.classList.add('on');}});
},{rootMargin:'-116px 0px -75% 0px'});
document.querySelectorAll('h2[id],h3[id]').forEach(h=>io.observe(h));
pick('yahoo');
"""


def render(ctx):
    yf_res, info = ctx["yf_res"], ctx["info"]
    eod_res, fund = ctx["eod_res"], ctx["fund"]
    nav = {"yahoo": [], "eodhd": [], "mining": []}
    body = {"yahoo": [], "eodhd": [], "mining": []}

    # ---------------------------------------------------------------- yahoo --
    if info:
        nav["yahoo"].append("<div class=navgroup>Inside .info</div>")
        body["yahoo"].append(f'<h2 id="info">Inside <code>.info</code>'
                             f'<span class=count>{len(info)} keys</span></h2>'
                             "<p class=lede>The richest non-pricing source Yahoo "
                             "has. Keys grouped by theme; anything not returned is "
                             "greyed rather than dropped, because a missing field "
                             "is itself a fact about coverage. Values are shown in "
                             "full — including the business summary, the raw "
                             "material for commodity and geography extraction.</p>")
        shown = set()
        for gname, keys in INFO_GROUPS:
            gid = "info-" + gname.lower().replace(" ", "-")
            nav["yahoo"].append(f'<a href="#{gid}">{html.escape(gname)}</a>')
            body["yahoo"].append(f'<h3 id="{gid}">{html.escape(gname)}</h3>'
                                 "<div class=info-grid>")
            for k in keys:
                shown.add(k)
                if k in info and info[k] not in (None, ""):
                    body["yahoo"].append(
                        f"<div class=k>{html.escape(k)}</div>"
                        f"<div class=v>{html.escape(_flat(info[k]))}</div>")
                else:
                    body["yahoo"].append(
                        f"<div class=k>{html.escape(k)}</div>"
                        f"<div class='v missing'>not returned</div>")
            body["yahoo"].append("</div>")
        extra = sorted(k for k in info if k not in shown)
        if extra:
            nav["yahoo"].append('<a href="#info-ungrouped">Ungrouped</a>')
            body["yahoo"].append(f'<h3 id="info-ungrouped">Ungrouped '
                                 f'<span class=shape>({len(extra)})</span></h3>'
                                 "<div class=info-grid>")
            for k in extra:
                body["yahoo"].append(f"<div class=k>{html.escape(k)}</div>"
                                     f"<div class=v>{html.escape(_flat(info[k]))}</div>")
            body["yahoo"].append("</div>")

    nav["yahoo"].append("<div class=navgroup>Surfaces</div>")
    for group, entries in YF_CATALOGUE:
        gid = "yg-" + group.lower().replace(" ", "-")
        nav["yahoo"].append(f'<a href="#{gid}">{html.escape(group)}</a>')
        body["yahoo"].append(f'<h2 id="{gid}">{html.escape(group)}'
                             f'<span class=count>{len(entries)}</span></h2>')
        for name, kind, desc in entries:
            r = yf_res.get(name)
            body["yahoo"].append("<div class=item><div class=head>"
                                 f"<code class=attr>.{html.escape(name)}"
                                 f"{'()' if kind == 'param' else ''}</code>")
            if kind == "param":
                body["yahoo"].append("<span class=kind>takes arguments</span>")
            if r:
                body["yahoo"].append(
                    f"<span class='pill {r['status']}'>{r['status']}</span>"
                    f"<span class=shape>{html.escape(r['shape'])}</span>")
            body["yahoo"].append(f"</div><p class=desc>{desc}</p>")
            if r and r["preview"]:
                body["yahoo"].append(f"<div class=prevwrap>{r['preview']}</div>")
            body["yahoo"].append("</div>")

    nav["yahoo"].append('<a href="#module">Beyond a single ticker</a>')
    body["yahoo"].append(f'<h2 id="module">Beyond a single ticker'
                         f'<span class=count>{len(MODULE_LEVEL)}</span></h2>')
    for name, desc in MODULE_LEVEL:
        body["yahoo"].append(f"<div class=item><div class=head><code class=attr>"
                             f"{html.escape(name)}</code></div>"
                             f"<p class=desc>{desc}</p></div>")

    # ---------------------------------------------------------------- eodhd --
    if ctx.get("key_src", "").startswith("demo") and ctx["eodhd_sym"] in ctx["demo_set"]:
        body["eodhd"].append(
            f"<p class=warn><b>This is {html.escape(ctx['eodhd_sym'])}, not a "
            f"miner — and that is deliberate.</b> EODHD's free trial key returns "
            f"almost nothing, so probing it teaches you about the trial rather "
            f"than the product. The <code>demo</code> key serves every data type "
            f"without limitation, but only for six symbols. Apple is the fullest "
            f"of them.<br><br>Read what follows as <b>the schema at full "
            f"fill</b> — which sections exist, how deep they go, what a populated "
            f"<code>General</code> block actually contains. It is strong evidence "
            f"about structure and <b>no evidence whatsoever</b> about whether a "
            f"C$3M shell on the TSX Venture exchange would return any of it. That "
            f"question is unanswerable without paying.</p>")
    body["eodhd"].append(
        "<p class=lede>Same company, same treatment. The structural difference to "
        "watch: yfinance spreads a company across a dozen attributes and a dozen "
        "round trips, while EODHD returns nearly all of it in one "
        "<code>fundamentals</code> call — which costs 10 API calls but arrives as "
        "a single nested document.</p>")

    for group, entries in EODHD_ENDPOINTS:
        gid = "eg-" + group.lower().replace(" ", "-")
        nav["eodhd"].append(f'<a href="#{gid}">{html.escape(group)}</a>')
        body["eodhd"].append(f'<h2 id="{gid}">{html.escape(group)}'
                             f'<span class=count>{len(entries)}</span></h2>')
        for label, path, cost, desc in entries:
            r = eod_res.get(label)
            shown_path = path.split("?")[0].replace("{s}", ctx["eodhd_sym"])
            body["eodhd"].append("<div class=item><div class=head>"
                                 f"<code class=attr>{html.escape(shown_path)}</code>")
            if cost:
                body["eodhd"].append(f"<span class=cost>{cost} call"
                                     f"{'s' if cost > 1 else ''}</span>")
            if r:
                body["eodhd"].append(
                    f"<span class='pill {r['status']}'>{r['status']}</span>"
                    f"<span class=shape>{html.escape(r['shape'])}</span>")
            body["eodhd"].append(f"</div><p class=desc>{desc}</p>")
            if r and r["preview"]:
                body["eodhd"].append(f"<div class=prevwrap>{r['preview']}</div>")
            body["eodhd"].append("</div>")

    # fundamentals tree
    if fund:
        nav["eodhd"].append("<div class=navgroup>Inside fundamentals</div>")
        body["eodhd"].append(f'<h2 id="fund">Inside <code>fundamentals</code>'
                             f'<span class=count>{len(fund)} sections</span></h2>'
                             "<p class=lede>One request, this whole tree. Each "
                             "section below is a top-level key of the returned "
                             "document.</p>")
        for sec in fund:
            sid = "fund-" + str(sec).lower().replace(" ", "-")
            nav["eodhd"].append(f'<a href="#{sid}">{html.escape(str(sec))}</a>')
            note = FUND_SECTIONS.get(sec, "")
            val = fund[sec]
            body["eodhd"].append(f'<h3 id="{sid}">{html.escape(str(sec))}</h3>')
            if note:
                body["eodhd"].append(f"<p class=desc>{note}</p>")
            if isinstance(val, dict) and val:
                body["eodhd"].append("<div class=info-grid>")
                for k, v in list(val.items())[:60]:
                    if isinstance(v, (dict, list)):
                        n = len(v)
                        kind = "keys" if isinstance(v, dict) else "rows"
                        inner = (", ".join(str(x) for x in list(v)[:8])
                                 if isinstance(v, dict) else "")
                        v = f"[{n} {kind}]" + (f"  {inner}" if inner else "")
                    body["eodhd"].append(
                        f"<div class=k>{html.escape(str(k))}</div>"
                        f"<div class=v>{html.escape(_flat(v))}</div>")
                body["eodhd"].append("</div>")
                if len(val) > 60:
                    body["eodhd"].append(f"<p class=more>+{len(val) - 60} more</p>")
            elif isinstance(val, list):
                body["eodhd"].append(f"<p class=wrap>list, {len(val):,} rows</p>")
            else:
                body["eodhd"].append(f"<p class=wrap>{html.escape(_short(val))}</p>")

    # --------------------------------------------------------------- mining --
    nav["mining"].append("<div class=navgroup>Deriving mining data</div>")
    body["mining"].append(
        "<p class=lede style='margin-top:4px'>Using <strong>only</strong> these "
        "two providers — no exchange export, no SEDAR+, no technical reports. Each "
        "route names the fields, says how it would work, and states what it cannot "
        "tell you. The badge says which provider it needs.</p>")
    for sec in MINING:
        nav["mining"].append(f'<a href="#{sec["id"]}">{html.escape(sec["title"])}</a>')
        body["mining"].append(f'<div class=q><h2 id="{sec["id"]}">'
                              f'{html.escape(sec["title"])}</h2>'
                              f'<p class=verdict>{sec["verdict"]}</p>')
        for row in sec["rows"]:
            fields = "".join(f"<code>{html.escape(f)}</code>" for f in row["fields"])
            body["mining"].append(
                f'<div class=route><div class=fields>'
                f'<span class="src src-{row["src"]}">{row["src"]}</span>{fields}</div>'
                f'<p class=how>{row["how"]}</p>'
                f'<p class=limit><b>Limit.</b> {row["limit"]}</p></div>')
        body["mining"].append(f'<p class=close>{sec["verdict_note"]}</p></div>')
    body["mining"].append(f'<p class=close>{MINING_CLOSING}</p>')

    sub = " · ".join(x for x in [ctx["sub_yf"], ctx["sub_eod"]] if x)
    return (
        "<!doctype html><html lang=en><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        "<title>Provider surfaces — yfinance vs EODHD</title>"
        f"<style>{CSS}</style>"
        "<header><div class=hin>"
        "<h1>What each provider gives you for one company</h1>"
        f"<p class=sub>{sub}</p>"
        "<nav class=tabs>"
        "<button data-tab=yahoo aria-selected=true>Yahoo · yfinance</button>"
        "<button data-tab=eodhd aria-selected=false>EODHD</button>"
        "<button data-tab=mining aria-selected=false>Deriving mining data</button>"
        "</nav></div></header><div class=layout><aside>"
        + "".join(f'<div data-tab={t}{" hidden" if t != "yahoo" else ""}>'
                  f'{"".join(nav[t])}</div>' for t in ("yahoo", "eodhd", "mining"))
        + "</aside><main>"
        + "".join(f'<div data-tab={t}{" hidden" if t != "yahoo" else ""}>'
                  f'{"".join(body[t])}</div>' for t in ("yahoo", "eodhd", "mining"))
        + "</main></div>"
        f"<footer>generated {dt.datetime.now():%Y-%m-%d %H:%M} · "
        f"<code>explore/provider_explore.py</code> · scratch work, nothing else in "
        f"this repo depends on it. Yahoo is free and unofficial and its fields "
        f"appear and vanish without notice; EODHD is contractual but its microcap "
        f"depth is unproven. Treat every &lsquo;empty&rsquo; as today's answer."
        f"</footer><script>{JS}</script></html>"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yf", default=YF_DEFAULT, help="Yahoo symbol")
    ap.add_argument("--eodhd", default=EODHD_DEFAULT, help="EODHD symbol")
    ap.add_argument("--key", default=None, help="EODHD API key")
    ap.add_argument("--demo", action="store_true",
                    help="force the demo key (full data, six symbols only)")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--yf-only", action="store_true")
    ap.add_argument("--eodhd-only", action="store_true")
    a = ap.parse_args()

    ctx = {"yf_res": {}, "info": {}, "eod_res": {}, "fund": None,
           "eodhd_sym": a.eodhd, "has_key": False, "key_src": "",
           "demo_set": DEMO_TICKERS, "sub_yf": "", "sub_eod": ""}

    # ---- yahoo ----
    if not a.offline and not a.eodhd_only:
        try:
            import yfinance as yf
        except ImportError:
            raise SystemExit("pip install yfinance")
        tk = yf.Ticker(a.yf)
        flat = [(n, k) for _, es in YF_CATALOGUE for n, k, _ in es]
        print(f"\nYAHOO  {a.yf} · {len(flat)} surfaces · yfinance "
              f"{getattr(yf, '__version__', '?')}")
        t0 = time.perf_counter()
        for i, (name, kind) in enumerate(flat, 1):
            r = probe_yf(tk, name, kind)
            ctx["yf_res"][name] = r
            print(f"  {i:>2}/{len(flat)}  {name:<26} {r['status']:<7} {r['shape']}")
        try:
            ctx["info"] = tk.info or {}
        except Exception:
            traceback.print_exc()
        el = time.perf_counter() - t0
        ok = sum(1 for r in ctx["yf_res"].values() if r["status"] == "ok")
        ctx["sub_yf"] = (f"Yahoo {html.escape(a.yf)}: {ok}/{len(flat)} returned "
                         f"data, {len(ctx['info'])} info keys, {el:.0f}s")

    # ---- eodhd ----
    if not a.offline and not a.yf_only:
        key, src = find_key(a.key, a.eodhd, a.demo)
        ctx["key_src"] = src
        if not key:
            print("\nEODHD  no API key — skipping (see --help)")
        else:
            ctx["has_key"] = True
            flat = [(l, p, c) for _, es in EODHD_ENDPOINTS for l, p, c, _ in es]
            print(f"\nEODHD  {a.eodhd} · {len(flat)} endpoints · "
                  f"~{sum(c for _, _, c in flat)} API calls · key from {src}")
            t0 = time.perf_counter()
            for i, (label, path, cost) in enumerate(flat, 1):
                r = probe_eodhd(path, a.eodhd, key)
                if label == "fundamentals" and isinstance(r.get("data"), dict):
                    ctx["fund"] = r["data"]
                if label == "user" and isinstance(r.get("data"), dict):
                    d = r["data"]
                    print(f"      plan={d.get('subscriptionType')} "
                          f"used={d.get('apiRequests')}/{d.get('dailyRateLimit')}")
                ctx["eod_res"][label] = r
                print(f"  {i:>2}/{len(flat)}  {label:<30} {r['status']:<7} "
                      f"{r['shape']}")
            el = time.perf_counter() - t0
            ok = sum(1 for r in ctx["eod_res"].values() if r["status"] == "ok")
            ctx["sub_eod"] = (f"EODHD {html.escape(a.eodhd)}: {ok}/{len(flat)} "
                              f"returned data, {el:.0f}s, key from "
                              f"{html.escape(src)}")

    if not ctx["sub_yf"] and not ctx["sub_eod"]:
        ctx["sub_yf"] = "Catalogues only — nothing fetched."

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(ctx), encoding="utf-8")
    print(f"\n-> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
