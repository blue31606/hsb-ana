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
| `dp_pkt_top` 設定 RAM 位置（`0x1000 + VP × 0x40`）與 RTL 讀取位址重映射 | R + X（`data_channel.hpp`） | [dp_pkt_top §4](docs/modules/dp_pkt_top.md#4-設定-ram) |
| 1722B CoE header 46 byte 的欄位與分段 | R + X（`data_channel.cpp`） | [dp_pkt_top §8](docs/modules/dp_pkt_top.md#8-1722b-coe-header) |
| Packetizer 三種模式、固定 pattern 編號、`pack_ctrl` 位元 | R + X（`packetizer_program.cpp`） | [packetizer](docs/modules/packetizer.md) |
| ECB 命令 0x04 / 0x09 / 0x14 / 0x19 與回應碼 | R + X | [rx_ls_parser §ECB](docs/modules/rx_ls_parser.md#ecb_rdwr_ctrlecb-協定) |
| BOOTP 用 UDP 12268 → 12267、vendor tag 0xE0「NVDA」、IP 取自 `yiaddr` | R + X | [rx_ls_parser §bootp](docs/modules/rx_ls_parser.md#bootp) |
| PTP profile（E2E / gPTP / P2P）、首次同步直接設定計時器、DPLL 為 PI 迴路 | R + X | [ptp](docs/modules/ptp.md) |
| IPv4 checksum 常數 `0xC52D` = 固定欄位和 + 28 | R（手算驗證） | [dp_pkt_top §7](docs/modules/dp_pkt_top.md#7-rocev2-header) |
| RoCE header 長 70 byte、metadata 封包 202 byte、CoE metadata 174 byte、各 HIF 寬度的拍數 | R | [dp_pkt_top §9–§10](docs/modules/dp_pkt_top.md#9-metadata-封包) |
| packetizer RAM 配置 `[CLEAR][SORT][VP]`、`pack_ram_addr = (RAM 編號 << 4) | 列` | R + X（testbench `pack_vp_ram_index()`） | [packetizer §4](docs/modules/packetizer.md#4-可程式化資料路徑packetizersv) |
| host RAW10 / RAW12 排程 `0x11F1FFF7` / `0x11210007` 的解碼 | R + X（`packetizer_program.cpp`） | [packetizer §8](docs/modules/packetizer.md#8-host-軟體的排程交叉比對) |
| `f_SCL ≈ f_APB / (2 × clk_cnt)`；host `clk_cnt = 0x19` 在 19.53 MHz 時為 390 kHz | R + X（host 註解「400 kHz」、testbench 註解） | [peripherals §I2C](docs/modules/peripherals.md#i2c) |
| `configure_roce()` 的寫入順序與每個暫存器的 RTL 效果 | R + X | [flow §5](docs/flow.md#5-設定-data-planedatachannelconfigure_roce) |
| CLNX17 → CPNX100 LVDS 格式與校正 pattern | R | [boards §感測器接收路徑](docs/boards.md#感測器接收路徑) |
| 頻寬、封包間隔、延遲、緩衝餘裕 | I（由 RTL 參數推算） | [performance](docs/performance.md) |
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
| `dpll.sv` 增益註解與實際（暫存器決定）不符；offset 只取 24 bit；Delay 量測與 Sync 之間沒有配對 | R | [ptp 注意事項](docs/modules/ptp.md#注意事項) |
| PTP 沒有 BMCA、忽略 Announce；correctionField 以無號 24 bit 處理；不支援 one-step Pdelay_Resp；秒只有 32 bit | R | [ptp 注意事項](docs/modules/ptp.md#注意事項) |
| packetizer `latency ≥ 9` 時 FSM 卡死（`latency_cnt` 只有 3 bit）；`PACK_DELAY` 是死碼；串流中寫 RAM 會打亂排程；`last_buf` 只看 VP 0 | R（影響為 I） | [packetizer 注意事項](docs/modules/packetizer.md#注意事項) |
| `dp_pkt` 不檢查 VP `tvalid`；`ROCE_WR_IMM` 是死碼；`dp_pkt_1722B` 暫存器沒有使用；RTL 檔頭的設定 RAM 註解過時；CoE timestamp 是送出時間 | R | [dp_pkt_top 注意事項](docs/modules/dp_pkt_top.md#注意事項) |
| I2C 10-bit 讀取不符規格；`status[2]` 實為逾時；高 APB 時脈板級上 SCL 超過 400 kHz | R + I | [peripherals 注意事項](docs/modules/peripherals.md#注意事項) |
| UART 註解寫 16x oversampling，參數是 8 | R | [peripherals §UART](docs/modules/peripherals.md#uart) |
| `cam_rcvr` 不能反壓相機，HSB 停止接收約 4 µs 後資料遺失 | R + I | [performance §6](docs/performance.md#6-緩衝與反壓鏈) |
| buffer 環不能跨 8 GB 邊界；host 預設 MTU 1500 | R + X + I | [flow 注意事項](docs/flow.md#注意事項) |
| 512-bit HIF、MTU 1500 時 Data Plane 約 80 Gb/s，達不到 100G 線速 | I | [performance §3](docs/performance.md#3-hsb-內部的封包間隔推斷) |
| `bootp` 的變數 `ciaddr` 實際讀 `yiaddr` | R | [rx_ls_parser 注意事項](docs/modules/rx_ls_parser.md#注意事項) |
| Bridge 透明時鐘用 OR 而不是加法修正 correctionField；CAM 沒有老化 | R | [bridge 注意事項](docs/modules/bridge.md#注意事項) |
| `lib` 中 `axis_demux`、`comparator`、`debouncer`、`str_fwd_fifo` 沒有被引用 | R | [lib](docs/modules/lib.md) |
| `imu_top` 沒有被任何板級實例化 | R | [ref_design](docs/modules/ref_design.md) |

## 時序圖

`docs/timing/` 的五張圖都是**依 RTL 推導的示意**。訊號的先後順序與因果關係可信；確切拍數需要模擬確認。

## 版本修正

| 項目 | 舊 | 新 |
|---|---|---|
| `dp_pkt_top` 設定 RAM | v1 誤把 RTL 的比對值當成 word 位置 | v3 以 host 軟體 offset 為準，並列出 RTL 的讀取位址重映射表與 1 拍延遲 |
| `inst_dec` index 6 | v1 寫成「未使用」 | 名稱為 `static_hif_qp`，RTL 與軟體都沒有引用 |
| PTP 秒寬度 | v3 寫 48 bit | v4：內部 32 bit，輸出補 0 到 48 bit |
| E2E Delay_Resp 配對 | v3 寫「沒有 sequenceId 檢查」 | v4：Delay_Resp 有 sequenceId 與 requestingPortIdentity 檢查；沒有配對的是 Delay 量測與 Sync |
| `dp_pkt_ts` | v3 寫「所有 VP 讀過才彈出」 | v4：FIFO 項目分配到每個 VP 的 4 筆環狀 RAM 後就彈出；讀指標在 metadata 後前進 |
| metadata `flags[1]` | v3 寫「frame 結尾沒有對齊封包邊界」 | v4：buffer 寫滿但還沒看到 VP 的 `tlast`（`bpw_only`） |
| `hsb_ctrl_1` | v2 未說明極性 | `o_sw_sen_rst = ~hsb_ctrl_1`，實際極性由板級決定 |

## 建議的下一步驗證

1. 取得 VCS 或 Xcelium 後，跑 `fpga/nv_hsb_ip_simple_tb`（`make run TEST_MODE=SINGLE_SENSOR|ALL_SENSORS|HOST2SEN`、`make coe`），見 [testbench](docs/testbench.md)。
2. 針對標「推斷」與「可能的問題」的項目寫定向測試：`rx_parser` 溢位 → metadata FIFO 吞吐量 → `tx_stream_buffer` 預填時序 → PTP offset 回捲 → Bridge correctionField。
3. 用模擬波形取代 `docs/timing/` 的示意圖（v4 共 5 張）。
4. 在硬體上量測 [performance](docs/performance.md) 的估算值，特別是 512-bit HIF 的封包間隔。
