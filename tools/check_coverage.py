#!/usr/bin/env python3
"""Documentation coverage: which RTL files and modules under fpga/nv_hsb_ip are never mentioned.

For every .sv / .v file under fpga/nv_hsb_ip (simple_tb excluded) and every module or package it defines,
look for the file name (in a link or in text) or the module name (as a word) anywhere in
docs/ and README.md. Files and modules that appear nowhere are listed by directory.

Usage:  python3 tools/check_coverage.py <path-to-holoscan-sensor-bridge> [--list]
  --list  also print the covered files
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    ip = Path(sys.argv[1]) / "fpga" / "nv_hsb_ip"
    files = sorted(f for f in list(ip.rglob("*.sv")) + list(ip.rglob("*.v")) if "simple_tb" not in str(f))
    docs = [p for p in (ROOT / "docs").rglob("*.md")] + [ROOT / "README.md"]
    text = "\n".join(p.read_text(errors="replace") for p in docs)
    words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text))
    mod_re = re.compile(r"^\s*(?:module|package)\s+([A-Za-z_]\w*)", re.M)

    n_mod = n_mod_cov = 0
    miss_file, miss_mod = [], []
    for f in files:
        rel = f.relative_to(ip)
        src = f.read_text(errors="replace")
        mods = mod_re.findall(re.sub(r"//.*", "", src))
        file_hit = f.name in text
        mod_hit = [m for m in mods if m in words]
        n_mod += len(mods)
        n_mod_cov += len(mod_hit)
        if not file_hit and not mod_hit:
            miss_file.append((rel, mods))
        for m in mods:
            if m not in words and not file_hit:
                miss_mod.append((rel, m))
        if "--list" in sys.argv and (file_hit or mod_hit):
            print(f"covered  {rel}")
    print(f"files: {len(files)}; covered: {len(files) - len(miss_file)}; "
          f"modules + packages: {n_mod}; names mentioned: {n_mod_cov}")
    if miss_file:
        print("\nfiles never mentioned (by file name or by any module they define):")
        for rel, mods in miss_file:
            print(f"  {rel}  [{', '.join(mods) or 'no module'}]")
    extra = [(r, m) for r, m in miss_mod if all(r != x for x, _ in miss_file)]
    if extra:
        print("\nmodules not mentioned in a file whose name is not mentioned either:")
        for rel, m in extra:
            print(f"  {rel}: {m}")

    # Line-count columns ("行數") in doc tables against the source files.
    size = {}
    for f in files:
        t = f.read_text(errors="replace")
        n = t.count("\n") + (0 if t.endswith("\n") else 1)
        for m in mod_re.findall(re.sub(r"//.*", "", t)):
            size[m] = (n, f.name)
    n_rows = 0
    bad = []
    for doc in sorted((ROOT / "docs").rglob("*.md")):
        hdr = None
        for i, ln in enumerate(doc.read_text().split("\n"), 1):
            if not ln.startswith("|"):
                hdr = None
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if "行數" in cells:
                hdr = cells.index("行數")
                continue
            if hdr is None or ln.startswith("|---") or len(cells) <= hdr:
                continue
            if "/tree/" in ln:          # directory link: the count is a sum over the directory
                continue
            names = re.findall(r"`(\w+)`", cells[0])
            num = re.match(r"(\d+)", cells[hdr].replace(",", ""))
            if names and num and names[0] in size:
                n_rows += 1
                if abs(size[names[0]][0] - int(num.group(1))) > 1:
                    bad.append(f"  {doc.relative_to(ROOT)}:{i} {names[0]} doc {num.group(1)}, "
                               f"{size[names[0]][1]} has {size[names[0]][0]}")
    print(f"\nline-count cells checked: {n_rows}; mismatches: {len(bad)}")
    print("\n".join(bad))
    return 1 if (miss_file or bad) else 0


if __name__ == "__main__":
    sys.exit(main())
