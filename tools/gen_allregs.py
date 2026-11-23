#!/usr/bin/env python3
"""Generate docs/registers/all-registers.md: every APB-visible register of HSB
with its absolute address (instance 0), in one table.

Registers listed in regmap_pkg.sv are parsed with gen_regmap.parse(). Blocks
that are not in regmap_pkg.sv (module-local registers, RAMs, peripherals,
reference-design modules) are listed in EXTRA below; their contents were taken
from the RTL by hand and are documented in the linked module documents.

Usage:
  python3 tools/gen_allregs.py <path-to-holoscan-sensor-bridge> > docs/registers/all-registers.md
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_regmap  # noqa: E402

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
        (0x04, "baud / thresh", "RW", "[15:0] 鮑率除數、[31:16] FIFO 門檻"),
        (0x08, "int_en", "RW", ""),
        (0x0C, "int_clr", "RW", ""),
        (0x80, "status", "RO", ""),
        (0x84, "int_status", "RO", ""),
        (0x140, "tx_data", "W", ""),
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
        (0x14, "VSYNC_GPIO", "RW", "[9:0] GPIO 多工"),
    ]),
]


def fmt(a):
    return f"0x{a >> 16:04X}_{a & 0xFFFF:04X}"


def main(root):
    text = (Path(root) / gen_regmap.SRC).read_text(encoding="utf-8")
    out = [
        "# 完整暫存器索引（自動產生）",
        "",
        "本檔由 `tools/gen_allregs.py` 產生，請勿手動修改。",
        "",
        "所有 APB 可存取的暫存器依絕對位址排列（多實例的區塊列實例 0 的位址）。",
        "",
        "- 位元細節請點各區塊的文件連結；`regmap_pkg.sv` 內的暫存器另見 [regmap.md](regmap.md)（含原始碼註解比對）。",
        "- 類型：RW = 控制暫存器；RO = 狀態暫存器（`s_apb_reg` 的 index ≥ 32）；RW* = RTL 也會寫入；W = 只寫。",
        "- 未定義位址讀回 `0xBADADD12`（[apb.md](../modules/apb.md#watchdog)）。",
        "",
    ]
    blocks = []
    for sec in gen_regmap.parse(text):
        base_txt, stride, module, _ = gen_regmap.BASES[sec["title"]]
        base = int(base_txt.replace("_", ""), 16)
        doc, count = DOC[sec["title"]]
        regs = [(idx * 4, name, "RO" if idx >= 32 else "RW", comment.split("//")[0])
                for name, idx, comment, _ in sec["regs"]]
        regs = [(o, n, k, gen_regmap.ADDR_RE.sub("", c).strip(" /")) for o, n, k, c in regs]
        stride_txt = stride if count == "1" else f"{stride}（{count} 個）"
        blocks.append((sec["title"], base, stride_txt, module, doc, regs))
    blocks += EXTRA
    blocks.sort(key=lambda b: b[1])

    out += ["## 區塊總覽", "", "| 基底 | 區塊 | RTL | 間距 / 數量 | 暫存器數 |", "|---|---|---|---|---:|"]
    for title, base, stride, module, doc, regs in blocks:
        out.append(f"| `{fmt(base)}` | [{title}]({doc}) | `{module}` | {stride} | {len(regs)} |")
    out.append("")

    out += ["## 全部暫存器", "", "| 位址 | 名稱 | 類型 | 區塊 | 說明 |", "|---|---|---|---|---|"]
    for title, base, _, _, doc, regs in blocks:
        for off, name, kind, desc in regs:
            out.append(f"| `{fmt(base + off)}` | `{name}` | {kind} | [{title}]({doc}) | {desc} |")
    out.append("")
    sys.stdout.write("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../holoscan-sensor-bridge")
