#!/usr/bin/env python3
"""Cross-check the register addresses the host software uses against the RTL register index.

Parses named address constants from the host software at the pinned commit
(src/hololink/core/*.hpp, *.cpp), turns base + offset groups into absolute addresses,
and looks each one up in docs/registers/all-registers.md (generated from the RTL by
tools/gen_allregs.py). Per-instance blocks are matched through their stride (host blocks
0x1_0000 per host, Data Plane VP RAM 0x40 per VP, SIF blocks 0x1_0000 per SIF).

Output per constant: host name, address, and the RTL register found there (or MISSING).
A MISSING address is not automatically a bug (board-level registers outside HOLOLINK_top
are not in the index); the script lists them so they can be read by hand.

With --bits it checks values instead of addresses: every `write_uint32(<address>, <value>)`
in src/hololink whose value is a literal or resolves through constexpr / const / #define
constants is compared with the bits the RTL reads from that register. RTL bits are collected
for the registers named in reg_map/regmap_pkg.sv: `<array>[<name>][hi:lo]`, `[bit]`, or the
whole word when used without a slice. Writes of 0 are skipped. --table also prints the RTL
bits used for every host constant that maps to a regmap register.

With --reads it checks the other direction: for every host read_uint32() of a register whose
result is tested with a mask (`value & MASK`, also on a later line, or `read_uint32(..) & MASK`),
the bits tested are compared with the bits the RTL can drive (`assign stat_reg[..] = ..`;
a constant 0 counts as never driven). Address parameters of helper classes are resolved
through their constructor initializers, instance 0; a status word captured by the APB event
sequencer is traced back to the register the sequencer read.

Usage:  python3 tools/check_host_regs.py <path-to-holoscan-sensor-bridge> [--bits | --reads] [--table]
Exit code 1 only if a constant cannot be parsed.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reviewed as reviewed_list  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# (file, base expression or None for absolute, regex of constant names)
GROUPS = [
    ("core/hololink.hpp", None,
     r"^(SPI_CTRL|I2C_CTRL|HSB_IP_VERSION|FPGA_DATE|FPGA_PTP_(CTRL|DELAY_ASYMMETRY|CTRL_DPLL_CFG1|"
     r"CTRL_DPLL_CFG2|CTRL_DELAY_AVG_FACTOR|SYNC_TS_0|SYNC_STAT|OFM|PROFILE|DOMAIN)|"
     r"FPGA_SENSOR_VP_VLAN_BASE|FPGA_EVT_VLAN|VSYNC_\w+|CTRL_EVENT|CTRL_EVT_\w+|APB_RAM)$"),
    ("core/hololink.hpp", "I2C_CTRL", r"^I2C_REG_\w+$"),
    ("core/hololink.cpp", "UART", r"^UART_(CTRL[0-4]|STATUS[01]|TX_DATA|RX_DATA|LAST_RX)$"),
    ("core/hololink.cpp", None, r"^I2S_CLOCK_CTRL$"),
    ("core/hololink.cpp", "I2S_APB", r"^I2S_(CTRL[0-8]|STAT[0-3])$"),
    ("core/hololink.cpp", "I2S_TX_FIFO", r"^I2S_TX_FIFO_(CTRL|ALMOST_FULL|ALMOST_EMPTY|PAUSE_LATCH)$"),
    ("core/hololink.cpp", "0", r"^GPIO_(OUTPUT|DIRECTION|STATUS)_BASE_REGISTER$"),
    ("core/data_channel.hpp", "0x02000300", r"^DP_(PACKET_SIZE|PACKET_UDP_PORT|VP_MASK)$"),
    ("core/data_channel.hpp", "0x1000",
     r"^DP_(QP|RKEY|PAGE_LSB|PAGE_MSB|PAGE_INC|MAX_BUFF|BUFFER_LENGTH|HOST_MAC_LOW|HOST_MAC_HIGH|"
     r"HOST_IP|HOST_UDP_PORT|VLAN)$"),
    ("core/packetizer_program.cpp", "0x01000000", r"^PACKETIZER_(MODE|RAM|DATA)$"),
    ("core/jesd.hpp", None, r"^JESD_(RX|TX|XCVR|PLL|REG)_CTRL$"),
]
# Base addresses used by host code but defined at run time (enumerator.cpp):
#   vp_address  = 0x1000 + 0x40 * sensor           (enumerator.cpp L665)
#   hif_address = 0x02000300 + 0x10000 * data_plane (enumerator.cpp L693)
STRIDES = [(0x02000000, 0x02FFFFFF, 0x10000), (0x01000000, 0x012FFFFF, 0x10000),
           (0x1000, 0x17FF, 0x40)]


def parse_consts(text):
    consts = {}
    for m in re.finditer(r"constexpr\s+uint32_t\s+(\w+)\s*=\s*([^;]+);", text):
        name, expr = m.group(1), m.group(2).replace("'", "")
        expr = re.sub(r"\b0b([01]+)", lambda x: str(int(x.group(1), 2)), expr)
        expr = re.sub(r"(\d)u\b", r"\1", expr)
        try:
            consts[name] = int(eval(expr, {}, dict(consts)))
        except Exception:
            pass
    return consts


def rtl_index():
    regs = {}
    text = (ROOT / "docs/registers/all-registers.md").read_text()
    part = text.split("## 全部暫存器", 1)[1]
    for m in re.finditer(r"^\| `0x([0-9A-F_]+)` \| \[?`([^`]+)`(?:\]\([^)]*\))? \| (\S+) \| [^|]*\| \[([^\]]+)\]", part, flags=re.M):
        regs[int(m.group(1).replace("_", ""), 16)] = (m.group(2), m.group(4))
    return regs


def lookup(regs, addr):
    if addr in regs:
        return regs[addr]
    for lo, hi, stride in STRIDES:
        if lo <= addr <= hi:
            base = lo + ((addr - lo) % stride) if stride == 0x40 else addr - ((addr - lo) // stride) * stride
            if stride == 0x40:
                base = 0x1000 + (addr - 0x1000) % 0x40
            if base in regs:
                return regs[base]
    return None


def host_rows(up):
    """(file, constant, absolute address, (rtl name, block) or None) for every host constant."""
    up = Path(up) / "src/hololink"
    regs = rtl_index()
    allc = {}
    for f in sorted({g[0] for g in GROUPS}):
        allc[f] = parse_consts((up / f).read_text())
    rows, missing, bad = [], [], []
    for f, base, rx in GROUPS:
        c = allc[f]
        names = [n for n in c if re.match(rx, n)]
        if not names:
            bad.append(f"{f}: nothing matches {rx}")
        for n in names:
            if base is None:
                addr = c[n]
            else:
                b = int(base, 16) if base.startswith("0x") else (c[base] if base in c else int(base))
                addr = b + c[n]
            hit = lookup(regs, addr)
            rows.append((f, n, addr, hit))
            if hit is None:
                missing.append((f, n, addr))
    return rows, missing, bad


def rtl_bits(ip):
    pkg = (ip / "reg_map" / "regmap_pkg.sv").read_text()
    names = set(re.findall(r"localparam\s+(\w+)\s*=\s*\d+\s*;", pkg))
    used = {n: 0 for n in names}
    seen = {n: [] for n in names}
    for f in ip.rglob("*.sv"):
        if "simple_tb" in str(f) or f.name == "regmap_pkg.sv":
            continue
        t = re.sub(r"//.*", "", f.read_text(errors="replace"))
        for m in re.finditer(r"\w+\s*\[\s*(\w+)\s*\](\s*\[\s*(\d+)\s*(?::\s*(\d+))?\s*\])?", t):
            n = m.group(1)
            if n not in used:
                continue
            if m.group(2):
                hi = int(m.group(3))
                lo = int(m.group(4)) if m.group(4) is not None else hi
                hi, lo = max(hi, lo), min(hi, lo)
                used[n] |= ((1 << (hi - lo + 1)) - 1) << lo
            else:
                used[n] = 0xFFFFFFFF
            seen[n].append(f"{f.relative_to(ip)}:{t[:m.start()].count(chr(10)) + 1}")
    return used, seen


def host_consts(src):
    consts = {}
    for p in sorted(list(src.rglob("*.cpp")) + list(src.rglob("*.hpp"))):
        t = p.read_text(errors="replace")
        for m in re.finditer(r"(?:constexpr|const)\s+(?:static\s+)?(?:u?int\d+_t|int|unsigned)\s+(\w+)\s*(?:=|\{)\s*([^;}]+)", t):
            consts.setdefault(m.group(1), m.group(2).strip())
        for m in re.finditer(r"#define\s+(\w+)\s+\(?([0-9xXa-fA-FuUlL <|()]+)\)?\s*$", t, re.M):
            consts.setdefault(m.group(1), m.group(2))
    return consts


def evaluate(expr, consts, depth=0):
    if depth > 6:
        return None
    e = re.sub(r"\b([A-Za-z_]\w*)\b",
               lambda m: "(" + str(evaluate(consts[m.group(1)], consts, depth + 1)) + ")"
               if m.group(1) in consts else m.group(0), expr.strip())
    e = re.sub(r"(0x[0-9a-fA-F]+|\b\d+)[uUlL]+\b", r"\1", e)
    if re.search(r"[A-Za-z_]", re.sub(r"0x[0-9a-fA-F]+", "", e)):
        return None
    try:
        return int(eval(e, {}))
    except Exception:
        return None


def check_bits(up, argv):
    used, seen = rtl_bits(up / "fpga" / "nv_hsb_ip")
    rows, _, _ = host_rows(up)
    name2reg = {n: hit[0] for _, n, _, hit in rows if hit}
    consts = host_consts(up / "src" / "hololink")
    n_writes = n_judged = 0
    flagged = []
    for p in sorted((up / "src" / "hololink").rglob("*.cpp")):
        t = p.read_text(errors="replace")
        for m in re.finditer(r"write_uint32\(\s*([^,;]+?)\s*,\s*([^,;]+?)\s*[,)]", t):
            addr_expr, val_expr = m.group(1), m.group(2)
            val = evaluate(val_expr, consts)
            if val is None:
                continue
            n_writes += 1
            ids = [i for i in re.findall(r"\b[A-Z][A-Z0-9_]+\b", addr_expr) if i in name2reg]
            if not ids or val == 0:
                continue
            reg = name2reg[ids[-1]]
            if reg not in used:
                continue
            n_judged += 1
            extra = val & ~used[reg] & 0xFFFFFFFF
            if extra:
                line = t[:m.start()].count("\n") + 1
                flagged.append(f"  {p.relative_to(up)}:{line}  {ids[-1]} = {val_expr.strip()} (0x{val:08X}) -> "
                               f"`{reg}`; RTL uses 0x{used[reg]:08X}; extra bits 0x{extra:08X}")
    print(f"constant host writes: {n_writes}; judged against a regmap register (non-zero): {n_judged}; "
          f"setting bits the RTL never reads: {len(flagged)}")
    print("\n".join(flagged))
    if "--table" in argv:
        print("\nhost constant -> regmap register: RTL bits used")
        for f, n, addr, hit in rows:
            if hit and hit[0] in used:
                print(f"  {n:34s} 0x{addr:08X} `{hit[0]}` 0x{used[hit[0]]:08X}  {', '.join(seen[hit[0]][:2])}")
    return 0

# ---- --reads: bits the host tests on status registers vs bits the RTL drives ----
# Address parameters of host helper classes, set to instance 0 (checked by hand).
HOST_BASE_VARS = {"spi_address": 0x0300_0000, "i2c_address": 0x0300_0200,
                  "port_number": 0, "bus_number": 0, "i2c_bus": 0, "spi_bus": 0}


def rtl_status_bits(ip):
    """{(file stem, status index or register name): mask of bits that can be non-zero}."""
    out = {}
    zero = re.compile(r"^(?:'0|'\{\s*default\s*:\s*0\s*\}|\d*'[hdb]0+|0)$")
    for f in ip.rglob("*.sv"):
        if "simple_tb" in str(f):
            continue
        t = re.sub(r"//.*", "", f.read_text(errors="replace"))
        for m in re.finditer(r"assign\s+stat_reg\s*\[\s*([^\]]+?)\s*\]\s*(?:\[\s*(\d+)\s*(?::\s*(\d+))?\s*\])?\s*=\s*([^;]+);", t):
            idx, hi, lo, rhs = m.group(1), m.group(2), m.group(3), m.group(4).strip()
            n = re.match(r"(\w+)\s*-\s*stat_ofst$", idx)
            key = (f.stem, n.group(1) if n else (int(idx) if idx.isdigit() else idx))
            if zero.match(rhs):
                out.setdefault(key, 0)
                continue
            if hi is not None:
                lo_ = int(lo) if lo is not None else int(hi)
                mask = ((1 << (int(hi) - lo_ + 1)) - 1) << lo_
            else:
                mask = 0xFFFFFFFF
                c = re.match(r"\{\s*(\d+)'[dhb]0+\s*,", rhs)
                sl = re.fullmatch(r"\w+\s*\[\s*(\d+)\s*:\s*(\d+)\s*\]", rhs)
                if c:
                    mask = (1 << (32 - int(c.group(1)))) - 1
                elif sl:
                    mask = (1 << (int(sl.group(1)) - int(sl.group(2)) + 1)) - 1
            out[key] = out.get(key, 0) | mask
    return out


def check_reads(up, argv):
    src = Path(up) / "src/hololink"
    ip = Path(up) / "fpga/nv_hsb_ip"
    regs = rtl_index()
    text = (ROOT / "docs/registers/all-registers.md").read_text()
    module_of = dict((t, m) for t, m in re.findall(r"^\| `0x[0-9A-F_]+` \| \[([^\]]+)\]\([^)]*\) \| `(\w+)` \|", text, re.M))
    first_ro = {}
    for a, (n, t) in sorted(regs.items()):
        pass
    for m in re.finditer(r"^\| `0x([0-9A-F_]+)` \| \[?`([^`]+)`(?:\]\([^)]*\))? \| RO \| [^|]*\| \[([^\]]+)\]", text, re.M):
        a = int(m.group(1).replace("_", ""), 16)
        first_ro.setdefault(m.group(3), a)
    driven = rtl_status_bits(ip)
    consts = {}
    for f in sorted(list(src.rglob("*.hpp")) + list(src.rglob("*.cpp"))):
        consts.update({k: v for k, v in parse_consts(f.read_text(errors="replace")).items() if k not in consts})
    consts.update(HOST_BASE_VARS)
    n_sites = n_judged = n_rev = 0
    rows, flagged = [], []
    reviewed = set(reviewed_list.load("check_host_reads"))
    for f in sorted(src.rglob("*.cpp")):
        t = f.read_text(errors="replace")
        L = t.split("\n")
        inits = []                    # (position, member, expression); the last one before a read wins
        for m in re.finditer(r"[,:]\s*(\w+_)\s*\(\s*([^()]*)\)", t):
            inits.append((m.start(), m.group(1), m.group(2)))
        for m in re.finditer(r"\b(\w+_)\s*=\s*([^;=]+);", t):
            inits.append((m.start(), m.group(1), m.group(2)))
        inits.sort()
        pos = [0]
        for ln in L:
            pos.append(pos[-1] + len(ln) + 1)
        for i, line in enumerate(L):
            m = re.search(r"(?:(\w+)\s*=\s*)?(?:[\w.]+(?:\.|->))?read_uint32\(\s*([^,()]+(?:\([^()]*\))?)\s*[,)](.*)", line)
            if not m or "fmt" in line or "HSB_LOG" in line or "uint32_t Hololink::" in line:
                continue
            var, aexpr, tail = m.group(1), m.group(2).strip(), m.group(3)
            e = aexpr
            for _ in range(3):                # local alias (status_cache = reg_status_) or member init
                if not re.fullmatch(r"\w+", e) or e in consts:
                    break
                local = [re.search(r"\b" + e + r"\s*=\s*([^;=]+);", x) for x in L[max(0, i - 60):i]]
                local = [x.group(1) for x in local if x]
                if local:
                    e = local[-1].strip()
                    continue
                cand = [ex for p_, mem, ex in inits if p_ < pos[i] and mem == e]
                if not cand:
                    break
                e = cand[-1]
            e = re.sub(r"\b([A-Za-z_]\w*)\b", lambda x: str(consts[x.group(1)]) if x.group(1) in consts else x.group(0), e)
            if "sequencer" in e:
                # a status word captured by the APB event sequencer and read back from its RAM:
                # use the register the sequencer read (sequencer.read_uint32(<reg>, ...)) nearby
                near = [re.search(r"sequencer\.read_uint32\(\s*(\w+)", x) for x in L[max(0, i - 200):i + 200]]
                near = [x.group(1) for x in near if x]
                if near:
                    cand = [ex for p_, mem, ex in inits if p_ < pos[i] and mem == near[0]]
                    e = cand[-1] if cand else near[0]
            e = re.sub(r"\b([A-Za-z_]\w*)\b", lambda x: str(consts[x.group(1)]) if x.group(1) in consts else x.group(0), e)
            try:
                addr = int(eval(e, {}))
            except Exception:
                continue
            hit = lookup(regs, addr)
            if not hit:
                continue
            name, title = hit
            n_sites += 1
            used = 0
            d = re.search(r"\)\s*&\s*(0x[0-9A-Fa-f]+|\w+)", ")" + tail)
            if d:
                used |= consts.get(d.group(1), 0) if not d.group(1).startswith("0x") else int(d.group(1), 16)
            if var:
                for nxt in L[i + 1:i + 31]:
                    if re.search(r"\b" + var + r"\s*=[^=]", nxt):
                        break
                    for k in re.finditer(r"\b" + var + r"\s*&\s*(\([^()]*\)|0x[0-9A-Fa-f]+|\w+)", nxt):
                        v = re.sub(r"\b([A-Za-z_]\w*)\b", lambda x: str(consts.get(x.group(1), x.group(1))), k.group(1))
                        try:
                            used |= int(eval(v, {}))
                        except Exception:
                            pass
            if not used:
                continue
            mod = module_of.get(title, "")
            if title in first_ro and re.match(r"[a-z_0-9]+$", name) and (mod, name) in driven:
                key = (mod, name)
            else:
                key = (mod, (addr - first_ro.get(title, addr)) // 4 if title in first_ro else None)
            for k2 in list(driven):
                if k2[1] == key[1] and k2[0].startswith(mod.split("_")[0]) and key not in driven:
                    key = k2
            mask = driven.get(key)
            where = f"{f.relative_to(Path(up))}:{i + 1}"
            rows.append(f"  {where:38s} `{name}` ({title}) host bits 0x{used:08X}; RTL can drive "
                        + (f"0x{mask:08X}" if mask is not None else "?"))
            if mask is not None:
                n_judged += 1
                if used & ~mask:
                    rv = (str(f.relative_to(Path(up))), f"{name}@{title}") in reviewed
                    n_rev += rv
                    if not rv:
                        flagged.append(f"  {where} `{name}`: host tests 0x{used & ~mask:08X}, RTL always drives 0 there")
    print(f"host register reads with a bit test: {len(rows)}; judged against RTL stat_reg assignments: "
          f"{n_judged}; testing bits the RTL never drives: {len(flagged) + n_rev} "
          f"({n_rev} reviewed by hand, tools/reviewed.txt)")
    print("\n".join(flagged))
    if "--table" in argv:
        print("\n".join(rows))
    return 1 if flagged else 0


def main():
    argv = sys.argv[1:]
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    if "--bits" in argv:
        return check_bits(Path(argv[0]), argv)
    if "--reads" in argv:
        return check_reads(Path(argv[0]), argv)
    rows, missing, bad = host_rows(argv[0])
    print(f"[RESULT] {len(rows)} host address constants, {len(rows) - len(missing)} found in the RTL index")
    for f, n, addr, hit in rows:
        tag = f"{hit[0]}  ({hit[1]})" if hit else "MISSING"
        print(f"        {Path(f).name:22s} {n:34s} 0x{addr:08X}  {tag}")
    for b in bad:
        print(f"[FAIL] {b}")
    print("\nFAILED: " + ("; ".join(bad) if bad else "none"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
