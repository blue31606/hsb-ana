#!/usr/bin/env python3
"""Board configuration table from each board's HOLOLINK_def.svh, compared with docs/boards.md.

Runs a small preprocessor over every board's HOLOLINK_def.svh (`define / `ifdef / `ifndef /
`else / `endif, // comments removed; nothing is defined from outside, so JESD_HIGH_PERF on
the S10 takes its `else branch), reads the defines and the SIF localparam arrays, and builds
the rows of the "設定比較" table in docs/boards.md. Each generated cell is compared with the
cell in the doc; rows that the doc does not have are reported too.

Usage:  python3 tools/gen_board_table.py <path-to-holoscan-sensor-bridge> [--write]
  --write  replace the generated rows in docs/boards.md (the hand-written rows 目錄, FPGA,
           是否含 HOLOLINK_top and Ethernet are kept) and add missing rows at the end of the table
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "boards.md"

# Column order of the table in docs/boards.md; None = board without HOLOLINK_top.
BOARDS = [
    ("Lattice CPNX100", "lattice/cpnx100-eth-sensor-bridge/cpnx100/rtl/top/HOLOLINK_def.svh"),
    ("Lattice CLNX17", None),
    ("Microchip MPF200", "microchip/mfp200-eth-sensor-bridge/rtl/MAC_Hololink/HOLOLINK_def.svh"),
    ("NV MIPI 參考", "nv_mipi_ref_design/mipi_cpnx_ref_design/rtl/top/HOLOLINK_def.svh"),
    ("PYNQ RFSoC", "pynq/rfsoc-pynq/rtl/top/HOLOLINK_def.svh"),
    ("Terasic S10", "terasic/s10_sensor_bridge/rtl/top/HOLOLINK_def.svh"),
]


def preprocess(text):
    """Return (defines, active lines) for a file with only local `define / `ifdef."""
    defs, out, stack = {}, [], []          # stack: (parent active, condition of this level)
    for raw in text.splitlines():
        line = re.sub(r"//.*", "", raw).strip()
        active = all(p and c for p, c in stack)
        m = re.match(r"`(ifdef|ifndef)\s+(\w+)", line)
        if m:
            cond = (m.group(2) in defs) == (m.group(1) == "ifdef")
            stack.append((active, cond))
            continue
        if line.startswith("`else"):
            p, c = stack.pop()
            stack.append((p, not c))
            continue
        if line.startswith("`endif"):
            stack.pop()
            continue
        if not active:
            continue
        m = re.match(r"`define\s+(\w+)\s*(.*)", line)
        if m:
            defs[m.group(1)] = m.group(2).strip().rstrip(";")
            continue
        out.append(line)
    return defs, out


def value(defs, s):
    s = s.strip()
    for _ in range(5):
        s = re.sub(r"`(\w+)", lambda m: defs.get(m.group(1), m.group(0)), s)
    try:
        return int(eval(s.replace("'", ""), {}))
    except Exception:
        return s


def array(defs, lines, name):
    for ln in lines:
        m = re.search(r"\b" + name + r"\s*\[[^\]]*\]\s*=\s*(.*?);", ln)
        if m:
            rhs = m.group(1).strip()
            d = re.match(r"'\{\s*default\s*:\s*(.*)\}", rhs)
            if d:
                return ("all", value(defs, d.group(1)))
            items = [value(defs, x) for x in rhs.strip("'{} ").split(",")]
            return ("list", items)
    return None


def mhz(v):
    return (f"{v / 1e6:.2f}".rstrip("0").rstrip(".") + " MHz") if isinstance(v, int) else ""


def board_rows(up):
    cols = []
    for _, rel in BOARDS:
        if rel is None:
            cols.append({})
            continue
        defs, lines = preprocess((up / rel).read_text(errors="replace"))
        dp = value(defs, defs.get("DATAPATH_WIDTH", "0"))
        n_rx = value(defs, defs["SENSOR_RX_IF_INST"]) if "SENSOR_RX_IF_INST" in defs else 0
        n_tx = value(defs, defs["SENSOR_TX_IF_INST"]) if "SENSOR_TX_IF_INST" in defs else 0
        c = {}
        c["`HIF_CLK_FREQ`"] = mhz(value(defs, defs["HIF_CLK_FREQ"]))
        for k in ("HOST_WIDTH", "HOST_IF_INST", "HOST_MTU"):
            c[f"`{k}`"] = str(value(defs, defs[k]))
        c["`SENSOR_RX_IF_INST`"] = str(n_rx) if n_rx else ""
        w = array(defs, lines, "SIF_RX_WIDTH") if n_rx else None
        ws = [] if not w else ([w[1]] if w[0] == "all" else w[1])
        c["`SIF_RX_WIDTH`"] = "" if not ws else (str(ws[0]) if len(set(ws)) == 1
                                                 else "{" + ", ".join(map(str, ws)) + "}")
        p = array(defs, lines, "SIF_RX_PACKETIZER_EN") if n_rx else None
        if not p:
            c["packetizer"] = ""
        else:
            vals = [p[1]] if p[0] == "all" else p[1]
            c["packetizer"] = ("開" if vals[0] else "關") if len(set(vals)) == 1 else "{" + ", ".join(map(str, vals)) + "}"
        if n_tx:
            tw = array(defs, lines, "SIF_TX_WIDTH")
            tws = [tw[1]] if tw[0] == "all" else tw[1]
            c["`SENSOR_TX_IF_INST`"] = str(n_tx) + (f"（{tws[0]}-bit）" if set(tws) != {dp} else "")
            b = array(defs, lines, "SIF_TX_BUF_SIZE")
            bs = [b[1]] if b[0] == "all" else b[1]
            c["`SIF_TX_BUF_SIZE`"] = " / ".join(map(str, sorted(set(bs))))
        else:
            c["`SENSOR_TX_IF_INST`"] = ""
            c["`SIF_TX_BUF_SIZE`"] = ""
        for k in ("SIF_RX_DATA_GEN", "DISABLE_COE", "ENUM_EEPROM"):
            c[f"`{k}`"] = "✓" if k in defs else ""
        c["`APB_CLK_FREQ`"] = mhz(value(defs, defs["APB_CLK_FREQ"]))
        c["`PTP_CLK_FREQ`"] = mhz(value(defs, defs["PTP_CLK_FREQ"]))
        c["`DATAPATH_WIDTH`"] = str(dp)
        c["`DATAUSER_WIDTH`"] = str(value(defs, defs["DATAUSER_WIDTH"]))
        for k in ("SPI_INST", "I2C_INST", "UART_INST", "GPIO_INST", "REG_INST", "N_INIT_REG"):
            c[f"`{k}`"] = str(value(defs, defs[k])) if k in defs else ""
        cols.append(c)
    keys = list(next(c for c in cols if c).keys())
    return keys, cols


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    up = Path(sys.argv[1]) / "fpga"
    keys, cols = board_rows(up)
    lines = DOC.read_text().split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith("| |") and "CPNX100" in l)
    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    doc_rows = {}
    for i in range(start + 2, end):
        cells = [x.strip() for x in lines[i].strip().strip("|").split("|")]
        doc_rows[cells[0]] = (i, cells[1:])
    gen = {k: [c.get(k, "") for c in cols] for k in keys}
    n_cells = n_bad = 0
    missing = []
    for k in keys:
        if k not in doc_rows:
            missing.append(k)
            continue
        _, have = doc_rows[k]
        for (name, _), want, got in zip(BOARDS, gen[k], have):
            n_cells += 1
            if want != got:
                n_bad += 1
                print(f"MISMATCH {k:22s} {name:18s} doc '{got}'  HOLOLINK_def.svh '{want}'")
    print(f"rows generated: {len(keys)}; in doc: {len(keys) - len(missing)}; "
          f"cells compared: {n_cells}; mismatches: {n_bad}; rows missing from doc: {len(missing)}")
    for k in missing:
        print(f"  missing row {k}: " + " | ".join(gen[k]))
    if "--write" in sys.argv:
        for k in keys:
            row = "| " + " | ".join([k] + gen[k]) + " |"
            while "|  |" in row:
                row = row.replace("|  |", "| |")
            if k in doc_rows:
                lines[doc_rows[k][0]] = row
            else:
                lines.insert(end, row)
                end += 1
        DOC.write_text("\n".join(lines))
        print("docs/boards.md updated")
    return 1 if (n_bad or missing) and "--write" not in sys.argv else 0


if __name__ == "__main__":
    sys.exit(main())
