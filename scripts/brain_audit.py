#!/usr/bin/env python3
"""Comprehensive Brain data-quality and interconnectivity audit.

Reads wiki/ and sources/ and prints a JSON report: link graph shape, broken
links, orphan and dead-end pages, connected components, frontmatter hygiene,
size distribution, source coverage, and near-duplicate slugs.

    python3 scripts/brain_audit.py | python3 -m json.tool | head -40

This is the raw data behind the /audit skill. It makes no model call and
touches no network.
"""
import os, re, json, sys, math
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "wiki"

FM = re.compile(r"^---\n(.*?)\n---\n", re.S)
LINK = re.compile(r"\[\[([^\]|#]+)")

pages = {}
for p in WIKI.rglob("*.md"):
    if p.name == "index.md":
        continue
    txt = p.read_text(errors="ignore")
    slug = p.stem
    m = FM.match(txt)
    meta, body = {}, txt
    if m:
        body = txt[m.end():]
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    links = [l.strip() for l in LINK.findall(body)]
    srcs = []
    if "sources" in meta:
        srcs = re.findall(r"[\w./\-]+\.md", meta["sources"])
    pages[slug] = dict(path=str(p.relative_to(ROOT)), kind=p.parent.name, meta=meta,
                       body=body, links=links, sources=srcs,
                       words=len(body.split()), chars=len(body))

if not pages:
    # A fresh clone has no wiki yet. Every metric below divides by the page
    # count, so report the empty state honestly instead of dividing by zero.
    print(json.dumps({
        "total_pages": 0,
        "status": "wiki is empty",
        "next": "Ingest sources, then run: python3 scripts/compile.py",
    }, indent=1))
    raise SystemExit(0)

slugs = set(pages)
out = defaultdict(set); inn = defaultdict(set); broken = Counter(); broken_ex = defaultdict(list)
for s, d in pages.items():
    for l in d["links"]:
        t = l.strip()
        if t in slugs:
            out[s].add(t); inn[t].add(s)
        else:
            broken[t] += 1
            if len(broken_ex[t]) < 3: broken_ex[t].append(s)

R = {}
R["total_pages"] = len(pages)
R["by_kind"] = dict(Counter(d["kind"] for d in pages.values()))
R["total_links"] = sum(len(v) for v in out.values())
R["broken_links"] = sum(broken.values())
R["broken_unique"] = len(broken)
R["top_broken"] = broken.most_common(25)
R["orphans"] = sorted(s for s in pages if not inn[s])           # nothing points here
R["deadends"] = sorted(s for s in pages if not out[s])          # points nowhere
R["isolated"] = sorted(s for s in pages if not inn[s] and not out[s])
R["avg_out"] = round(sum(len(out[s]) for s in pages)/len(pages), 2)
deg = {s: len(inn[s]) for s in pages}
R["hubs"] = sorted(deg.items(), key=lambda x: -x[1])[:25]

# connected components (undirected)
adj = defaultdict(set)
for s in pages:
    for t in out[s]:
        adj[s].add(t); adj[t].add(s)
seen, comps = set(), []
for s in pages:
    if s in seen: continue
    stack, comp = [s], []
    seen.add(s)
    while stack:
        c = stack.pop(); comp.append(c)
        for n in adj[c]:
            if n not in seen:
                seen.add(n); stack.append(n)
    comps.append(sorted(comp))
comps.sort(key=len, reverse=True)
R["components"] = len(comps)
R["largest_component"] = len(comps[0]) if comps else 0
R["component_sizes"] = [len(c) for c in comps[:15]]
R["small_components"] = [c for c in comps[1:] if len(c) <= 6][:25]

# frontmatter hygiene
R["missing_frontmatter"] = sorted(s for s,d in pages.items() if not d["meta"])
R["no_sources"] = sorted(s for s,d in pages.items() if not d["sources"])
R["confidence"] = dict(Counter(d["meta"].get("confidence","MISSING") for d in pages.values()))
R["updated_years"] = dict(Counter(d["meta"].get("updated","MISSING")[:7] for d in pages.values()))

# size distribution
w = sorted(d["words"] for d in pages.values())
R["words_median"] = w[len(w)//2] if w else 0
R["words_p10"] = w[len(w)//10] if w else 0
R["words_p90"] = w[int(len(w)*0.9)] if w else 0
R["thin_pages"] = sorted([(s,d["words"]) for s,d in pages.items() if d["words"] < 120], key=lambda x:x[1])[:40]
R["fat_pages"] = sorted([(s,d["words"]) for s,d in pages.items()], key=lambda x:-x[1])[:15]

# source coverage
all_src = {str(p.relative_to(ROOT)) for p in (ROOT/"sources").rglob("*.md")}
cited = set()
for d in pages.values():
    for s in d["sources"]:
        cited.add(s.lstrip("./"))
cited_norm = {c for c in cited}
R["sources_total"] = len(all_src)
R["sources_cited"] = len(all_src & cited_norm)
R["sources_uncited"] = len(all_src - cited_norm)
R["cited_not_found"] = len(cited_norm - all_src)
uncited = sorted(all_src - cited_norm)
R["uncited_by_folder"] = Counter(x.split("/")[1] for x in uncited if "/" in x).most_common(20)
R["sources_by_folder"] = Counter(x.split("/")[1] for x in all_src if "/" in x).most_common(20)

# multi-source pages (synthesis depth)
ns = Counter(len(d["sources"]) for d in pages.values())
R["sources_per_page"] = dict(sorted(ns.items()))
R["pages_multi_source"] = sum(v for k,v in ns.items() if k >= 2)

# near-duplicate / topic-collision detection via token overlap on slugs
def toks(s): return set(re.split(r"[-_]", s))
dupes = []
sl = sorted(pages)
for i, a in enumerate(sl):
    ta = toks(a)
    for b in sl[i+1:]:
        tb = toks(b)
        inter = ta & tb
        if not inter: continue
        j = len(inter)/len(ta|tb)
        if j >= 0.5:
            dupes.append((round(j,2), a, b))
dupes.sort(reverse=True)
R["slug_near_dupes_count"] = len(dupes)
R["slug_near_dupes"] = dupes[:60]

# cluster by leading token to show topic sprawl
lead = defaultdict(list)
for s in pages: lead[s.split("-")[0]].append(s)
R["topic_sprawl"] = sorted(((k, len(v)) for k,v in lead.items() if len(v) >= 5), key=lambda x:-x[1])[:25]

print(json.dumps(R, indent=1, default=str))
