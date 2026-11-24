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

Usage:  python3 tools/check_host_regs.py <path-to-holoscan-sensor-bridge>
Exit code 1 only if a constant cannot be parsed.
"""
import re
import sys
from pathlib import Path

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
    for m in re.finditer(r"^\| `0x([0-9A-F_]+)` \| `([^`]+)` \| (\S+) \| \[([^\]]+)\]", part, flags=re.M):
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


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    up = Path(sys.argv[1]) / "src/hololink"
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
