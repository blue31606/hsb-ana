#!/usr/bin/env python3
"""Issue IDs: docs/issues.md against the rest of the documentation.

Checks that
  1. every ID referenced anywhere in docs/, README.md, VERIFICATION.md or CHANGELOG.md is
     defined in the issues.md tables;
  2. every ID defined in issues.md is referenced at least once in a module / flow / overview
     document (the place where the analysis is written);
  3. the ID cell in issues.md links to that place, at the heading above it: the doc of the
     module named in the row first, then any module doc, then the rest of docs/.
--write rewrites the ID cells in issues.md to those links.

Needs no upstream checkout.  Usage:  python3 tools/check_issue_refs.py [--write]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ISSUES = ROOT / "docs" / "issues.md"
ID = re.compile(r"\b([A-Z]{2}-\d+)\b")
ROW = re.compile(r"^\| (?:\[)?([A-Z]{2}-\d+)(?:\]\([^)]*\))? \|")


def anchor(heading):
    t = heading.lstrip("#").strip().lower()
    return re.sub(r"[^\w\- ]", "", t).replace(" ", "-")


def main():
    lines = ISSUES.read_text().split("\n")
    defined = {}
    owner = {}                       # ID -> module names in its 模組 / 位置 cell
    for i, l in enumerate(lines):
        m = ROW.match(l)
        if m:
            defined[m.group(1)] = i
            cells = l.split("|")
            owner[m.group(1)] = " ".join(cells[2:4])
    docs = sorted((ROOT / "docs").rglob("*.md"))
    first = {}
    unknown = []
    for d in [p for p in docs if p != ISSUES] + [ROOT / n for n in ("README.md", "VERIFICATION.md", "CHANGELOG.md")]:
        if not d.exists():
            continue
        head = ""
        in_analysis = d.parent.name in ("modules", "architecture") or d.name in ("flow.md", "performance.md")
        for n, l in enumerate(d.read_text().split("\n"), 1):
            if l.startswith("#"):
                head = l
            for x in ID.findall(l):
                if x not in defined:
                    if d.name != "CHANGELOG.md":
                        unknown.append(f"{d.relative_to(ROOT)}:{n} {x}")
                    continue
                if in_analysis:
                    # prefer the doc of the module named in the row, then any module doc
                    rank = (0 if re.search(r"`" + re.escape(d.stem) + r"`", owner[x]) else 1) \
                        + (0 if d.parent.name == "modules" else 2)
                    if x not in first or rank < first[x][0]:
                        first[x] = (rank, d, head)
    orphan = sorted(set(defined) - set(first), key=lambda s: (s[:2], int(s[3:])))
    stale = []
    for x, i in defined.items():
        if x not in first:
            continue
        _, d, head = first[x]
        rel = d.relative_to(ISSUES.parent).as_posix()
        link = f"[{x}]({rel}#{anchor(head)})" if head else f"[{x}]({rel})"
        cell = lines[i].split("|")[1].strip()
        if cell != link:
            stale.append(x)
            if "--write" in sys.argv:
                parts = lines[i].split("|")
                parts[1] = f" {link} "
                lines[i] = "|".join(parts)
    if "--write" in sys.argv:
        ISSUES.write_text("\n".join(lines))
    lv, me, n_nt = {}, {}, 0
    for x, i in defined.items():
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", lines[i].strip().strip("|"))]
        if x.startswith("NT-"):
            n_nt += 1
            continue
        lv[cells[1][0]] = lv.get(cells[1][0], 0) + 1
        me[cells[-2]] = me.get(cells[-2], 0) + 1
    stats = (f"issues: {sum(lv.values())} (高 {lv.get('高', 0)}, 中 {lv.get('中', 0)}, 低 {lv.get('低', 0)}); "
             f"notes and dead code: {n_nt}; methods: "
             + ", ".join(f"{k} {v}" for k, v in sorted(me.items(), key=lambda kv: -kv[1])))
    print(f"issue IDs defined: {len(defined)}; described in a module / flow doc: {len(first)}; "
          f"not described anywhere else: {len(orphan)}; undefined IDs referenced: {len(unknown)}; "
          f"ID links {'rewritten' if '--write' in sys.argv else 'out of date'}: {len(stale)}")
    print(stats)
    for x in orphan:
        print(f"  not described: {x}")
    for u in unknown:
        print(f"  undefined: {u}")
    bad = orphan or unknown or (stale and "--write" not in sys.argv)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
