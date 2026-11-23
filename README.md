# hsb-ana — NVIDIA Holoscan Sensor Bridge FPGA IP 分析

這份文件分析 NVIDIA Holoscan Sensor Bridge（HSB）的 FPGA IP（`fpga/nv_hsb_ip`）。分析的目的是支援 IEEE 1722（AVTP）與 HSB 的整合工作。

## 分析基準

| 項目 | 值 |
|---|---|
| 上游 repo | https://github.com/nvidia-holoscan/holoscan-sensor-bridge |
| 版本 | `VERSION` = 3.0.0 |
| Commit | `41cecaa81ab906a55e7ec22e5e6989f7e602a4c8`（2026-11-09） |
| IP 版本常數 | `HOLOLINK_REV = 16'h2609`、`HOLOLINK_BACKWARD_COMPAT_REV = 16'h2603` |
| 參考板級設定 | `fpga/lattice/cpnx100-eth-sensor-bridge/cpnx100/rtl/top/HOLOLINK_def.svh` |

## 文件結構

文件由粗到細排列。先讀 01，再依需要讀各個 RTL 章節。

| 文件 | 內容 | 層級 |
|---|---|---|
| [01-block-view.md](docs/01-block-view.md) | 頂層方塊圖、時脈域、資料路徑、APB 位址空間、初始化流程 | 廣（block view） |
| [02-rtl-host-rx.md](docs/02-rtl-host-rx.md) | `rx_parser`、`rx_ls_parser`、ECB、BOOTP/ARP/Ping | 細（RTL） |
| [03-rtl-sensor-tx.md](docs/03-rtl-sensor-tx.md) | Ethernet → Sensor TX：`sensor_tx_pkt_proc`、`tx_stream_buffer`、`pause_gen` | 細（RTL） |
| [04-rtl-dataplane.md](docs/04-rtl-dataplane.md) | Sensor RX → Ethernet：`packetizer_top`、`dp_pkt_top`（RoCEv2 / 1722B CoE）、`eth_pkt` | 細（RTL） |
| [05-rtl-infra.md](docs/05-rtl-infra.md) | Reset、APB interconnect、PTP、事件、周邊、Bridge 模式 | 細（RTL） |
| [06-1722-integration-notes.md](docs/06-1722-integration-notes.md) | 對 1722 Listener（Ethernet → MIPI）整合的觀察與修改點 | 應用 |

## 分析深度

每個模組的分析深度不同。下表說明哪些部分逐行讀過，哪些只讀了結構。

| 深度 | 模組 |
|---|---|
| 逐行 | `HOLOLINK_top`、`rx_parser`、`sensor_tx_pkt_proc`、`tx_stream_buffer`、`eth_pkt`（仲裁與輸出部分） |
| 主要邏輯 | `rx_ls_parser`、`ecb_rdwr_ctrl`（解析與命令部分）、`dp_pkt_top`（CoE header 部分）、`apb_intc_top`（位址解碼） |
| 結構與註解 | `packetizer_top`、`ptp_top`、`bootp`、`ctrl_bus_evt_*`、`routing_table`、`bridge_pkt_proc`、`reset_gen`、`glb_ctrl_top` |
| 未讀 | `i2c`、`spi`、`uart` 內部、`lib_axis` 大部分元件、`roce_ack` 內部、各板級 top |

文件中標記「推斷」的內容沒有逐行驗證，使用前請對照原始碼。

## 命名慣例

- **HIF**：Host Interface，FPGA 與 Ethernet MAC 之間的 AXIS 介面。
- **SIF**：Sensor Interface，FPGA 與感測器（例如 MIPI CSI-2 RX/TX）之間的 AXIS 介面。
- **SIF RX**：感測器 → FPGA（相機資料進來）。
- **SIF TX**：FPGA → 感測器（Ethernet 資料出去給感測器端）。
- **ECB**：HSB 的控制封包協定（Ethernet Control Bus），用 UDP 讀寫暫存器。
- **LS**：Low Speed，控制類封包（ECB、BOOTP、ARP、Ping、Loopback）走的 8-bit 路徑。
- **VP**：Virtual Port，`packetizer` 拆出來的子串流。
- **CoE**：Camera over Ethernet，HSB 用 IEEE 1722B 實作的資料平面格式。
