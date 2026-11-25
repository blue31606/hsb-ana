#!/usr/bin/env python3
"""Generate docs/registers/all-registers.md: every APB-visible register of HSB
with its absolute address (instance 0), in one table.

Registers listed in regmap_pkg.sv are parsed here (offset = index * 4); the
address written in each source comment is compared with it and mismatches are
listed at the end of the document. Blocks
that are not in regmap_pkg.sv (module-local registers, RAMs, peripherals,
reference-design modules) are listed in EXTRA below; their contents were taken
from the RTL by hand and are documented in the linked module documents.

Usage:
  python3 tools/gen_allregs.py <path-to-holoscan-sensor-bridge> > docs/registers/all-registers.md
"""
import re
import sys
from pathlib import Path

COMMIT = "41cecaa81ab906a55e7ec22e5e6989f7e602a4c8"
SRC = "fpga/nv_hsb_ip/reg_map/regmap_pkg.sv"
URL = f"https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/{COMMIT}/{SRC}"

# section title in regmap_pkg.sv -> (base address text, instance stride text, RTL module, evidence)
# Base addresses are not in regmap_pkg.sv: they come from the apb_switch settings in
# apb_intc_top.sv; the evidence column names the host constant or RTL setting checked.
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



DOC = {
    "Global Register": ("../modules/boot_and_reset.md#glb_ctrl_top", "1"),
    "PTP Register": ("../modules/ptp.md#暫存器", "1"),
    "Control Bus Event": ("../modules/event.md#暫存器", "1"),
    "ECB": ("../modules/rx_ls_parser.md#暫存器", "1"),
    "Instruction Decoder Registers": ("../modules/rx_parser.md#暫存器", "HOST_IF_INST"),
    "Ethernet Packet": ("../modules/eth_pkt.md#暫存器", "HOST_IF_INST"),
    "Dataplane Packetizer": ("../modules/dp_pkt_top.md#暫存器", "HOST_IF_INST"),
    "Packetizer Register": ("../modules/packetizer.md#暫存器", "SENSOR_RX_IF_INST"),
    "Sensor RX Data Generator": ("../modules/data_gen.md#暫存器", "SENSOR_RX_IF_INST"),
}

