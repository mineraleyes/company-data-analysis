"""
Chart section for the report: commodity and asset-region breakdowns.

Reads data/processed/mining_enriched.csv and emits a self-contained HTML
fragment — data as inline JSON, rendering in vanilla JS, no CDN.

Two controls, applied to both charts:
  - Board     TSX / TSXV, either or both
  - Measure   one of four, in two families:

              ADDITIVE  (companies, market cap) — boards stack, because a
                        company sits on exactly one board and the parts sum
                        to the whole.
              STATISTIC (typical size, turnover) — boards sit SIDE BY SIDE.
                        A median or a ratio cannot be stacked: median gold
                        market cap is C$1,539M on TSX and C$20M on TSXV, but
                        C$35M combined. Stacking those would be nonsense.

Value traded is deliberately absent — it ranks identically to market cap
(Spearman 1.0 across commodities), so it would be a duplicate chart.

Commodity and region flags OVERLAP — a company can hold gold and copper, or
ground in Canada and Peru. So a bar reads "companies with gold exposure" and
the bars deliberately sum to more than the sector total. That is why these are
bars and not a pie: a pie of overlapping shares would total ~240%.
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "mining_enriched.csv"

SPECIFIC_COMMODITIES = [
    "Gold", "Silver", "Copper", "Nickel", "Diamond", "Molybdenum",
    "Platinum/PGM", "Iron", "Lead", "Zinc", "Rare Earths", "Potash",
    "Lithium", "Uranium", "Coal", "Tungsten",
]

REGION_LABELS = {
    "prop_canada": "Canada",
    "prop_latin_america": "Latin America",
    "prop_usa": "USA",
    "prop_africa": "Africa",
    "prop_uk_europe": "UK / Europe",
    "prop_aus_nz_png": "Aus / NZ / PNG",
    "prop_asia": "Asia",
    "prop_other": "Other",
}

BOARDS = ["TSX", "TSXV"]


def _slug(commodity):
    return "comm_" + (
        commodity.lower().replace(" & ", "_").replace("/", "_").replace(" ", "_")
    )


def _stats(sub):
    """Everything a measure might need, per board per category."""
    traded = float(sub["value_ytd"].fillna(0).sum())
    mcap = float(sub["mcap"].sum())
    return {
        "n": int(len(sub)),
        "mcap": mcap,
        "median": float(sub["mcap"].median()) if len(sub) else 0.0,
        # aggregate turnover: money traded per dollar of market cap
        "turnover": (traded / mcap) if mcap else 0.0,
        "traded": traded,
    }


def _series_mask(df, mask, label):
    row = {"label": label}
    for board in BOARDS:
        row[board] = _stats(df[mask & (df["board"] == board)])
    row["ALL"] = _stats(df[mask])       # for non-additive measures on both boards
    return row


def _series(df, flag_col, label):
    return _series_mask(df, df[flag_col].fillna(False), label)


def build_data():
    df = pd.read_csv(DATA)

    commodity = [
        _series(df, _slug(c), c)
        for c in SPECIFIC_COMMODITIES
        if _slug(c) in df.columns
    ]
    commodity = [r for r in commodity if sum(r[b]["n"] for b in BOARDS) > 0]

    region = [
        _series(df, col, label)
        for col, label in REGION_LABELS.items()
        if col in df.columns
    ]
    region = [r for r in region if sum(r[b]["n"] for b in BOARDS) > 0]

    # Commodity x region — counts only; a cell is "companies with this
    # commodity AND ground in this region", so rows and columns both overlap.
    heat_com = [c for c in SPECIFIC_COMMODITIES if _slug(c) in df.columns]
    heat_reg = [c for c in REGION_LABELS if c in df.columns]
    heat = {
        "commodities": heat_com,
        "regions": [REGION_LABELS[c] for c in heat_reg],
        "cells": [
            [
                {
                    b: int(
                        (
                            df[_slug(c)].fillna(False)
                            & df[r].fillna(False)
                            & (df["board"] == b)
                        ).sum()
                    )
                    for b in BOARDS
                }
                for c in heat_com
            ]
            for r in heat_reg
        ],
    }

    # ---- listings per year, optionally split ----
    lines = build_lines(df)

    totals = {
        b: {
            "n": int((df["board"] == b).sum()),
            "mcap": float(df.loc[df["board"] == b, "mcap"].sum()),
        }
        for b in BOARDS
    }

    # Companies with no commodity / no property disclosed — the bars can't show
    # these, so they're reported as a footnote instead of a silent omission.
    gaps = {
        "no_commodity": int(df["no_disclosed_commodity"].sum()),
        "no_property": int(df["no_disclosed_property"].sum()),
    }
    return {
        "commodity": commodity,
        "region": region,
        "heat": heat,
        "lines": lines,
        "returns": build_returns(),
        "geo": build_geo(df),
        "size": build_size(df),
        "stage": build_stage(df),
        "stage_series": build_stage_series(df),
        "npsize": build_npsize(df),
        "prodshare": build_prodshare(df),
        "totals": totals,
        "gaps": gaps,
    }


# Listing-date chart starts here — only 30 surviving companies list before 2000,
# so earlier years are a long flat tail that squashes the readable part.
FIRST_YEAR = 2000

# Top 5 by company count, plus an "Other" catch-all. Capped because a line
# chart cannot carry more than a handful of series legibly.
TOP_COMMODITIES = ["Gold", "Copper", "Silver", "Lithium", "Nickel"]
TOP_REGIONS = ["prop_canada", "prop_latin_america", "prop_usa",
               "prop_africa", "prop_uk_europe"]


PRICES = ROOT / "data" / "processed" / "price_milestones.csv"
ASX_DATA = ROOT / "data" / "processed" / "asx_clean.csv"

MILESTONE_LABELS = {7: "7d", 30: "1m", 90: "3m", 180: "6m", 365: "1y", 730: "2y",
                    1095: "3y", 1825: "5y", 2555: "7y", 3650: "10y", 5475: "15y"}

# Below this a median is noise, not a finding.
MIN_SAMPLE = 10


TOP_HQ = 7          # HQ countries shown as their own row; rest fold into Other
TOP_OP = 14         # operating countries shown as their own column


SIZE_BINS = [0, 5e6, 25e6, 100e6, 500e6, 2e9, float("inf")]
SIZE_LABELS = ["< C$5M", "C$5\u201325M", "C$25\u2013100M",
               "C$100\u2013500M", "C$500M\u20132B", "> C$2B"]


# Lifecycle order, not frequency order: the bars are read as a sequence from
# "sells metal" to "nothing disclosed", so sorting them by count would hide the
# shape. Unknown sits last because it is an absence of data, not a stage.
STAGE_ORDER = ["Producer", "Royalty/Streamer", "Explorer", "Shell", "Unknown"]


def build_stage(df):
    if "stage" not in df.columns:
        return None
    return [
        {"label": st,
         **{b: int(((df["stage"] == st) & (df["board"] == b)).sum()) for b in BOARDS}}
        for st in STAGE_ORDER
        if (df["stage"] == st).any()
    ]


# Everything that is not selling metal. Royalty/streamer is excluded because
# it earns without operating, so it belongs in neither camp.
NON_PRODUCING = ("Explorer", "Shell", "Unknown")

# Below this a producing share is one or two companies and reads as noise.
PRODSHARE_MIN = 15


def build_stage_series(df):
    """Stage in the same shape as commodity and region.

    That is the whole point of the shape: the Measure toggle then answers
    "is explorer trading thinner, or only smaller?" without any new plumbing.
    """
    if "stage" not in df.columns:
        return None
    return [_series_mask(df, df["stage"] == st, st)
            for st in STAGE_ORDER if (df["stage"] == st).any()]


def build_npsize(df):
    """Size distribution of the companies that are not producing.

    Explorer runs from a shell holding one claim to Seabridge at C$3.9B.
    Nothing in the free data separates those, but market cap does it well
    enough to be worth showing on its own rather than implying a stage.
    """
    if "stage" not in df.columns:
        return None
    sub = df[df["stage"].isin(NON_PRODUCING)]
    band = pd.cut(sub["mcap"], bins=SIZE_BINS, labels=SIZE_LABELS)
    return [_series_mask(sub, band == lab, lab) for lab in SIZE_LABELS]


def build_prodshare(df):
    """Producing companies as a share of each commodity's companies.

    Counts, not the share itself, because the board filter has to be applied
    before the division — a share of a share is not a share.
    """
    if "stage" not in df.columns:
        return None
    producing = df["stage"] == "Producer"
    out = []
    for c in SPECIFIC_COMMODITIES:
        col = _slug(c)
        if col not in df.columns:
            continue
        m = df[col].fillna(False)
        row = {"label": c}
        for b in BOARDS:
            mb = m & (df["board"] == b)
            row[b] = {"prod": int((mb & producing).sum()), "tot": int(mb.sum())}
        if sum(row[b]["tot"] for b in BOARDS):
            out.append(row)
    return out


def build_size(df):
    band = pd.cut(df["mcap"], bins=SIZE_BINS, labels=SIZE_LABELS)
    return [
        {"label": lab,
         **{b: int(((band == lab) & (df["board"] == b)).sum()) for b in BOARDS}}
        for lab in SIZE_LABELS
    ]


def build_geo(df):
    """Domicile country against operating country, company counts.

    A company with ground in three countries appears in three cells, so the
    grid sums to more than the number of companies.
    """
    if "hq_country" not in df.columns or "property_countries" not in df.columns:
        return None

    rows = []
    for hq, pc, board in zip(df["hq_country"], df["property_countries"], df["board"]):
        if pd.isna(hq) or pd.isna(pc):
            continue
        for op in str(pc).split(" | "):
            rows.append((hq, op, board))
    if not rows:
        return None
    pairs = pd.DataFrame(rows, columns=["hq", "op", "board"])

    hq_order = pairs["hq"].value_counts().head(TOP_HQ).index.tolist()
    op_order = pairs["op"].value_counts().head(TOP_OP).index.tolist()
    pairs["hq_b"] = pairs["hq"].where(pairs["hq"].isin(hq_order), "Other")
    pairs["op_b"] = pairs["op"].where(pairs["op"].isin(op_order), "Other")

    hq_rows = hq_order + ["Other"]
    op_cols = op_order + ["Other"]

    cells = []
    for h in hq_rows:
        row = []
        for o in op_cols:
            m = (pairs["hq_b"] == h) & (pairs["op_b"] == o)
            row.append({b: int((m & (pairs["board"] == b)).sum()) for b in BOARDS})
        cells.append(row)

    return {
        "hq": hq_rows,
        "op": op_cols,
        "cells": cells,
        "pairs": int(len(pairs)),
        "companies": int(df["property_countries"].notna().sum()),
        "abroad": int((df["hq_country_matches_property"] == False).sum()),
    }


def build_returns():
    """Median return and share underwater at each milestone, per board.

    Returns None if the price file has not been generated yet, so the report
    still builds on a machine that has not run fetch_prices.py.
    """
    if not PRICES.exists():
        return None
    p = pd.read_csv(PRICES)
    ok = p[p["status"] == "ok"]
    if ok.empty:
        return None

    days = [d for d in MILESTONE_LABELS if f"ret_d{d}" in ok.columns]
    out = {"labels": [MILESTONE_LABELS[d] for d in days], "boards": {}}

    for b in BOARDS:
        sub = ok[ok["board"] == b]
        med, neg, n, p25, p75 = [], [], [], [], []
        for d in days:
            v = sub[f"ret_d{d}"].dropna()
            if len(v) < MIN_SAMPLE:
                med.append(None); neg.append(None)
                p25.append(None); p75.append(None); n.append(len(v))
            else:
                med.append(round(float(v.median()) * 100, 1))
                neg.append(round(float((v < 0).mean()) * 100, 1))
                p25.append(round(float(v.quantile(0.25)) * 100, 1))
                p75.append(round(float(v.quantile(0.75)) * 100, 1))
                n.append(int(len(v)))
        out["boards"][b] = {"median": med, "neg": neg, "n": n,
                            "p25": p25, "p75": p75}

    out["usable"] = int(len(ok))
    out["total"] = int(len(p))
    out["no_listing_date"] = int((p["status"] == "no listing date").sum())
    out["no_history"] = int((p["status"] == "no price near listing").sum())
    # Read back from CSV the column is object dtype, so fillna would downcast
    # and pandas warns about it on every build. An equality test is exact and
    # needs no fill.
    out["consolidated"] = int((ok["consolidated"] == True).sum())
    return out


def build_lines(df):
    """Companies by listing year, whole and split two ways.

    Counts are of companies that listed in a given year AND ARE STILL LISTED.
    Failures are absent from the source file entirely, so early years are
    systematically undercounted — the upward slope is part real, part
    survivorship. Stated on the chart.
    """
    d = df.dropna(subset=["lyear"]).copy()
    d["lyear"] = d["lyear"].astype(int)
    d = d[d["lyear"] >= FIRST_YEAR]
    years = list(range(FIRST_YEAR, int(d["lyear"].max()) + 1))

    def counts(sub):
        by = {b: [0] * len(years) for b in BOARDS}
        for (yr, board), n in sub.groupby(["lyear", "board"]).size().items():
            if yr in years:
                by[board][years.index(yr)] = int(n)
        return by

    def split(masks, labels):
        out = []
        covered = pd.Series(False, index=d.index)
        for mask, label in zip(masks, labels):
            out.append({"label": label, "byBoard": counts(d[mask])})
            covered |= mask
        out.append({"label": "Other", "byBoard": counts(d[~covered])})
        return out

    com_masks = [d[_slug(c)].fillna(False) for c in TOP_COMMODITIES]
    reg_masks = [d[r].fillna(False) for r in TOP_REGIONS]

    return {
        "years": years,
        "missing": int(df["lyear"].isna().sum()),
        "before": int(df["lyear"].notna().sum()
                      - (df["lyear"] >= FIRST_YEAR).sum()),
        "partial": years[-1],
        "none": [{"label": "All mining", "byBoard": counts(d)}],
        "commodity": split(com_masks, TOP_COMMODITIES),
        "region": split(reg_masks, [REGION_LABELS[r] for r in TOP_REGIONS]),
    }


# The ASX export has no board split and no second series of any kind, so its
# charts are single-series. A third hue rather than a borrowed board colour:
# TSX blue on an ASX chart would read as a comparison that is not being made.
ASX_SIZE_LABELS = ["< $5M", "$5\u201325M", "$25\u2013100M",
                   "$100\u2013500M", "$500M\u20132B", "> $2B"]

# Before this, surviving listings are a thin tail back to 1885.
ASX_FIRST_YEAR = 2000


def build_asx():
    """Everything the ASX file can support, which is not much.

    Population is GICS Materials — the finest classification in the export.
    It carries roughly A$92B of packaging, steel and chemicals, and it leaves
    coal and uranium miners out in Energy. Both are stated wherever the number
    is used rather than quietly corrected.
    """
    if not ASX_DATA.exists():
        return None
    df = pd.read_csv(ASX_DATA)
    m = df[df["is_materials"] == True]          # noqa: E712 — CSV round-trip
    priced = m[m["mcap"].notna()]
    total = float(priced["mcap"].sum())

    size = [{"label": lab, "n": int((m["size_band"] == lab).sum())}
            for lab in ASX_SIZE_LABELS]

    yrs = m["listing_year"].dropna().astype(int)
    years = [{"label": str(y), "n": int((yrs == y).sum())}
             for y in range(ASX_FIRST_YEAR, int(yrs.max()) + 1)]

    top10 = priced.nlargest(10, "mcap")
    return {
        "n": int(len(m)),
        "total": total,
        "median": float(priced["mcap"].median()),
        "no_mcap": int(m["mcap"].isna().sum()),
        "size": size,
        "years": years,
        "before": int((yrs < ASX_FIRST_YEAR).sum()),
        "top10_share": 100 * float(top10["mcap"].sum()) / total,
        "largest": top10.iloc[0]["name"],
        "largest_share": 100 * float(top10.iloc[0]["mcap"]) / total,
    }


def _esc(text):
    """Labels carry < and > (size bands), which would break the markup."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def static_bars(rows, note="", pct=False):
    """A plain stacked bar list — no controls, no JS.

    Used inside the written sections, where a chart illustrates the paragraph
    it sits in. The interactive versions live on the Charts tab; these are
    deliberately inert so the prose stays the thing being read.
    """
    biggest = max((sum(r[b] for b in BOARDS) for r in rows), default=1) or 1
    total = sum(sum(r[b] for b in BOARDS) for r in rows) or 1

    out = ['<div class="viz-root viz-static"><div class="legend">'
           '<span><i style="background:var(--series-TSX)"></i>TSX</span>'
           '<span><i style="background:var(--series-TSXV)"></i>TSXV</span>'
           '</div><div class="rows">']
    for r in rows:
        tot = sum(r[b] for b in BOARDS)
        segs = "".join(
            f'<div class="seg-fill" style="width:{100 * r[b] / biggest:.2f}%;'
            f'background:var(--series-{b})" title="{b}: {r[b]:,}"></div>'
            for b in BOARDS if r[b] > 0
        )
        val = f"{tot:,}" + (f" · {100 * tot / total:.0f}%" if pct else "")
        out.append(
            f'<div class="row"><div class="cat">{_esc(r["label"])}</div>'
            f'<div class="track"><div class="bar">{segs}</div></div>'
            f'<div class="val">{val}</div></div>'
        )
    out.append("</div>")
    if note:
        out.append(f'<p class="note" style="margin-top:12px">{note}</p>')
    out.append("</div>")
    return "".join(out)


