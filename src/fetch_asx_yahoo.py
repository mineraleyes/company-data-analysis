"""
Collect Yahoo Finance data for ASX companies.

    python src/fetch_asx_yahoo.py                # 775 GICS Materials
    python src/fetch_asx_yahoo.py --limit 25     # trial run
    python src/fetch_asx_yahoo.py --wide         # + mining-named names outside Materials
    python src/fetch_asx_yahoo.py --all          # every ASX listing (1,843)
    python src/fetch_asx_yahoo.py --shares       # + shares-outstanding series
    python src/fetch_asx_yahoo.py --retry-failed # re-attempt rows that came back empty

In:   data/processed/asx_clean.csv
Out:  data/raw/asx_yahoo.csv          one row per ticker, resumable
      data/raw/asx_yahoo_shares.csv   long-form dilution series (--shares only)

COLLECTION ONLY
This fetches and stores. It derives nothing: no commodity flags, no stage, no
geography, no turnover. Those are judgements and they belong in an enrich step
that can be re-run and argued with, not baked into the thing that talks to the
network. What is stored here is what Yahoo said, so a later change of mind about
classification costs no refetching.

WHY A SEPARATE FILE, NOT asx_clean.csv
asx_clean.csv is the deterministic output of build_asx_dataset.py — re-running
that script would silently erase anything appended in place. Keeping Yahoo's
answers in their own file also keeps the provenance honest: the ASX export is
official and dated 26 August 2026; this is a free, unofficial source read on
whatever day it ran. Those two things should not sit in one table pretending to
be equally solid.

WHICH COMPANIES
Default is GICS Materials — 775 of the 1,843 listings. That keeps BHP, Newmont,
Fortescue, South32, Alcoa, PLS and IGO, none of which say "mining" in their
names, and it drops the coal and uranium miners GICS files under Energy
(Yancoal, Whitehaven). Excluding those is a deliberate choice, and it is worth
recording that it makes this population differ in kind from the TMX one, which
does carry coal and uranium.

Materials still contains genuine non-miners — Amcor at A$31B, James Hardie A$25B,
BlueScope A$14B, Orica A$10B, Dyno Nobel A$7B, Sims A$5B, roughly A$92B in all.
They are NOT excluded here, on purpose. A hand-written exclusion list only ever
catches the names large enough to notice, and leaves the long tail of small
non-miners untouched. Yahoo assigns an industry per company that separates them
properly — Packaging & Containers, Building Products & Equipment, Specialty
Chemicals — so the mining population gets defined in the enrich step, from data
this run is about to fetch, and can be re-argued without re-fetching.

--wide adds the 41 mining-named companies outside Materials, if the Energy
decision is ever revisited. --all fetches everything.

WHAT THIS COSTS
Four requests per company — info, income statement, balance sheet, cash flow —
so roughly 3,200 requests on the default run. Expect 20-40 minutes. It is
resumable: interrupt it and run it again.

Requires: pip install yfinance     Needs internet.
"""

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "processed" / "asx_clean.csv"
OUT = ROOT / "data" / "raw" / "asx_yahoo.csv"
SHARES_OUT = ROOT / "data" / "raw" / "asx_yahoo_shares.csv"

PAUSE = 0.35          # between companies; Yahoo publishes no rate limit
SHARES_YEARS = 8      # how far back the dilution series reaches

# ─────────────────────────────────────────────────────────────────────────────
# Statement row labels. yfinance passes through Yahoo's own naming, which is
# neither stable nor consistent between companies, so every field lists the
# variants seen in the wild and takes the first that exists.
# ─────────────────────────────────────────────────────────────────────────────

INCOME_ROWS = {
    "revenue_stmt": ["Total Revenue", "Operating Revenue"],
    "cost_of_revenue": ["Cost Of Revenue", "Reconciled Cost Of Revenue"],
    "gross_profit": ["Gross Profit"],
    "ebitda_stmt": ["EBITDA", "Normalized EBITDA"],
    "operating_income": ["Operating Income", "Total Operating Income As Reported"],
    "net_income": ["Net Income", "Net Income Common Stockholders"],
}

BALANCE_ROWS = {
    # The developer signal. A company with no revenue, rising construction in
    # progress and a capex spike is building a mine — the one route to a
    # developer bucket that does not depend on a business summary saying so.
    "construction_in_progress": ["Construction In Progress"],
    "net_ppe": ["Net PPE", "Net Property Plant And Equipment"],
    "gross_ppe": ["Gross PPE", "Gross Property Plant And Equipment"],
    "total_assets": ["Total Assets"],
    "cash_and_equiv": ["Cash And Cash Equivalents",
                       "Cash Cash Equivalents And Short Term Investments"],
    "total_debt": ["Total Debt"],
    "stockholders_equity": ["Stockholders Equity", "Total Equity Gross Minority Interest"],
}

