# 驗證狀態

本文件記錄每類結論是怎麼確認的。**所有結論都沒有經過模擬或硬體驗證**：分析環境沒有 HDL 模擬器（VCS / Xcelium / Questa / Verilator / Icarus 都沒有），也無法安裝。

## 確認方法

| 代號 | 方法 | 可信度 |
|---|---|---|
| **R** | 逐行讀 RTL | 高；但時序細節（確切拍數）可能差 1–2 拍 |
| **X** | RTL 與 host 軟體（`src/hololink/core/*.cpp/.hpp`）交叉比對 | 很高：兩邊獨立寫成，互相一致 |
| **A** | `tools/gen_regmap.py` 自動解析 | 很高（對 `regmap_pkg.sv` 的內容而言） |
| **I** | 推斷：從結構或部分程式碼推論，沒有逐行追完 | 中；文件中標「推斷」 |

## 主要結論

| 結論 | 方法 | 文件 |
|---|---|---|
| `eth_pkt` 輸入順序為 dp / ptp / ack / ls / pause / bridge，與註解不符 | R | [overview §6](docs/architecture/overview.md#6-eth_pkt-輸入埠分配) |
| 位址空間（Global 子區、RAM、SIF RX/TX、Host、周邊） | R + X | [memory-map](docs/registers/memory-map.md) |
| 暫存器 offset；`ecb_addr_lsb/msb` 註解寫反 | A | [regmap](docs/registers/regmap.md) |
| `rx_parser` 分類條件與 `tuser` 格式 | R | [rx_parser §3、§6](docs/modules/rx_parser.md) |
| 1722 封包在 `rx_parser` 被丟棄 | R | [rx_parser §與 1722](docs/modules/rx_parser.md#與-1722-listener-的關係) |
| `rx_parser` 帶 VLAN 的 PTP messageType 讀錯 byte | R | [rx_parser 注意事項 3](docs/modules/rx_parser.md#注意事項) |
| `rx_parser` 輸入 FIFO 溢位時 beat 遺失、封包邊界可能錯位 | R + I | [rx_parser 注意事項 5](docs/modules/rx_parser.md#注意事項)、[lib_axis](docs/modules/lib_axis.md#axis_buffer) |
| `rx_parser` metadata FIFO 可能比資料 FIFO 先滿 | I | [rx_parser 注意事項 6](docs/modules/rx_parser.md#注意事項) |
| `sensor_tx_pkt_proc` 去 54 + 4 byte、依 `QP[8:1]` 選感測器 | R | [sensor_tx_pkt_proc](docs/modules/sensor_tx_pkt_proc.md) |
| `roce_ack` 與 `sensor_tx_pkt_proc` 的 QP 位元範圍不同 | R | [roce_ack 注意事項 1](docs/modules/roce_ack.md#注意事項) |
| `roce_ack` 錯誤注入註解與程式不符；PSN 比較不處理回捲 | R（回捲影響為 I） | [roce_ack 注意事項 2、3](docs/modules/roce_ack.md#注意事項) |
| `tx_stream_buffer` 預填、門檻、pause 遲滯 | R | [tx_stream_buffer](docs/modules/tx_stream_buffer.md) |
| `tx_stream_buffer` 暫存器位置 | R + X（`jesd.cpp`） | 同上 |
| 多個 SIF TX 只有 sensor 0 的 pause quanta 有效 | R | [tx_stream_buffer 注意事項 1](docs/modules/tx_stream_buffer.md#注意事項) |
| `dp_pkt_top` 設定 RAM 位置；RTL 的 `cfg_ram_addr` 比對不是 word 編號 | R + X | [dp_pkt_top §1](docs/modules/dp_pkt_top.md#1-設定-ram) |
| 1722B CoE header 46 byte 的欄位與分段 | R + X（`data_channel.cpp`） | [dp_pkt_top §3](docs/modules/dp_pkt_top.md#3-1722b-coe-header) |
| PTP 支援 gPTP（profile 1） | R + X | [others §ptp_top](docs/modules/others.md#ptp_top) |
| `ctrl_bus_evt_fsm` 從 APB RAM 執行暫存器序列 | I | [others §ctrl_bus_evt](docs/modules/others.md#ctrl_bus_evt) |

## 時序圖

`docs/timing/` 的三張圖都是**依 RTL 推導的示意**。訊號的先後順序與因果關係可信；確切拍數需要模擬確認。

## v1 → v2 修正

| 項目 | v1 | v2 |
|---|---|---|
| `dp_pkt_top` 設定 RAM | 誤把 RTL 的 `cfg_ram_addr` 比對值當成 word 位置（v1 推送前已修正） | 以 host 軟體 `data_channel.hpp` 為準，並說明 RTL 比對值的意義 |
| `inst_dec` index 6 | 寫成「未使用」 | 名稱為 `static_hif_qp`，RTL 與軟體都沒有引用 |

## 建議的下一步驗證

1. 取得模擬器後，跑上游的 `fpga/nv_hsb_ip_simple_tb`（`make run`、`make coe`），確認環境正常。
2. 針對標「推斷」的項目寫定向測試，優先順序：`rx_parser` 溢位行為 → metadata FIFO 吞吐量 → `tx_stream_buffer` 預填時序。
3. 用模擬波形取代 `docs/timing/` 的示意圖。