# (block title, base, stride / count, module, doc link, [(offset, name, type, description)])
EXTRA = [
    ("Data Plane 設定 RAM（APB RAM 0）", 0x0000_1000, "0x40 / VP（最多 32 個）", "dp_pkt_top",
     "../modules/dp_pkt_top.md#4-設定-ram", [
        (0x00, "DP_QP", "RW", "[23:0] dest QP（CoE：[5:0] channel）、[24] 1722B、[31:25] line 長度 log2"),
        (0x04, "DP_RKEY", "RW", "RETH R_Key"),
        (0x08, "DP_PAGE_LSB", "RW", "[31:7] buffer 起點（page）"),
        (0x0C, "DP_PAGE_MSB", "RW", "[0] 起點 page bit 25、[31:1] VA[63:33]"),
        (0x10, "DP_PAGE_INC", "RW", "buffer 間距（page）"),
        (0x14, "DP_MAX_BUFF", "RW", "[27:16] 起始 / [11:0] 結束 buffer 指標"),
        (0x18, "DP_BUFFER_LENGTH", "RW", "frame byte 數"),
        (0x20, "DP_HOST_MAC_LOW", "RW", "host MAC [31:0]"),
        (0x24, "DP_HOST_MAC_HIGH", "RW", "host MAC [47:32]"),
        (0x28, "DP_HOST_IP", "RW", "host IPv4"),
        (0x2C, "DP_HOST_UDP_PORT", "RW", "[15:0] UDP 埠、[16] md_disable"),
        (0x34, "DP_VLAN", "RW", "[15:0] TCI、[16] 插入 VLAN"),
        (0x3C, "PSN", "RW*", "FSM 回寫目前 PSN"),
    ]),
    ("事件序列 RAM（APB RAM 1）", 0x0000_2000, "1024 word", "ctrl_bus_evt_fsm",
     "../modules/event.md#2-序列器apb-時脈", [
        (0x000, "程式 / 資料", "RW", "每個事件一段序列：POLL / WRITE / READ / NOP；READ 結果寫回 RAM"),
    ]),
    ("RoCE QP RAM（APB RAM 2）", 0x0000_3000, "-", "roce_ack",
     "../modules/roce_ack.md", [
        (0x000, "QP 資訊", "RW", "SIF_TX_ROCE_RC_ENABLE 時使用；只有 host 0 的 RAM 回應讀取"),
    ]),
    ("SIF TX（tx_stream_buffer）", 0x0120_0000, "0x1_0000 / SENSOR_TX_IF_INST", "tx_stream_buffer",
     "../modules/tx_stream_buffer.md#暫存器", [
        (0x00, "ctrl", "RW", "[0] 輸出啟用、[1] pause、[2] 程式化門檻、[4] 統計 reset、[8] 除錯清空"),
        (0x04, "sw_almost_full_thresh", "RW", ""),
        (0x08, "sw_almost_empty_thresh", "RW", ""),
        (0x0C, "host_pause_mapping", "RW", "哪些 host 埠送 PAUSE"),
        (0x10, "pause_quanta", "RW", "[15:0]"),
        (0x80, "high_watermark", "RO", ""),
        (0x84, "low_watermark", "RO", ""),
        (0x88, "status", "RO", "[1] overflow、[0] underflow"),
    ]),
    ("SPI", 0x0300_0000, "-（SPI_INST 條匯流排共用）", "spi_ctrl_fsm",
     "../modules/peripherals.md#spi--qspi", [
        (0x00, "ctrl", "RW", "[0] start"),
        (0x04, "bus_en", "RW", "選擇匯流排"),
        (0x08, "len", "RW", "[15:0] 寫入 / [31:16] 讀取 byte 數"),
        (0x0C, "cfg", "RW", "[3:0] prescaler、[5:4] mode、[9:8] 資料線寬度"),
        (0x10, "cmd", "RW", "[7:0] turnaround、[15:8] 命令 byte 數"),
        (0x80, "status", "RO", "[0] busy、[1] 命令錯誤、[4] done"),
        (0x100, "data", "RW", "資料緩衝"),
    ]),
    ("I2C", 0x0300_0200, "-（I2C_INST 條匯流排共用）", "i2c_ctrl_fsm",
     "../modules/peripherals.md#i2c", [
        (0x00, "ctrl", "RW", "[0] start、[1] 10-bit 位址、[25:16] 裝置位址"),
        (0x04, "bus_en", "RW", "選擇匯流排"),
        (0x08, "len", "RW", "[15:0] 寫入 / [31:16] 讀取 byte 數"),
        (0x0C, "clk_cnt", "RW", "[15:0] SCL 分頻"),
        (0x10, "stretch_timeout", "RW", "reset 5,000,000"),
        (0x14, "num_trans", "RW", "[7:0]"),
        (0x80, "status", "RO", "[0] busy、[2] arbitration lost、[3] NACK、[4] done"),
        (0x100, "data", "RW", "資料緩衝"),
    ]),
    ("UART", 0x0300_0400, "-", "uart_ctrl_fsm",
     "../modules/peripherals.md#uart", [
        (0x00, "ctrl", "RW", "啟用、TX / RX、loopback、資料位元、parity、FIFO reset、stop bit"),
        (0x04, "baud / thresh", "RW", "[15:0] 鮑率除數、[23:16] / [31:24] TX FIFO 門檻"),
        (0x08, "int_en", "RW", ""),
        (0x0C, "int_clr", "RW", ""),
        (0x10, "glitch", "RW", "[3:0] 視窗寬度、[7:4] / [11:8] start / data 多數決門檻、[16] 濾波啟用"),
        (0x80, "status", "RO", ""),
        (0x84, "int_status", "RO", ""),
        (0x140, "tx_data", "W", "讀回：TX FIFO 滿時 0xFF"),
        (0x144, "rx_data", "RO", "讀取時彈出 RX FIFO"),
        (0x148, "last_rx", "RO", "最後收到的 byte（`ctrl[10]` 清除）"),
    ]),
    ("Bridge（BRIDGE_IF_INST）", 0x0600_0000, "-", "bridge_pkt_proc",
     "../modules/bridge.md#暫存器", [
        (0x00, "broadcast_ports", "RW", "[NUM_HOST-1:0] 廣播 / PTP 埠"),
        (0x04, "host0_fwd_mask", "RW", "index 2h+1：host h 可轉送的 host 埠"),
        (0x08, "host0_sub_mask", "RW", "index 2h+2：host h 訂閱的 SIF 埠"),
    ]),
    ("vsync_gen（CPNX100 使用者 APB）", 0x7000_0000, "-", "vsync_gen",
     "../modules/ref_design.md#vsync_gen", [
        (0x00, "VSYNC_CONTROL", "RW", "[0] 啟用"),
        (0x04, "VSYNC_FREQUENCY", "RW", "[3:0] 模式"),
        (0x08, "VSYNC_DELAY", "RW", "相對秒起點的延遲（ns）"),
        (0x0C, "VSYNC_START", "RW", "[0] 初始電位"),
        (0x10, "VSYNC_EXPOSURE", "RW", "脈衝寬度"),
        (0x14, "VSYNC_GPIO", "RW", "[9:0] GPIO 多工（host 的 `I2S_CLOCK_CTRL` 也寫這個位址）"),
    ]),
    ("delayed_io（CPNX100 使用者 APB）", 0x7000_0800, "-", "delayed_io",
     "../modules/ref_design.md#delayed_io", [
        (0x04, "delay_us", "RW", "延遲（µs），reset 1000"),
        (0x08, "set_now", "W", "立即設 1（位元遮罩）"),
        (0x0C, "clr_now", "W", "立即清 0（位元遮罩）"),
        (0x14, "set_delayed", "W", "延遲後設 1"),
        (0x18, "clr_delayed", "W", "延遲後清 0"),
        (0x20, "cancel", "W", "取消尚未執行的延遲操作"),
        (0x80, "out_state", "RO", "目前輸出狀態"),
        (0x84, "pending", "RO", "計數中的輸出"),
        (0xF0, "enable", "RW", "[0] 全域啟用"),
        (0xF8, "cycles_per_us", "RO", "除錯"),
    ]),
    ("i2s_top（CPNX100 使用者 APB）", 0x8000_0000, "-", "i2s_top",
     "../modules/ref_design.md#i2s_top", [
        (0x00, "CTRL0", "RW", "[0] TX、[1] RX 啟用"),
        (0x04, "CTRL1", "RW", "MCLK 分頻"),
        (0x08, "CTRL2", "RW", "BCLK 分頻代碼"),
        (0x0C, "CTRL3", "RW", "[1:0] 位元深度、[3:2] 格式"),
        (0x10, "CTRL4", "RW", "[0] mono、[2] loopback"),
        (0x14, "CTRL5", "RW", "RX 封包拍數"),
        (0x18, "CTRL6", "RW", "中斷啟用（未使用）"),
        (0x1C, "CTRL7", "RW", "LRCLK 極性"),
        (0x20, "CTRL8", "RW", "slot 模式"),
        (0x800, "STAT0", "RO", "locked（固定 1）；`W_OFST = 12`，狀態區從 0x800 開始"),
        (0x804, "STAT1", "RO", ""),
        (0x808, "STAT2", "RO", "[0] TX underrun、[1] RX overrun"),
        (0x80C, "STAT3", "RO", ""),
    ]),
]


