"""
Render the notes markdown into a single self-contained HTML document.

Input:  notes/stage1-dataset.md
        notes/stage1-numbers.md
        notes/stage2.md
Output: outputs/report.html

The markdown files stay the source of truth — edit those, re-run this.
Requires: pip install markdown
"""

import re
import sys
from pathlib import Path

import markdown

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asx_charts
import charts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "notes"
OUT = ROOT / "outputs" / "report.html"

TITLE = "Listed Mining"

# Two markets, each with its own tabs. They are not merged into one set of
# charts: the TMX export carries commodity, geography and trading data that the
# ASX export simply does not have, so a shared view would be mostly blank
# columns pretending to be a comparison.
MARKETS = [
    ("tsx", "TSX / TSXV"),
    ("asx", "ASX"),
]

# (tab label, filename). Order defines tab order.
# A filename of None means the tab is generated, not read from markdown.
TABS = {
    "tsx": [
        ("Stage 1 · Dataset", "stage1-dataset.md"),
        ("Stage 1 · Numbers", "stage1-numbers.md"),
        ("Stage 1 · Charts", None),
        ("Stage 2", "stage2.md"),
    ],
    "asx": [
        ("Dataset", "asx-dataset.md"),
        ("Numbers", "asx-numbers.md"),
        ("Charts", None),
    ],
}

CSS = """
*, *::before, *::after { box-sizing: border-box; }

:root {
  --bg: #ffffff;
  --panel: #fafafa;
  --ink: #1a1a1a;
  --ink-soft: #5c5c5c;
  --ink-faint: #8a8a8a;
  --line: #e4e4e4;
  --line-soft: #f0f0f0;
  --accent: #1a1a1a;
  --max: 820px;
}

html { -webkit-text-size-adjust: 100%; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 16px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Inter,
        Helvetica, Arial, sans-serif;
  font-feature-settings: "kern", "liga", "tnum";
}

/* ---- header ---- */
header {
  border-bottom: 1px solid var(--line);
  padding: 32px 24px 0;
}
.head-inner { max-width: var(--max); margin: 0 auto; }
h1.site {
  margin: 0 0 18px;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

/* ---- tabs ---- */
nav { display: flex; gap: 4px; }
nav button {
  appearance: none;
  border: 0;
  background: none;
  font: inherit;
  font-size: 14px;
  color: var(--ink-soft);
  padding: 9px 14px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: color .12s;
}
nav button:hover { color: var(--ink); }
nav button[aria-selected="true"] {
  color: var(--ink);
  font-weight: 550;
  border-bottom-color: var(--accent);
}
nav button:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }

/* ---- content ---- */
main { max-width: var(--max); margin: 0 auto; padding: 8px 24px 96px; }
section[hidden] { display: none; }

/* each note's own H1 duplicates its tab label — the tab carries it */
main h1 { display: none; }

h2 {
  font-size: 21px;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin: 44px 0 12px;
  padding-top: 20px;
  border-top: 1px solid var(--line-soft);
}
main > section > h1 + h2,
main > section > h1 + p + h2 { border-top: 0; padding-top: 0; margin-top: 8px; }
main > section > h1 + p { margin-top: 24px; }
h3 { font-size: 15px; font-weight: 600; margin: 26px 0 8px; }

p { margin: 12px 0; }
em { color: var(--ink-faint); font-style: normal; font-size: 13px; }

/* the bold lead line under each h2 — the takeaway */
h2 + p > strong:only-child {
  display: block;
  font-weight: 500;
  font-size: 17px;
  line-height: 1.5;
  color: var(--ink);
  border-left: 2px solid var(--accent);
  padding: 2px 0 2px 14px;
  margin: 2px 0 6px;
}

ul, ol { margin: 12px 0; padding-left: 22px; }
li { margin: 5px 0; }

code {
  font: 13px/1.4 ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
  background: var(--panel);
}

.head-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
}
.seg.market { display: flex; gap: 4px; }
.seg.market button {
  appearance: none;
  font: inherit;
  font-size: 13px;
  padding: 5px 14px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink-soft);
  border-radius: 5px;
  cursor: pointer;
}
.seg.market button:hover { border-color: #c9c9c9; color: var(--ink); }
.seg.market button[aria-pressed="true"] {
  color: var(--ink);
  border-color: #b0b0b0;
  font-weight: 550;
  border: 1px solid var(--line-soft);
  border-radius: 3px;
  padding: 1px 5px;
}

/* ---- tables ---- */
.tw { overflow-x: auto; margin: 18px 0; }
table {
  border-collapse: collapse;
  width: 100%;
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}
th, td {
  text-align: left;
  padding: 8px 14px 8px 0;
  border-bottom: 1px solid var(--line-soft);
  white-space: nowrap;
}
th {
  font-weight: 550;
  font-size: 12px;
  letter-spacing: .04em;
  text-transform: uppercase;
  color: var(--ink-faint);
  border-bottom: 1px solid var(--line);
}
td:first-child, th:first-child { white-space: normal; }
/* numeric columns right-align; set per column by the build script */
th.num, td.num { text-align: right; padding-right: 0; padding-left: 14px; }
tbody tr:last-child td { border-bottom: 0; }

a { color: var(--ink); text-decoration: underline; text-decoration-color: #c2c2c2;
    text-underline-offset: 2px; }
a:hover { text-decoration-color: var(--ink); }
td a, th a { white-space: nowrap; }

hr { border: 0; border-top: 1px solid var(--line); margin: 40px 0; }

footer {
  max-width: var(--max);
  margin: 0 auto;
  padding: 0 24px 40px;
  font-size: 12px;
  color: var(--ink-faint);
}

@media (max-width: 640px) {
  main { padding: 8px 16px 64px; }
  header { padding: 24px 16px 0; }
  nav { overflow-x: auto; }
  h2 { font-size: 19px; }
}

@media print {
  nav, footer { display: none; }
  section[hidden] { display: block !important; }
  h2 { page-break-after: avoid; }
  .tw, table { page-break-inside: avoid; }
}
"""