def static_bars_one(rows, note="", legend="Companies"):
    """One series, no board split — the ASX charts.

    Same markup as the stacked version so the hover script and the CSS both
    keep working; only the number of segments differs.
    """
    biggest = max((r["n"] for r in rows), default=1) or 1
    out = ['<div class="viz-root viz-static"><div class="legend">'
           f'<span><i style="background:var(--series-ASX)"></i>{_esc(legend)}</span>'
           '</div><div class="rows">']
    for r in rows:
        w = 100 * r["n"] / biggest
        seg = (f'<div class="seg-fill" style="width:{w:.2f}%;'
               f'background:var(--series-ASX)" title="{r["n"]:,}"></div>'
               if r["n"] else "")
        out.append(
            f'<div class="row"><div class="cat">{_esc(r["label"])}</div>'
            f'<div class="track"><div class="bar">{seg}</div></div>'
            f'<div class="val">{r["n"]:,}</div></div>'
        )
    out.append("</div>")
    if note:
        out.append(f'<p class="note" style="margin-top:12px">{note}</p>')
    out.append("</div>")
    return "".join(out)


def static_chart(kind):
    """Render one named static chart for embedding in a markdown tab."""
    data = build_data()

    if kind == "size":
        return static_bars(data["size"])

    if kind.startswith("asx_"):
        a = build_asx()
        if not a:
            raise KeyError("asx_clean.csv missing — run build_asx_dataset.py")
        if kind == "asx_size":
            return static_bars_one(
                a["size"],
                note=f"Market cap in Australian dollars. {a['no_mcap']} companies "
                     f"show no market cap in the export — suspended lines, read as "
                     f"blank rather than zero, so they appear in no band.")
        if kind == "asx_listings":
            return static_bars_one(
                a["years"],
                note=f"Companies that listed in each year <strong>and are still "
                     f"listed today</strong>, so early years are undercounted by "
                     f"everything that has since failed or been acquired. "
                     f"{a['before']} surviving companies listed before "
                     f"{ASX_FIRST_YEAR} and are not shown.",
                legend="Listings")
        raise KeyError(f"unknown chart: {kind}")

    if kind == "stage":
        if not data["stage"]:
            raise KeyError("stage column missing — run fetch_fundamentals.py")
        return static_bars(
            data["stage"],
            note="Producer means the company reported revenue. Everything else "
                 "without revenue is an explorer: Yahoo's business summaries "
                 "name the commodity but not the project stage, so a separate "
                 "developer bucket could not be built from them.")

    if kind == "commodity":
        rows = [{"label": r["label"], **{b: r[b]["n"] for b in BOARDS}}
                for r in data["commodity"]]
        rows.sort(key=lambda r: -sum(r[b] for b in BOARDS))
        return static_bars(
            rows,
            note="Companies hold more than one commodity, so these bars sum to "
                 "more than the sector total.")

    if kind == "assets":
        rows = [{"label": r["label"], **{b: r[b]["n"] for b in BOARDS}}
                for r in data["region"]]
        rows.sort(key=lambda r: -sum(r[b] for b in BOARDS))
        return static_bars(
            rows,
            note="Region of the company's properties, not its head office. "
                 "Companies with ground in several regions appear in each.")

    raise KeyError(f"unknown chart: {kind}")


