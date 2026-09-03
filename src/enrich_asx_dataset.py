"""
Derive the ASX mining dataset from the exchange export plus Yahoo.

    python src/enrich_asx_dataset.py

In:   data/processed/asx_clean.csv     the ASX export, official, 26 Aug 2026
      data/raw/asx_yahoo.csv           Yahoo, free and unofficial
Out:  data/processed/asx_enriched.csv  one row per company, TSX-shaped columns

WHAT THIS IS FOR
The TMX exports arrive with commodity and property columns already in them. The
ASX export has five columns. Everything the TSX analysis takes for granted has
to be derived here, from a business summary and a set of financial statements,
and every derivation is a judgement that can be re-argued by editing this file
and re-running it. Nothing here touches the network.

COLUMN NAMES MIRROR THE TSX SIDE
comm_gold, prop_africa, stage, turnover and the rest carry the same names and
the same meanings as in mining_enriched.csv, so the same chart code can read
both. Where a measure is NOT the same thing, it gets a different name and says
so — see turnover below.

THE THREE JUDGEMENTS, IN ORDER OF HOW MUCH THEY CAN BE TRUSTED

1. WHO IS A MINER.  Yahoo's industry field is authoritative when it names a
   mining industry. Otherwise the business summary has to say something only a
   miner says — that it explores FOR something, or holds deposits, ore bodies,
   tenements or mineral properties. A supplier to the industry talks about
   products, services and solutions instead, which is how Orica (explosives),
   Imdex (drilling tools) and BlueScope (steel products) fall out while Champion
   Iron, MGX and BCI Minerals stay in. 726 of 775 survive.

2. WHAT THEY MINE.  Keyword extraction over the summary. Reliable in the sense
   that the words are really there, unreliable in that a summary states what a
   company says it explores for, which is not the same as what it holds, and
   goes stale. Yahoo's industry gives a primary label as a cross-check.

3. WHERE THEY OPERATE.  The same extraction against a country list, and much
   weaker: a summary usually names the flagship project and stops. Counts built
   from it UNDERSTATE by construction. This is the one place where the TSX side
   has a real property register and the ASX side has prose.

STAGE
Producer is decided on revenue, as on the TSX side, but with one refinement the
TSX classifier did not need. A junior with A$1M of "revenue" and a gross profit
of exactly A$1M has no cost of revenue, which means the line is interest or a
tenement sale rather than metal. Requiring a cost of revenue outright would be
too strict — Yahoo simply omits it for IGO (A$512M) and Catalyst (A$317M) — so
the floor is A$1M where a cost of revenue exists and A$10M where it does not.

Royalty and streaming companies are pulled out first, as on the TSX side. They
have revenue and no cost of revenue by construction, because they do not operate
anything: Deterra collects A$242M against Australian iron ore without owning a
mine. Left in the producer bucket they would look like an accounting anomaly.

Developer is decided on construction in progress, and ONLY on that. Capex was
tried as a second signal and had to be thrown out: under AASB 6, Australian
explorers capitalise exploration expenditure, so drilling arrives on the cash
flow statement as capex. The rule "capex above 10% of assets" labelled 226
companies as developers, including Southern Cross Gold — a A$3.3B EXPLORER — and
Vita Resources, a A$1.9M shell whose entire capex was one drill programme. Any
capex-based rule measures how hard a company is drilling, not whether it is
building a mine.

Construction in progress is the honest signal, with a materiality floor: a
balance with A$0.1M in it is an office fit-out. What survives is a small number,
which is correct — at any moment only a handful of ASX juniors are actually
building something.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "processed" / "asx_clean.csv"
YAHOO = ROOT / "data" / "raw" / "asx_yahoo.csv"
OUT = ROOT / "data" / "processed" / "asx_enriched.csv"

# ─────────────────────────────────────────────────────────── who is a miner ──

# Yahoo industries that are mining outright. Note Coking Coal, Thermal Coal and
# Uranium appear here: excluding the Energy SECTOR did not exclude coal and
# uranium miners, because GICS files some of them under Materials.
MINING_INDUSTRIES = {
    "Other Industrial Metals & Mining", "Gold", "Other Precious Metals & Mining",
    "Copper", "Aluminum", "Silver", "Coking Coal", "Thermal Coal", "Uranium",
}

# Positive evidence only, deliberately. An exclusion list of manufacturing words
# was tried first and got BCI Minerals wrong, because a salt and potash producer
# talks about food and fertiliser. What separates a miner from its suppliers is
# that a miner explores FOR something and holds ground.
# A royalty holder earns from someone else's mine. Its own bucket, mirroring the
# TSX is_royalty_streamer flag, which TMX supplies and Yahoo does not.
ROYALTY_RE = re.compile(r"\broyalt|\bstreaming agreement|royalty and streaming")

MINER_RE = re.compile(
    r"explores for|exploration of|mineral resources compan|"
    r"\bdeposits\b|ore (?:propert|bod|deposit|project)|"
    r"mining leases|tenement|mineral propert|"
    r"exploration,? (?:and )?(?:development|evaluation|mining)|"
    r"engages in the mining|\bmine site\b"
)

# ────────────────────────────────────────────────────────────── commodities ──

# The first 16 mirror the TSX SPECIFIC_COMMODITIES exactly, so the two markets
# can share a chart. The rest are ASX-weight commodities that the TMX flag set
# has no column for — they are extra, not a substitute.
COMMODITIES = {
    # shared with the TSX side
    "gold": r"\bgold\b",
    "silver": r"\bsilver\b",
    "copper": r"\bcopper\b",
    "nickel": r"\bnickel\b",
    "diamond": r"\bdiamonds?\b",
    "molybdenum": r"\bmolybdenum\b",
    "platinum_pgm": r"\bplatinum\b|\bpalladium\b|\bpgm\b|platinum group",
    "iron": r"\biron ore\b|\bhematite\b|\bmagnetite\b|\biron\b",
    "lead": r"\blead\b(?!ing)",
    "zinc": r"\bzinc\b",
    "rare_earths": r"rare earth",
    "potash": r"\bpotash\b",
    "lithium": r"\blithium\b|\bspodumene\b",
    "uranium": r"\buranium\b",
    "coal": r"\bcoal\b",
    "tungsten": r"\btungsten\b",
    # ASX additions
    "cobalt": r"\bcobalt\b",
    "graphite": r"\bgraphite\b",
    "vanadium": r"\bvanadium\b",
    "manganese": r"\bmanganese\b",
    "antimony": r"\bantimony\b",
    "mineral_sands": r"mineral sands|\bzircon\b|\brutile\b|\bilmenite\b",
    "tin": r"\btin\b",
    "bauxite_alumina": r"\bbauxite\b|\balumina\b",
    "phosphate": r"\bphosphate\b",
    "scandium": r"\bscandium\b",
    "niobium_tantalum": r"\bniobium\b|\btantalum\b",
    "silica": r"\bsilica\b|\bquartz\b",
}

SHARED_WITH_TSX = ["gold", "silver", "copper", "nickel", "diamond", "molybdenum",
                   "platinum_pgm", "iron", "lead", "zinc", "rare_earths",
                   "potash", "lithium", "uranium", "coal", "tungsten"]

# Yahoo's own primary label, mapped onto the same vocabulary. Used as a
# cross-check on the extraction, never as a replacement: it collapses a
# polymetallic company to one metal and dumps most juniors in "Other".
INDUSTRY_TO_COMMODITY = {
    "Gold": "gold", "Copper": "copper", "Silver": "silver",
    "Aluminum": "bauxite_alumina", "Uranium": "uranium",
    "Coking Coal": "coal", "Thermal Coal": "coal",
}

# ───────────────────────────────────────────────────────────────── geography ──

# Region names mirror the TSX prop_* columns exactly.
REGIONS = {
    "prop_aus_nz_png": [
        "australia", "australian", "western australia", "queensland",
        "new south wales", "victoria", "tasmania", "northern territory",
        "south australia", "new zealand", "papua new guinea", "pilbara",
        "yilgarn", "goldfields",
    ],
    "prop_canada": ["canada", "canadian", "ontario", "quebec", "british columbia",
                    "saskatchewan", "labrador", "yukon", "nunavut"],
    "prop_usa": ["united states", "u.s.", "usa", "nevada", "arizona", "alaska",
                 "utah", "idaho", "montana", "texas", "california"],
    "prop_latin_america": ["brazil", "chile", "peru", "argentina", "mexico",
                           "colombia", "bolivia", "ecuador", "guyana",
                           "latin america", "south america"],
    "prop_africa": ["africa", "tanzania", "ghana", "botswana", "namibia",
                    "zambia", "zimbabwe", "south africa", "mali", "burkina",
                    "ivory coast", "côte d'ivoire", "cote d'ivoire", "drc",
                    "democratic republic of the congo", "morocco", "egypt",
                    "senegal", "guinea", "ethiopia", "madagascar", "mozambique"],
    "prop_uk_europe": ["united kingdom", "england", "scotland", "ireland",
                       "finland", "sweden", "norway", "spain", "portugal",
                       "greenland", "serbia", "europe", "germany", "italy"],
    "prop_asia": ["china", "indonesia", "japan", "korea", "india", "vietnam",
                  "philippines", "malaysia", "thailand", "mongolia",
                  "kazakhstan", "laos", "myanmar", "bangladesh", "asia"],
}

# Size bands: same numeric thresholds as the TSX side so the distributions have
# the same shape. The currency is NOT the same and is never converted.
SIZE_BINS = [0, 5e6, 25e6, 100e6, 500e6, 2e9, np.inf]
SIZE_LABELS = ["< $5M", "$5–25M", "$25–100M", "$100–500M", "$500M–2B", "> $2B"]

# Below this, revenue is interest on the treasury rather than production. Same
# floor as the TSX classifier, in A$ rather than C$ — deliberately not converted,
# because a floor is a judgement about materiality, not an exchange rate.
REVENUE_FLOOR = 1_000_000
# Where no cost of revenue is reported, the bar is higher — see STAGE above.
REVENUE_FLOOR_NO_COGS = 10_000_000

# Construction in progress has to be big enough to be a mine. Either an absolute
# floor, or a meaningful share of a small company's balance sheet.
CIP_FLOOR = 5_000_000
CIP_SHARE = 0.05


def _has(series, pattern):
    return series.str.contains(pattern, regex=True, na=False)


def classify_stage(row):
    """(stage, basis). Revenue is a fact; everything after it is inference."""
    if row.get("is_royalty_streamer"):
        return "Royalty/Streamer", "summary names royalties"

    rev = row["revenue_stmt"] if pd.notna(row["revenue_stmt"]) else row["revenue_info"]
    cogs = row["cost_of_revenue"]
    has_cogs = pd.notna(cogs) and cogs != 0
    if pd.notna(rev):
        floor = REVENUE_FLOOR if has_cogs else REVENUE_FLOOR_NO_COGS
        if rev >= floor:
            return "Producer", "revenue" + ("" if has_cogs else ", no cost line")

    # No revenue, but building something. Construction in progress only — see
    # the STAGE note above for why capex cannot be used here. The floor keeps
    # out balances too small to be a mine: an explorer with A$0.1M of
    # construction in progress has fitted out an office.
    cip = row["construction_in_progress"]
    assets = row["total_assets"]
    if pd.notna(cip) and cip > 0:
        material = cip >= CIP_FLOOR or (
            pd.notna(assets) and assets > 0 and cip / assets >= CIP_SHARE)
        if material:
            return "Developer", "construction in progress"

    if pd.notna(row["total_assets"]):
        return "Explorer", "statements, no revenue"
    # Nothing came back at all. Not the same as knowing it does nothing.
    return "Unknown", "no data"


def main():
    clean = pd.read_csv(CLEAN)
    yah = pd.read_csv(YAHOO).drop_duplicates(subset="ticker_full", keep="last")

    df = clean.merge(yah.drop(columns=["ticker", "name"], errors="ignore"),
                     on="ticker_full", how="inner")
    print(f"{len(clean):,} ASX listings · {len(yah):,} fetched · {len(df):,} joined")

    summ = df["summary"].fillna("").str.lower()

    # ---- 1. who is a miner ----
    df["industry_is_mining"] = df["industry"].isin(MINING_INDUSTRIES)
    df["summary_is_mining"] = _has(summ, MINER_RE.pattern)
    df["is_miner"] = df["industry_is_mining"] | df["summary_is_mining"]
    df["is_royalty_streamer"] = _has(summ, ROYALTY_RE.pattern)

    # ---- 2. commodities ----
    for name, pat in COMMODITIES.items():
        df["comm_" + name] = _has(summ, pat)
    commflags = ["comm_" + c for c in COMMODITIES]
    df["commodity_count"] = df[commflags].sum(axis=1)
    df["is_polymetallic"] = df["commodity_count"] > 1
    df["no_disclosed_commodity"] = df["commodity_count"] == 0
    order = list(COMMODITIES)
    df["commodities"] = df[commflags].apply(
        lambda r: " | ".join(order[i].replace("_", " ").title()
                             for i, v in enumerate(r) if v) or pd.NA, axis=1)
    df["primary_commodity_industry"] = df["industry"].map(INDUSTRY_TO_COMMODITY)

    # ---- 3. geography ----
    for col, words in REGIONS.items():
        df[col] = _has(summ, "|".join(re.escape(w) for w in words))
    regcols = list(REGIONS)
    df["prop_other"] = ~df[regcols].any(axis=1) & (summ.str.len() > 0)
    regcols_all = regcols + ["prop_other"]
    df["property_region_count"] = df[regcols_all].sum(axis=1)
    df["property_regions"] = df[regcols_all].apply(
        lambda r: " | ".join(regcols_all[i][5:].replace("_", " ").title()
                             for i, v in enumerate(r) if v) or pd.NA, axis=1)
    df["no_disclosed_property"] = df["property_region_count"] == 0
    df["operates_offshore"] = df[[c for c in regcols_all
                                  if c != "prop_aus_nz_png"]].any(axis=1)

    # ---- 4. stage ----
    st = df.apply(classify_stage, axis=1, result_type="expand")
    df["stage"], df["stage_basis"] = st[0], st[1]
    df.loc[df["no_disclosed_commodity"] & df["no_disclosed_property"]
           & df["stage"].eq("Explorer"), "stage"] = "Shell"

    # ---- 5. market measures ----
    # NOT the TSX turnover. There, turnover is dollars traded in six months over
    # market cap, straight from the exchange. The ASX export carries no trading
    # data at all, so this is average daily volume x price x 126 trading days
    # over market cap — an estimate of the same quantity from a different
    # direction, and it carries a different name to keep that visible.
    px = df["price"]
    df["turnover_est"] = np.where(
        df["mcap"].gt(0) & px.notna() & df["volume_avg"].notna(),
        df["volume_avg"] * px * 126 / df["mcap"], np.nan)
    df["size_band"] = pd.cut(df["mcap"], bins=SIZE_BINS, labels=SIZE_LABELS)
    df["shares_implied"] = np.where(df["mcap"].gt(0) & px.gt(0),
                                    df["mcap"] / px, np.nan)
    df["market"] = "ASX"
    df["days_listed"] = (pd.Timestamp("2026-08-26")
                         - pd.to_datetime(df["listing_date"])).dt.days

    df.to_csv(OUT, index=False)

    # ─────────────────────────────── what the judgements actually produced ──
    mine = df[df["is_miner"]]
    print(f"\nMINING POPULATION  {len(mine):,} of {len(df):,}   "
          f"A${mine['mcap'].sum()/1e9:,.0f}B of A${df['mcap'].sum()/1e9:,.0f}B")
    print(f"  industry says mining      {int(df['industry_is_mining'].sum()):>4}")
    print(f"  summary says mining       {int(df['summary_is_mining'].sum()):>4}")
    print(f"  excluded                  {int((~df['is_miner']).sum()):>4}   "
          f"A${df.loc[~df['is_miner'],'mcap'].sum()/1e9:,.0f}B")

    print(f"\n  royalty / streaming       "
          f"{int(mine['is_royalty_streamer'].sum()):>4}")
    print(f"\nSTAGE (miners only)")
    print(mine["stage"].value_counts().to_string())
    print("\nbasis:")
    print(mine["stage_basis"].value_counts().to_string())

    print(f"\nCOMMODITY — shared with the TSX chart, miners only")
    for c in SHARED_WITH_TSX:
        n = int(mine["comm_" + c].sum())
        if n:
            print(f"  {c:<16}{n:>4}   {100*n/len(mine):4.1f}%")
    print("  — ASX additions —")
    for c in COMMODITIES:
        if c not in SHARED_WITH_TSX:
            n = int(mine["comm_" + c].sum())
            if n >= 10:
                print(f"  {c:<16}{n:>4}   {100*n/len(mine):4.1f}%")
    print(f"  no commodity named        {int(mine['no_disclosed_commodity'].sum()):>4}")
    print(f"  polymetallic              {int(mine['is_polymetallic'].sum()):>4}")

    print(f"\nWHERE THE ASSETS ARE (miners only, overlapping)")
    for c in regcols_all:
        n = int(mine[c].sum())
        print(f"  {c[5:]:<16}{n:>4}   {100*n/len(mine):4.1f}%")
    print(f"  operates offshore too     {int(mine['operates_offshore'].sum()):>4}")

    print(f"\nwrote {len(df):,} rows x {len(df.columns)} cols -> "
          f"{OUT.relative_to(ROOT)}")
    print("Filter on is_miner for the mining population.")


if __name__ == "__main__":
    main()