CASHFLOW_ROWS = {
    "capex": ["Capital Expenditure", "Purchase Of PPE"],
    # How a junior actually funds itself. The private-placement history that
    # would otherwise need SEDAR+ or ASX announcements.
    "stock_issuance": ["Issuance Of Capital Stock", "Net Common Stock Issuance",
                       "Common Stock Issuance"],
    "operating_cf": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "free_cf": ["Free Cash Flow"],
    "exploration_spend": ["Exploration Development And Mineral Property Lease Expenses"],
}

# info keys copied straight through. Extraction from `summary` happens later.
INFO_FIELDS = {
    "name_yahoo": "longName",
    "exchange": "exchange",
    "quote_type": "quoteType",
    "currency": "currency",
    "financial_currency": "financialCurrency",
    "sector": "sector",
    "industry": "industry",
    "industry_key": "industryKey",
    "summary": "longBusinessSummary",
    "employees": "fullTimeEmployees",
    "website": "website",
    "hq_country": "country",
    "hq_city": "city",
    "hq_state": "state",
    "price": "currentPrice",
    "mcap_yahoo": "marketCap",
    "shares_outstanding": "sharesOutstanding",
    "float_shares": "floatShares",
    "volume_avg": "averageVolume",
    "volume_avg_10d": "averageVolume10days",
    "beta": "beta",
    "revenue_info": "totalRevenue",
    "ebitda_info": "ebitda",
    "gross_margin": "grossMargins",
    "operating_margin": "operatingMargins",
    "profit_margin": "profitMargins",
    "total_cash": "totalCash",
    "total_debt_info": "totalDebt",
    "held_insiders": "heldPercentInsiders",
    "held_institutions": "heldPercentInstitutions",
    "analysts": "numberOfAnalystOpinions",
}

COLUMNS = (["ticker", "ticker_full"]
           + list(INFO_FIELDS)
           + list(INCOME_ROWS) + ["revenue_year"]
           + list(BALANCE_ROWS) + ["balance_year"]
           + list(CASHFLOW_ROWS) + ["cashflow_year"]
           + ["fetch_status", "fetch_note", "fetched_at"])


def _pick(df, names):
    """First matching row of a statement, most recent column. None if absent."""
    if df is None or getattr(df, "empty", True):
        return None, None
    for name in names:
        if name in df.index:
            vals = df.loc[name].dropna()
            if len(vals):
                return float(vals.iloc[0]), str(vals.index[0])[:4]
    return None, None


def fetch_one(yf, ticker_full):
    """Everything for one company. Never raises — a failure is a row."""
    rec = {c: None for c in COLUMNS}
    rec["ticker_full"] = ticker_full
    rec["fetched_at"] = dt.datetime.now().isoformat(timespec="seconds")
    notes = []

    try:
        tk = yf.Ticker(ticker_full)

        try:
            info = tk.info or {}
        except Exception as e:
            info = {}
            notes.append(f"info:{type(e).__name__}")
        for col, key in INFO_FIELDS.items():
            v = info.get(key)
            rec[col] = " ".join(str(v).split()) if isinstance(v, str) else v

        for label, frame, rows, yearcol in (
                ("income", "income_stmt", INCOME_ROWS, "revenue_year"),
                ("balance", "balance_sheet", BALANCE_ROWS, "balance_year"),
                ("cash", "cashflow", CASHFLOW_ROWS, "cashflow_year")):
            try:
                df = getattr(tk, frame)
            except Exception as e:
                notes.append(f"{label}:{type(e).__name__}")
                continue
            for col, names in rows.items():
                val, yr = _pick(df, names)
                rec[col] = val
                if yr and not rec[yearcol]:
                    rec[yearcol] = yr

        got = any(rec[c] is not None for c in
                  ("summary", "mcap_yahoo", "revenue_stmt", "total_assets"))
        rec["fetch_status"] = "ok" if got else "empty"
    except Exception as e:
        rec["fetch_status"] = "error"
        notes.append(f"{type(e).__name__}: {str(e)[:80]}")

    rec["fetch_note"] = "; ".join(notes) or None
    return rec


def fetch_shares(yf, ticker_full, years):
    """Shares outstanding over time — the dilution series, long-form."""
    try:
        s = yf.Ticker(ticker_full).get_shares_full(
            start=dt.date.today() - dt.timedelta(days=365 * years))
        if s is None or not len(s):
            return []
        s = s[~s.index.duplicated(keep="last")]
        return [{"ticker_full": ticker_full,
                 "date": str(i)[:10],
                 "shares": float(v)} for i, v in s.items()]
    except Exception:
        return []