CSS = """
.viz-root {
  color-scheme: light;
  --surface-1: #ffffff;
  --series-TSX: #2a78d6;
  --series-TSXV: #eb6834;
  /* A share is not a board, so it must not borrow a board's colour. Slot 3 of
     the validated categorical palette; passes CVD separation against both. */
  --series-stage: #1baf7a;
  /* A third market, not a third board — slot 6 of the same validated palette. */
  --series-ASX: #4a3aa7;
  --axis: #e4e4e4;
}

.ctrls {
  display: flex;
  flex-wrap: wrap;
  gap: 26px;
  align-items: center;
  padding: 14px 0 18px;
  margin-bottom: 8px;
  border-bottom: 1px solid var(--line);
  position: sticky;
  top: 0;
  background: #fff;
  z-index: 5;
}
.ctrl-group { display: flex; align-items: center; gap: 8px; }
.ctrl-label {
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--ink-faint);
}
.seg { display: flex; gap: 4px; }
.seg button {
  appearance: none;
  font: inherit;
  font-size: 13px;
  padding: 5px 12px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink-soft);
  border-radius: 5px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 7px;
}
.seg button:hover { border-color: #c9c9c9; color: var(--ink); }
.seg button[aria-pressed="true"] { color: var(--ink); border-color: #b0b0b0; font-weight: 550; }
.seg button .dot {
  width: 9px; height: 9px; border-radius: 2px;
  background: currentColor; opacity: .25;
}
.seg button[aria-pressed="true"] .dot { opacity: 1; }
.seg button[data-board="TSX"] .dot { color: var(--series-TSX); }
.seg button[data-board="TSXV"] .dot { color: var(--series-TSXV); }

.chart { margin: 30px 0 8px; }
.chart h3 { margin: 0 0 2px; font-size: 17px; font-weight: 600; }
.chart .note { margin: 0 0 16px; font-size: 13px; color: var(--ink-faint); }

.legend { display: flex; gap: 16px; margin: 0 0 14px; font-size: 13px; }
.legend span { display: inline-flex; align-items: center; gap: 7px; color: var(--ink-soft); }
.legend i { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }

.rows { display: flex; flex-direction: column; gap: 9px; }
.row { display: grid; grid-template-columns: 108px 1fr auto; align-items: center; gap: 12px; }
.row .cat { font-size: 13px; color: var(--ink); text-align: right; }
.track { position: relative; height: 20px; }
.bar { display: flex; height: 100%; gap: 2px; }
.seg-fill {
  height: 100%;
  border-radius: 0;
  transition: opacity .12s;
}
.bar .seg-fill:last-child { border-radius: 0 4px 4px 0; }
.bar .seg-fill:only-child  { border-radius: 0 4px 4px 0; }

/* non-additive measures: one thin bar per board, side by side */
.bar.grouped { flex-direction: column; gap: 3px; }
.bar.grouped .seg-fill { height: calc(50% - 1.5px); border-radius: 0 3px 3px 0; }
.row .val {
  font-size: 13px;
  color: var(--ink-soft);
  font-variant-numeric: tabular-nums;
  min-width: 72px;
  text-align: right;
}
.row:hover .seg-fill { opacity: .75; }

.tip {
  position: fixed;
  pointer-events: none;
  background: #1a1a1a;
  color: #fff;
  font-size: 12px;
  line-height: 1.45;
  padding: 7px 10px;
  border-radius: 5px;
  opacity: 0;
  transition: opacity .1s;
  z-index: 40;
  white-space: nowrap;
}
.tip b { font-weight: 600; }
.tip .k { color: #b9b9b9; }

/* ---- line chart ---- */
.linewrap { position: relative; }
.linewrap svg { display: block; width: 100%; height: 300px; overflow: visible; }
.linewrap .grid { stroke: var(--axis); stroke-width: 1; }
.linewrap .axis-txt { fill: var(--ink-faint); font-size: 11px; }
.linewrap .ser { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.linewrap .dot { stroke: #fff; stroke-width: 2; }
.linewrap .endlab { font-size: 11px; font-weight: 550; }
.linewrap .cross { stroke: #b8b8b8; stroke-width: 1; }
.linewrap .partial { stroke: #c9c9c9; stroke-width: 1; stroke-dasharray: 3 3; }
.linewrap .hit { fill: transparent; cursor: crosshair; }

/* ---- heatmap ---- */
.heat { overflow-x: auto; }
.heat table { border-collapse: separate; border-spacing: 2px; font-size: 12px; width: auto; }
.heat th {
  font-weight: 500;
  font-size: 10px;
  color: var(--ink-faint);
  text-transform: none;
  letter-spacing: 0;
  border: 0;
  padding: 2px 4px;
  white-space: nowrap;
}
.heat thead th { text-align: center; vertical-align: bottom; }
.heat tbody th { text-align: right; }
.heat td {
  border: 0;
  padding: 0;
  width: 36px;
  height: 28px;
  text-align: center;
  border-radius: 3px;
  font-variant-numeric: tabular-nums;
  cursor: default;
}
.heat td.z { color: #c4c4c4; background: #fafafa; }
/* the diagonal: operating in your own country of domicile */
.heat td.home { box-shadow: inset 0 0 0 1.5px #9a9a9a; }
.heat tbody th { max-width: 92px; white-space: normal; line-height: 1.25; }
.scale { display: flex; align-items: center; gap: 8px; margin: 12px 0 0; font-size: 11px; color: var(--ink-faint); }
.scale i { width: 22px; height: 10px; border-radius: 2px; display: inline-block; }

details.tbl { margin: 14px 0 0; }
details.tbl summary {
  cursor: pointer;
  font-size: 12px;
  color: var(--ink-faint);
  padding: 4px 0;
}
details.tbl summary:hover { color: var(--ink); }

@media (max-width: 640px) {
  .row { grid-template-columns: 84px 1fr; }
  .row .val { grid-column: 2; text-align: left; font-size: 12px; }
  .ctrls { gap: 16px; }
}
"""