JS = """
const tabs = [...document.querySelectorAll('nav button')];
// Market first, then tab. Switching market swaps which tab bar is live and
// lands on that market's first tab — carrying the tab index across would point
// at a tab the other market does not have.
let market = document.querySelector('.seg.market button').dataset.market;

function showMarket(m) {
  market = m;
  document.querySelectorAll('.seg.market button').forEach(b =>
    b.setAttribute('aria-pressed', b.dataset.market === m));
  document.querySelectorAll('[data-market]').forEach(el => {
    if (el.tagName === 'BUTTON' && el.closest('.seg.market')) return;
    el.hidden = el.dataset.market !== m;
  });
  const first = [...document.querySelectorAll(`nav [data-market="${m}"]`)][0];
  if (first) first.click();
}

document.querySelectorAll('.seg.market button').forEach(btn =>
  btn.addEventListener('click', () => showMarket(btn.dataset.market)));

const panels = [...document.querySelectorAll('main section')];

function show(i, push) {
  tabs.forEach((t, n) => t.setAttribute('aria-selected', n === i));
  panels.forEach((p, n) => p.hidden = n !== i || p.dataset.market !== market);
  if (push) history.replaceState(null, '', '#' + panels[i].id);
  window.scrollTo(0, 0);
}

tabs.forEach((t, i) => {
  t.addEventListener('click', () => show(i, true));
  t.addEventListener('keydown', e => {
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const n = (i + d + tabs.length) % tabs.length;
    tabs[n].focus();
    show(n, true);
  });
});

const start = panels.findIndex(p => '#' + p.id === location.hash);
if (start > -1) {
  showMarket(panels[start].dataset.market);
  show(start, false);
} else {
  showMarket(market);
}

// Hover readout for the static charts embedded in the written tabs. They have
// no controls by design, but a stacked bar still needs to say which part is
// which — the legend gives the colour, this gives the number.
(function () {
  const seg = document.querySelectorAll('.viz-static .seg-fill');
  if (!seg.length) return;
  const tip = document.createElement('div');
  tip.className = 'tip';
  document.body.appendChild(tip);

  seg.forEach(el => {
    const label = el.closest('.row').querySelector('.cat').textContent;
    const place = e => {
      tip.innerHTML = '<b>' + label + '</b><br><span class="k">' +
                      (el.dataset.v || '') + '</span>';
      tip.style.opacity = 1;
      const r = tip.getBoundingClientRect();
      let x = e.clientX + 14;
      if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
      tip.style.left = x + 'px';
      tip.style.top = Math.min(e.clientY + 14, innerHeight - r.height - 8) + 'px';
    };
    el.addEventListener('mouseover', place);
    el.addEventListener('mousemove', place);
    el.addEventListener('mouseleave', () => { tip.style.opacity = 0; });
    // the native title tooltip would fight the styled one
    el.dataset.v = el.getAttribute('title');
    el.removeAttribute('title');
  });
})();
"""

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}
{vizcss}</style>
</head>
<body>

<header>
  <div class="head-inner">
    <div class="head-top">
      <h1 class="site">{title}</h1>
      <div class="seg market">{markets}</div>
    </div>
    <nav role="tablist">{tabs}</nav>
  </div>
</header>

<main>{panels}</main>

<footer>{footer}</footer>

