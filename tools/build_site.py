#!/usr/bin/env python3
"""Build the static site in docs/ from results/*/result.json and data/*.json.

Every result with a graph is verified again; the build fails if any graph is not complete or its
size does not match. Usage: python3 tools/build_site.py
"""
import html
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from ordergraph import compact, lower_bound, missing_requirements, parse_graph  # noqa: E402

MODELS = {"bi": "Bidirectional", "uni": "Unidirectional"}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def link(text, url):
    if url and (url.startswith("https://") or url.startswith("http://")):
        return f'<a href="{esc(url)}">{esc(text)}</a>'
    return esc(text)


def load():
    results = []
    rdir = os.path.join(ROOT, "results")
    for rid in sorted(os.listdir(rdir)):
        path = os.path.join(rdir, rid, "result.json")
        if not os.path.isfile(path):
            continue
        r = json.load(open(path, encoding="utf-8"))
        r["id"] = rid
        if r.get("graph"):
            d, E = parse_graph(open(os.path.join(rdir, rid, r["graph"])).read())
            if d != r["d"]:
                sys.exit(f"{rid}: graph has d={d}, result says d={r['d']}")
            if len(E) != r["edges"]:
                sys.exit(f"{rid}: graph has {len(E)} edges, result says {r['edges']}")
            if missing_requirements(E, d, r["model"] == "uni"):
                sys.exit(f"{rid}: graph is NOT complete")
            r["_edges"] = E
        results.append(r)
    return results


def load_claims():
    """Lower-bound claims: claims/NNNN-*/claim.json, with status "claimed" or "accepted"."""
    claims = []
    cdir = os.path.join(ROOT, "claims")
    if not os.path.isdir(cdir):
        return claims
    for cid in sorted(os.listdir(cdir)):
        path = os.path.join(cdir, cid, "claim.json")
        if os.path.isfile(path):
            c = json.load(open(path, encoding="utf-8"))
            c["id"] = cid
            c["bounds"] = {int(k): int(v) for k, v in c.get("bounds", {}).items()}
            claims.append(c)
    return claims


def claim_models(c):
    return ["bi", "uni"] if c["model"] == "both" else [c["model"]]