JS = """
(function () {
  const D = window.__VIZ__;
  const boards = new Set(['TSX', 'TSXV']);
  let measure = 'n';

  // Additive measures stack the boards; statistics sit side by side, because
  // a median or a ratio of the parts is not the value for the whole.
  const ADDITIVE = { n: true, mcap: true, median: false, turnover: false };

  // Sorting a distribution by value destroys it — the bands are the x axis.
  const KEEP_ORDER = { npsize: true };

  const fmtN = v => v.toLocaleString('en-US');
  const fmtM = v =>
    v >= 1e9 ? 'C$' + (v / 1e9).toFixed(1) + 'B'
             : v >= 1e6 ? 'C$' + Math.round(v / 1e6).toLocaleString('en-US') + 'M'
                        : 'C$' + Math.round(v / 1e3).toLocaleString('en-US') + 'k';
  const fmt = v =>
    measure === 'n' ? fmtN(v)
      : measure === 'turnover' ? Math.round(v * 100) + '%'
      : fmtM(v);

  const tip = document.createElement('div');
  tip.className = 'tip';
  document.body.appendChild(tip);

  function showTip(e, html) {
    tip.innerHTML = html;
    tip.style.opacity = 1;
    const r = tip.getBoundingClientRect();
    let x = e.clientX + 14;
    if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
    tip.style.left = x + 'px';
    tip.style.top = Math.min(e.clientY + 14, innerHeight - r.height - 8) + 'px';
  }
  const hideTip = () => (tip.style.opacity = 0);

  function draw(key) {
    const host = document.getElementById('chart-' + key);
    const additive = ADDITIVE[measure];
    const sel = [...boards];

    const rows = D[key]
      .map(r => {
        const parts = sel.map(b => ({ board: b, v: r[b][measure], n: r[b].n }));
        // headline value: sum for additive, the combined figure otherwise
        const total = additive
          ? parts.reduce((s, p) => s + p.v, 0)
          : (sel.length === 2 ? r.ALL[measure] : parts[0].v);
        return { label: r.label, parts, total };
      });
    if (!KEEP_ORDER[key]) rows.sort((a, b) => b.total - a.total);

    // additive bars scale to the stacked total; grouped bars to the largest part
    const max = additive
      ? Math.max(...rows.map(r => r.total))
      : Math.max(...rows.flatMap(r => r.parts.map(p => p.v)));

    host.innerHTML = rows
      .map(r => {
        const segs = r.parts
          .filter(p => additive ? p.v > 0 : p.n > 0)
          .map(p => {
            const w = Math.max((p.v / (max || 1)) * 100, p.v > 0 ? 0.4 : 0);
            return `<div class="seg-fill" style="width:${w}%;background:var(--series-${p.board})"
                     data-label="${r.label}" data-board="${p.board}"
                     data-v="${p.v}" data-n="${p.n}"></div>`;
          })
          .join('');
        return `<div class="row"><div class="cat">${r.label}</div>
                <div class="track"><div class="bar${additive ? '' : ' grouped'}">${segs}</div></div>
                <div class="val">${fmt(r.total)}</div></div>`;
      })
      .join('');

    host.querySelectorAll('.seg-fill').forEach(el => {
      el.addEventListener('mousemove', e =>
        showTip(e,
          `<b>${el.dataset.label}</b><br>` +
          `<span class="k">${el.dataset.board}</span> ${fmt(+el.dataset.v)}` +
          `<br><span class="k">${(+el.dataset.n).toLocaleString('en-US')} companies</span>`)
      );
      el.addEventListener('mouseleave', hideTip);
    });

    // table view — the same numbers, always available
    const tb = document.getElementById('table-' + key);
    tb.innerHTML =
      '<table><thead><tr><th></th>' +
      [...boards].map(b => `<th class="num">${b}</th>`).join('') +
      '<th class="num">Total</th></tr></thead><tbody>' +
      rows.map(r =>
        `<tr><td>${r.label}</td>` +
        r.parts.map(p => `<td class="num">${fmt(p.v)}</td>`).join('') +
        `<td class="num">${fmt(r.total)}</td></tr>`
      ).join('') +
      '</tbody></table>';
  }

  // ---- listings per year ----
  // Six categorical slots, validated for line use. Colour follows the label,
  // never its rank, so changing the board filter never repaints a series.
  const LINE_HUES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#4a3aa7'];
  let split = 'none';

  function drawLines() {
    const L = D.lines;
    const sel = [...boards];
    const series = L[split].map((s, i) => ({
      label: s.label,
      colour: split === 'none' ? '#2a78d6' : LINE_HUES[i % LINE_HUES.length],
      vals: L.years.map((_, yi) => sel.reduce((t, b) => t + s.byBoard[b][yi], 0)),
    }));

    const W = 820, H = 300, ml = 34, mr = 74, mt = 12, mb = 26;
    const iw = W - ml - mr, ih = H - mt - mb;
    const maxV = Math.max(4, ...series.flatMap(s => s.vals));
    const step = maxV > 60 ? 20 : maxV > 30 ? 10 : 5;
    const top = Math.ceil(maxV / step) * step;

    const x = i => ml + (i / (L.years.length - 1)) * iw;
    const y = v => mt + ih - (v / top) * ih;

    let g = '';
    for (let v = 0; v <= top; v += step) {
      g += `<line class="grid" x1="${ml}" x2="${ml + iw}" y1="${y(v)}" y2="${y(v)}"/>` +
           `<text class="axis-txt" x="${ml - 8}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
    }
    L.years.forEach((yr, i) => {
      if (yr % 5 === 0 || i === L.years.length - 1)
        g += `<text class="axis-txt" x="${x(i)}" y="${H - 6}" text-anchor="middle">${yr}</text>`;
    });

    // the final year is a part-year — the file stops at 30 June
    const px = x(L.years.length - 1);
    g += `<line class="partial" x1="${px}" x2="${px}" y1="${mt}" y2="${mt + ih}"/>`;

    // End labels: nudge apart so they never overlap. The dot stays on the
    // true value; only the text moves, so the data is never misplaced.
    const GAP = 13;
    const ends = series
      .map((s, i) => ({ i, yTrue: y(s.vals[s.vals.length - 1]), yLab: 0 }))
      .sort((a, b) => a.yTrue - b.yTrue);
    ends.forEach((e, k) => {
      const want = e.yTrue + 4;   // +4 puts the baseline level with the dot
      e.yLab = k === 0 ? want : Math.max(want, ends[k - 1].yLab + GAP);
    });
    // if pushing down overflowed the plot, pull the whole stack back up
    const over = ends.length ? ends[ends.length - 1].yLab - (mt + ih) : 0;
    if (over > 0) ends.forEach(e => (e.yLab -= over));
    const labY = {};
    ends.forEach(e => (labY[e.i] = e.yLab));

    const paths = series.map((s, si) => {
      const d = s.vals.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
      const li = s.vals.length - 1;
      const yv = y(s.vals[li]);
      const ly = labY[si];
      // a hairline connects the dot to its label when the label has moved
      const leader = Math.abs(ly - yv) > 2
        ? `<line x1="${x(li) + 5}" y1="${yv}" x2="${x(li) + 8}" y2="${ly - 4}"
             stroke="${s.colour}" stroke-width="1" opacity=".5"/>` : '';
      return `<path class="ser" d="${d}" stroke="${s.colour}"/>` +
             `<circle class="dot" cx="${x(li)}" cy="${yv}" r="4" fill="${s.colour}"/>` +
             leader +
             `<text class="endlab" x="${x(li) + 9}" y="${ly}" fill="${s.colour}">${s.label}</text>`;
    }).join('');

    const hit = L.years.map((yr, i) =>
      `<rect class="hit" x="${x(i) - iw / (L.years.length - 1) / 2}" y="${mt}"
         width="${iw / (L.years.length - 1)}" height="${ih}" data-i="${i}"/>`).join('');

    const host = document.getElementById('chart-lines');
    host.innerHTML =
      `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
         ${g}<g id="crosshair"></g>${paths}${hit}</svg>`;

    host.querySelectorAll('.hit').forEach(r => {
      r.addEventListener('mousemove', e => {
        const i = +r.dataset.i;
        document.getElementById('crosshair').innerHTML =
          `<line class="cross" x1="${x(i)}" x2="${x(i)}" y1="${mt}" y2="${mt + ih}"/>`;
        const rows = series
          .filter(s => s.vals[i] > 0)
          .map(s => `<span class="k">${s.label}</span> ${s.vals[i]}`)
          .join('<br>') || '<span class="k">none</span>';
        showTip(e, `<b>${L.years[i]}</b>${L.years[i] === L.partial ? ' <span class="k">(part-year)</span>' : ''}<br>${rows}`);
      });
      r.addEventListener('mouseleave', () => {
        document.getElementById('crosshair').innerHTML = '';
        hideTip();
      });
    });

    document.getElementById('line-legend').innerHTML =
      split === 'none' ? '' :
      series.map(s => `<span><i style="background:${s.colour}"></i>${s.label}</span>`).join('');

    document.getElementById('table-lines').innerHTML =
      '<table><thead><tr><th>Year</th>' +
      series.map(s => `<th class="num">${s.label}</th>`).join('') +
      '</tr></thead><tbody>' +
      L.years.map((yr, i) =>
        `<tr><td>${yr}${yr === L.partial ? ' *' : ''}</td>` +
        series.map(s => `<td class="num">${s.vals[i]}</td>`).join('') + '</tr>'
      ).join('') + '</tbody></table>';
  }

  document.querySelectorAll('.tsx [data-split]').forEach(btn => {
    btn.addEventListener('click', () => {
      split = btn.dataset.split;
      document.querySelectorAll('.tsx [data-split]').forEach(b =>
        b.setAttribute('aria-pressed', b.dataset.split === split));
      drawLines();
    });
  });

  // ---- returns since listing ----
  // Median is used, not mean: a handful of 20x survivors would drag a mean
  // upward and hide what happens to the typical company.
  let retMode = 'median';

  function drawReturns() {
    const R = D.returns;
    if (!R) return;
    const sel = [...boards];
    const spread = retMode === 'spread';
    const series = sel.map(b => ({
      board: b,
      vals: R.boards[b][spread ? 'median' : retMode],
      lo: R.boards[b].p25,
      hi: R.boards[b].p75,
      n: R.boards[b].n,
    }));

    const W = 820, H = 320, ml = 44, mr = 62, mt = 14, mb = 44;
    const iw = W - ml - mr, ih = H - mt - mb;
    const flat = series.flatMap(s => spread ? [...s.vals, ...s.lo, ...s.hi] : s.vals)
                       .filter(v => v !== null);
    if (!flat.length) return;

    // domain always includes zero — the whole point is which side of it we're on
    let lo = Math.min(0, ...flat), hi = Math.max(0, ...flat);
    const step = 20;
    lo = Math.floor(lo / step) * step;
    hi = Math.ceil(hi / step) * step;

    const x = i => ml + (i / (R.labels.length - 1)) * iw;
    const y = v => mt + ih - ((v - lo) / (hi - lo)) * ih;

    let g = '';
    for (let v = lo; v <= hi; v += step) {
      const zero = v === 0;
      g += `<line class="grid" x1="${ml}" x2="${ml + iw}" y1="${y(v)}" y2="${y(v)}"
              ${zero ? 'stroke="#9a9a9a"' : ''}/>` +
           `<text class="axis-txt" x="${ml - 8}" y="${y(v) + 4}" text-anchor="end">${v}%</text>`;
    }
    R.labels.forEach((lab, i) => {
      g += `<text class="axis-txt" x="${x(i)}" y="${H - 24}" text-anchor="middle">${lab}</text>`;
      // sample size under each tick — it falls from ~600 to ~170 across the
      // grid, and every later point is a smaller, more selected group
      const n = series.reduce((t, s) => t + (s.n[i] || 0), 0);
      g += `<text class="axis-txt" x="${x(i)}" y="${H - 9}" text-anchor="middle"
              style="font-size:10px;opacity:.7">${n}</text>`;
    });

    // interquartile band, under the medians as a 12% wash — the spread is the
    // finding here, so it has to read as area rather than as more lines
    const bands = !spread ? '' : series.map(s => {
      const idx = s.lo.map((v, i) => i).filter(i => s.lo[i] !== null && s.hi[i] !== null);
      if (idx.length < 2) return '';
      const top = idx.map((i, k) => (k ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(s.hi[i]).toFixed(1)).join(' ');
      const bot = idx.slice().reverse().map(i => 'L' + x(i).toFixed(1) + ' ' + y(s.lo[i]).toFixed(1)).join(' ');
      return '<path d="' + top + ' ' + bot + ' Z" fill="var(--series-' + s.board + ')" opacity=".12"/>';
    }).join('');

    const paths = series.map(s => {
      const pts = s.vals.map((v, i) => [i, v]).filter(([, v]) => v !== null);
      if (!pts.length) return '';
      const d = pts.map(([i, v], k) => `${k ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
      const [li, lv] = pts[pts.length - 1];
      return `<path class="ser" d="${d}" stroke="var(--series-${s.board})"/>` +
             `<circle class="dot" cx="${x(li)}" cy="${y(lv)}" r="4" fill="var(--series-${s.board})"/>` +
             `<text class="endlab" x="${x(li) + 9}" y="${y(lv) + 4}"
                fill="var(--series-${s.board})">${s.board}</text>`;
    }).join('');

    const hit = R.labels.map((_, i) =>
      `<rect class="hit" x="${x(i) - iw / (R.labels.length - 1) / 2}" y="${mt}"
         width="${iw / (R.labels.length - 1)}" height="${ih}" data-i="${i}"/>`).join('');

    const host = document.getElementById('chart-returns');
    host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
        ${g}${bands}<g id="ret-cross"></g>${paths}${hit}</svg>`;

    host.querySelectorAll('.hit').forEach(r => {
      r.addEventListener('mousemove', e => {
        const i = +r.dataset.i;
        document.getElementById('ret-cross').innerHTML =
          `<line class="cross" x1="${x(i)}" x2="${x(i)}" y1="${mt}" y2="${mt + ih}"/>`;
        const rows = series.filter(s => s.vals[i] !== null).map(s =>
          spread
            ? `<span class="k">${s.board}</span> median ${s.vals[i]}%` +
              `<br><span class="k">middle half ${s.lo[i]}% to ${s.hi[i]}% · n=${s.n[i]}</span>`
            : `<span class="k">${s.board}</span> ${s.vals[i]}%` +
              ` <span class="k">(n=${s.n[i]})</span>`).join('<br>');
        showTip(e, `<b>${R.labels[i]} after listing</b><br>${rows || '<span class="k">too few companies</span>'}`);
      });
      r.addEventListener('mouseleave', () => {
        document.getElementById('ret-cross').innerHTML = '';
        hideTip();
      });
    });

    document.getElementById('table-returns').innerHTML =
      '<table><thead><tr><th>After listing</th>' +
      series.flatMap(s => spread
        ? [`<th class="num">${s.board} p25</th>`, `<th class="num">${s.board} median</th>`,
           `<th class="num">${s.board} p75</th>`, `<th class="num">n</th>`]
        : [`<th class="num">${s.board}</th>`, `<th class="num">n</th>`]).join('') +
      '</tr></thead><tbody>' +
      R.labels.map((lab, i) =>
        `<tr><td>${lab}</td>` +
        series.flatMap(s => spread
          ? [`<td class="num">${s.lo[i] === null ? '' : s.lo[i] + '%'}</td>`,
             `<td class="num">${s.vals[i] === null ? '' : s.vals[i] + '%'}</td>`,
             `<td class="num">${s.hi[i] === null ? '' : s.hi[i] + '%'}</td>`,
             `<td class="num">${s.n[i]}</td>`]
          : [`<td class="num">${s.vals[i] === null ? '' : s.vals[i] + '%'}</td>`,
             `<td class="num">${s.n[i]}</td>`]).join('') + '</tr>'
      ).join('') + '</tbody></table>';
  }

  document.querySelectorAll('.tsx [data-ret]').forEach(btn => {
    btn.addEventListener('click', () => {
      retMode = btn.dataset.ret;
      document.querySelectorAll('.tsx [data-ret]').forEach(b =>
        b.setAttribute('aria-pressed', b.dataset.ret === retMode));
      drawReturns();
    });
  });

  // ---- heatmap: domicile country x operating country ----
  function drawGeo() {
    const G = D.geo;
    if (!G) return;
    const sel = [...boards];
    const val = c => sel.reduce((t, b) => t + c[b], 0);
    const max = Math.max(...G.cells.flatMap(r => r.map(val)));

    const colour = v => {
      if (!v) return null;
      const i = Math.min(RAMP.length - 1, Math.floor((v / max) ** 0.5 * RAMP.length));
      return RAMP[i];
    };

    const head = '<tr><th></th>' + G.op.map(o => `<th>${o}</th>`).join('') + '</tr>';
    const body = G.hq.map((h, ri) =>
      `<tr><th>${h}</th>` +
      G.cells[ri].map((cell, ci) => {
        const v = val(cell);
        const o = G.op[ci];
        // a company operating in its own country of domicile
        const home = h === o && h !== 'Other';
        if (!v) return `<td class="z${home ? ' home' : ''}">·</td>`;
        const ink = v / max > 0.45 ? '#fff' : 'var(--ink)';
        return `<td class="${home ? 'home' : ''}" style="background:${colour(v)};color:${ink}"
                  data-h="${h}" data-o="${o}" data-v="${v}">${v}</td>`;
      }).join('') + '</tr>').join('');

    const host = document.getElementById('chart-geo');
    host.innerHTML = `<table><thead>${head}</thead><tbody>${body}</tbody></table>`;
    host.querySelectorAll('td[data-v]').forEach(td => {
      td.addEventListener('mousemove', e =>
        showTip(e, `<b>${td.dataset.h}</b> companies operating in <b>${td.dataset.o}</b>` +
                   `<br><span class="k">${td.dataset.v} companies</span>`));
      td.addEventListener('mouseleave', hideTip);
    });
  }

  // ---- heatmap: commodity x region, company counts ----
  const RAMP = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#104281'];

  function drawHeat() {
    const H = D.heat;
    const sel = [...boards];
    const val = c => sel.reduce((s, b) => s + c[b], 0);
    const max = Math.max(...H.cells.flatMap(row => row.map(val)));

    const colour = v => {
      if (!v) return null;
      const i = Math.min(RAMP.length - 1, Math.floor((v / max) ** 0.5 * RAMP.length));
      return RAMP[i];
    };

    const head =
      '<tr><th></th>' +
      H.commodities.map(c => `<th>${c.replace('/', '/<wbr>')}</th>`).join('') +
      '</tr>';

    const body = H.regions.map((r, ri) =>
      `<tr><th>${r}</th>` +
      H.cells[ri].map((cell, ci) => {
        const v = val(cell);
        const bg = colour(v);
        // ink flips to white on the darker half of the ramp
        const ink = v / max > 0.45 ? '#fff' : 'var(--ink)';
        return v
          ? `<td style="background:${bg};color:${ink}" data-r="${r}"
                 data-c="${H.commodities[ci]}" data-v="${v}">${v}</td>`
          : `<td class="z">·</td>`;
      }).join('') +
      '</tr>'
    ).join('');

    const host = document.getElementById('chart-heat');
    host.innerHTML = `<table><thead>${head}</thead><tbody>${body}</tbody></table>`;
    host.querySelectorAll('td[data-v]').forEach(td => {
      td.addEventListener('mousemove', e =>
        showTip(e, `<b>${td.dataset.c}</b> in <b>${td.dataset.r}</b><br>` +
                   `<span class="k">${td.dataset.v} companies</span>`));
      td.addEventListener('mouseleave', hideTip);
    });
  }

  // ---- producing share by commodity ----
  // One series, so no CVD pair to worry about, but every bar carries its own
  // number and the table view is there — the relief the contrast check wants.
  function drawProdShare() {
    const host = document.getElementById('chart-prodshare');
    if (!host || !D.prodshare) return;
    const sel = [...boards];
    const MIN = 15;

    const rows = D.prodshare
      .map(r => {
        const prod = sel.reduce((s, b) => s + r[b].prod, 0);
        const tot = sel.reduce((s, b) => s + r[b].tot, 0);
        return { label: r.label, prod, tot, share: tot ? prod / tot : 0 };
      })
      // filtered AFTER the board filter: TSXV-only can thin a commodity out
      .filter(r => r.tot >= MIN)
      .sort((a, b) => b.share - a.share);

    const max = Math.max(...rows.map(r => r.share), 0.01);

    host.innerHTML = rows
      .map(r => {
        const w = Math.max((r.share / max) * 100, r.share > 0 ? 0.4 : 0);
        return `<div class="row"><div class="cat">${r.label}</div>
                <div class="track"><div class="bar"><div class="seg-fill"
                  style="width:${w}%;background:var(--series-stage)"
                  data-label="${r.label}" data-prod="${r.prod}"
                  data-tot="${r.tot}"></div></div></div>
                <div class="val">${Math.round(r.share * 100)}%</div></div>`;
      })
      .join('');

    host.querySelectorAll('.seg-fill').forEach(el => {
      el.addEventListener('mousemove', e =>
        showTip(e, `<b>${el.dataset.label}</b><br>` +
          `${el.dataset.prod} producing of ${el.dataset.tot}`));
      el.addEventListener('mouseleave', hideTip);
    });

    document.getElementById('table-prodshare').innerHTML =
      '<table><thead><tr><th></th><th class="num">Producing</th>' +
      '<th class="num">Companies</th><th class="num">Share</th></tr></thead><tbody>' +
      rows.map(r =>
        `<tr><td>${r.label}</td><td class="num">${r.prod}</td>` +
        `<td class="num">${r.tot}</td>` +
        `<td class="num">${Math.round(r.share * 100)}%</td></tr>`).join('') +
      '</tbody></table>';
  }

  function drawAll() {
    // scoped to the live chart: the static charts in the written tabs
    // carry their own legend and must not be filtered
    document.querySelectorAll('.viz-live .legend span').forEach(s => {
      s.style.display = boards.has(s.dataset.board) ? '' : 'none';
    });
    const noteText =
      measure === 'turnover'
        ? 'Share of the companies\u2019 value that changed hands in the six months to 30 June \u2014 dollars traded \u00f7 market cap. Puts a C$3M shell and a C$100B producer on the same footing. Boards sit side by side; a ratio of the parts is not the ratio for the whole.'
        : measure === 'median'
        ? 'The middle company in each group, not the total \u2014 shows whether a commodity is a few big miners or a swarm of small ones. Boards sit side by side; a median of the parts is not the median for the whole.'
        : '';
    document.querySelectorAll('.measure-note').forEach(n => { n.textContent = noteText; });
    draw('commodity');
    draw('region');
    if (D.stage_series) draw('stage_series');
    if (D.npsize) draw('npsize');
    drawProdShare();
    drawHeat();
    drawGeo();
    drawLines();
    drawReturns();
  }

  document.querySelectorAll('.tsx [data-board]').forEach(btn => {
    if (btn.tagName !== 'BUTTON') return;
    btn.addEventListener('click', () => {
      const b = btn.dataset.board;
      if (boards.has(b)) {
        if (boards.size === 1) return;   // never allow zero boards
        boards.delete(b);
      } else {
        boards.add(b);
      }
      btn.setAttribute('aria-pressed', boards.has(b));
      drawAll();
    });
  });

  document.querySelectorAll('.tsx [data-measure]').forEach(btn => {
    btn.addEventListener('click', () => {
      measure = btn.dataset.measure;
      document.querySelectorAll('.tsx [data-measure]').forEach(b =>
        b.setAttribute('aria-pressed', b.dataset.measure === measure));
      drawAll();
    });
  });

  drawAll();
})();
"""


