#!/usr/bin/env python3
"""Registers the host never touches, and host address constants nothing uses.

1. Every register in docs/registers/all-registers.md (control, status, RAM windows count once
   per block entry) is looked for in the host software at the pinned commit:
     - named address constants resolved by tools/check_host_regs.py (src/hololink/core);
     - any 8-digit hex literal in src/, python/, examples/, hololink_module/ and tools/ (e.g. 0x0200_0020, 0x70000014);
     - for SPI, I2C and UART, the offsets the helper classes add to their base
       (`reg_status_(i2c_address + 0x80)`, `UART + UART_STATUS0`);
     - register arrays indexed at run time (`GPIO_STATUS_BASE_REGISTER + (pin / 32) * 4`).
   Per-instance blocks are folded to instance 0 (strides of check_host_regs.py).
   The registers found in none of these are listed per block, split into RW and RO.
2. Every host address constant from check_host_regs.py that appears only in its own
   definition (no other use in those directories) is listed.

The lists are for reading by hand: a register the host never writes runs at its reset value
(the Reset column of all-registers.md), and one it never reads is invisible to software.

Usage:  python3 tools/check_unused.py <path-to-holoscan-sensor-bridge>
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_host_regs as C  # noqa: E402

HELPERS = {  # block title in all-registers.md -> base variable used by the helper class
    "SPI": "spi_address", "I2C": "i2c_address", "UART": "UART",
}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    up = Path(sys.argv[1])
    regs = C.rtl_index()
    text = (C.ROOT / "docs/registers/all-registers.md").read_text()
    kind = {}
    for m in re.finditer(r"^\| `0x([0-9A-F_]+)` \| \[?`([^`]+)`(?:\]\([^)]*\))? \| (\S+) \|", text, re.M):
        kind[int(m.group(1).replace("_", ""), 16)] = m.group(3)
    rows, _, _ = C.host_rows(up)
    hit = set()
    for _, _, addr, h in rows:
        if h:
            hit.add(h)
    files = [p for d in ("src", "python", "examples", "hololink_module", "tools") for p in (up / d).rglob("*")
             if p.suffix in (".cpp", ".hpp", ".py", ".h")]
    texts = {p: p.read_text(errors="replace") for p in files}
    for t in texts.values():
        for m in re.finditer(r"\b0x([0-9A-Fa-f]{4}_?[0-9A-Fa-f]{4})\b", t):
            h = C.lookup(regs, int(m.group(1).replace("_", ""), 16))
            if h:
                hit.add(h)
    core = texts[up / "src/hololink/core/hololink.cpp"] + texts[up / "src/hololink/core/hololink.hpp"]
    consts = C.parse_consts(core)
    for title, var in HELPERS.items():
        base = [a for a, (n, t) in regs.items() if t == title]
        if not base:
            continue
        b0 = min(base)
        offs = {int(x, 16) for x in re.findall(var + r"\s*\+\s*(0x[0-9A-Fa-f]+|\d+)", core) if x.startswith("0x")}
        offs |= {int(x) for x in re.findall(var + r"\s*\+\s*(\d+)\b", core)}
        if var == "UART":
            offs |= {v for k, v in consts.items() if k.startswith("UART_") and "STRIDE" not in k and v < 0x200}
        for o in offs:
            h = C.lookup(regs, b0 + o)
            if h:
                hit.add(h)
    # register arrays indexed at run time: <BASE> + (index) * <step>, every element counts as touched
    for m in re.finditer(r"(\w+)\s*\+\s*\(\(?\s*\w+\s*/\s*32\s*\)?\s*\*\s*(\w+)\s*\)", core):
        if m.group(1) in consts and m.group(2) in consts:
            for k in range(8):
                h = C.lookup(regs, consts[m.group(1)] + k * consts[m.group(2)])
                if h:
                    hit.add(h)
    by_block = defaultdict(lambda: {"RW": [], "RO": []})
    n_rw = n_ro = 0
    for a, (n, t) in sorted(regs.items()):
        if (n, t) in hit:
            continue
        k = "RO" if kind.get(a, "RW") == "RO" else "RW"
        by_block[t][k].append(n)
        n_rw += k == "RW"
        n_ro += k == "RO"
    print(f"registers in the index: {len(regs)}; touched by the host: {len(regs) - n_rw - n_ro}; "
          f"never touched: {n_rw} control (RW / W), {n_ro} status (RO)")
    for t, d in by_block.items():
        for k in ("RW", "RO"):
            if d[k]:
                print(f"  {t} {k}: {', '.join(d[k])}")

    uses = "\n".join(texts.values())
    dead = []
    for f, n, addr, h in rows:
        if len(re.findall(r"\b" + n + r"\b", uses)) <= 1:
            dead.append(f"  {Path(f).name}: {n} = 0x{addr:08X}" + (f" (`{h[0]}`)" if h else ""))
    print(f"\nhost address constants: {len(rows)}; defined but never used: {len(dead)}")
    print("\n".join(dead))
    return 0


if __name__ == "__main__":
    sys.exit(main())