def build():
    site = json.load(open(os.path.join(ROOT, "data", "site.json"), encoding="utf-8"))
    results = load()
    claims = load_claims()
    out = os.path.join(ROOT, "docs")
    gdir = os.path.join(out, "graphs")
    shutil.rmtree(gdir, ignore_errors=True)
    os.makedirs(gdir)

    dmax = max([site.get("dmax", 9)] + [r["d"] for r in results])
    # proven lower bound: the formula, or a larger bound from an accepted claim;
    # claimed: the largest bound from an unverified claim, if larger than the proven one
    proven, claimed = {}, {}
    for m in MODELS:
        for d in range(3, dmax + 1):
            proven[m, d] = {"value": lower_bound(m, d), "claim": None}
            claimed[m, d] = None
    for c in claims:
        for m in claim_models(c):
            for d, v in c["bounds"].items():
                if (m, d) not in proven:
                    continue
                if c.get("status") == "accepted":
                    if v > proven[m, d]["value"]:
                        proven[m, d] = {"value": v, "claim": c}
                elif claimed[m, d] is None or v > claimed[m, d]["value"]:
                    claimed[m, d] = {"value": v, "claim": c}
    for key in claimed:
        if claimed[key] and claimed[key]["value"] <= proven[key]["value"]:
            claimed[key] = None
    best, lb = {}, {}
    for m in MODELS:
        for d in range(3, dmax + 1):
            cand = [r for r in results if r["model"] == m and r["d"] == d]
            # best = smallest size; among ties, the earliest one (smallest id)
            best[m, d] = min(cand, key=lambda r: (r["edges"], r["id"])) if cand else None
            lb[m, d] = proven[m, d]

    for r in results:
        if r.get("_edges"):
            shutil.copy(os.path.join(ROOT, "results", r["id"], r["graph"]),
                        os.path.join(gdir, f"{r['id']}.txt"))

    # ------------------------------------------------------------ summary table
    rows = []
    for d in range(3, dmax + 1):
        cells = [f'<th scope="row">{d}</th>']
        for m in MODELS:
            b, L = best[m, d], lb[m, d]["value"]
            cl = claimed[m, d]
            mark = (f'<a class="claimed" href="#{esc(cl["claim"]["id"])}" title="unverified claim">'
                    f'({cl["value"]}?)</a> ' if cl else "")
            cells.append(f'<td class="num lb">{mark}{L}</td>')
            if b is None:
                cells.append('<td class="num">&ndash;</td><td></td>')
                continue
            cells.append(f'<td class="num best"><a href="#{esc(b["id"])}">{b["edges"]}</a></td>')
            if b["edges"] == L:
                status = '<span class="tag opt">optimal</span>'
            else:
                gap = 100 * (b["edges"] - L) / L
                status = f'<span class="gap">+{gap:.1f}%</span>'
            cells.append(f"<td>{status}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    table = f"""
<div class="scroll"><table class="summary">
<thead>
<tr><th rowspan="2" scope="col"><i>d</i></th><th colspan="3" scope="colgroup">Bidirectional</th>
<th colspan="3" scope="colgroup">Unidirectional</th></tr>
<tr><th scope="col">lower bound</th><th scope="col">best known</th><th scope="col"></th>
<th scope="col">lower bound</th><th scope="col">best known</th><th scope="col"></th></tr>
</thead>
<tbody>
{chr(10).join(rows)}
</tbody></table></div>"""

    # ------------------------------------------------------------ all results
    sections = []
    for m, mname in MODELS.items():
        blocks = []
        for d in range(3, dmax + 1):
            cand = sorted([r for r in results if r["model"] == m and r["d"] == d],
                          key=lambda r: (r["edges"], r["id"]))
            if not cand:
                continue
            items = []
            for r in cand:
                is_best = best[m, d] is r
                ref = r.get("reference") or {}
                if ref == "paper":          # shorthand for the paper in data/site.json
                    ref = site.get("paper", {})
                meta = [f'<span class="who">{esc(r.get("contributors"))}</span>',
                        f'<span class="when">{esc(r.get("date"))}</span>']
                body = []
                if r.get("method"):
                    body.append(f'<p><b>Method.</b> {esc(r["method"])}</p>')
                if ref.get("text") or ref.get("url"):
                    body.append(f'<p><b>Reference.</b> {link(ref.get("text") or ref.get("url"), ref.get("url"))}</p>')
                if r.get("comment"):
                    body.append(f'<p><b>Comment.</b> {esc(r["comment"])}</p>')
                if r.get("_edges"):
                    gl = f'<a href="graphs/{esc(r["id"])}.txt" download>edge list</a>'
                    if d <= 9:
                        code = "\n".join(f"{p}: {s}" for p, s in compact(r["_edges"]))
                        body.append(f'<details><summary>Graph ({gl}, verified complete)</summary>'
                                    f'<pre class="code">{esc(code)}</pre></details>')
                    else:
                        body.append(f'<p>Graph: {gl} (verified complete).</p>')
                else:
                    body.append('<p class="muted">Graph not available.</p>')
                cls = "entry best" if is_best else "entry"
                badge = '<span class="tag">best known</span>' if is_best else ""
                items.append(f"""<li class="{cls}" id="{esc(r['id'])}">
<div class="head"><span class="size">{r['edges']} edges</span>{badge}{''.join(meta)}</div>
{''.join(body)}
</li>""")
            L = lb[m, d]
            lbref = ""
            if L["claim"]:
                lbref = f' (<a href="#{esc(L["claim"]["id"])}">accepted claim</a>)'
            if claimed[m, d]:
                cl = claimed[m, d]
                lbref += (f'; claimed {cl["value"]} '
                          f'(<a href="#{esc(cl["claim"]["id"])}">unverified</a>)')
            blocks.append(f"""<section class="cell" id="{m}-d{d}">
<h3><i>d</i> = {d} <span class="muted">&middot; lower bound {L['value']}{lbref}</span></h3>
<ul class="entries">{''.join(items)}</ul>
</section>""")
        sections.append(f'<h2 id="{m}">{mname} model</h2>' + "".join(blocks))

    citems = []
    for c in sorted(claims, key=lambda c: c["id"], reverse=True):
        acc = c.get("status") == "accepted"
        badge = ('<span class="tag opt">accepted</span>' if acc
                 else '<span class="tag claim">unverified claim</span>')
        mname = {"bi": "bidirectional", "uni": "unidirectional", "both": "both models"}[c["model"]]
        bl = ", ".join(f"<i>d</i>&nbsp;=&nbsp;{d}: &ge;&nbsp;{v}" for d, v in sorted(c["bounds"].items()))
        ref = c.get("reference") or {}
        body = [f'<p><b>Bounds ({mname}).</b> {bl}</p>']
        if c.get("statement"):
            body.append(f'<p><b>Statement.</b> {esc(c["statement"])}</p>')
        if ref.get("text") or ref.get("url"):
            body.append(f'<p><b>Proof.</b> {link(ref.get("text") or ref.get("url"), ref.get("url"))}</p>')
        if c.get("comment"):
            body.append(f'<p><b>Comment.</b> {esc(c["comment"])}</p>')
        citems.append(f"""<li class="entry" id="{esc(c['id'])}">
<div class="head">{badge}<span class="who">{esc(c.get('contributors'))}</span>
<span class="when">{esc(c.get('date'))}</span></div>
{''.join(body)}
</li>""")
    claims_html = (f'<ul class="entries">{"".join(citems)}</ul>' if citems
                   else '<p class="muted">No claims so far.</p>')

    repo = site.get("repository", "")
    submit = f"https://github.com/{repo}/issues/new?template=new-result.yml"
    submit_lb = f"https://github.com/{repo}/issues/new?template=lower-bound.yml"
    paper = site.get("paper", {})
    page = TEMPLATE.format(
        title=esc(site["title"]), table=table, sections="".join(sections), claims=claims_html,
        submit_lb=esc(submit_lb),
        paper=link(paper.get("text", ""), paper.get("url")), submit=esc(submit),
        repo=esc(f"https://github.com/{repo}"),
        maintainer=link(site.get("maintainer", ""), site.get("maintainer_url")))
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(page)
    open(os.path.join(out, ".nojekyll"), "w").close()
    data = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
    json.dump(data, open(os.path.join(out, "results.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    print(f"built docs/ with {len(results)} results and {len(claims)} lower-bound claims")


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{
  --bg: #fbfaf7; --fg: #1d1d1b; --muted: #6b6a66; --line: #e3e0d8; --card: #ffffff;
  --accent: #1f5f8b; --best: #eef5fa; --opt: #2f7d4f; --optbg: #e6f3ea; --claim: #9a5b00; --claimbg: #fbf0dc;
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #16171a; --fg: #e8e6e1; --muted: #9c9a94; --line: #2d2f34; --card: #1d1f23;
    --accent: #7db7e0; --best: #1c2a35; --opt: #7fcf9b; --optbg: #1d3326; --claim: #e5b567; --claimbg: #3a2e17; }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
main {{ max-width: 860px; margin: 0 auto; padding: 32px 16px 64px; }}
h1 {{ font-size: 1.75rem; line-height: 1.2; margin: 0 0 12px; }}
h2 {{ font-size: 1.3rem; margin: 48px 0 8px; padding-bottom: 6px; border-bottom: 1px solid var(--line); }}
h3 {{ font-size: 1.05rem; margin: 24px 0 8px; }}
a {{ color: var(--accent); }}
p {{ margin: 8px 0; }}
.muted {{ color: var(--muted); font-weight: normal; }}
.lead {{ color: var(--muted); }}
nav {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 16px 0 8px; font-size: .95rem; }}
.scroll {{ overflow-x: auto; }}
table.summary {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-variant-numeric: tabular-nums; }}
.summary th, .summary td {{ padding: 6px 10px; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }}
.summary thead th {{ font-size: .85rem; color: var(--muted); font-weight: 600; }}
.summary thead tr:first-child th {{ color: var(--fg); font-size: .95rem; }}
.summary td.num {{ text-align: right; }}
.summary td.best a {{ font-weight: 700; text-decoration: none; }}
.summary td.lb {{ color: var(--muted); }}
.tag {{ display: inline-block; font-size: .75rem; padding: 1px 8px; border-radius: 999px;
  background: var(--best); color: var(--accent); margin-left: 8px; font-weight: 600; }}
.tag.claim {{ background: var(--claimbg); color: var(--claim); margin-left: 0; }}
a.claimed {{ color: var(--claim); font-size: .85rem; text-decoration: none; }}
.button.secondary {{ background: transparent; color: var(--accent); border: 1px solid var(--accent); }}
.entry .head .tag {{ margin-left: 0; }}
.tag.opt {{ background: var(--optbg); color: var(--opt); margin-left: 0; }}
.gap {{ font-size: .85rem; color: var(--muted); }}
ul.entries {{ list-style: none; padding: 0; margin: 0; }}
.entry {{ background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 10px 14px; margin: 8px 0; }}
.entry.best {{ border-color: var(--accent); background: var(--best); }}
.entry .head {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; }}
.entry .size {{ font-weight: 700; }}
.entry .who {{ color: var(--fg); }}
.entry .when {{ color: var(--muted); font-size: .9rem; }}
.entry p {{ font-size: .93rem; }}
details summary {{ cursor: pointer; font-size: .93rem; margin: 6px 0; }}
pre {{ background: var(--bg); border: 1px solid var(--line); border-radius: 6px; padding: 10px 12px;
  font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; overflow-x: auto; }}
pre.code {{ white-space: pre-wrap; word-break: break-all; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .92em; }}
.button {{ display: inline-block; background: var(--accent); color: var(--bg); padding: 8px 16px;
  border-radius: 6px; text-decoration: none; font-weight: 600; }}
footer {{ margin-top: 56px; font-size: .9rem; color: var(--muted); }}
</style>
</head>
<body>
<main>
<h1>{title}</h1>
<p class="lead">An <em>order graph</em> of dimension <i>d</i> has attribute orders (permutations of
1,&hellip;,<i>d</i>) as nodes, and an edge labeled <i>a</i> from each order &pi; to the order <i>a</i>&middot;&pi;
obtained by moving <i>a</i> to the front. It is <em>complete</em> if, for every set <i>S</i> of attributes and
every <i>x</i> &notin; <i>S</i>, some path is labeled exactly by <i>S</i> &cup; {{<i>x</i>}}, with <i>x</i> at one
end (bidirectional model) or at the end (unidirectional model). Complete order graphs give indexes that support
worst-case optimal joins in every attribute order; their number of edges is the space of the index. This page
tracks the smallest complete order graphs known.</p>
<p>Background and lower bounds: {paper}</p>
<nav><a href="#bi">Bidirectional results</a><a href="#uni">Unidirectional results</a>
<a href="#claims">Lower-bound claims</a><a href="#format">Graph format</a><a href="#contribute">Contribute</a></nav>

<h2 id="summary">Current best sizes</h2>
{table}
<p class="muted">Lower bounds: max<sub><i>m</i></sub> C(<i>d</i>,<i>m</i>)&lceil;<i>m</i>/2&rceil; (bidirectional) and
<i>d</i>&middot;C(<i>d</i>&minus;1,&lfloor;(<i>d</i>&minus;1)/2&rfloor;) (unidirectional), unless a larger bound has
been accepted. A value in parentheses with a question mark is a larger bound that has been
<a href="#claims">claimed but not verified</a>. A size is marked optimal when it matches the proven lower bound. Every
listed graph has been checked mechanically for completeness.</p>

{sections}

<h2 id="claims">Lower-bound claims</h2>
<p>Lower bounds cannot be checked mechanically, so claims are listed here as they are received, marked as
<span class="tag claim">unverified claim</span>, and only used in the table once they have been
<span class="tag opt">accepted</span> (for example, after peer review or a check by the maintainer). The only
automatic check is that a claimed bound does not exceed the size of a verified graph.</p>
{claims}
<p><a class="button secondary" href="{submit_lb}">Submit a lower-bound claim</a></p>

<h2 id="format">Graph format</h2>
<p>Each graph can be downloaded as an edge list: one edge per line, written as the source order and the label,
e.g. <code>412563 6</code> (the target is the order with the label moved to the front). Graphs with
<i>d</i> &le; 9 are also shown in a compact format, one line per weakly connected component: a start order, then
a bracketed list of edges. A digit <i>a</i> is an edge labeled <i>a</i> from the current node to <i>a</i>&middot;&pi;,
where &pi; is the current order, and the brackets that follow it list the edges leaving that target; a star marks an
edge whose target already appeared. This Python function lists the edges of a component:</p>
<pre>def edges(start, s):
    out, stack, cur = [], [], start
    for c in s:
        if c.isdigit():
            last = c + cur.replace(c, "")
            out.append((cur, c, last))
        elif c == "[":
            stack.append(cur)
            cur = last
        elif c == "]":
            cur = stack.pop()
    return out</pre>

<h2 id="contribute">Contribute a result</h2>
<p>Found a smaller complete order graph? Submit it through the form below (a free GitHub account is needed).
Paste the graph in either format above, and add your name, the method, and optionally a reference and a
comment. The graph is checked automatically within a few minutes, and the result appears here once the
maintainer approves it.</p>
<p><a class="button" href="{submit}">Submit a new result</a></p>
<p class="muted">Lower bounds are submitted separately; see <a href="#claims">lower-bound claims</a>.</p>

<footer>Maintained by {maintainer}. Data and code: <a href="{repo}">{repo}</a>.</footer>
</main>
</body>
</html>
"""

if __name__ == "__main__":
    build()
