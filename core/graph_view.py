"""A-06 / A-11: draw a Roadmap as Graphviz DOT (rendered in the browser by Streamlit) and as a standalone HTML file."""
from __future__ import annotations

import html
import json

from core.schemas import Roadmap
from core.taxonomy import Taxonomy

TODO_FILL, TODO_LINE = "#FDE7C8", "#B8650A"
KNOWN_FILL, KNOWN_LINE = "#D8F0DD", "#2E7D3A"
FONT = "Vazirmatn, Tahoma, sans-serif"


def _q(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)  # DOT accepts JSON-style quoted strings


def roadmap_dot(rm: Roadmap, tax: Taxonomy) -> str:
    """Stages top to bottom; to-learn concepts orange, known direct prerequisites green."""
    todo = [c for stage in rm.stages for c in stage]
    todo_set = set(todo)
    known_shown = sorted({p for c in todo for p in tax.graph.predecessors(c) if p not in todo_set})
    lines = [
        "digraph roadmap {",
        f'  graph [rankdir=TB, nodesep=0.25, ranksep=0.45, bgcolor="transparent", fontname={_q(FONT)}];',
        f'  node [shape=box, style="rounded,filled", fontname={_q(FONT)}, fontsize=12, margin="0.15,0.06"];',
        '  edge [color="#8A94A6", arrowsize=0.6];',
    ]
    if known_shown:
        lines.append(f'  subgraph cluster_known {{ label={_q("بلد هستید")}; style=dashed; color="{KNOWN_LINE}"; fontcolor="{KNOWN_LINE}";')
        for c in known_shown:
            lines.append(f'    {_q(c)} [label={_q(tax.concepts[c]["name_fa"])}, fillcolor="{KNOWN_FILL}", color="{KNOWN_LINE}"];')
        lines.append("  }")
    for i, stage in enumerate(rm.stages, 1):
        lines.append(f'  subgraph cluster_s{i} {{ label={_q(f"مرحله‌ی {i}")}; style=rounded; color="#C9D2DC"; fontcolor="#56657A";')
        for c in stage:
            lines.append(f'    {_q(c)} [label={_q(tax.concepts[c]["name_fa"])}, fillcolor="{TODO_FILL}", color="{TODO_LINE}"];')
        lines.append("  }")
    shown = todo_set | set(known_shown)
    for u, v in tax.graph.edges:
        if u in shown and v in todo_set:
            lines.append(f"  {_q(u)} -> {_q(v)};")
    lines.append("}")
    return "\n".join(lines)


def roadmap_html(rm: Roadmap, tax: Taxonomy, title: str, summary: str, resources: dict[str, list[dict]]) -> str:
    """A-11 export: a self-contained RTL page (graph drawn by viz.js from a CDN, plus the stage list and links)."""
    items = []
    for i, stage in enumerate(rm.stages, 1):
        rows = []
        for c in stage:
            links = "".join(
                f'<li><a href="{html.escape(r["url"])}">{html.escape(r["title"])}</a></li>' for r in resources.get(c, [])
            )
            rows.append(f"<li><b>{html.escape(tax.concepts[c]['name_fa'])}</b>{f'<ul>{links}</ul>' if links else ''}</li>")
        items.append(f"<h3>مرحله‌ی {i}</h3><ul>{''.join(rows)}</ul>")
    return f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap" rel="stylesheet">
<style>body{{font-family:Vazirmatn,Tahoma,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;line-height:1.9}}
#g svg{{max-width:100%;height:auto}} pre{{white-space:pre-wrap;background:#F4F6F8;padding:12px;border-radius:8px}}</style></head>
<body><h1>{html.escape(title)}</h1><pre>{html.escape(summary)}</pre><div id="g"></div>{''.join(items)}
<script src="https://unpkg.com/@viz-js/viz@3.2.4/lib/viz-standalone.js"></script>
<script>Viz.instance().then(v=>document.getElementById('g').appendChild(v.renderSVGElement({json.dumps(roadmap_dot(rm, tax), ensure_ascii=False)})));</script>
</body></html>"""
