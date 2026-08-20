"""
Enrich the cleaned TSX/TSXV mining dataset with join keys, TMX commodity and
property data, and derived market-structure metrics.

Input:  data/processed/mining_clean.csv                      (30-June-2026)
        data/raw/tmx_mining_properties_2026-07-31.xlsx       (31-July-2026)
        data/raw/enrichment/*.csv                            (optional)
Output: data/processed/mining_enriched.csv
        data/raw/enrichment/_template.csv                    (written if absent)

Commodity, property jurisdiction and royalty/streaming status all come from the
TMX mining properties file. Name-based commodity inference has been removed —
that file covers 92% of companies against name inference's 39%, and is sourced
rather than guessed.

Commodity is expressed two ways, and no single "primary commodity" is derived:
  - commodities   every commodity the company holds, pipe-joined in a fixed
                  order ("Gold | Silver | Copper"), so identical sets produce
                  identical strings and group directly.
  - comm_*        one boolean per commodity. Overlapping, so "companies with
                  any gold exposure" is answerable.
Property footprint follows the same pattern: property_regions /
property_jurisdictions as fixed-order pipe-joined sets, plus prop_* booleans.
Picking one commodity for a polymetallic company requires revenue data this
file does not contain, so it is not attempted.

NOTE ON DATES: the properties file is one month later than the issuer file.
Only the commodity and property columns are joined across; market cap, shares
and all trading figures stay on the 30-June basis so nothing mixes two dates.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "processed" / "mining_clean.csv"
PROPS = ROOT / "data" / "raw" / "tmx_mining_properties_2026-07-31.xlsx"
ENRICH_DIR = ROOT / "data" / "raw" / "enrichment"
TEMPLATE = ENRICH_DIR / "_template.csv"
OUT = ROOT / "data" / "processed" / "mining_enriched.csv"

DATA_ASOF = "2026-06-30"       # issuer file: market cap, shares, trading
PROPS_ASOF = "2026-07-31"      # properties file: commodity, jurisdiction
PROPS_HEADER_ROW = 9

# Still require external sourcing. Scaffolded empty, filled from enrichment/.
ENRICH_COLS = [
    "isin",
    "cusip",
    "sedar_issuer_no",
    "former_names",
    "stage",
    "incorporation_jurisdiction",
]

# TMX commodity flag columns, in file order.
COMMODITY_FLAGS = [
    "Oil and Gas", "Gold", "Silver", "Copper", "Nickel", "Diamond",
    "Molybdenum", "Platinum/PGM", "Iron", "Lead", "Zinc", "Rare Earths",
    "Potash", "Lithium", "Uranium", "Coal", "Tungsten",
    "Base & Precious Metals", "Royalty Streaming", "Other Properties",
]

# Non-specific buckets — real flags, but they don't name a commodity.
NON_SPECIFIC = {"Base & Precious Metals", "Other Properties", "Royalty Streaming"}
SPECIFIC_COMMODITIES = [c for c in COMMODITY_FLAGS if c not in NON_SPECIFIC]

# TMX property region columns. Values are jurisdiction text, not Y flags.
PROPERTY_REGIONS = [
    "AFRICA", "ASIA", "AUS/NZ/PNG", "CANADA", "LATIN AMERICA",
    "OTHER", "UK/EUROPE", "USA",
]

# HQ region value -> property region column, for the HQ/asset comparison.
HQ_TO_REGION = {
    "Canada": "CANADA",
    "USA": "USA",
    "Latin America": "LATIN AMERICA",
    "Australia/NZ/PNG": "AUS/NZ/PNG",
    "UK/Europe": "UK/EUROPE",
    "Asia": "ASIA",
    "Africa": "AFRICA",
    "Other": "OTHER",
}

SIZE_BINS = [0, 5e6, 25e6, 100e6, 500e6, 2e9, np.inf]
SIZE_LABELS = ["<5M", "5-25M", "25-100M", "100-500M", "500M-2B", ">2B"]

# Board-specific duplicates unified into one. (tsx_col, tsxv_col, output)
UNIFY = [
    ("Interlisted I", "Interlisted", "interlisted"),
    ("Trading \non OTC", "Trading on OTC", "otc_tier"),
    ("Former\nCPC", "CPC/\nFormer\nCPC", "cpc_flag"),
    ("S&P/TSX Index", "S&P/TSX Venture \nComposite Index", "index_member"),
    ("2025 TSX30", "2026 Venture 50", "annual_list"),
]

# Empty for mining, or irrelevant. Dropped.
DROP_COLS = [
    "Clean Technology Primary Industry", "Clean Technology Sub-Sector",
    "Cleantech Sub-Sector", "Consumer Products & Services\nSub-Sector",
    "Life Sciences Sub-Sector", "Real Estate Sub-Sector ",
    "Real Estate Sub-Sector", "Technology Sub-Sector ", "Technology Sub-Sector",
    "Israel Related", "Fund Family/Issuing Entity", "SP_Type", "SP_Sub",
    "Trust", "Sub\nSector", "Sub-Sector", "Asia Region", "USA City",
]

RENAME = {
    "Co_ID": "co_id",
    "Name": "name",
    "Exchange": "exchange",
    "Sector": "sector",
    "Listing Type": "listing_type",
    "Listing Date": "listing_date",
    "Interlisted II": "interlisted_2",
    "TSX \nVenture \nGrad": "tsxv_grad",
    "PO ID": "po_id",
}

LEGAL_SUFFIXES = (
    r"\b(inc|incorporated|corp|corporation|ltd|limited|plc|llc|lp|nl|"
    r"co|company|holdings?|group)\b\.?"
)


# --------------------------------------------------------------------------
# Tidy
# --------------------------------------------------------------------------

def tidy(df):
    for tsx_col, tsxv_col, out in UNIFY:
        left = df[tsx_col] if tsx_col in df.columns else pd.NA
        right = df[tsxv_col] if tsxv_col in df.columns else pd.NA
        df[out] = pd.Series(left, index=df.index).combine_first(
            pd.Series(right, index=df.index)
        )
        df = df.drop(columns=[c for c in (tsx_col, tsxv_col) if c in df.columns])

    return df.drop(columns=[c for c in DROP_COLS if c in df.columns])


# --------------------------------------------------------------------------
# Join keys
# --------------------------------------------------------------------------

def add_join_keys(df):
    """Stable identifiers. Needed before any history file exists, because
    tickers change on rebrand and Co_ID schemes differ by board."""
    suffix = df["board"].map({"TSX": ".TO", "TSXV": ".V"})
    df["ticker_full"] = df["ticker"].astype(str).str.strip() + suffix

    name = df["name"].astype(str).str.lower()
    name = name.str.replace(r"[^\w\s]", " ", regex=True)
    name = name.str.replace(LEGAL_SUFFIXES, " ", regex=True)
    df["name_normalised"] = name.str.replace(r"\s+", " ", regex=True).str.strip()
    return df


# --------------------------------------------------------------------------
# TMX commodity + property join
# --------------------------------------------------------------------------

def load_properties():
    """Read both sheets of the TMX mining properties file.

    Only the commodity and property columns are kept — market cap, shares and
    trading figures are a month later than the issuer file and must not mix.
    """
    if not PROPS.exists():
        print(f"  WARNING: {PROPS.name} not found — commodity columns will be empty")
        return None

    frames = []
    for sheet in (0, 1):
        raw = pd.read_excel(PROPS, sheet_name=sheet, skiprows=PROPS_HEADER_ROW)
        keep = ["Co_ID"] + [c for c in COMMODITY_FLAGS + PROPERTY_REGIONS
                            if c in raw.columns]
        missing = set(COMMODITY_FLAGS + PROPERTY_REGIONS) - set(raw.columns)
        if missing:
            print(f"  note: sheet {sheet} missing {sorted(missing)}")
        frames.append(raw[keep])

    props = pd.concat(frames, ignore_index=True)
    return props.drop_duplicates(subset="Co_ID").set_index("Co_ID")


def add_commodities(df, props):
    """Commodity flags as booleans, plus derived set / count / primary."""
    for col in COMMODITY_FLAGS:
        slug = "comm_" + col.lower().replace(" & ", "_").replace("/", "_").replace(" ", "_")
        if props is not None and col in props.columns:
            df[slug] = df["co_id"].map(props[col]).notna()
        else:
            df[slug] = False

    def slug_of(col):
        return "comm_" + col.lower().replace(" & ", "_").replace("/", "_").replace(" ", "_")

    specific = [slug_of(c) for c in SPECIFIC_COMMODITIES]
    df["commodity_count"] = df[specific].sum(axis=1)
    df["is_polymetallic"] = df["commodity_count"] > 1

    # Every commodity the company holds, always emitted in SPECIFIC_COMMODITIES
    # order, so identical sets produce identical strings and group cleanly.
    df["commodities"] = df[specific].apply(
        lambda r: " | ".join(
            SPECIFIC_COMMODITIES[i] for i, v in enumerate(r) if v
        ) or pd.NA,
        axis=1,
    )

    df["is_royalty_streamer"] = df[slug_of("Royalty Streaming")]
    df["company_type"] = np.where(
        df["is_royalty_streamer"], "Royalty/Streamer", "Operator"
    )
    df["no_disclosed_commodity"] = df["commodity_count"] == 0
    return df


def add_properties(df, props):
    """Property regions and jurisdictions, mirroring the commodity treatment.

    Source values mix separators — jurisdictions are comma-separated within a
    region column and the columns themselves are separate. Both are normalised
    to one pipe-joined list in a fixed order, so identical footprints produce
    identical strings.

    Region attribution comes from which column a token appeared in, so "CA"
    from the USA column is California, not Canada.
    """
    present = {}
    for region in PROPERTY_REGIONS:
        if props is not None and region in props.columns:
            present[region] = df["co_id"].map(props[region])
        else:
            present[region] = pd.Series(pd.NA, index=df.index)

    flags = pd.DataFrame({r: v.notna() for r, v in present.items()}, index=df.index)

    # One boolean per region, mirroring comm_*.
    for region in PROPERTY_REGIONS:
        slug = "prop_" + region.lower().replace("/", "_").replace(" ", "_")
        df[slug] = flags[region]

    df["property_regions"] = flags.apply(
        lambda r: " | ".join(c for c in PROPERTY_REGIONS if r[c]) or pd.NA, axis=1
    )
    df["property_region_count"] = flags.sum(axis=1)

    # Jurisdictions: split on comma, dedupe, emit in region order then
    # alphabetical within region.
    def jurisdictions(idx):
        out = []
        for region in PROPERTY_REGIONS:
            val = present[region].iat[idx]
            if pd.isna(val):
                continue
            toks = sorted({t.strip() for t in str(val).split(",") if t.strip()})
            out.extend(t for t in toks if t not in out)
        return " | ".join(out) or pd.NA

    df["property_jurisdictions"] = [jurisdictions(i) for i in range(len(df))]
    df["jurisdiction_count"] = (
        df["property_jurisdictions"].fillna("").apply(
            lambda s: len([t for t in s.split(" | ") if t])
        )
    )

    df["no_disclosed_property"] = df["property_region_count"] == 0

    # Does the company hold assets in the region it is headquartered in?
    hq_col = df["hq_region"].map(HQ_TO_REGION)
    df["hq_matches_property"] = [
        bool(flags.at[i, c]) if pd.notna(c) and c in flags.columns else pd.NA
        for i, c in zip(df.index, hq_col)
    ]

    # Listed as a miner, but discloses neither a commodity nor a property.
    df["shell_like"] = df["no_disclosed_commodity"] & df["no_disclosed_property"]
    return df


# --------------------------------------------------------------------------
# Derived market-structure metrics
# --------------------------------------------------------------------------

def add_derived(df):
    df["size_band"] = pd.cut(df["mcap"], bins=SIZE_BINS, labels=SIZE_LABELS)

    # Attention: share of sector trading value vs share of sector market cap.
    # >1 means the company draws more money than its size warrants.
    value_share = df["value_ytd"] / df["value_ytd"].sum()
    mcap_share = df["mcap"] / df["mcap"].sum()
    df["attention_ratio"] = value_share / mcap_share

    df["turnover_pctile"] = df["turnover"].rank(pct=True) * 100
    df["turnover_pctile_in_band"] = (
        df.groupby("size_band", observed=True)["turnover"].rank(pct=True) * 100
    )
    df["dormant"] = (df["turnover"] < 0.01) | (df["months"] < 6) | df["value_ytd"].isna()

    ld = pd.to_numeric(df["listing_date"], errors="coerce")
    parsed = pd.to_datetime(
        ld.where(ld > 19000000).astype("Int64").astype(str),
        format="%Y%m%d", errors="coerce",
    )
    df["listing_date_iso"] = parsed.dt.strftime("%Y-%m-%d")
    df["days_listed"] = (pd.Timestamp(DATA_ASOF) - parsed).dt.days
    return df


# --------------------------------------------------------------------------
# External enrichment join (for what TMX doesn't supply)
# --------------------------------------------------------------------------

def write_template(df):
    ENRICH_DIR.mkdir(parents=True, exist_ok=True)
    if TEMPLATE.exists():
        return
    cols = ["ticker_full", "co_id", "name", "board", "mcap"] + ENRICH_COLS
    out = df[["ticker_full", "co_id", "name", "board", "mcap"]].copy()
    for c in ENRICH_COLS:
        out[c] = pd.NA
    out.sort_values("mcap", ascending=False)[cols].to_csv(TEMPLATE, index=False)
    print(f"wrote enrichment template -> {TEMPLATE.relative_to(ROOT)}")


def join_enrichment(df):
    """Left-join every CSV in the enrichment dir on ticker_full, in filename
    order. Later files fill gaps but never overwrite an existing value."""
    for c in ENRICH_COLS:
        df[c] = pd.NA
    df["enrich_source"] = pd.NA

    if not ENRICH_DIR.exists():
        return df

    for path in sorted(p for p in ENRICH_DIR.glob("*.csv") if p.name != "_template.csv"):
        ext = pd.read_csv(path, dtype=str)
        if "ticker_full" not in ext.columns:
            print(f"  skipped {path.name} — no ticker_full column")
            continue
        ext = ext.drop_duplicates(subset="ticker_full").set_index("ticker_full")
        matched = df["ticker_full"].isin(ext.index).sum()
        for c in ENRICH_COLS:
            if c not in ext.columns:
                continue
            incoming = df["ticker_full"].map(ext[c])
            df[c] = df[c].combine_first(incoming)
            df.loc[incoming.notna(), "enrich_source"] = (
                df.loc[incoming.notna(), "enrich_source"].fillna(path.stem)
            )
        print(f"  joined {path.name}: {matched}/{len(df)} rows matched")
    return df


# --------------------------------------------------------------------------

def main():
    df = pd.read_csv(SRC)
    df = df.rename(columns=RENAME)
    df = tidy(df)
    df = add_join_keys(df)

    props = load_properties()
    matched = df["co_id"].isin(props.index).sum() if props is not None else 0
    df = add_commodities(df, props)
    df = add_properties(df, props)
    df = add_derived(df)

    write_template(df)
    df = join_enrichment(df)

    df["data_asof"] = DATA_ASOF
    df["properties_asof"] = PROPS_ASOF

    lead = [
        "co_id", "ticker_full", "ticker", "name", "name_normalised", "board",
        "isin", "cusip", "sedar_issuer_no", "former_names",
        "commodities", "commodity_count", "is_polymetallic", "company_type",
        "is_royalty_streamer", "no_disclosed_commodity",
        "property_regions", "property_jurisdictions", "property_region_count",
        "jurisdiction_count", "hq_matches_property", "no_disclosed_property",
        "shell_like", "stage", "incorporation_jurisdiction",
        "mcap", "shares", "px", "size_band",
        "value_ytd", "vol_ytd", "trades_ytd", "months",
        "turnover", "turnover_pctile", "turnover_pctile_in_band",
        "attention_ratio", "avg_trade", "dormant",
        "hq_location", "hq_region",
        "listing_type", "listing_date_iso", "days_listed", "lyear", "yrs",
    ]
    ordered = [c for c in lead if c in df.columns]
    ordered += [c for c in df.columns if c not in ordered]
    df = df[ordered]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    n = len(df)
    print(f"\nproperties file matched: {matched}/{n} companies")
    print(f"commodity known: {df['commodities'].notna().sum()}/{n}   "
          f"distinct sets: {df['commodities'].nunique()}")
    print(f"polymetallic: {df.is_polymetallic.sum()}   "
          f"royalty/streamer: {df.is_royalty_streamer.sum()}")
    print(f"no disclosed commodity: {df.no_disclosed_commodity.sum()}   "
          f"no property: {df.no_disclosed_property.sum()}   "
          f"shell-like: {df.shell_like.sum()}")
    print(f"\nrows: {n}   columns: {len(df.columns)}")
    print(f"written -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