GEO_BLOCK = """
<div class="chart">
  <h3>Where companies are based vs where they mine</h3>
  <p class="note">Rows are country of head office, columns are country of the
  company's properties. A company with ground in three countries appears in three
  cells, so the grid sums to more than {companies} companies. Outlined cells are
  the diagonal — operating in the country you are based in.
  <strong>{abroad} companies hold no property in their own country of domicile.</strong></p>
  <div class="heat" id="chart-geo"></div>
  <div class="scale">
    <span>fewer</span>
    <i style="background:#cde2fb"></i><i style="background:#9ec5f4"></i><i style="background:#6da7ec"></i><i style="background:#3987e5"></i><i style="background:#256abf"></i><i style="background:#104281"></i>
    <span>more companies</span>
  </div>
</div>
"""

RETURNS_BLOCK = """
<div class="chart">
  <h3>What happens after listing</h3>
  <p class="note">Median share-price return at each point in a company's own life,
  measured against the average of its first five trading days. Based on
  {usable} of {total} companies — {no_listing_date} have no listing date to anchor
  to and {no_history} have no price history reaching back that far.
  <strong>These are survivors only</strong>: companies that failed outright are
  absent from the source file, so the real picture is worse than this. Each point
  is also a different subset — only companies old enough to reach it — and the
  count under each label shows how quickly that thins out. <strong>Spread</strong> shades the middle half of companies, 25th to 75th percentile — the median alone hides how wide this gets.</p>
  <div class="ctrl-group" style="margin:0 0 14px">
    <span class="ctrl-label">Show</span>
    <div class="seg">
      <button data-ret="median" aria-pressed="true">Median return</button>
      <button data-ret="spread" aria-pressed="false">Spread</button>
      <button data-ret="neg" aria-pressed="false">% underwater</button>
    </div>
  </div>
  <div class="linewrap" id="chart-returns"></div>
  <details class="tbl"><summary>Show as table</summary><div id="table-returns"></div></details>
</div>
"""


