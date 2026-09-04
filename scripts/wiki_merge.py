#!/usr/bin/env python3
"""Merge duplicate wiki pages, rewrite inbound links, keep a canonical registry.

Phase 1 of the wiki plan. The merge is DETERMINISTIC and lossless on purpose:
an LLM rewrite of two good pages risks quietly dropping claims, and the
syntheses are the asset. So:

  - the canonical page's body is kept verbatim
  - sections from the duplicate whose heading the canonical lacks are appended
  - `sources:` frontmatter is unioned
  - every [[duplicate-slug]] in the wiki is rewritten to [[canonical-slug]]
  - the duplicate file is deleted and its index.md line removed
  - the old name is recorded in wiki/canonical-names.md so it still resolves

Redundancy across differently-worded headings is possible and is the accepted
cost of not losing content. Review the merged pages afterwards.

    python3 scripts/wiki_merge.py --dry-run
    python3 scripts/wiki_merge.py
"""
from __future__ import annotations

import argparse
import re
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import compile as compile_mod  # noqa: E402

WIKI = REPO / "wiki"
REGISTRY = WIKI / "canonical-names.md"

# Merges and renames are DATA, not code. They are specific to your vault, so
# they live in references/wiki-merges.json and this script just applies them.
#
#   {
#     "merges":  { "canonical-slug": ["duplicate-slug", "another-dupe"] },
#     "renames": { "wrong-slug": "right-slug" }
#   }
#
# A merge folds the duplicate pages into the canonical one and rewrites every
# [[link]] that pointed at them. A rename is for a page whose content is fine
# but whose slug lies about it. Read both pages before adding a pair.
MERGE_FILE = REPO / "references" / "wiki-merges.json"


def _load_merge_table() -> tuple[dict[str, list[str]], dict[str, str]]:
    if not MERGE_FILE.exists():
        return {}, {}
    try:
        data = json.loads(MERGE_FILE.read_text())
    except json.JSONDecodeError as e:
        raise SystemExit(f"{MERGE_FILE} is not valid JSON: {e}")
    return data.get("merges", {}) or {}, data.get("renames", {}) or {}


MERGES, RENAMES = _load_merge_table()

LINK = re.compile(r"\[\[([^\]|]+?)(\|[^\]]*)?\]\]")
HEADING = re.compile(r"^(#{2,6})\s+(.*)$", re.M)


def find_page(slug: str) -> Path | None:
    for p in WIKI.rglob(f"{slug}.md"):
        return p
    return None


def split_front(text: str) -> tuple[str, str]:
    """Return (frontmatter_without_fences, body)."""
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", text
    return text[3:end].strip("\n"), text[end + 4 :].lstrip("\n")


def sources_of(front: str) -> list[str]:
    m = re.search(r"^sources:\s*\[(.*?)\]\s*$", front, re.M | re.S)
    if not m:
        return []
    return [s.strip() for s in m.group(1).split(",") if s.strip()]


def set_sources(front: str, srcs: list[str]) -> str:
    joined = ", ".join(srcs)
    if re.search(r"^sources:", front, re.M):
        return re.sub(r"^sources:.*$", f"sources: [{joined}]", front, count=1, flags=re.M)
    return front + f"\nsources: [{joined}]"


def sections(body: str) -> list[tuple[str, str]]:
    """[(heading_text_lowercased, full_section_markdown)] for ## and deeper."""
    out, marks = [], list(HEADING.finditer(body))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        out.append((m.group(2).strip().lower(), body[m.start() : end].rstrip()))
    return out


