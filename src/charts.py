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


def _series(df, flag_col, label):
    row = {"label": label}
    mask = df[flag_col].fillna(False)
    for board in BOARDS:
        row[board] = _stats(df[mask & (df["board"] == board)])
    row["ALL"] = _stats(df[mask])       # for non-additive measures on both boards
    return row


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


CSS = """
.viz-root {
  color-scheme: light;
  --surface-1: #ffffff;
  --series-TSX: #2a78d6;
  --series-TSXV: #eb6834;
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
      })
      .sort((a, b) => b.total - a.total);

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

  document.querySelectorAll('[data-split]').forEach(btn => {
    btn.addEventListener('click', () => {
      split = btn.dataset.split;
      document.querySelectorAll('[data-split]').forEach(b =>
        b.setAttribute('aria-pressed', b.dataset.split === split));
      drawLines();
    });
  });

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

  function drawAll() {
    document.querySelectorAll('.legend span').forEach(s => {
      s.style.display = boards.has(s.dataset.board) ? '' : 'none';
    });
    const note = document.getElementById('measure-note');
    note.textContent =
      measure === 'turnover'
        ? 'Share of the companies\u2019 value that changed hands in the six months to 30 June \u2014 dollars traded \u00f7 market cap. Puts a C$3M shell and a C$100B producer on the same footing. Boards sit side by side; a ratio of the parts is not the ratio for the whole.'
        : measure === 'median'
        ? 'The middle company in each group, not the total \u2014 shows whether a commodity is a few big miners or a swarm of small ones. Boards sit side by side; a median of the parts is not the median for the whole.'
        : '';
    draw('commodity');
    draw('region');
    drawHeat();
    drawLines();
  }

  document.querySelectorAll('[data-board]').forEach(btn => {
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

  document.querySelectorAll('[data-measure]').forEach(btn => {
    btn.addEventListener('click', () => {
      measure = btn.dataset.measure;
      document.querySelectorAll('[data-measure]').forEach(b =>
        b.setAttribute('aria-pressed', b.dataset.measure === measure));
      drawAll();
    });
  });

  drawAll();
})();
"""


def section_html():
    data = build_data()
    g = data["gaps"]
    L = data["lines"]

    return f"""
<div class="viz-root">

<div class="ctrls">
  <div class="ctrl-group">
    <span class="ctrl-label">Board</span>
    <div class="seg">
      <button data-board="TSX" aria-pressed="true"><i class="dot"></i>TSX</button>
      <button data-board="TSXV" aria-pressed="true"><i class="dot"></i>TSXV</button>
    </div>
  </div>
  <div class="ctrl-group">
    <span class="ctrl-label">Measure</span>
    <div class="seg">
      <button data-measure="n" aria-pressed="true">Companies</button>
      <button data-measure="mcap" aria-pressed="false">Market cap</button>
      <button data-measure="median" aria-pressed="false">Typical size</button>
      <button data-measure="turnover" aria-pressed="false">% traded</button>
    </div>
  </div>
</div>
<p class="note" id="measure-note" style="margin:-4px 0 0"></p>

<div class="chart">
  <h3>Commodity</h3>
  <p class="note">Companies hold more than one commodity, so the bars sum to more
  than the sector total. {g['no_commodity']} companies disclose no commodity and
  appear in none of these bars.</p>
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
  <div class="legend">
    <span data-board="TSX"><i style="background:var(--series-TSX)"></i>TSX</span>
    <span data-board="TSXV"><i style="background:var(--series-TSXV)"></i>TSXV</span>
  </div>
  <div class="rows" id="chart-region"></div>
  <details class="tbl"><summary>Show as table</summary><div id="table-region"></div></details>
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
