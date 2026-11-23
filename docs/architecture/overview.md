# 架構總覽

原始碼：[`top/HOLOLINK_top.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv)（1933 行，逐行分析）

## 1. HSB IP 在 FPGA 裡的位置

`HOLOLINK_top` 不含 MAC、PCS 或感測器 PHY。板級 top 實例化這些 IP，再用 AXIS 接到 `HOLOLINK_top`。

```mermaid
flowchart LR
  subgraph Board["板級 FPGA_top（各家 FPGA 不同）"]
    PHY["Ethernet PCS/MAC<br/>(10G / 25G / 100G)"]
    CSI["MIPI CSI-2 RX IP<br/>或其他感測器 IF"]
    TXIF["感測器 TX IF<br/>(MIPI TX / JESD / I2S ...)"]
    USR["使用者暫存器模組<br/>(APB, REG_INST 個)"]
    PERI["I2C / SPI / UART / GPIO 腳位"]
  end
  HSB["HOLOLINK_top<br/>(nv_hsb_ip)"]
  PHY <-- "HIF AXIS × HOST_IF_INST" --> HSB
  CSI -- "SIF RX AXIS × SENSOR_RX_IF_INST" --> HSB
  HSB -- "SIF TX AXIS × SENSOR_TX_IF_INST" --> TXIF
  HSB -- "APB master" --> USR
  HSB <--> PERI
```

host 軟體裡已經有 SIF TX 的使用者：JESD（`src/hololink/core/jesd.cpp` 寫 `0x0120_0000` 啟用 TX）與 I2S。

## 2. 頂層方塊圖

非 Bridge 模式（沒有定義 `BRIDGE_IF_INST`）。每個 host 埠各有一份 `rx_parser` 與 `eth_pkt`；`rx_ls_parser`、`sensor_tx_pkt_proc`、`dp_pkt_top`、`ptp_top` 只有一份。

```mermaid
flowchart LR
  MACRX(["HIF RX<br/>i_hif_axis_*"])
  MACTX(["HIF TX<br/>o_hif_axis_*"])
  SIFRX(["SIF RX<br/>i_sif_axis_*"])
  SIFTX(["SIF TX<br/>o_sif_axis_*"])

  subgraph RX["Host RX（每個 host 埠一份）"]
    RXP["rx_parser<br/>header 解析・分類・<br/>store-and-forward・VLAN 移除"]
    RACK["roce_ack<br/>(SIF_TX_ROCE_RC_ENABLE)"]
  end

  subgraph CTRL["控制平面（共用）"]
    LSP["rx_ls_parser<br/>ECB / BOOTP / ARP / Ping / Loopback / Event"]
    APB["apb_intc_top<br/>APB interconnect"]
  end

  subgraph STX["Sensor TX 路徑（Host → 感測器）"]
    STXP["sensor_tx_pkt_proc<br/>去 header・依 QP 分流"]
    TSB["tx_stream_buffer × N<br/>雙時脈 FIFO・預填・PAUSE"]
    PG["pause_gen（每個 host 埠）<br/>802.3x PAUSE"]
  end

  subgraph DP["Data Plane（Sensor RX → Host）"]
    PKZ["packetizer_top × N<br/>位元重排・VP 拆分・CDC"]
    DPP["dp_pkt_top<br/>RoCEv2 / 1722B CoE"]
  end

  PTP["ptp_top<br/>1588 / gPTP"]
  ETH["eth_pkt（每個 host 埠一份）<br/>優先權仲裁・VLAN 插入"]

  MACRX --> RXP
  RXP --- RACK
  RXP -- "LS (8-bit)" --> LSP
  RXP -- "STX (RoCE)" --> STXP
  RXP -- "PTP" --> PTP
  RACK -- "ACK/NAK" --> ETH
  STXP --> TSB --> SIFTX
  TSB -- "pause req" --> PG --> ETH
  TSB -. "stx_is_ready" .-> RACK
  SIFRX --> PKZ --> DPP --> ETH
  LSP -- "LS 回應" --> ETH
  PTP --> ETH
  ETH --> MACTX
  LSP -- "ECB → APB master" --> APB
```

## 3. 時脈域

| 時脈 | 用途 | CPNX100（其他板級見 [boards](../boards.md)） |
|---|---|---|
| `i_hif_clk` | Host 資料路徑：`rx_parser`、`eth_pkt`、`dp_pkt_top`、`sensor_tx_pkt_proc`、`tx_stream_buffer` 寫入端 | 156.25 MHz（10G，64-bit） |
| `i_apb_clk` | 暫存器、`sys_init`、`eeprom_info`、I2C/SPI/UART | 19.53125 MHz |
| `i_ptp_clk` | PTP 計時器 | 100.446545 MHz |
| `i_sif_rx_clk[n]` | 每個 SIF RX 一個 | 由感測器 IP 提供 |
| `i_sif_tx_clk[n]` | 每個 SIF TX 一個；`tx_stream_buffer` 讀出端 | 由感測器 IP 提供 |

跨時脈的位置：

| 位置 | 方向 | 方式 |
|---|---|---|
| `packetizer_top` | SIF RX → HIF | 內部 FIFO |
| `tx_stream_buffer` / `axis_buffer_tx` | HIF → SIF TX | `dc_fifo`（`DUAL_CLOCK = 1`） |
| 每個模組的 `s_apb_reg` | APB → 模組時脈 | `SYNC_CLK_HIF_APB` 定義時省略 |
| `streaming_cdc` ×2（[L1008–L1034](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L1008-L1034)） | PTP → HIF、PTP → APB | 80 bit：48 bit 秒 + 32 bit 奈秒 |
| `init_done`（[L583](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L583)） | APB → HIF | `data_sync` |

## 4. 編譯參數（`HOLOLINK_def.svh`）

| Define / 參數 | 意義 | CPNX100（其他板級見 [boards](../boards.md)） |
|---|---|---|
| `HOST_IF_INST` | Host（Ethernet）埠數 | 2 |
| `HOST_WIDTH` | HIF AXIS 寬度 | 64 |
| `HOST_MTU` | 最大封包長度 | 4096 |
| `SENSOR_RX_IF_INST` | SIF RX 數 | 3 |
| `SIF_RX_WIDTH[]` / `SIF_RX_PACKETIZER_EN[]` / `SIF_RX_VP_COUNT[]` | 每個 SIF RX 的寬度 / packetizer 模式 / VP 數 | {32,64,64} / {0,1,1} / {2,2,2} |
| `SENSOR_TX_IF_INST` | SIF TX 數 | 1 |
| `SIF_TX_WIDTH[]` / `SIF_TX_BUF_SIZE[]` | 每個 SIF TX 的寬度 / FIFO 深度 | {32} / 4096 |
| `DATAPATH_WIDTH` | SIF 埠實體寬度（RX/TX 最大值） | 64 |
| `I2C_INST` / `SPI_INST` / `UART_INST` / `GPIO_INST` | 周邊數量 | 4 / 2 / 1 / 31 |
| `REG_INST` | 使用者 APB slave 數 | 8 |
| `N_INIT_REG` | 開機自動寫入的暫存器數 | 22 |
| `ENUM_EEPROM` | MAC/SN/IP 從 EEPROM 讀 | 定義 |

改變結構的 define：

| Define | 效果 |
|---|---|
| `BRIDGE_IF_INST` | Bridge 模式：SIF 當 Ethernet 埠，Data Plane / Sensor TX / PAUSE 全部移除 |
| `EXT_PTP` | 不實例化 `ptp_top`，PTP 時間由外部輸入 |
| `DISABLE_VLAN` | 移除 VLAN 解析與插入 |
| `DISABLE_COE` | 合成時移除 1722B CoE header（模擬時一律保留） |
| `SIF_RX_DATA_GEN` | 每個 SIF RX 前加測試資料產生器 |
| `SIF_TX_ROCE_RC_ENABLE` | `rx_parser` 實例化 `roce_ack`，接受 RC SEND/WRITE |
| `SYNC_CLK_HIF_APB` / `SYNC_CLK_HIF_PTP` | 宣告兩個時脈同源，省略同步器 |

## 5. 資料路徑

| 路徑 | 模組鏈 | 文件 |
|---|---|---|
| Host RX → 控制平面 | `rx_parser` → `rx_ls_parser`（ECB/BOOTP/ARP/Ping/Loopback）→ `eth_pkt` 第 3 埠；ECB → APB | [rx_ls_parser](../modules/rx_ls_parser.md)、[apb](../modules/apb.md) |
| Host RX → Sensor TX | `rx_parser` → `sensor_tx_pkt_proc` → `tx_stream_buffer[i]` → `o_sif_axis_*[i]` | [rx_parser](../modules/rx_parser.md)、[sensor_tx_pkt_proc](../modules/sensor_tx_pkt_proc.md)、[tx_stream_buffer](../modules/tx_stream_buffer.md) |
| Sensor RX → Host | `packetizer_top[n]` → `dp_pkt_top` → `eth_pkt` 第 0 埠 | [packetizer](../modules/packetizer.md)、[dp_pkt_top](../modules/dp_pkt_top.md) |
| PTP | `rx_parser` → `ptp_top` → `eth_pkt` 第 1 埠（只有 host 埠 0） | [ptp](../modules/ptp.md) |
| 事件 → Host | `i_sif_event` 等 → `ctrl_bus_evt_int` → 中斷封包 / 暫存器序列 | [event](../modules/event.md) |
| Bridge（`BRIDGE_IF_INST`） | `rx_parser` ↔ `bridge_pkt_proc` ↔ SIF | [bridge](../modules/bridge.md) |

## 6. `eth_pkt` 輸入埠分配

每個 host 埠的 `eth_pkt` 有 6 個輸入，固定優先權（index 小的優先）。以 [`HOLOLINK_top.sv#L924–L964`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L924-L964) 的 concat 為準：

| Index | 來源 | 說明 |
|---|---|---|
| 0 | `dp_axis_*` | Data Plane |
| 1 | `ptp_tx_axis_*` | PTP（只有 host 0） |
| 2 | `ack_axis_*` | RoCE ACK/NAK |
| 3 | `lso_axis_*` | LS 回應 |
| 4 | `pause_axis_*` | 802.3x PAUSE |
| 5 | `btx_axis_*` | Bridge |

> ⚠️ [L897–L902](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L897-L902) 的註解少了 RoCE ACK，順序和 concat 不一致。

## 7. 位址空間

完整的位址表見 [memory-map.md](../registers/memory-map.md)；各暫存器見 [regmap.md](../registers/regmap.md)。

| 範圍 | 目標 |
|---|---|
| `0x0000_0000`–`0x0000_3FFF` | Global：`glb_ctrl`、PTP、Event、ECB、三個 APB RAM |
| `0x0100_0000`–`0x011F_FFFF` | SIF RX（packetizer、data_gen） |
| `0x0120_0000`–`0x013F_FFFF` | SIF TX（`tx_stream_buffer`） |
| `0x0200_0000`–`0x02FF_FFFF` | Host 埠（`rx_parser`、`eth_pkt`、`dp_pkt`） |
| `0x0300_0000`–`0x03FF_FFFF` | SPI / I2C / UART |
| `0x0600_0000` | Bridge（`BRIDGE_IF_INST`） |
| `0x1000_0000`–`0xFFFF_FFFF` | 使用者模組（`o_apb_*`） |

APB master 有 4 個：

| Master | 來源 |
|---|---|
| `m_apb[0]` | ECB（host 軟體） |
| `m_apb[1]` | `sys_init` |
| `m_apb[2]` | `eeprom_info` |
| `m_apb[3]` | `ctrl_bus_evt`（事件觸發的暫存器序列） |

## 8. 開機與初始化

詳見 [boot_and_reset](../modules/boot_and_reset.md)。

```mermaid
sequenceDiagram
  participant RST as reset_gen
  participant SI as sys_init
  participant EE as eeprom_info
  participant TOP as HOLOLINK_top
  participant RXP as rx_parser
  participant BP as bootp
  RST->>SI: 釋放 APB reset
  SI->>SI: 依序寫入 init_reg[N_INIT_REG]（例如 PCS/MAC 設定）
  SI->>EE: sys_init_done
  EE->>EE: 經 I2C 讀 EEPROM：MAC、board SN、IP
  EE->>TOP: eeprom_dval
  TOP->>TOP: init_done = eeprom_dval && sys_init_done
  TOP->>RXP: tvalid 解除遮罩、o_hif_axis_tready = 1
  TOP->>BP: i_init_done
  BP->>BP: 對每個 host 埠送出 BOOTP request（含 enumeration 資料）
```

- `init_done` 之前，`rx_parser` 的 `tvalid` 被 `init_done_hif_clk` 遮掉（[L415](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L415)），`o_hif_axis_tready = init_done_hif_clk`（[L381](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L381)）。
- host 埠 `i` 的 MAC = EEPROM MAC + `i`（[L847](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L847)）。
- IP：EEPROM 有值就用；否則預設 `192.168.0.2`，之後可由 BOOTP reply 改寫。

## 9. Reset 與軟體控制

詳見 [boot_and_reset §glb_ctrl_top](../modules/boot_and_reset.md#glb_ctrl_top)。

- `o_sw_sys_rst = hsb_ctrl[3]`：軟體系統 reset，回接 `reset_gen.i_cfg_rst`（[L801](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L801)）。
- `o_sw_sen_rst = ~hsb_ctrl[63:32]`：32 個感測器 reset 給板級（[L800](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L800)）。

## 10. 事件向量

```
event_vec = { i_sif_event[15:0], 11'h0, uart_irq, 2'b00(內部), spi_busy, i2c_busy }
```

詳見 [event](../modules/event.md)。（[L528](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L528)）板級可以用 `i_sif_event` 把感測器事件送給 host。

## 11. 系統層級文件

- [端到端流程](../flow.md)：從上電到一個 frame 送達 host。
- [效能分析](../performance.md)：頻寬、延遲、緩衝餘裕。
- [完整暫存器索引](../registers/all-registers.md)。