def merge_bodies(canon_body: str, dup_body: str, dup_slug: str) -> str:
    have = {h for h, _ in sections(canon_body)}
    add = [sec for h, sec in sections(dup_body)
           if h not in have and not h.startswith("related concept")]
    if not add:
        return canon_body
    return canon_body.rstrip() + f"\n\n<!-- merged from {dup_slug} -->\n" + "\n\n".join(add) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    index = compile_mod.read_index(REPO)
    alias_to_canon: dict[str, str] = {}
    removed: list[Path] = []
    report: list[str] = []

    # ---------------------------------------------------------------- merges
    for canon, dups in MERGES.items():
        cpath = find_page(canon)
        if not cpath:
            report.append(f"SKIP {canon}: canonical page not found")
            continue
        ctext = cpath.read_text(errors="replace")
        cfront, cbody = split_front(ctext)
        csrcs = sources_of(cfront)

        merged_any = []
        for dup in dups:
            dpath = find_page(dup)
            if not dpath:
                report.append(f"  skip {dup}: not found")
                continue
            dtext = dpath.read_text(errors="replace")
            dfront, dbody = split_front(dtext)
            cbody = merge_bodies(cbody, dbody, dup)
            for s in sources_of(dfront):
                if s not in csrcs:
                    csrcs.append(s)
            alias_to_canon[dup] = canon
            removed.append(dpath)
            merged_any.append(dup)

        if not merged_any:
            continue
        cfront = set_sources(cfront, csrcs)
        if not args.dry_run:
            cpath.write_text(f"---\n{cfront}\n---\n\n{cbody.lstrip()}")
        report.append(f"MERGE -> {canon}  <- {', '.join(merged_any)}")

    # --------------------------------------------------------------- renames
    for old, new in RENAMES.items():
        opath = find_page(old)
        if not opath:
            report.append(f"SKIP rename {old}: not found")
            continue
        npath = opath.with_name(f"{new}.md")
        if not args.dry_run:
            opath.rename(npath)
        alias_to_canon[old] = new
        report.append(f"RENAME {old} -> {new}")

    # ---------------------------------------------- rewrite links everywhere
    # Recompute the page list: renames moved files, so the list captured at the
    # top holds stale paths and a renamed page would never get its own links
    # rewritten.
    rewrites = 0
    current = [p for p in WIKI.rglob("*.md")
               if p.name != "index.md" and p not in removed and p != REGISTRY]
    for live in current:
        text = live.read_text(errors="replace")

        def sub(m: re.Match) -> str:
            nonlocal rewrites
            target, alias = m.group(1).strip(), (m.group(2) or "")
            if target in alias_to_canon:
                rewrites += 1
                return f"[[{alias_to_canon[target]}{alias}]]"
            return m.group(0)

        new_text = LINK.sub(sub, text)
        # a page must not link to itself after a merge
        self_link = re.compile(rf"^\s*[-*]\s*\[\[{re.escape(live.stem)}\]\]\s*$", re.M)
        new_text = self_link.sub("", new_text)
        if new_text != text and not args.dry_run:
            live.write_text(new_text)
    report.append(f"LINKS rewritten: {rewrites}")

    # ------------------------------------------------------- delete + index
    for p in removed:
        rel = p.relative_to(WIKI).as_posix()
        index.pop(rel, None)
        if not args.dry_run:
            p.unlink()
    for old, new in RENAMES.items():
        for rel in list(index):
            if Path(rel).stem == old:
                index[rel.replace(f"{old}.md", f"{new}.md")] = index.pop(rel)
    if not args.dry_run:
        compile_mod.write_index(REPO, index)

    # ------------------------------------------------------------- registry
    lines = ["# Canonical names", "",
             "Old slugs that were merged or renamed, and where they now live.",
             "Wiki links to the left-hand name were rewritten; this registry is",
             "so a future reference to the old name still resolves.", ""]
    for old in sorted(alias_to_canon):
        lines.append(f"- `{old}` -> [[{alias_to_canon[old]}]]")
    if not args.dry_run:
        REGISTRY.write_text("\n".join(lines) + "\n")

    print("\n".join(report))
    print(f"\npages removed: {len(removed)}   aliases recorded: {len(alias_to_canon)}")
    if args.dry_run:
        print("DRY RUN, nothing written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