def already_done(retry_failed):
    """Tickers to skip. A row that came back with nothing is a failed fetch, not
    a company with nothing to say — so with --retry-failed those go back on the
    list rather than being cached as failures forever."""
    if not OUT.exists():
        return set()
    have = pd.read_csv(OUT).drop_duplicates(subset="ticker_full", keep="last")
    if retry_failed:
        have = have[have["fetch_status"] == "ok"]
    return set(have["ticker_full"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true",
                    help="every ASX listing, not just Materials")
    ap.add_argument("--wide", action="store_true",
                    help="Materials plus mining-named companies outside it "
                         "(pulls coal and uranium back in from Energy)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--shares", action="store_true",
                    help="also fetch the shares-outstanding series (one extra "
                         "request per company)")
    ap.add_argument("--retry-failed", action="store_true")
    a = ap.parse_args()

    try:
        import yfinance as yf
    except ImportError:
        sys.exit("pip install yfinance")

    df = pd.read_csv(SRC)
    if a.all:
        pool = df
        which = "all ASX listings"
    elif a.wide:
        pool = df[(df["is_materials"] == True) | (df["mining_name"] == True)]  # noqa: E712
        which = "Materials or mining-named"
    else:
        # GICS Materials. Keeps BHP and Fortescue, which the name test misses;
        # drops the Energy-sector coal and uranium miners, which is a deliberate
        # narrowing. The packaging and chemicals names that Materials also
        # carries are filtered later, on Yahoo industry, not here.
        pool = df[df["is_materials"] == True]  # noqa: E712
        which = "GICS Materials"

    tickers = pool["ticker_full"].dropna().tolist()
    done = already_done(a.retry_failed)
    todo = [t for t in tickers if t not in done]
    if a.limit:
        todo = todo[:a.limit]

    print(f"{len(df):,} rows in asx_clean · {len(tickers):,} {which} · "
          f"{len(done):,} already fetched · {len(todo):,} to go")
    if not todo:
        print("nothing to do")
        return

    per = 5 if a.shares else 4
    print(f"~{len(todo) * per:,} requests, roughly "
          f"{len(todo) * (PAUSE + 1.5) / 60:.0f} min. Resumable — Ctrl-C is safe.\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    ok = empty = err = 0

    for i, t in enumerate(todo, 1):
        rec = fetch_one(yf, t)
        rec["ticker"] = t.split(".")[0]
        pd.DataFrame([rec])[COLUMNS].to_csv(
            OUT, mode="a", header=not OUT.exists(), index=False)

        if a.shares:
            rows = fetch_shares(yf, t, SHARES_YEARS)
            if rows:
                pd.DataFrame(rows).to_csv(
                    SHARES_OUT, mode="a",
                    header=not SHARES_OUT.exists(), index=False)

        ok += rec["fetch_status"] == "ok"
        empty += rec["fetch_status"] == "empty"
        err += rec["fetch_status"] == "error"
        if i % 25 == 0 or i == len(todo):
            print(f"  {i:>4}/{len(todo)}  ok={ok} empty={empty} error={err}"
                  f"   last={t}")
        time.sleep(PAUSE)

    # ---- what actually landed ----
    full = pd.read_csv(OUT).drop_duplicates(subset="ticker_full", keep="last")
    print(f"\nwrote {len(full):,} rows -> {OUT.relative_to(ROOT)}")
    print(f"  ok {ok} · empty {empty} · error {err} this run\n")

    print("coverage of the fields the analysis will need:")
    for col, why in [
            ("summary", "commodity + geography extraction"),
            ("industry", "primary commodity"),
            ("hq_country", "domicile"),
            ("mcap_yahoo", "size, second reading"),
            ("shares_outstanding", "turnover denominator"),
            ("volume_avg", "turnover numerator"),
            ("revenue_stmt", "producer test"),
            ("construction_in_progress", "developer test"),
            ("capex", "developer test"),
            ("total_assets", "statement coverage at all")]:
        n = int(full[col].notna().sum())
        print(f"  {col:<26} {n:>5} / {len(full):<5} {100*n/len(full):5.1f}%   {why}")

    if a.shares and SHARES_OUT.exists():
        sh = pd.read_csv(SHARES_OUT)
        print(f"\nshares series: {len(sh):,} observations across "
              f"{sh['ticker_full'].nunique():,} companies "
              f"-> {SHARES_OUT.relative_to(ROOT)}")

    if "industry" in full:
        print("\nYahoo industry — the field the mining population will be "
              "defined from:")
        vc = full["industry"].value_counts(dropna=False)
        for name, n in vc.head(18).items():
            print(f"  {str(name)[:44]:<46}{n:>5}")
        if len(vc) > 18:
            print(f"  {'… ' + str(len(vc) - 18) + ' more industries':<46}"
                  f"{int(vc.iloc[18:].sum()):>5}")

    print("\nNothing is derived yet. The mining population, commodity flags, "
          "stage, geography and turnover all come from a separate enrich step.")


if __name__ == "__main__":
    main()
