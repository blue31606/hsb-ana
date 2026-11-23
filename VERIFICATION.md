# 驗證狀態

本文件記錄每類結論是怎麼確認的。**所有結論都沒有經過模擬或硬體驗證**：分析環境沒有 HDL 模擬器（VCS / Xcelium / Questa / Verilator / Icarus 都沒有），也無法安裝。

## 確認方法

| 代號 | 方法 | 可信度 |
|---|---|---|
| **R** | 讀 RTL | 高；但時序細節（確切拍數）可能差 1–2 拍 |
| **X** | RTL 與 host 軟體（`src/hololink/core/*.cpp/.hpp`）交叉比對 | 很高：兩邊獨立寫成，互相一致 |
| **A** | `tools/gen_regmap.py` 自動解析 | 很高（對 `regmap_pkg.sv` 的內容而言） |
| **I** | 推斷：從結構或部分程式碼推論，沒有逐行追完 | 中；文件中標「推斷」 |

## 架構與位址

| 結論 | 方法 | 文件 |
|---|---|---|
| `eth_pkt` 輸入順序為 dp / ptp / ack / ls / pause / bridge，與 `HOLOLINK_top` 註解不符 | R | [overview §6](docs/architecture/overview.md#6-eth_pkt-輸入埠分配) |
| 位址空間：Global（PTP `0x100`、Event `0x200`、ECB `0x300`、RAM `0x1000` / `0x2000` / `0x3000`）、SIF RX `0x0100_0000 + 0x10000 × n`、SIF TX `0x0120_0000`、SPI / I2C / UART `0x0300_0000` / `0x0300_0200` / `0x0300_0400` | R + X | [memory-map](docs/registers/memory-map.md) |
| 暫存器 offset；`ecb_addr_lsb/msb` 註解寫反 | A | [regmap](docs/registers/regmap.md) |
| APB 有 4 個 master；watchdog 256 拍後回 `0xBADADD12` 並設 `pslverr` | R | [apb](docs/modules/apb.md) |
| 6 個板級的 `HOLOLINK_def` 設定 | R | [boards](docs/boards.md) |

## 子系統

| 結論 | 方法 | 文件 |
|---|---|---|
| `rx_parser` 分類條件與 `tuser` 格式；未知流量的處理 | R | [rx_parser](docs/modules/rx_parser.md) |
| `sensor_tx_pkt_proc` 去 54 + 4 byte、依 `QP[8:1]` 選感測器 | R | [sensor_tx_pkt_proc](docs/modules/sensor_tx_pkt_proc.md) |
| `tx_stream_buffer` 預填、門檻、pause 遲滯；暫存器位置 | R + X（`jesd.cpp`） | [tx_stream_buffer](docs/modules/tx_stream_buffer.md) |
| `dp_pkt_top` 設定 RAM 位置（`0x1000 + VP × 0x40`）與 RTL 讀取位址重映射 | R + X（`data_channel.hpp`） | [dp_pkt_top §2](docs/modules/dp_pkt_top.md#2-設定-ram) |
| 1722B CoE header 46 byte 的欄位與分段 | R + X（`data_channel.cpp`） | [dp_pkt_top §8](docs/modules/dp_pkt_top.md#8-1722b-coe-header) |
| Packetizer 三種模式、固定 pattern 編號、`pack_ctrl` 位元 | R + X（`packetizer_program.cpp`） | [packetizer](docs/modules/packetizer.md) |
| ECB 命令 0x04 / 0x09 / 0x14 / 0x19 與回應碼 | R + X | [rx_ls_parser §ECB](docs/modules/rx_ls_parser.md#ecb_rdwr_ctrlecb-協定) |
| BOOTP 用 UDP 12268 → 12267、vendor tag 0xE0「NVDA」、IP 取自 `yiaddr` | R + X | [rx_ls_parser §bootp](docs/modules/rx_ls_parser.md#bootp) |
| PTP profile（E2E / gPTP / P2P）、首次同步直接設定計時器、DPLL 為 PI 迴路 | R + X | [ptp](docs/modules/ptp.md) |
| 事件序列器指令格式（POLL / WRITE / READ / NOP），RAM 在 `0x2000` | R + X | [event](docs/modules/event.md) |
| EEPROM 版面、預設 MAC `CA:FE:C0:FF:EE:00`、I2C 位址 0x50 | R | [boot_and_reset](docs/modules/boot_and_reset.md) |
| Bridge CAM 64 筆、只從 SIF 學習 | R | [bridge](docs/modules/bridge.md) |
| `vsync_gen` 模式與暫存器 | R + X | [ref_design](docs/modules/ref_design.md) |

## 原始碼中的不一致與可能的問題

| 項目 | 方法 | 文件 |
|---|---|---|
| `rx_parser` 帶 VLAN 的 PTP messageType 讀錯 byte（也影響 Bridge 的 PTP 判斷） | R | [rx_parser 注意事項](docs/modules/rx_parser.md#注意事項) |
| `rx_parser` 輸入 FIFO 溢位時 beat 遺失、封包邊界可能錯位 | R + I | [rx_parser 注意事項](docs/modules/rx_parser.md#注意事項)、[lib](docs/modules/lib.md#axis_buffer) |
| `rx_parser` metadata FIFO 可能比資料 FIFO 先滿 | I | [rx_parser 注意事項](docs/modules/rx_parser.md#注意事項) |
| `roce_ack` 與 `sensor_tx_pkt_proc` 的 QP 位元範圍不同；PSN 比較不處理回捲 | R（影響為 I） | [roce_ack 注意事項](docs/modules/roce_ack.md#注意事項) |
| 多個 SIF TX 只有 sensor 0 的 pause quanta 有效 | R | [tx_stream_buffer 注意事項](docs/modules/tx_stream_buffer.md#注意事項) |
| `eth_pkt` 逾時恢復時 MAC 可能收到半個封包 | I | [eth_pkt 注意事項](docs/modules/eth_pkt.md#注意事項) |
| `dp_pkt_len` reset 值只用低 8 bit，必須由軟體設定 | R | [dp_pkt_top 注意事項](docs/modules/dp_pkt_top.md#注意事項) |
| `dpll.sv` 增益註解與實際（暫存器決定）不符；offset 只取 24 bit；E2E 配對沒有 sequenceId 檢查 | R | [ptp 注意事項](docs/modules/ptp.md#注意事項) |
| `bootp` 的變數 `ciaddr` 實際讀 `yiaddr` | R | [rx_ls_parser 注意事項](docs/modules/rx_ls_parser.md#注意事項) |
| Bridge 透明時鐘用 OR 而不是加法修正 correctionField；CAM 沒有老化 | R | [bridge 注意事項](docs/modules/bridge.md#注意事項) |
| `lib` 中 `axis_demux`、`comparator`、`debouncer`、`str_fwd_fifo` 沒有被引用 | R | [lib](docs/modules/lib.md) |
| `imu_top` 沒有被任何板級實例化 | R | [ref_design](docs/modules/ref_design.md) |

## 時序圖

`docs/timing/` 的三張圖都是**依 RTL 推導的示意**。訊號的先後順序與因果關係可信；確切拍數需要模擬確認。

## 版本修正

| 項目 | 舊 | 新 |
|---|---|---|
| `dp_pkt_top` 設定 RAM | v1 誤把 RTL 的比對值當成 word 位置 | v3 以 host 軟體 offset 為準，並列出 RTL 的讀取位址重映射表與 1 拍延遲 |
| `inst_dec` index 6 | v1 寫成「未使用」 | 名稱為 `static_hif_qp`，RTL 與軟體都沒有引用 |
| `hsb_ctrl_1` | v2 未說明極性 | `o_sw_sen_rst = ~hsb_ctrl_1`，實際極性由板級決定 |

## 建議的下一步驗證

1. 取得 VCS 或 Xcelium 後，跑 `fpga/nv_hsb_ip_simple_tb`（`make run TEST_MODE=SINGLE_SENSOR|ALL_SENSORS|HOST2SEN`、`make coe`），見 [testbench](docs/testbench.md)。
2. 針對標「推斷」與「可能的問題」的項目寫定向測試：`rx_parser` 溢位 → metadata FIFO 吞吐量 → `tx_stream_buffer` 預填時序 → PTP offset 回捲 → Bridge correctionField。
3. 用模擬波形取代 `docs/timing/` 的示意圖。