def section_html():
    data = build_data()
    g = data["gaps"]
    L = data["lines"]
    R = data["returns"]
    returns_block = RETURNS_BLOCK.format(**R) if R else ""
    G = data["geo"]
    geo_block = GEO_BLOCK.format(**G) if G else ""

    return f"""
<div class="viz-root viz-live tsx">

<div class="ctrls">
  <div class="ctrl-group">
    <span class="ctrl-label">Board</span>
    <div class="seg">
      <button data-board="TSX" aria-pressed="true"><i class="dot"></i>TSX</button>
      <button data-board="TSXV" aria-pressed="true"><i class="dot"></i>TSXV</button>
    </div>
  </div>
</div>

<div class="chart">
  <h3>Commodity</h3>
  <p class="note">Companies hold more than one commodity, so the bars sum to more
  than the sector total. {g['no_commodity']} companies disclose no commodity and
  appear in none of these bars.</p>
  <div class="ctrl-group" style="margin:0 0 6px">
    <span class="ctrl-label">Measure</span>
    <div class="seg">
      <button data-measure="n" aria-pressed="true">Companies</button>
      <button data-measure="mcap" aria-pressed="false">Market cap</button>
      <button data-measure="median" aria-pressed="false">Typical size</button>
      <button data-measure="turnover" aria-pressed="false">% traded</button>
    </div>
  </div>
  <p class="note measure-note" style="margin:0 0 12px"></p>
  <div class="legend">
    <span data-board="TSX"><i style="background:var(--series-TSX)"></i>TSX</span>
    <span data-board="TSXV"><i style="background:var(--series-TSXV)"></i>TSXV</span>
  </div>
  <div class="rows" id="chart-commodity"></div>
  <details class="tbl"><summary>Show as table</summary><div id="table-commodity"></div></details>
</div>

<div class="chart">
  <h3>Where the assets are</h3>
  <p class="note">Region of the company's properties, not its head office. Companies
  with ground in several regions appear in each. {g['no_property']} companies
  disclose no property location.</p>
  <div class="ctrl-group" style="margin:0 0 6px">
    <span class="ctrl-label">Measure</span>
    <div class="seg">
      <button data-measure="n" aria-pressed="true">Companies</button>
      <button data-measure="mcap" aria-pressed="false">Market cap</button>
      <button data-measure="median" aria-pressed="false">Typical size</button>
      <button data-measure="turnover" aria-pressed="false">% traded</button>
    </div>
  </div>
  <p class="note measure-note" style="margin:0 0 12px"></p>
  <div class="legend">
    <span data-board="TSX"><i style="background:var(--series-TSX)"></i>TSX</span>
    <span data-board="TSXV"><i style="background:var(--series-TSXV)"></i>TSXV</span>
  </div>
  <div class="rows" id="chart-region"></div>
  <details class="tbl"><summary>Show as table</summary><div id="table-region"></div></details>
</div>


<div class="chart">
  <h3>By stage</h3>
  <p class="note">Producer means the company reported revenue; everything else
  without revenue is an explorer. Switch the measure to <strong>% traded</strong>
  for the question the counts can't answer — whether explorer trading is genuinely
  thinner, or only looks that way because the companies are smaller.</p>
  <div class="ctrl-group" style="margin:0 0 6px">
    <span class="ctrl-label">Measure</span>
    <div class="seg">
      <button data-measure="n" aria-pressed="true">Companies</button>
      <button data-measure="mcap" aria-pressed="false">Market cap</button>
      <button data-measure="median" aria-pressed="false">Typical size</button>
      <button data-measure="turnover" aria-pressed="false">% traded</button>
    </div>
  </div>
  <p class="note measure-note" style="margin:0 0 12px"></p>
  <div class="legend">
    <span data-board="TSX"><i style="background:var(--series-TSX)"></i>TSX</span>
    <span data-board="TSXV"><i style="background:var(--series-TSXV)"></i>TSXV</span>
  </div>
  <div class="rows" id="chart-stage_series"></div>
  <details class="tbl"><summary>Show as table</summary><div id="table-stage_series"></div></details>
</div>

<div class="chart">
  <h3>Size of the non-producers</h3>
  <p class="note">Market cap of the companies that are not selling anything —
  explorers, shells and the five with no data. Royalty companies are excluded;
  they earn without operating. This is the honest substitute for a developer
  bucket: the free data will not say who has a feasibility study, but the top
  band is where the advanced projects are and the bottom band is where they
  are not.</p>
  <div class="ctrl-group" style="margin:0 0 6px">
    <span class="ctrl-label">Measure</span>
    <div class="seg">
      <button data-measure="n" aria-pressed="true">Companies</button>
      <button data-measure="mcap" aria-pressed="false">Market cap</button>
      <button data-measure="median" aria-pressed="false">Typical size</button>
      <button data-measure="turnover" aria-pressed="false">% traded</button>
    </div>
  </div>
  <p class="note measure-note" style="margin:0 0 12px"></p>
  <div class="legend">
    <span data-board="TSX"><i style="background:var(--series-TSX)"></i>TSX</span>
    <span data-board="TSXV"><i style="background:var(--series-TSXV)"></i>TSXV</span>
  </div>
  <div class="rows" id="chart-npsize"></div>
  <details class="tbl"><summary>Show as table</summary><div id="table-npsize"></div></details>
</div>

<div class="chart">
  <h3>How much of each commodity actually produces</h3>
  <p class="note">Producing companies as a share of the companies holding that
  commodity. Commodities with fewer than 15 companies on the selected boards are
  dropped, since a share of six is not a rate. Companies holding several
  commodities count in each, so this reads down the column, not across.</p>
  <div class="legend">
    <span><i style="background:var(--series-stage)"></i>Share producing</span>
  </div>
  <div class="rows" id="chart-prodshare"></div>
  <details class="tbl"><summary>Show as table</summary><div id="table-prodshare"></div></details>
</div>

<div class="chart">
  <h3>Companies by listing year</h3>
  <p class="note">Companies that listed in each year <strong>and are still listed
  today</strong>. Failed and delisted companies are absent from the source file
  entirely, so early years are undercounted and part of the upward slope is
  survivorship rather than growth. {L['before']} surviving companies listed before 2000
  and are not shown; {L['missing']} TSXV companies have no listing date at all.
  {L['partial']} is a part-year — the data stops at 30 June.</p>
  <div class="ctrl-group" style="margin:0 0 14px">
    <span class="ctrl-label">Split by</span>
    <div class="seg">
      <button data-split="none" aria-pressed="true">Total</button>
      <button data-split="commodity" aria-pressed="false">Commodity</button>
      <button data-split="region" aria-pressed="false">Region</button>
    </div>
  </div>
  <div class="legend" id="line-legend"></div>
  <div class="linewrap" id="chart-lines"></div>
  <details class="tbl"><summary>Show as table</summary><div id="table-lines"></div></details>
</div>

{returns_block}

{geo_block}

<div class="chart">
  <h3>Commodity by region</h3>
  <p class="note">Number of companies holding each commodity in each region. Follows
  the board filter; company counts only, since a median or ratio on cells this small
  would be noise. A company with two commodities in two regions appears in four cells.</p>
  <div class="heat" id="chart-heat"></div>
  <div class="scale">
    <span>fewer</span>
    <i style="background:#cde2fb"></i><i style="background:#9ec5f4"></i><i style="background:#6da7ec"></i><i style="background:#3987e5"></i><i style="background:#256abf"></i><i style="background:#104281"></i>
    <span>more companies</span>
  </div>
</div>

</div>

<script>window.__VIZ__ = {json.dumps(data)};</script>
<script>{JS}</script>
"""
