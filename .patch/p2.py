# -*- coding: utf-8 -*-
import io, sys

p = sys.argv[1]
s = io.open(p, encoding="utf-8").read()


def sub(a, b):
    global s
    assert a in s, "NOT FOUND: " + a[:70]
    s = s.replace(a, b, 1)


MEASURE = """  <div class="ctrl-group" style="margin:0 0 6px">
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
  </div>"""

BLOCKS = """
<div class="chart">
  <h3>By stage</h3>
  <p class="note">Producer means the company reported revenue; everything else
  without revenue is an explorer. Switch the measure to <strong>% traded</strong>
  for the question the counts can't answer — whether explorer trading is genuinely
  thinner, or only looks that way because the companies are smaller.</p>
""" + MEASURE + """
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
""" + MEASURE + """
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
"""

# placed after the two population cuts they belong with, before the time series
sub(
    """<div class="chart">
  <h3>Companies by listing year</h3>""",
    BLOCKS + """
<div class="chart">
  <h3>Companies by listing year</h3>""",
)

io.open(p, "w", encoding="utf-8").write(s)
print("patched charts.py (blocks)")
