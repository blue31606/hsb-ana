#!/usr/bin/env python3
"""List handshake / status ports that are left unconnected or tied to a constant.

Parses every module definition and every instantiation under fpga/nv_hsb_ip (plus the
board top files) at the pinned commit. For each instance it reports ports whose name
looks like flow control or an error / status flag (tready, ready, valid, full, afull,
empty, err, error, overflow, busy, ack, done, pause, drop, stall, lock) that are
  - connected with an empty expression:            .o_x_tready ( )
  - not listed at all in a named-connection instance
  - an input tied to a constant ('1, 1'b1, '0, 0, ...)
Output ports left open and input ports tied off are the two cases that can hide lost
back-pressure or ignored errors (BR-1 and PE-10 were both of this kind). The list is
for reading by hand: most entries are intentional (unused status, always-ready sinks).

Usage:  python3 tools/scan_ports.py <path-to-holoscan-sensor-bridge> [--all]
  --all   also list non-handshake ports that are open or tied off
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reviewed as reviewed_list  # noqa: E402

KEY = re.compile(r"(tready|ready|valid|full|afull|empty|err|error|overflow|underflow|busy|"
                 r"ack|done|pause|drop|stall|lock|gnt|grant|req)", re.I)
CONST = re.compile(r"^\s*(\d*'[bdhoBDHO]?[0-9a-fA-F_xXzZ]+|'[01xXzZ]|\d+|\{[^{}]*\}\s*\{\s*1'b[01]\s*\}|"
                   r"\{\s*\w+\s*\{\s*1'b[01]\s*\}\s*\})\s*$")


def strip(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def balanced(text, i):
    """text[i] == '('; return index after the matching ')'."""
    depth = 0
    for j in range(i, len(text)):
        c = text[j]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return j + 1
    return len(text)


def split_top(s):
    out, depth, cur = [], 0, ""
    for c in s:
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        if c == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += c
    if cur.strip():
        out.append(cur)
    return out


def parse_modules(files):
    mods = {}
    for f in files:
        text = strip(f.read_text(errors="replace"))
        for m in re.finditer(r"\bmodule\s+(\w+)\s*", text):
            name = m.group(1)
            i = m.end()
            # skip imports
            while True:
                im = re.match(r"\s*import\s+[^;]*;\s*", text[i:])
                if not im:
                    break
                i += im.end()
            if text[i:i + 1] == "#":
                j = text.index("(", i)
                i = balanced(text, j)
                while text[i].isspace():
                    i += 1
            if text[i:i + 1] != "(":
                continue
            end = balanced(text, i)
            ports, cur = {}, None
            for tok in split_top(text[i + 1:end - 1]):
                d = re.search(r"\b(input|output|inout)\b", tok)
                if d:
                    cur = d.group(1)
                elif re.search(r"\.\w+\s*\(|\binterface\b|\bmodport\b", tok):
                    cur = cur
                names = re.findall(r"([A-Za-z_]\w*)\s*(?:\[[^\]]*\]\s*)*$", tok.strip())
                if names and cur:
                    ports[names[0]] = cur
            mods.setdefault(name, (f, ports))
    return mods


def parse_instances(files, mods):
    out = []
    names = "|".join(sorted(mods, key=len, reverse=True))
    rx = re.compile(r"(?<![\w.])(" + names + r")\b\s*(#\s*\()?")
    for f in files:
        text = strip(f.read_text(errors="replace"))
        for m in rx.finditer(text):
            mod = m.group(1)
            # not a module header, not a type use in a declaration
            pre = text[max(0, m.start() - 10):m.start()]
            if re.search(r"\bmodule\s*$|\bendmodule\s*$", pre):
                continue
            i = m.end()
            if m.group(2):
                i = balanced(text, i - 1)
            im = re.match(r"\s*([A-Za-z_]\w*)\s*(\[[^\]]*\])?\s*\(", text[i:])
            if not im:
                continue
            inst = im.group(1)
            p0 = i + im.end() - 1
            p1 = balanced(text, p0)
            body = text[p0 + 1:p1 - 1]
            if not re.search(r"\.\w+\s*\(", body):
                continue
            conns = {}
            wildcard = ".*" in body
            for tok in split_top(body):
                cm = re.match(r"\s*\.(\w+)\s*\((.*)\)\s*$", tok, flags=re.S)
                if cm:
                    conns[cm.group(1)] = cm.group(2).strip()
            line = text[:m.start()].count("\n") + 1
            out.append((f, line, mod, inst, conns, wildcard))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    up = Path(sys.argv[1]) / "fpga"
    show_all = "--all" in sys.argv
    ip = sorted((up / "nv_hsb_ip").rglob("*.sv")) + sorted((up / "nv_hsb_ip").rglob("*.v"))
    tops = sorted(up.glob("*/*/*/rtl/top/FPGA_top.sv")) + sorted(up.glob("*/*/rtl/top/FPGA_top.*v"))
    files = [f for f in ip + tops if "simple_tb" not in str(f)]
    mods = parse_modules(files)
    insts = parse_instances(files, mods)
    rows = defaultdict(list)
    n_open = n_tied = 0
    for f, line, mod, inst, conns, wildcard in insts:
        if wildcard:
            continue
        ports = mods[mod][1]
        for p, d in ports.items():
            hand = bool(KEY.search(p))
            if not (hand or show_all):
                continue
            if p not in conns or conns[p] == "":
                if d == "output":
                    rows[(mod, p, "output open")].append((f, line, inst))
                    n_open += 1
                elif d == "input":
                    rows[(mod, p, "INPUT OPEN")].append((f, line, inst))
                    n_open += 1
            elif d == "input" and CONST.match(conns[p]):
                rows[(mod, p, f"input = {conns[p]}")].append((f, line, inst))
                n_tied += 1
    rel = lambda f: str(f).split("/fpga/", 1)[1]
    # Hand-reviewed findings: "scan_ports <mod>.<port> <file or *>" in tools/reviewed.txt.
    reviewed = {}
    if not show_all:
        for key, where_ in reviewed_list.load("scan_ports"):
            reviewed.setdefault(key, set()).add(where_)
    def is_reviewed(mod, p, f):
        w = reviewed.get(f"{mod}.{p}", set())
        return "*" in w or rel(f) in w
    n_rev = 0
    left = {}
    for k, where in rows.items():
        rest = [x for x in where if not is_reviewed(k[0], k[1], x[0])]
        n_rev += len(where) - len(rest)
        if rest:
            left[k] = rest
    print(f"modules parsed: {len(mods)}; instances: {len(insts)}; "
          f"handshake/status ports open: {n_open}, inputs tied to a constant: {n_tied}; "
          f"reviewed by hand: {n_rev} (tools/reviewed.txt); not reviewed: {sum(map(len, left.values()))}")
    for (mod, p, kind), where in sorted(left.items(), key=lambda x: (x[0][2] != "INPUT OPEN", x[0][2], x[0][0], x[0][1])):
        locs = "; ".join(f"{rel(f)}:{ln} {inst}" for f, ln, inst in where[:4])
        more = f" (+{len(where) - 4})" if len(where) > 4 else ""
        print(f"{kind:22s} {mod}.{p}\n        {locs}{more}")
    return 1 if left and not show_all else 0


if __name__ == "__main__":
    sys.exit(main())
