#!/usr/bin/env python3
"""Clock-domain crossings between modules (through ports), coarse screen.

tools/scan_cdc.py looks inside one file. This one follows instance ports:

  1. Every module (fpga/nv_hsb_ip and the board FPGA_top files) gets a summary, built
     bottom-up: which input ports are clocks, which clock port each output is registered on,
     and which clock ports sample each input (through always_ff, assign / always_comb and
     child instances).
  2. In every parent, each instance input is compared: the clock(s) of the parent signal
     driving it (a local always_ff, or another instance's output, mapped to parent nets)
     against the clock(s) the child samples it with (mapped to parent nets). No common
     clock net = a crossing.
  3. An input synchronizer (data_sync, glitch_filter) whose output, possibly through
     combinational logic, is sampled by a child on another clock is reported too
     ("sync@<clock>"): the signal was synchronized to the wrong clock.
  4. Children that are synchronizers or dual-clock buffers (name contains sync, cdc, fifo,
     axis_buffer, reset_gen, pulse; s_apb_reg and s_apb_ram, which cross with reg_cdc / data_sync)
     are skipped: crossing into them is their job.

Limits: clock nets are compared by name after removing indices (i_sif_clk[0] and
i_sif_clk[1] are one net; two names tied to the same clock on a board are two nets);
parameters and generate conditions are ignored; inout and interface ports are skipped.

Usage:  python3 tools/scan_cdc_ports.py <path-to-holoscan-sensor-bridge> [--all]
  --all  also print the crossings listed in tools/reviewed.txt
         ("scan_cdc_ports <parent module, or the board top file> <instance>.<port>")
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reviewed as reviewed_list  # noqa: E402
import scan_cdc as C  # noqa: E402
import scan_ports as P  # noqa: E402

CDC_MOD = re.compile(r"(sync|cdc|fifo|axis_buffer|reset_gen|pulse|s_apb_reg|s_apb_ram)", re.I)
SYNC_MOD = re.compile(r"(data_sync|glitch_filter)", re.I)   # input synchronizers / filters


def base(expr):
    """Identifiers of a connection expression, without indices / fields."""
    return {x for x in C.IDENT.findall(re.sub(r"\[[^\]]*\]", "", expr))
            if x not in C.KEYWORDS and not re.fullmatch(r"\d+'?\w*|'[01]|[bhd][0-9a-fA-F_]+", x)}


def bodies(files):
    out = {}
    for f in files:
        t = C.strip(f.read_text(errors="replace"))
        for m in re.finditer(r"\bmodule\s+(\w+)", t):
            e = t.find("endmodule", m.end())
            out.setdefault(m.group(1), (f, t[m.start():e if e > 0 else len(t)],
                                        t[:m.start()].count("\n")))
    return out


def analyse(name, mods, body, insts, summ):
    """Return (summary, crossings) for one module."""
    f, text, line0 = body
    ports = mods[name][1]
    dom = defaultdict(set)      # signal -> clock nets it is registered on
    sdom = defaultdict(set)     # signal -> clock nets of the synchronizer that produced it
    use = defaultdict(set)      # signal -> clock nets that sample it
    comb = []
    alias = {}
    for kind, clk, blk, _ in C.blocks(text):
        if kind == "ff":
            l, r = C.lhs_rhs(blk, "<=")
            for x in l:
                dom[x].add(clk)
            for x in r:
                use[x].add(clk)
        else:
            comb.append(C.lhs_rhs(blk, "="))
    for m in re.finditer(r"\bassign\s+([A-Za-z_]\w*)[^=;]*=\s*([^;]*);", text):
        rhs = base(m.group(2))
        comb.append(({m.group(1)}, rhs))
        if len(rhs) == 1 and re.fullmatch(r"\s*[A-Za-z_]\w*\s*", m.group(2)):
            alias[m.group(1)] = next(iter(rhs))
    my = [i for i in insts if i[0] == f and i[2] in summ]
    # child outputs -> parent domains, child inputs -> parent uses
    for _, ln, child, inst, conns, _ in my:
        cs = summ[child]
        cmap = {cp: base(conns.get(cp, "")) for cp in cs["clk"]}
        for op, cps in cs["out"].items():
            if op in conns:
                for s in base(conns[op]):
                    for cp in cps:
                        dom[s] |= cmap.get(cp, set())
                        if SYNC_MOD.search(child):
                            sdom[s] |= cmap.get(cp, set())
        for ip, cps in cs["use"].items():
            if ip in conns and not CDC_MOD.search(child):   # a synchronizer input is not a use
                for s in base(conns[ip]):
                    for cp in cps:
                        use[s] |= cmap.get(cp, set())
    for _ in range(10):
        ch = False
        for l, r in comb:
            src = set().union(*(dom[x] for x in r if x in dom)) if r else set()
            snk = set().union(*(use[x] for x in l if x in use)) if l else set()
            ssrc = set().union(*(sdom[x] for x in r if x in sdom)) if r else set()
            for x in l:
                if not src <= dom[x]:
                    dom[x] |= src
                    ch = True
                if not ssrc <= sdom[x]:
                    sdom[x] |= ssrc
                    ch = True
            for x in r:
                if not snk <= use[x]:
                    use[x] |= snk
                    ch = True
        if not ch:
            break

    def net(c):
        seen = 0
        while c in alias and seen < 5:
            c, seen = alias[c], seen + 1
        return c
    clocks = {net(c) for s in list(dom.values()) + list(use.values()) for c in s}
    for _, _, child, _, conns, _ in my:
        for cp in summ[child]["clk"]:
            clocks |= {net(x) for x in base(conns.get(cp, ""))}
    clk_ports = {p for p, d in ports.items() if d == "input" and p in clocks}
    summary = {"clk": clk_ports,
               "out": {p: {net(c) for c in dom[p]} & clk_ports for p, d in ports.items() if d == "output"},
               "use": {p: {net(c) for c in use[p]} & clk_ports for p, d in ports.items() if d == "input"}}
    crossings = []
    for _, ln, child, inst, conns, _ in my:
        if CDC_MOD.search(child):
            continue
        cs = summ[child]
        cmap = {cp: {net(x) for x in base(conns.get(cp, ""))} for cp in cs["clk"]}
        for ip, cps in cs["use"].items():
            if ip not in conns or ip in cs["clk"] or not cps:
                continue
            u = set().union(*(cmap.get(cp, set()) for cp in cps))
            src = set()
            for s in base(conns[ip]):
                src |= {net(c) for c in dom.get(s, set())}
            if src and u and not (src & u):
                crossings.append((f, ln, name, inst, child, ip, conns[ip].strip(), sorted(src), sorted(u)))
                continue
            # an input synchronizer clocked by another clock than the one that samples its output
            ssrc = set()
            for s in base(conns[ip]):
                ssrc |= {net(c) for c in sdom.get(s, set())}
            if ssrc and u and not (ssrc & u):
                crossings.append((f, ln, name, inst, child, ip, conns[ip].strip(),
                                  ["sync@" + c for c in sorted(ssrc)], sorted(u)))
    return summary, crossings


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    up = Path(sys.argv[1]) / "fpga"
    ip = sorted((up / "nv_hsb_ip").rglob("*.sv")) + sorted((up / "nv_hsb_ip").rglob("*.v"))
    tops = sorted(up.glob("*/*/*/rtl/top/FPGA_top.sv")) + sorted(up.glob("*/*/rtl/top/FPGA_top.*v"))
    files = [f for f in ip + tops if "simple_tb" not in str(f)]
    mods = P.parse_modules(files)
    insts = P.parse_instances(files, mods)
    body = bodies(files)
    summ = {m: {"clk": set(), "out": {}, "use": {}} for m in mods}
    for _ in range(6):                       # bottom-up by repetition (hierarchy depth < 6)
        new, cross = {}, []
        for m in mods:
            if m in body:
                new[m], c = analyse(m, mods, body[m], insts, summ)
                cross += c
            else:
                new[m] = summ[m]
        if new == summ:
            break
        summ = new
    # board tops all use the module name FPGA_top: analyse each file on its own
    cross = [c for c in cross if c[2] != "FPGA_top"]
    for f in tops:
        t = C.strip(f.read_text(errors="replace"))
        m = re.search(r"\bmodule\s+(\w+)", t)
        if m:
            _, c = analyse(m.group(1), mods, (f, t[m.start():], 0), insts, summ)
            cross += c
    reviewed = set(reviewed_list.load("scan_cdc_ports"))
    seen, shown, n_rev = set(), [], 0
    for f, ln, parent, inst, child, port, expr, src, u in cross:
        rel = str(f).split("/fpga/", 1)[1]
        key = (rel if parent == "FPGA_top" else parent, f"{inst}.{port}")
        if key in seen:
            continue
        seen.add(key)
        rv = key in reviewed
        n_rev += rv
        if rv and "--all" not in sys.argv:
            continue
        rel = str(f).split("/fpga/", 1)[1]
        shown.append(f"  {'reviewed ' if rv else ''}{rel}:{ln} {parent}.{inst}.{port} <= {expr[:40]} "
                     f"({', '.join(src)} -> {', '.join(u)})")
    n_clk = sum(1 for s in summ.values() if len(s["clk"]) >= 2)
    print(f"modules: {len(mods)}; with two or more clock ports: {n_clk}; instances: {len(insts)}; "
          f"port crossings without a synchronizer module: {len(seen)}; reviewed by hand: {n_rev} "
          f"(tools/reviewed.txt); not reviewed: {len(seen) - n_rev}")
    print("\n".join(shown))
    return 1 if len(seen) - n_rev else 0


if __name__ == "__main__":
    sys.exit(main())