# ---- reset values of s_apb_reg control registers (parameter RST_VAL) ----
def _strip(t):
    return re.sub(r"//.*", "", re.sub(r"/\*.*?\*/", "", t, flags=re.S))


def _split_top(body):
    items, depth, cur = [], 0, ""
    for ch in body:
        if ch in "{(":
            depth += 1
        elif ch in "})":
            depth -= 1
        if ch == "," and depth == 0:
            items.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        items.append(cur.strip())
    return items


def _num(tok, consts):
    tok = tok.strip()
    m = re.fullmatch(r"(\d+)?'([hdbHDB])([0-9a-fA-F_xXzZ]+)", tok)
    if m:
        base = {"h": 16, "d": 10, "b": 2}[m.group(2).lower()]
        return (int(m.group(1)) if m.group(1) else None), int(m.group(3).replace("_", ""), base)
    e = re.sub(r"\b([A-Za-z_]\w*)\b", lambda x: str(consts.get(x.group(1), x.group(1))), tok)
    return None, int(eval(e, {}))


# parameters of RST_VAL set from each board's HOLOLINK_def.svh (checked by hand)
BOARD_PARAM = {"GPIO_RST_VAL": "板級 `GPIO_RESET_VALUE`（S10 `0x0000000F`，其他 0）"}


