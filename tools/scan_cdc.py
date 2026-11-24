#!/usr/bin/env python3
"""Coarse clock-domain-crossing screen inside each RTL file.

For every file under fpga/nv_hsb_ip (simple_tb excluded):
  1. each `always_ff @(posedge <clk>)` / `always @(posedge <clk>)` block gives its clock;
     every signal assigned with `<=` in the block belongs to that clock;
  2. a signal driven by `assign x = ...` or `always_comb` takes the clock(s) of the signals it
     reads (repeated until nothing changes), so a crossing through combinational logic is seen;
  3. a block clocked by B that reads a signal of clock A != B is a crossing.
The first register of a crossing is accepted silently when its name looks like a synchronizer
stage (`*_sync*`, `*_meta*`, `*_ff1`, `*_d1`, `*_r1`, `*_cdc*`), or when the source signal is
only a quasi-static setting (named `*cfg*`, `*ctrl*`, `*reg*`, `*mode*`, `*en`). Everything else
is printed for reading by hand, unless tools/reviewed.txt lists "scan_cdc <file> <signal>".

Limits: crossings between modules (through ports) are not traced; clocks with different names
that are the same net (or SYNC_CLK = 1 builds) are reported as crossings; generate-for
indexing and arrays are matched by name only.

Usage:  python3 tools/scan_cdc.py <path-to-holoscan-sensor-bridge> [--all]
  --all  also print the crossings that the name rules accept
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reviewed as reviewed_list  # noqa: E402

SYNC_NAME = re.compile(r"(sync|meta|_ff1|_d1\b|_r1\b|cdc|_s1\b|_dly)", re.I)
STATIC = re.compile(r"(cfg|ctrl_reg|ctrl\b|_reg\b|mode|_en\b|enable|param|config)", re.I)
IDENT = re.compile(r"\b([A-Za-z_]\w*)\b")
KEYWORDS = set("""begin end if else case endcase default for posedge negedge or and not
logic reg wire assign always always_ff always_comb always_latch int integer genvar generate
endgenerate unique priority inside localparam parameter signed unsigned""".split())


def strip(t):
    t = re.sub(r"/\*.*?\*/", " ", t, flags=re.S)
    return re.sub(r"//.*", "", t)


def blocks(t):
    """Yield (kind, clock, body, line) for always_ff / always @(posedge) and always_comb."""
    for m in re.finditer(r"\balways(?:_ff)?\s*@\s*\(\s*posedge\s+([\w\[\]\.]+)[^)]*\)|\balways_comb\b|\balways\s*@\s*\(\s*\*\s*\)", t):
        start = m.end()
        # body: a begin ... end with nesting, or a single statement up to ';'
        rest = t[start:]
        s = rest.lstrip()
        off = start + len(rest) - len(s)
        if s.startswith("begin"):
            depth = 0
            for tok in re.finditer(r"\b(begin|end|case|endcase)\b", t[off:]):
                if tok.group(1) in ("begin", "case"):
                    depth += 1
                else:
                    depth -= 1
                if depth == 0:
                    body = t[off:off + tok.end()]
                    break
            else:
                body = t[off:]
        else:
            body = t[off:t.find(";", off) + 1]
        clk = m.group(1)
        clk = re.sub(r"\[.*?\]", "", clk) if clk else None
        yield ("ff" if clk else "comb", clk, body, t[:m.start()].count("\n") + 1)


def lhs_rhs(body, op):
    """(lhs names, rhs names) for every statement '<lhs> op <rhs>;' plus if/case conditions."""
    lhs, rhs = set(), set()
    for m in re.finditer(r"([A-Za-z_][\w\.]*)\s*(?:\[[^\]=;]*\])*\s*" + op + r"\s*([^;]*);", body):
        lhs.add(m.group(1).split(".")[0])
        rhs |= {x for x in IDENT.findall(m.group(2)) if x not in KEYWORDS}
    for m in re.finditer(r"\b(?:if|case|unique\s+case)\s*\((.*?)\)\s*(?:begin|\w)", body, re.S):
        rhs |= {x for x in IDENT.findall(m.group(1)) if x not in KEYWORDS}
    return lhs, rhs


def scan(path):
    t = strip(path.read_text(errors="replace"))
    dom = defaultdict(set)            # signal -> clocks
    ff = []                           # (clk, lhs, rhs, line)
    comb = []                         # (lhs, rhs)
    for kind, clk, body, line in blocks(t):
        if kind == "ff":
            l, r = lhs_rhs(body, "<=")
            for x in l:
                dom[x].add(clk)
            ff.append((clk, l, r, line))
        else:
            comb.append(lhs_rhs(body, "="))
    for m in re.finditer(r"\bassign\s+([A-Za-z_]\w*)[^=]*=\s*([^;]*);", t):
        comb.append(({m.group(1)}, {x for x in IDENT.findall(m.group(2)) if x not in KEYWORDS}))
    for _ in range(10):
        changed = False
        for l, r in comb:
            src = set().union(*(dom[x] for x in r if x in dom)) if r else set()
            for x in l:
                if not src <= dom[x]:
                    dom[x] |= src
                    changed = True
        if not changed:
            break
    clocks = {c for c, *_ in ff}
    out = []
    if len(clocks) < 2:
        return out
    for clk, l, r, line in ff:
        for x in sorted(r):
            other = dom.get(x, set()) - {clk}
            if other and x not in clocks:
                accepted = bool(SYNC_NAME.search(" ".join(l)) or SYNC_NAME.search(x) or STATIC.search(x))
                out.append((line, clk, sorted(other), x, sorted(l), accepted))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    ip = Path(sys.argv[1]) / "fpga" / "nv_hsb_ip"
    show_all = "--all" in sys.argv
    reviewed = set(reviewed_list.load("scan_cdc"))
    n_rev = 0
    files = sorted(f for f in list(ip.rglob("*.sv")) + list(ip.rglob("*.v")) if "simple_tb" not in str(f))
    n_multi = n_cross = n_acc = 0
    report = []
    for f in files:
        res = scan(f)
        if res:
            n_multi += 1
        for line, clk, other, x, l, acc in res:
            n_cross += 1
            n_acc += acc
            rev = (str(f.relative_to(ip)), x) in reviewed
            n_rev += rev and not acc
            if show_all or not (acc or rev):
                tag = "accepted " if acc else ("reviewed " if rev else "")
                report.append(f"  {tag}{f.relative_to(ip)}:{line}  @{clk} reads `{x}` ({', '.join(other)}) -> "
                              f"{', '.join(l[:3])}{' ...' if len(l) > 3 else ''}")
    print(f"files: {len(files)}; files with crossings inside: {n_multi}; crossings: {n_cross}; "
          f"accepted by name: {n_acc}; reviewed by hand: {n_rev} (tools/reviewed.txt); "
          f"not reviewed: {n_cross - n_acc - n_rev}")
    print("\n".join(report))
    return 1 if n_cross - n_acc - n_rev else 0


if __name__ == "__main__":
    sys.exit(main())
