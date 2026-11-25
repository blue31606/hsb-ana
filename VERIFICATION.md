# 驗證狀態

本文件記錄每類結論是怎麼確認的。**所有結論都沒有經過模擬或硬體驗證**：分析環境沒有 HDL 模擬器（VCS / Xcelium / Questa / Verilator / Icarus 都沒有），也無法安裝。可以計算的部分（checksum、CRC、排程、版面）改用 Python 重寫 RTL 運算做數值比對（方法 **N**）；需要時序的部分照 RTL 逐暫存器重寫成 Python 逐拍模型（方法 **M**）；其餘以文字解析的腳本做靜態比對（[自動檢查](#自動檢查)）。全部文件經過一次獨立 agent 對照 RTL 的稽核，找到的 33 項都已修正或併入問題清單。

## 確認方法

| 代號 | 方法 | 可信度 |
|---|---|---|
| **R** | 讀 RTL | 高；但時序細節（確切拍數）可能差 1–2 拍 |
| **X** | RTL 與 host 軟體（`src/hololink/core/*.cpp/.hpp`）交叉比對；host 的位址常數與寫入值由 `tools/check_host_regs.py` 自動比對 | 很高：兩邊獨立寫成，互相一致 |
| **A** | `tools/gen_allregs.py` 自動解析 `regmap_pkg.sv` | 很高（對 `regmap_pkg.sv` 的內容而言） |
| **I** | 推斷：從結構或部分程式碼推論，沒有逐行追完 | 中；文件中標「推斷」 |
| **N** | 數值驗證：`tools/verify/verify_calcs.py` 照 RTL 重寫運算，與獨立參考實作比對（[結果](docs/verification-calcs.md)） | 很高（只限運算本身，不含時序） |
| **M** | 逐拍模型：`tools/model/` 下的腳本照 RTL 逐暫存器重寫一段邏輯的時序行為，餵入流量重現結論：`rx_parser_model.py`（[結果](docs/performance.md#7-rx_parser-讀出能力逐拍模型)）、`dp_pkt_model.py`（[結果](docs/performance.md#3-hsb-內部的封包間隔逐拍模型)）、`uart_rx_model.py`、`roce_ack_model.py`（封包層級） | 高，介於讀 RTL 與模擬之間：模型本身是人工轉寫，可能和 RTL 有出入；每個腳本都列出建模範圍與假設，預期不符時失敗 |

## 架構與位址

| 結論 | 方法 | 文件 |
|---|---|---|
| `eth_pkt` 輸入順序為 dp / ptp / ack / ls / pause / bridge，與 `HOLOLINK_top` 註解不符 | R | [overview §6](docs/architecture/overview.md#6-eth_pkt-輸入埠分配) |
| 位址空間：Global（PTP `0x100`、Event `0x200`、ECB `0x300`、RAM `0x1000` / `0x2000` / `0x3000`）、SIF RX `0x0100_0000 + 0x10000 × n`、SIF TX `0x0120_0000`、SPI / I2C / UART `0x0300_0000` / `0x0300_0200` / `0x0300_0400` | R + X | [memory-map](docs/registers/memory-map.md) |
| 暫存器 offset；`ecb_addr_lsb/msb` 註解寫反 | A | [all-registers](docs/registers/all-registers.md#註解與程式不一致的項目) |
| APB 有 4 個 master；watchdog 256 拍後回 `0xBADADD12` 並設 `pslverr` | R | [apb](docs/modules/apb.md) |
| 6 個板級的 `HOLOLINK_def` 設定 | R（自動比對） | [boards](docs/boards.md) |

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
| IPv4 checksum 常數 `0xC52D` = 固定欄位和 + 28 | R + N（20000 組隨機 header） | [dp_pkt_top §7](docs/modules/dp_pkt_top.md#7-rocev2-header) |
| RoCE header 長 70 byte、metadata 封包 202 byte、CoE metadata 174 byte、各 HIF 寬度的拍數 | R | [dp_pkt_top §9–§10](docs/modules/dp_pkt_top.md#9-metadata-封包) |
| packetizer RAM 配置 `[CLEAR][SORT][VP]`、`pack_ram_addr = (RAM 編號 << 4) \| 列` | R + X（testbench `pack_vp_ram_index()`） | [packetizer §4](docs/modules/packetizer.md#4-可程式化資料路徑packetizersv) |
| host RAW10 / RAW12 排程 `0x11F1FFF7` / `0x11210007` 的解碼 | R + X（`packetizer_program.cpp`） | [packetizer §8](docs/modules/packetizer.md#8-host-軟體的排程交叉比對) |
| `f_SCL ≈ f_APB / (2 × clk_cnt)`；host `clk_cnt = 0x19` 在 19.53 MHz 時為 390 kHz | R + X（host 註解「400 kHz」、testbench 註解） | [peripherals §I2C](docs/modules/peripherals.md#i2c) |
| `configure_roce()` 的寫入順序與每個暫存器的 RTL 效果 | R + X | [flow §5](docs/flow.md#5-設定-data-planedatachannelconfigure_roce) |
| CLNX17 → CPNX100 LVDS 格式與校正 pattern | R | [boards §感測器接收路徑](docs/boards.md#感測器接收路徑) |
| 頻寬、封包間隔、延遲、緩衝餘裕 | I（由 RTL 參數推算） | [performance](docs/performance.md) |
| 各模組的實例化次數（每 host 埠 / 每感測器 / 共用）；PTP 只接 host 0 | R | [overview §2](docs/architecture/overview.md#2-頂層方塊圖) |
| 全部跨時脈點與使用的同步元件 | R | [overview §跨時脈地圖](docs/architecture/overview.md#跨時脈地圖)、[lib §CDC 元件](docs/modules/lib.md#cdc-元件) |
| ECB 寫入沒有 `ACK_REQUEST` 時不回應；回應尾端帶 2 byte sequence；N ≤ 1 時補到 18 byte | R + X（host 一律設 `ACK_REQUEST`） | [rx_ls_parser §回應格式](docs/modules/rx_ls_parser.md#回應格式) |
| RoCE-ECB 回應是 RDMA WRITE with Immediate（0x2B） | R | 同上 |
| `roce_icrc` 支援的最後一拍長度剛好涵蓋 HSB 產生的所有 RoCE 封包；`lfsr_hc` 只有特定寬度有方程式；11 種寬度的方程式全部等於反射 CRC-32 | R + N | [roce](docs/modules/roce.md) |
| reset 串接：HIF / PTP / SIF reset 都以 APB reset 為來源；軟體 reset 自我清除 | R | [boot_and_reset §reset_gen](docs/modules/boot_and_reset.md#reset_gen) |
| EEPROM 每次讀 32 byte、共 8 次；CRC 多項式實為 0x31（反射 0x8C） | R + X + N（check 值 0xA1） | [boot_and_reset §eeprom_info](docs/modules/boot_and_reset.md#eeprom_info) |
| Bridge 的 correctionField 位置是 byte 22–27（Layer 2 PTP） | R | [bridge §PTP 透明時鐘](docs/modules/bridge.md#ptp-透明時鐘) |
| 事件序列器指令格式（POLL / WRITE / READ / NOP），RAM 在 `0x2000` | R + X | [event](docs/modules/event.md) |
| EEPROM 版面、預設 MAC `CA:FE:C0:FF:EE:00`、I2C 位址 0x50 | R | [boot_and_reset](docs/modules/boot_and_reset.md) |
| Bridge CAM 64 筆、只從 SIF 學習 | R | [bridge](docs/modules/bridge.md) |
| `vsync_gen` 模式與暫存器 | R + X | [ref_design](docs/modules/ref_design.md) |

## 問題清單

RTL 問題的描述、嚴重度、觸發條件、確認方法與建議修正只在 [issues.md](docs/issues.md) 維護，這裡不重複。目前 65 項（高 1、中 20、低 44），另有註解與死碼 15 項；方法分布為 R 43、R + M 11、R + X 7、R + N 2、R + I 1、R + X + N 1，沒有只靠推斷（I）的項目。每個編號都連到描述它的模組文件，模組文件的注意事項也都標了編號。不屬於 `nv_hsb_ip` 的板級限制（例如 CPNX100 `cam_rcvr` 不能反壓相機）記在 [performance §6](docs/performance.md#6-緩衝與反壓鏈) 與 [boards](docs/boards.md)。

## 自動檢查

`python3 tools/check_all.py ../holoscan-sensor-bridge` 一次跑完下列檢查（各工具說明見 [tools/README](tools/README.md)），並確認本節與其他文件中寫死的數字和工具輸出一致。

| 結果 | 方法 | 工具 |
|---|---|---|
| host 用到的 96 個位址常數中 87 個在 RTL 暫存器索引找得到；其餘 9 個是 I2S 狀態 4 個（PE-15）與 S10 的 JESD 廠商 IP 5 個（不在本 repo 的 RTL 內） | X | `check_host_regs.py` |
| host 寫入的 597 個常數值中，526 個可對到 `regmap_pkg` 暫存器且非 0，都沒有寫到 RTL 不讀的位元 | X | `check_host_regs.py --bits` |
| host 讀取後做位元測試的 9 處中，8 處可對到 RTL 的 `stat_reg` 指派；1 處測試 RTL 固定為 0 的位元（NT-15） | X | `check_host_regs.py --reads` |
| 暫存器索引的 185 個項目中，host 存取了 122 個；其餘 63 個逐一分類（依 reset 值運作、沒有作用、host 未使用的功能、除錯用狀態），見 [memory-map](docs/registers/memory-map.md#host-沒有存取的暫存器) | R + X | `check_unused.py` |
| 文件中 622 個原始碼連結的行號都在檔案範圍內；231 個可依識別字判斷的連結中，204 個自動吻合、27 個人工確認 | 自動 + 人工 | `check_links.py` |
| 80 個問題編號都在模組文件中有描述，`issues.md` 的編號連到該處 | 自動 | `check_issue_refs.py` |
| 290 個實例中，握手 / 狀態類埠空接 131 處、輸入綁常數 14 處，全部人工分類；新問題併入 BR-7，其餘是已知問題或刻意設計 | R（掃描 + 人工） | `scan_ports.py` |
| 檔案內跨時脈 23 處：5 處依名稱判定為同步器或準靜態設定，18 處人工確認，沒有新問題 | R（掃描 + 人工） | `scan_cdc.py`，見 [lib §HSB 中的使用檢查](docs/modules/lib.md#hsb-中的使用檢查) |
| 模組之間（經由埠）的跨時脈 13 處：7 處是 `init_done` 前就固定的 EEPROM 資料，6 處是板級 I2C / SPI 輸入同步在錯的時脈（PE-17） | R（掃描 + 人工） | `scan_cdc_ports.py` |
| `nv_hsb_ip` 的 115 個檔案、115 個模組 / package 都在文件中出現；文件表格的 23 個「行數」欄、22 個 reset 值與原始碼一致；212 個表格的欄數依 GitHub 的切法一致 | 自動 | `check_coverage.py` |
| 各板級 `HOLOLINK_def.svh` 的 22 列設定（132 格）與 [boards.md](docs/boards.md#設定比較) 一致 | 自動 | `gen_board_table.py` |
| `tests/` 草稿用到的埠、參數、task 參數個數與階層路徑都存在 | 自動 | `check_tests.py` |

## 時序圖

`docs/timing/` 的五張圖中，`rx_parser_readout` 由 `tools/model/rx_parser_model.py --wave` 產生（M）；其餘四張是**依 RTL 推導的示意**，訊號的先後順序與因果關係可信，確切拍數需要模擬確認。

## 建議的下一步驗證

1. 取得 VCS 或 Xcelium 後，跑 `fpga/nv_hsb_ip_simple_tb`（`make run TEST_MODE=SINGLE_SENSOR|ALL_SENSORS|HOST2SEN`、`make coe`），見 [testbench](docs/testbench.md)。
2. 跑 [定向測試計畫](docs/test-plan.md) 的 U1–U3、S1–S13，確認 [問題清單](docs/issues.md) 中標 R / I / M 的項目；S11 與 U2 同時驗證 `rx_parser_model.py`、`uart_rx_model.py` 這兩個模型本身。之後再做 PTP master 模型等需要新模型的測試。
3. 用模擬波形取代 `docs/timing/` 的四張示意圖。
4. 在硬體上量測 [performance](docs/performance.md) 的估算值，特別是 512-bit HIF 的封包間隔；`dp_pkt_model.py` 沒有包含 `roce_icrc` 與 `eth_pkt`。