def _concat_words(expr, consts):
    """Evaluate a {..} concatenation of reset values into {word index: value or label}."""
    expr = expr.strip()
    if not expr.startswith("{"):
        return None
    items = _split_top(expr[1:-1])
    words, pos = {}, 0
    for it in reversed(items):                  # LSB first
        if it in ("'0", "0"):
            break                               # fill: the rest is zero
        m = re.fullmatch(r"\{\s*\((.*)\)\s*\{\s*1'b0\s*\}\s*\}", it)
        if m:
            pos += _num(m.group(1), consts)[1]
            continue
        if re.fullmatch(r"[A-Za-z_]\w*", it):  # a parameter set by the board (GPIO_RST_VAL)
            words[pos // 32] = BOARD_PARAM.get(it, f"板級 `{it}`")
            pos += 32
            continue
        w, v = _num(it, consts)
        words[pos // 32] = v
        pos += w or 32
    return words


def reset_values(ip, module, consts):
    """{ctrl index: reset} for the s_apb_reg in <module>; {} when RST_VAL is left at '0; None if not s_apb_reg."""
    src = None
    for f in ip.rglob("*.sv"):
        if "simple_tb" in str(f):
            continue
        t = f.read_text(errors="replace")
        if re.search(r"^\s*module\s+" + module + r"\b", t, re.M):
            src = _strip(t)
            break
    if src is None or not re.search(r"(?<![\w.])s_apb_reg\s*#", src):
        return None
    inst = src[re.search(r"(?<![\w.])s_apb_reg\s*#", src).start():]
    m = re.search(r"\.RST_VAL\s*\(\s*(\w+)\s*\)", inst[:inst.find(");")])
    if not m:
        return {}
    name = m.group(1)
    pool = src + "\n".join(_strip(p.read_text(errors="replace")) for p in ip.rglob("*_pkg.sv"))
    d = re.search(r"localparam\s*\[[^\]]*\]\s*" + name + r"\s*=\s*", pool)
    if not d:
        return None
    rest = pool[d.end():]
    depth = 0
    for i, ch in enumerate(rest):
        depth += ch == "{"
        depth -= ch == "}"
        if depth == 0 and ch == "}":
            return _concat_words(rest[:i + 1], consts)
    return None


def fmt_reset(v):
    if v is None:
        return ""
    return v if isinstance(v, str) else f"`0x{v:08X}`"


def fmt(a):
    return f"0x{a >> 16:04X}_{a & 0xFFFF:04X}"


def main(root):
    text = (Path(root) / SRC).read_text(encoding="utf-8")
    out = [
        "# 完整暫存器索引（自動產生）",
        "",
        "本檔由 `tools/gen_allregs.py` 產生，請勿手動修改。",
        "",
        "所有 APB 可存取的暫存器依絕對位址排列（多實例的區塊列實例 0 的位址）。",
        "",
        "- 位元細節請點各區塊的文件連結。`regmap_pkg.sv` 內的暫存器名稱連到原始碼那一行；位址 = 基底 + index × 4，"
        "index ≥ 32 是狀態暫存器（`stat_ofst = 32`）；原始碼註解寫的位址不同時標 ⚠️。",
        "- 基底位址取自 `apb_intc_top.sv` 的 `apb_switch` 設定，host 的位址常數由 `tools/check_host_regs.py` 逐一比對。",
        "- 類型：RW = 控制暫存器；RO = 狀態暫存器（`s_apb_reg` 的 index ≥ 32）；RW* = RTL 也會寫入；W = 只寫。",
        "- 未定義位址讀回 `0xBADADD12`（[apb.md](../modules/apb.md#watchdog)）。",
        "",
    ]
    blocks = []
    mismatches = []
    for sec in parse(text):
        base_txt, stride, module, _ = BASES[sec["title"]]
        base = int(base_txt.replace("_", ""), 16)
        doc, count = DOC[sec["title"]]
        regs = []
        for name, idx, comment, line in sec["regs"]:
            desc = ADDR_RE.sub("", comment.split("//")[0]).strip(" /")
            m = ADDR_RE.search(comment)
            if m and int(m.group(1).replace("_", ""), 16) != idx * 4:
                cval = int(m.group(1).replace("_", ""), 16)
                desc = (desc + "；" if desc else "") + f"⚠️ 原始碼註解寫 `0x{cval:04X}`"
                mismatches.append((sec["title"], name, idx * 4, cval, line))
            regs.append((idx * 4, f"[`{name}`]({URL}#L{line})", "RO" if idx >= 32 else "RW", desc))
        stride_txt = stride if count == "1" else f"{stride}（{count} 個）"
        blocks.append((sec["title"], base, stride_txt, module, doc, regs))
    blocks += EXTRA
    blocks.sort(key=lambda b: b[1])

    out += ["## 區塊總覽", "", "| 基底 | 區塊 | RTL | 間距 / 數量 | 暫存器數 |", "|---|---|---|---|---:|"]
    for title, base, stride, module, doc, regs in blocks:
        out.append(f"| `{fmt(base)}` | [{title}]({doc}) | `{module}` | {stride} | {len(regs)} |")
    out.append("")

    ip = Path(root) / "fpga" / "nv_hsb_ip"
    consts = {k: int(v) for k, v in re.findall(r"localparam\s+(\w+)\s*=\s*(\d+)\s*;", text)}
    out += ["## 全部暫存器", "",
            "Reset 欄：`s_apb_reg` 控制暫存器的 `RST_VAL`（沒有給的區塊為 0）；空白表示不是 `s_apb_reg` 的控制暫存器，"
            "reset 值見各區塊文件。", "",
            "| 位址 | 名稱 | 類型 | Reset | 區塊 | 說明 |", "|---|---|---|---|---|---|"]
    for title, base, _, module, doc, regs in blocks:
        # RAM windows share their module with a register block; only registers get a reset value
        rv = None if "RAM" in title else reset_values(ip, module, consts)
        for off, name, kind, desc in regs:
            shown = name if name.startswith("[") else f"`{name}`"
            r = ""
            if rv is not None and kind.startswith("RW") and off % 4 == 0 and off // 4 < 32:
                r = fmt_reset(rv.get(off // 4, 0))
            out.append(f"| `{fmt(base + off)}` | {shown} | {kind} | {r} | [{title}]({doc}) | {desc} |")
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
