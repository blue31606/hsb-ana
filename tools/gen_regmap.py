#!/usr/bin/env python3
"""Generate docs/registers/regmap.md from HSB regmap_pkg.sv.

The script reads the register index constants in regmap_pkg.sv, computes the
byte offset (index * 4), and compares it with the address written in the
source comment. A mismatch is flagged in the output table.

Base addresses are not in regmap_pkg.sv. They come from the apb_switch
configuration in apb_intc_top.sv and are cross-checked against the host
software constants in src/hololink/core/hololink.hpp (see BASES below).

Usage:
  python3 tools/gen_regmap.py <path-to-holoscan-sensor-bridge> > docs/registers/regmap.md
"""
import re
import sys
from pathlib import Path

COMMIT = "41cecaa81ab906a55e7ec22e5e6989f7e602a4c8"
SRC = "fpga/nv_hsb_ip/reg_map/regmap_pkg.sv"
URL = f"https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/{COMMIT}/{SRC}"

# section title in regmap_pkg.sv -> (base address text, instance stride text, RTL module, evidence)
BASES = {
    "Global Register": ("0x0000_0000", "-", "glb_ctrl_top", "HSB_IP_VERSION = 0x80"),
    "PTP Register": ("0x0000_0100", "-", "ptp_top", "FPGA_PTP_CTRL = 0x104"),
    "Control Bus Event": ("0x0000_0200", "-", "ctrl_bus_evt_int", "CTRL_EVENT = 0x0000'0200"),
    "ECB": ("0x0000_0300", "-", "ecb_rdwr_ctrl", "apb_intc_top u_apb_switch_glb port 3"),
    "Instruction Decoder Registers": ("0x0200_0000", "0x1_0000 / host", "rx_parser", "apb_intc_top host level"),
    "Ethernet Packet": ("0x0200_0100", "0x1_0000 / host", "eth_pkt", "apb_intc_top host level"),
    "Dataplane Packetizer": ("0x0200_0300", "0x1_0000 / host", "dp_pkt_top", "apb_intc_top host level"),
    "Packetizer Register": ("0x0100_0000", "0x1_0000 / SIF RX", "packetizer_top", "enumerator.cpp sif_address"),
    "Sensor RX Data Generator": ("0x0100_0100", "0x1_0000 / SIF RX", "data_gen", "apb_intc_top sensor level"),
}

SECTION_RE = re.compile(r"^//-+//\s*$")
TITLE_RE = re.compile(r"^//\s*(\S.*?)\s*$")
PARAM_RE = re.compile(r"localparam\s+(\w+)\s*=\s*(\d+)\s*;\s*(?://\s*(.*))?$")
ADDR_RE = re.compile(r"0x([0-9A-Fa-f_]+)")


def parse(text):
    lines = text.splitlines()
    sections, cur = [], None
    for i, line in enumerate(lines):
        s = line.strip()
        if SECTION_RE.match(s) and i + 2 < len(lines) and SECTION_RE.match(lines[i + 2].strip()):
            m = TITLE_RE.match(lines[i + 1].strip())
            if m:
                cur = {"title": m.group(1), "line": i + 2, "regs": [], "n": {}}
                sections.append(cur)
            continue
        if cur is None:
            continue
        m = PARAM_RE.search(s)
        if not m:
            continue
        name, val, comment = m.group(1), int(m.group(2)), (m.group(3) or "")
        if name.endswith("_nctrl") or name.endswith("_nstat"):
            cur["n"][name[-5:]] = val
            continue
        cur["regs"].append((name, val, comment, i + 1))
    return [s for s in sections if s["title"] in BASES]


def main(root):
    text = (Path(root) / SRC).read_text(encoding="utf-8")
    out = [
        "# 暫存器表（自動產生）",
        "",
        f"本檔由 `tools/gen_regmap.py` 從 [`regmap_pkg.sv`]({URL}) 產生，請勿手動修改。",
        "",
        "- **Offset** = index × 4，是程式實際使用的值。",
        "- **註解位址** 是原始碼註解裡寫的位址。兩者不同時標記 ⚠️。",
        "- index ≥ 32 的是唯讀狀態暫存器（`stat_ofst = 32`）。",
        "- 基底位址取自 `apb_intc_top.sv` 的 `apb_switch` 設定，並用 host 軟體常數交叉確認（見各表的「佐證」）。",
        "",
    ]
    mismatches = []
    for sec in parse(text):
        base, stride, module, evidence = BASES[sec["title"]]
        out += [
            f"## {sec['title']}",
            "",
            f"| 項目 | 值 |",
            f"|---|---|",
            f"| RTL 模組 | `{module}` |",
            f"| 基底位址 | `{base}` |",
            f"| 實例間距 | {stride} |",
            f"| 控制暫存器數 / 狀態暫存器數 | {sec['n'].get('nctrl', '?')} / {sec['n'].get('nstat', '?')} |",
            f"| 佐證 | {evidence} |",
            f"| 原始碼 | [regmap_pkg.sv#L{sec['line']}]({URL}#L{sec['line']}) |",
            "",
            "| Index | 名稱 | 類型 | Offset | 註解位址 | 註解 |",
            "|---:|---|---|---|---|---|",
        ]
        for name, idx, comment, line in sec["regs"]:
            off = idx * 4
            kind = "RO" if idx >= 32 else "RW"
            m = ADDR_RE.search(comment)
            caddr, flag = "", ""
            if m:
                cval = int(m.group(1).replace("_", ""), 16)
                caddr = f"`0x{cval:04X}`"
                if cval != off:
                    flag = " ⚠️"
                    mismatches.append((sec["title"], name, off, cval, line))
            rest = ADDR_RE.sub("", comment).strip(" /")
            out.append(f"| {idx} | [`{name}`]({URL}#L{line}) | {kind} | `0x{off:04X}` | {caddr}{flag} | {rest} |")
        out.append("")
    out += ["## 註解與程式不一致的項目", ""]
    if mismatches:
        out += ["| 區塊 | 名稱 | 實際 offset | 註解位址 |", "|---|---|---|---|"]
        for t, n, off, c, line in mismatches:
            out.append(f"| {t} | [`{n}`]({URL}#L{line}) | `0x{off:04X}` | `0x{c:04X}` |")
    else:
        out.append("沒有。")
    out.append("")
    sys.stdout.write("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../holoscan-sensor-bridge")
