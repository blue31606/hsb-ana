#!/usr/bin/env python3
"""Bit-field check: constant values the host writes against the bits the RTL actually uses.

1. RTL side. For every register index named in reg_map/regmap_pkg.sv, collect the bit slices
   the RTL reads from it: `<array>[<name>][hi:lo]`, `<array>[<name>][bit]`, or the whole word
   when `<array>[<name>]` is used without a slice (counted as 32 bits). Only these registers
   are judged; registers of blocks with their own local register list are reported as "-".
2. Host side. Every `write_uint32(<address>, <value>)` in src/hololink whose value is a
   literal or resolves through constexpr / const / #define constants. The address expression
   is matched to a host constant through tools/check_host_regs.py (same address table).
3. A write is reported when it sets a bit the RTL never reads. Writes of 0 are skipped.

Usage:  python3 tools/check_host_bits.py <path-to-holoscan-sensor-bridge> [--table]
  --table  also print, for every host constant that maps to a regmap register, the RTL bits used
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_host_regs as C  # noqa: E402


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


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    up = Path(sys.argv[1])
    used, seen = rtl_bits(up / "fpga" / "nv_hsb_ip")
    rows, _, _ = C.host_rows(up)
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
    if "--table" in sys.argv:
        print("\nhost constant -> regmap register: RTL bits used")
        for f, n, addr, hit in rows:
            if hit and hit[0] in used:
                print(f"  {n:34s} 0x{addr:08X} `{hit[0]}` 0x{used[hit[0]]:08X}  {', '.join(seen[hit[0]][:2])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
