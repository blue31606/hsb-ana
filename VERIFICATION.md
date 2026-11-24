# 驗證狀態

本文件記錄每類結論是怎麼確認的。**所有結論都沒有經過模擬或硬體驗證**：分析環境沒有 HDL 模擬器（VCS / Xcelium / Questa / Verilator / Icarus 都沒有），也無法安裝。可以計算的部分（checksum、CRC、排程、版面）改用 Python 重寫 RTL 運算做數值比對（方法 **N**）；v7 另外把 `rx_parser` 讀出路徑與 Bridge host RX 緩衝照 RTL 逐暫存器重寫成 Python 逐拍模型（方法 **M**），並用腳本靜態核對測試草稿的名稱與階層（[test-plan §靜態檢查](docs/test-plan.md#靜態檢查v7)）。v6 另外請一個獨立的 agent 逐項對照 RTL 稽核全部文件，找到的 33 項逐一對照 RTL 確認：31 項已修正；另外 2 項（`roce_ack` QP RAM 越界、Bridge 學習請求遺失）稽核時無法確認，v6 後續追完 RTL，兩項都成立，已列入問題清單（TX-10、BR-9）。

## 確認方法

| 代號 | 方法 | 可信度 |
|---|---|---|
| **R** | 讀 RTL | 高；但時序細節（確切拍數）可能差 1–2 拍 |
| **X** | RTL 與 host 軟體（`src/hololink/core/*.cpp/.hpp`）交叉比對 | 很高：兩邊獨立寫成，互相一致 |
| **A** | `tools/gen_regmap.py` 自動解析 | 很高（對 `regmap_pkg.sv` 的內容而言） |
| **I** | 推斷：從結構或部分程式碼推論，沒有逐行追完 | 中；文件中標「推斷」 |
| **N** | 數值驗證：`tools/verify/verify_calcs.py` 照 RTL 重寫運算，與獨立參考實作比對（[結果](docs/verification-calcs.md)） | 很高（只限運算本身，不含時序） |
| **M** | 逐拍模型：`tools/model/rx_parser_model.py` 照 RTL 逐暫存器重寫一段邏輯的時序行為，餵入流量重現結論（[結果](docs/performance.md#7-rx_parser-讀出能力逐拍模型)） | 高，介於讀 RTL 與模擬之間：模型本身是人工轉寫，可能和 RTL 有出入；腳本的對照組與各項預期會在不符時失敗 |

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
| IPv4 checksum 常數 `0xC52D` = 固定欄位和 + 28 | R + N（20000 組隨機 header） | [dp_pkt_top §7](docs/modules/dp_pkt_top.md#7-rocev2-header) |
| RoCE header 長 70 byte、metadata 封包 202 byte、CoE metadata 174 byte、各 HIF 寬度的拍數 | R | [dp_pkt_top §9–§10](docs/modules/dp_pkt_top.md#9-metadata-封包) |
| packetizer RAM 配置 `[CLEAR][SORT][VP]`、`pack_ram_addr = (RAM 編號 << 4) | 列` | R + X（testbench `pack_vp_ram_index()`） | [packetizer §4](docs/modules/packetizer.md#4-可程式化資料路徑packetizersv) |
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

## 原始碼中的不一致與可能的問題

| 項目 | 方法 | 文件 |
|---|---|---|
| `rx_parser` 帶 VLAN 的 PTP messageType 讀錯 byte（也影響 Bridge 的 PTP 判斷） | R | [rx_parser 注意事項](docs/modules/rx_parser.md#注意事項) |
| `rx_parser` 輸入 FIFO 溢位時 beat 遺失，`in_pkt_cnt` 仍計入被丟的 `tlast`，之後資料與 metadata 永久錯開（v7：由 I 升為 R + M） | R + M | [rx_parser 注意事項](docs/modules/rx_parser.md#注意事項)、[lib](docs/modules/lib.md#axis_buffer) |
| `rx_parser` metadata FIFO 比資料 FIFO 先滿，三個 metadata FIFO 各自丟（v7：由 I 升為 R + M） | R + M | [rx_parser 注意事項](docs/modules/rx_parser.md#注意事項) |
| `rx_parser` 背靠背讀出每個封包多 1 拍（v6 寫 2 拍）；Terasic S10 在 100G 下連續短封包會溢位（DP-15，v7 新增） | R + M | [performance §7](docs/performance.md#7-rx_parser-讀出能力逐拍模型) |
| `roce_ack` 與 `sensor_tx_pkt_proc` 的 QP 位元範圍不同；PSN 比較不處理回捲 | R（影響為 I） | [roce_ack 注意事項](docs/modules/roce_ack.md#注意事項) |
| 多個 SIF TX 只有 sensor 0 的 pause quanta 有效 | R | [tx_stream_buffer 注意事項](docs/modules/tx_stream_buffer.md#注意事項) |
| `eth_pkt` 逾時恢復時 MAC 收到兩個封包接成的 frame（v7：由 I 升為 R） | R | [eth_pkt 注意事項](docs/modules/eth_pkt.md#注意事項) |
| `dp_pkt_len` reset 值只用低 8 bit，必須由軟體設定 | R | [dp_pkt_top 注意事項](docs/modules/dp_pkt_top.md#注意事項) |
| `dpll.sv` 增益註解與實際（暫存器決定）不符；offset 只取 24 bit；Delay 量測與 Sync 之間沒有配對 | R | [ptp 注意事項](docs/modules/ptp.md#注意事項) |
| PTP 沒有 BMCA、忽略 Announce；correctionField 只用 24 bit（mod 2²⁴，負值正確、超過 ±8.4 ms 回捲）；不支援 one-step Pdelay_Resp；秒只有 32 bit | R | [ptp 注意事項](docs/modules/ptp.md#注意事項) |
| packetizer `latency ≥ 9` 時 FSM 卡死（`latency_cnt` 只有 3 bit）；`PACK_DELAY` 是死碼；串流中寫 RAM 會打亂排程；`last_buf` 只看 VP 0 | R（影響為 I） | [packetizer 注意事項](docs/modules/packetizer.md#注意事項) |
| `dp_pkt` 不檢查 VP `tvalid`；`ROCE_WR_IMM` 是死碼；`dp_pkt_1722B` 暫存器沒有使用；RTL 檔頭的設定 RAM 註解過時；CoE timestamp 是送出時間 | R | [dp_pkt_top 注意事項](docs/modules/dp_pkt_top.md#注意事項) |
| I2C 10-bit 讀取不符規格；`status[2]` 實為逾時；高 APB 時脈板級上 SCL 超過 400 kHz | R + I | [peripherals 注意事項](docs/modules/peripherals.md#注意事項) |
| UART 註解寫 16x oversampling，參數是 8 | R | [peripherals §UART](docs/modules/peripherals.md#uart) |
| `cam_rcvr` 不能反壓相機，HSB 停止接收約 4 µs 後資料遺失 | R + I | [performance §6](docs/performance.md#6-緩衝與反壓鏈) |
| buffer 環不能跨 8 GB 邊界；host 預設 MTU 1500 | R + X + I | [flow 注意事項](docs/flow.md#注意事項) |
| 512-bit HIF、MTU 1500 時 Data Plane 約 80 Gb/s，達不到 100G 線速 | I | [performance §3](docs/performance.md#3-hsb-內部的封包間隔推斷) |
| Bridge 透明時鐘用 OR 而不是加法修正 correctionField；CAM 沒有老化 | R | [bridge 注意事項](docs/modules/bridge.md#注意事項) |
| `lib` 中 `axis_demux`、`comparator`、`debouncer`、`str_fwd_fifo` 沒有被引用 | R | [lib](docs/modules/lib.md) |
| `imu_top` 沒有被任何板級實例化 | R | [ref_design](docs/modules/ref_design.md) |
| ECB 封包在 pair 中途結束仍執行一次 APB 存取；單組 `WR_BLOCK` 被補齊時可能多寫一次 `glb_scratch` | R + I | [rx_ls_parser 注意事項](docs/modules/rx_ls_parser.md#注意事項) |
| ECB `cmd_dout` 跨時脈沒有同步器；BOOTP reply 沒有 xid / chaddr 驗證；LS 路徑所有 host 埠共用，會互相阻擋 | R + I | 同上 |
| `roce_ack`：重複封包不回 ACK；IPv4 checksum 增量更新在借位時差 2（N）；第一個 ACK 的 PSN 為 0 | R + I + N | [roce_ack 注意事項](docs/modules/roce_ack.md#注意事項) |
| `reg_cdc` 在握手進行中的更新會遺失（HSB 內由 `apb_switch` 的 10 拍延遲避免） | R + I | [lib §reg_cdc](docs/modules/lib.md#reg_cdc) |
| `streaming_cdc` 讓 HIF 端的 PTP 時間固定晚約 20–40 ns，未補償 | R + I | [lib §streaming_cdc](docs/modules/lib.md#streaming_cdc) |
| `dc_fifo` 實體深度補到 2 的次方；AUTO RAM 判斷條件前後不一致 | R | [lib §dc_fifo_generic](docs/modules/lib.md#dc_fifo_generic--dc_fifo_stub) |
| EEPROM 不存在時 MAC 變成 I2C 資料緩衝 RAM 的上電內容（v7：由 I 升為 R）；EEPROM CRC 檢查與寫入工具不一致（N：正確映像 99.6 % 判為錯誤）且結果未使用 | R + X + N | [boot_and_reset 注意事項](docs/modules/boot_and_reset.md#注意事項) |
| Bridge：本 repo 沒有板級使用；只支援 Layer 2 PTP；一般 multicast 被丟棄；host 優先於 SIF | R | [bridge 注意事項](docs/modules/bridge.md#注意事項) |
| Bridge host RX 緩衝的 `o_axis_rx_tready` 沒接，64-bit 時大於約 1.8 KB 的封包讓該埠 bridge 路徑永久停擺；`rx_parser` 不受影響（v7：由 I 升為 R + M，並更正機制） | R + M | [bridge 注意事項 7](docs/modules/bridge.md#注意事項) |
| `tx_stream_buffer` 溢位時逐 beat 丟棄、`tlast` 遺失時兩包合併；不會永久錯位（v7：由 I 升為 R） | R | [tx_stream_buffer 注意事項 2](docs/modules/tx_stream_buffer.md#注意事項) |
| SPI 只讀交易與 `turnaround_len` ≥ 33 卡死；UART 接收端連續資料下可能失去同步 | R（UART 為 R + I） | [peripherals 注意事項](docs/modules/peripherals.md#注意事項) |
| I2S 除數超出範圍時 BCLK 停止；PCM 等同 LJ；RX 聲道沒有標記 | R | [ref_design §i2s_top](docs/modules/ref_design.md#i2s_top) |
| `ram_player` `timer = 0` 不循環、`window_size < W_KEEP` 沒有 `tlast`、中途停止違反 AXIS | R | [data_gen §ram_player](docs/modules/data_gen.md#ram_player) |
| Bridge `del_req_val` 用錯 index；CAM 填滿後未命中送往 entry 0 | R | [bridge 注意事項](docs/modules/bridge.md#注意事項) |
| 事件序列器 opcode `11` 不是 NOP | R | [event](docs/modules/event.md) |
| `roce_ack` host QP RAM 只有 2 個 word；Bridge 學習請求可能遺失 | R | [roce_ack](docs/modules/roce_ack.md)、[bridge 注意事項](docs/modules/bridge.md#注意事項) |
| `delayed_io` 取消不停止計數器；CPNX100 延遲多 2.4 % | R | [ref_design §delayed_io](docs/modules/ref_design.md#delayed_io) |

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
| `bootp` 的 `ciaddr` | v3 列為「名稱與內容不符」 | v5：它是 BOOTP request 的 ciaddr 欄位（目前 IP），從 reply 的 `yiaddr` 更新，命名正確 |
| EEPROM 每次讀取長度 | v3 寫 28 byte（照抄原始碼註解） | v5：程式實際設定 32 byte |
| ECB `ACK_REQUEST` | v3 寫「host 軟體定義」 | v5：RTL 依此決定寫入命令是否回應 |
| 頂層方塊圖 | v2–v4 只部分標示實例化次數 | v5：每個模組都標示份數，並列出共用資源對效能的影響 |
| `hsb_ctrl_1` | v2 未說明極性 | `o_sw_sen_rst = ~hsb_ctrl_1`，實際極性由板級決定 |
| `dp_pkt_top` §5 單封包 + `md_disable` | v5 寫 `fsm_cnt_max = 7` | v6：18（前一輪必為 metadata，`is_new = 1`） |
| packetizer `duplicate` | v5 寫「全 1」 | v6：`'b1` = `{select 0, commit 1}`，每個 VP 收到 VP 0 的資料 |
| Terasic S10 `VP_SIZE` | v5 寫 256 | v6：預設 128（256 只在 `JESD_HIGH_PERF`、1024-bit） |
| PTP correctionField | v5 寫「無號、負值算錯」 | v6：mod 2²⁴ 運算，負值正確，只有超過 ±8.4 ms 回捲 |
| ECB `total_pairs` | v5 寫成 N | v6：等於 N − 1，與完成數比較；只用於 RoCE-ECB |
| BOOTP / EEPROM IP 優先順序 | v5 寫「BOOTP > EEPROM」 | v6：最後發生的事件勝出，同拍才是 BOOTP 優先 |
| `data_gen` 速率 | v5 寫 `/ 2^17` | v6：`/ 2^16` |
| `tx_stream_buffer` 容量（performance） | v5 寫 16 KB | v6：4096 × 64 bit = 32 KB |
| 事件序列器 opcode `11` | v5 寫 NOP | v6：不是空操作，會對 addr 做 POLL |
| Bridge CAM 未命中 | v5 寫「丟棄」 | v6：CAM 填滿後轉送到 entry 0 的埠 |
| `eth_pkt` skid 設定 | v5 照抄註解 | v6：依 index 是 DP / PTP / LS |
| `ram_player` 的 `i_ptp` | v3 推測「在指定 PTP 時間播放」 | v6：把送出時間寫進資料 |
| `rx_parser` 封包間空檔 | v6 寫「至少 2 拍」 | v7：背靠背時 1 拍，n 拍封包讀出需 n + 1 拍（M） |
| `rx_parser` 溢位後果 | v6 寫「封包邊界可能錯位」（推斷） | v7：`in_pkt_cnt` 計入被丟的 `tlast`，之後每個封包都配到前一包的 metadata，直到 reset |
| Bridge host RX 緩衝 | v6 寫「almost full 時對 `rx_parser` 反壓，經 `rx_parser` 擋住同埠所有流量」 | v7：`o_axis_rx_tready` 沒接，沒有反壓；beat 被靜默丟棄，該埠 bridge 路徑停擺，`rx_parser` 不受影響 |
| 測試草稿 S6 的巨集 | v6 寫 `+define+ENABLE_ROCE_ACK` | v7：`SIF_TX_ROCE_RC_ENABLE`（`ENABLE_ROCE_ACK` 是 `rx_parser` 的參數） |

## 建議的下一步驗證

1. 取得 VCS 或 Xcelium 後，跑 `fpga/nv_hsb_ip_simple_tb`（`make run TEST_MODE=SINGLE_SENSOR|ALL_SENSORS|HOST2SEN`、`make coe`），見 [testbench](docs/testbench.md)。
2. 跑 [定向測試計畫](docs/test-plan.md) 的 U1–U3、S1–S12，確認 [問題清單](docs/issues.md) 中標 R / I / M 的項目；S11 同時驗證 `tools/model/rx_parser_model.py` 這個模型本身。之後再做 PTP master 模型、多 VP packetizer（DP-8）等需要新模型的測試。
3. 用模擬波形取代 `docs/timing/` 的示意圖（v4 共 5 張）。
4. 在硬體上量測 [performance](docs/performance.md) 的估算值，特別是 512-bit HIF 的封包間隔；`dp_pkt_top` 的 header FSM（§3）在 v7 仍是推斷，沒有建模。

