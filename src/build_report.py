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
import charts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "notes"
OUT = ROOT / "outputs" / "report.html"

TITLE = "TSX / TSXV Mining"

# (tab label, filename). Order defines tab order.
# A filename of None means the tab is generated, not read from markdown.
TABS = [
    ("Stage 1 · Dataset", "stage1-dataset.md"),
    ("Stage 1 · Numbers", "stage1-numbers.md"),
    ("Stage 1 · Charts", None),
    ("Stage 2", "stage2.md"),
]

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
const panels = [...document.querySelectorAll('main section')];

function show(i, push) {
  tabs.forEach((t, n) => t.setAttribute('aria-selected', n === i));
  panels.forEach((p, n) => p.hidden = n !== i);
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
show(start > -1 ? start : 0, false);
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
    <h1 class="site">{title}</h1>
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


def slugify(name):
    return name.lower().replace(".md", "").replace("_", "-")


def render():
    md = markdown.Markdown(extensions=["tables", "attr_list", "sane_lists"])

    tabs_html, panels_html = [], []
    for i, (label, filename) in enumerate(TABS):
        if filename is None:
            body = charts.section_html()
            slug = "charts"
        else:
            path = NOTES / filename
            if not path.exists():
                print(f"  WARNING: {filename} not found — tab skipped")
                continue

            md.reset()
            body = md.convert(path.read_text(encoding="utf-8"))
            body = align_tables(body)
            # Let wide tables scroll rather than break the layout.
            body = body.replace("<table>", '<div class="tw"><table>')
            body = body.replace("</table>", "</table></div>")
            slug = slugify(filename)
        selected = "true" if i == 0 else "false"
        tabs_html.append(
            f'<button role="tab" aria-selected="{selected}" '
            f'aria-controls="{slug}">{label}</button>'
        )
        panels_html.append(
            f'<section id="{slug}" role="tabpanel"'
            f'{"" if i == 0 else " hidden"}>{body}</section>'
        )

    sources = " · ".join(f for _, f in TABS if f)
    footer = (
        f"Rendered from {sources} — edit the markdown and re-run "
        f"<code>src/build_report.py</code>. "
        f"Size and trading data as at 30 June 2026; "
        f"commodity and property as at 31 July 2026."
    )

    html = PAGE.format(
        title=TITLE,
        css=CSS,
        vizcss=charts.CSS,
        js=JS,
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