<script>{js}</script>
</body>
</html>
"""


NUM_STRIP = str.maketrans("", "", "C$%,<>+~ \u2013\u2014")


def _is_numeric(cell):
    """True for '183', '8%', 'C$1,053.6B', '35 / 32', '0.319'."""
    txt = re.sub(r"<[^>]+>", "", cell).strip()
    if not txt:
        return True  # blanks don't decide a column
    core = txt.translate(NUM_STRIP).replace("B", "").replace("M", "")
    core = core.replace("/", "").strip()
    if not core:
        return True  # placeholders like "—" don't decide a column either
    return bool(re.fullmatch(r"[\d.]*", core)) and any(c.isdigit() for c in txt)


def align_tables(html):
    """Right-align only the columns whose body cells are numeric."""

    def fix(match):
        table = match.group(0)
        rows = re.findall(r"<tr>(.*?)</tr>", table, re.S)
        if not rows:
            return table

        body = [re.findall(r"<td[^>]*>(.*?)</td>", r, re.S) for r in rows]
        body = [cells for cells in body if cells]
        if not body:
            return table

        width = max(len(c) for c in body)
        numeric = [
            all(_is_numeric(cells[i]) for cells in body if i < len(cells))
            for i in range(width)
        ]

        def tag_row(row):
            i = [0]

            def tag(m):
                idx = i[0]
                i[0] += 1
                cls = ' class="num"' if idx < width and numeric[idx] else ""
                return f"<{m.group(1)}{cls}>{m.group(2)}</{m.group(1)}>"

            return re.sub(r"<(th|td)>(.*?)</\1>", tag, row, flags=re.S)

        return re.sub(r"<tr>(.*?)</tr>",
                      lambda m: "<tr>" + tag_row(m.group(1)) + "</tr>",
                      table, flags=re.S)

    return re.sub(r"<table>.*?</table>", fix, html, flags=re.S)


CHART_TOKEN = re.compile(r"<p>\{\{chart:([a-z_]+)\}\}</p>|\{\{chart:([a-z_]+)\}\}")


def embed_charts(html):
    """Swap {{chart:name}} in the markdown for a rendered static chart.

    Markdown wraps a lone token in <p>, so both forms are matched.
    """
    def repl(m):
        name = m.group(1) or m.group(2)
        try:
            if name.startswith("asx_"):
                return asx_charts.static_chart(name)
            return charts.static_chart(name)
        except KeyError:
            print(f"  WARNING: unknown chart token {{{{chart:{name}}}}}")
            return m.group(0)

    return CHART_TOKEN.sub(repl, html)


def slugify(name):
    return name.lower().replace(".md", "").replace("_", "-")


def render():
    md = markdown.Markdown(extensions=["tables", "attr_list", "sane_lists"])

    tabs_html, panels_html, markets_html = [], [], []
    flat = [(mk, label, filename)
            for mk, _ in MARKETS for label, filename in TABS[mk]]

    for mk, mlabel in MARKETS:
        markets_html.append(
            f'<button data-market="{mk}" '
            f'aria-pressed="{"true" if mk == MARKETS[0][0] else "false"}">'
            f'{mlabel}</button>')

    for i, (mk, label, filename) in enumerate(flat):
        if filename is None:
            body = charts.section_html() if mk == "tsx" else asx_charts.section_html()
            slug = "charts" if mk == "tsx" else "asx-charts"
        else:
            path = NOTES / filename
            if not path.exists():
                print(f"  WARNING: {filename} not found — tab skipped")
                continue

            md.reset()
            body = md.convert(path.read_text(encoding="utf-8"))
            body = align_tables(body)
            body = embed_charts(body)
            # Let wide tables scroll rather than break the layout.
            body = body.replace("<table>", '<div class="tw"><table>')
            body = body.replace("</table>", "</table></div>")
            slug = slugify(filename)
        selected = "true" if i == 0 else "false"
        tabs_html.append(
            f'<button role="tab" aria-selected="{selected}" '
            f'data-market="{mk}" '
            f'{"" if mk == MARKETS[0][0] else "hidden "}'
            f'aria-controls="{slug}">{label}</button>'
        )
        panels_html.append(
            f'<section id="{slug}" role="tabpanel" data-market="{mk}"'
            f'{"" if i == 0 else " hidden"}>{body}</section>'
        )

    sources = " · ".join(f for _, _, f in flat if f)
    footer = (
        f"Rendered from {sources} — edit the markdown and re-run "
        f"<code>src/build_report.py</code>. "
        f"TSX/TSXV size and trading as at 30 June 2026, commodity and property "
        f"as at 31 July 2026; ASX as at 26 August 2026. "
        f"Canadian and Australian dollars are never converted."
    )

    html = PAGE.format(
        title=TITLE,
        css=CSS,
        vizcss=charts.CSS,
        js=JS,
        markets="".join(markets_html),
        tabs="".join(tabs_html),
        panels="".join(panels_html),
        footer=footer,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    kb = len(html.encode()) / 1024
    print(f"{len(panels_html)} tabs -> {OUT.relative_to(ROOT)}  ({kb:.0f} KB)")


if __name__ == "__main__":
    render()
