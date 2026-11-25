# hsb-ana — NVIDIA Holoscan Sensor Bridge FPGA IP 分析

本 repo 完整分析 NVIDIA Holoscan Sensor Bridge（HSB）的 FPGA IP（`fpga/nv_hsb_ip`），涵蓋所有子系統、共用元件、參考設計、板級整合與驗證環境。粗看用方塊圖（block view），細看用 RTL 逐段說明，每項說明都附固定 commit 的原始碼行號連結。

## 分析基準

| 項目 | 值 |
|---|---|
| 上游 repo | [nvidia-holoscan/holoscan-sensor-bridge](https://github.com/nvidia-holoscan/holoscan-sensor-bridge) |
| 版本 | 3.0.0 |
| Commit | [`41cecaa`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/tree/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8)（2026-11-09） |
| IP 版本常數 | `HOLOLINK_REV = 16'h2609` |
| 參數舉例用的板級 | Lattice CPNX100（各板級比較見 [boards](docs/boards.md)） |

文件中所有原始碼連結都固定在這個 commit，上游更新後連結不會失效。

## 閱讀順序

1. **[架構總覽](docs/architecture/overview.md)**：頂層方塊圖（區分每個 host 埠一份 / 每個感測器一份 / 全系統共用）、跨時脈地圖、控制平面與 Data Plane 全貌、編譯參數、`eth_pkt` 優先權、位址空間、開機流程。
2. **子系統**：

   | 子系統 | 文件 | 模組 | 分析深度 |
   |---|---|---|---|
   | Host RX | [`rx_parser`](docs/modules/rx_parser.md) | Header 解析、分類、store-and-forward、VLAN 移除 | 逐行 |
   | Host TX | [`eth_pkt`](docs/modules/eth_pkt.md) | 6 埠優先權仲裁、VLAN 插入、MAC 逾時 | 逐行 |
   | 控制平面 | [`rx_ls_parser`](docs/modules/rx_ls_parser.md) | LS 分派、ECB 協定（握手、跨時脈、邊界情況）、BOOTP enumeration、ARP / Ping | 逐行 |
   | 控制平面 | [APB 匯流排](docs/modules/apb.md) | 解碼樹、`apb_switch`、watchdog、`s_apb_reg` / `s_apb_ram` 跨時脈與埠仲裁 | 逐行 |
   | 控制平面 | [事件與序列器](docs/modules/event.md) | 事件向量、中斷封包、暫存器序列器 | 逐行 |
   | Data Plane（Sensor → Host） | [`packetizer`](docs/modules/packetizer.md) | bypass / 可程式化 / 固定 pattern、Virtual Port | 逐行 |
   | Data Plane | [`dp_pkt_top`](docs/modules/dp_pkt_top.md) | VP 仲裁、設定 RAM、header FSM、RoCEv2 / CoE header、metadata、SOF 時間戳 | 逐行 |
   | Data Plane | [`data_gen` / `ram_player`](docs/modules/data_gen.md) | 測試資料產生、RAM 重播與時間戳模式 | 逐行 |
   | Sensor TX（Host → Sensor） | [`sensor_tx_pkt_proc`](docs/modules/sensor_tx_pkt_proc.md) | 去 header / ICRC、依 QP 分流 | 逐行 |
   | Sensor TX | [`tx_stream_buffer`](docs/modules/tx_stream_buffer.md) | 雙時脈 FIFO、預填、PAUSE（含 `pause_gen`） | 逐行 |
   | RoCE | [`roce_ack`](docs/modules/roce_ack.md) | RC 的 PSN 檢查、ACK / NAK | 逐行 |
   | RoCE | [`roce_icrc` / `lfsr_hc`](docs/modules/roce.md) | ICRC 計算、支援的封包長度 | 逐行 |
   | 時間同步 | [PTP](docs/modules/ptp.md) | 1588 E2E / gPTP / P2P、時間戳、offset 計算、DPLL 迴路增益、計時器 | 逐行 |
   | 開機 | [開機與 reset](docs/modules/boot_and_reset.md) | `reset_gen`（串接與軟體 reset）、`sys_init`、`eeprom_info`、`glb_ctrl_top` | 逐行 |
   | 周邊 | [I2C / SPI / UART / GPIO](docs/modules/peripherals.md) | 交易狀態機、位元引擎、時脈公式、逾時、暫存器 | 逐行 |
   | Bridge | [Bridge 模式](docs/modules/bridge.md) | `routing_table`、`bridge_pkt_proc`、透明時鐘、緩衝 | 逐行 |
   | 共用 | [`lib_axis` / `misc`](docs/modules/lib.md) | 39 個元件目錄；CDC 元件與使用檢查、`axis_insert` 逐行 | 目錄 + 重點元件逐行 |
   | 參考設計 | [`ref_design`](docs/modules/ref_design.md) | `vsync_gen`、`delayed_io`、`i2s_top`（時脈、序列化、buffer）、`imu_top`（串流 I2C） | `delayed_io` 逐行；`vsync_gen` / I2S / IMU 主要邏輯 |

3. **系統層級**：
   - [端到端流程](docs/flow.md)：上電 → enumeration → 時間同步 → 設定 Data Plane → 一個 frame 的傳送，串起 host 軟體與 RTL，附數值範例。
   - [效能分析](docs/performance.md)：頻寬、封包效率、內部封包間隔、延遲、緩衝與反壓鏈、同步精度。
   - [板級整合](docs/boards.md)：6 個板級的設定比較、感測器接收路徑（CPNX100 + CLNX17 雙晶片架構）。
   - [驗證環境](docs/testbench.md)：`nv_hsb_ip_simple_tb` 的組成、初始化流程與檢查項目。
4. **參考資料**：
   - [完整暫存器索引](docs/registers/all-registers.md)：所有區塊的絕對位址，含原始碼註解比對（由 `tools/gen_allregs.py` 產生）
   - [位址空間與 RAM](docs/registers/memory-map.md)
   - [時序圖](docs/timing/)
5. **問題與驗證**：
   - [問題清單](docs/issues.md)：全部 RTL 問題的分級、觸發條件、確認方法與修正草稿。
   - [數值驗證](docs/verification-calcs.md)：`tools/verify/verify_calcs.py` 對 checksum、CRC、排程、版面等可計算結論的獨立比對。
   - [定向測試計畫](docs/test-plan.md)：對應問題清單的測試與 SystemVerilog 草稿（`tests/`）。
   - [驗證狀態](VERIFICATION.md)：每項結論是怎麼確認的，以及自動檢查的結果。

分析深度：**逐行** = 每個 always / assign 都讀過；**主要邏輯** = FSM、資料格式、暫存器都讀過，輔助邏輯略讀；**介面 / 暫存器層級** = 只讀介面、暫存器與註解。

## 模組文件格式

| 章節 | 內容 |
|---|---|
| 概要 | 功能、原始碼連結、分析深度 |
| 參數 / 介面 | parameter、port 表 |
| 內部結構 | Mermaid 方塊圖 |
| 行為 | 依處理順序說明，附原始碼行號 |
| 時序 | 時序圖（如果有） |
| 暫存器 | 暫存器表 |
| 注意事項 | 限制、原始碼的不一致、可能的問題 |

## 工具與重新產生

暫存器索引、板級設定表、時序圖由腳本產生；結論另有數值驗證、逐拍模型與多項靜態檢查。一次跑完：

```sh
python3 tools/check_all.py ../holoscan-sensor-bridge      # 上游 checkout 到 41cecaa
```

各工具說明見 [tools/README](tools/README.md)。

## 名詞

| 名詞 | 意義 |
|---|---|
| HIF | Host Interface。FPGA 與 Ethernet MAC 之間的 AXIS 介面 |
| SIF RX / SIF TX | Sensor Interface。感測器 → FPGA / FPGA → 感測器 |
| STX | Sensor TX 路徑：Ethernet 資料送到 SIF TX |
| LS | Low Speed。控制封包（ECB、BOOTP、ARP、Ping、Loopback）走的 8-bit 路徑 |
| ECB | HSB 的暫存器讀寫協定（UDP 8192） |
| VP | Virtual Port。packetizer 拆出的子串流 |
| CoE | Camera over Ethernet。HSB 用 IEEE 1722B 實作的 Data Plane 格式 |
| QP / PSN | RoCE 的 Queue Pair 編號 / 封包序號 |
| DPLL | PTP 用來調整本地計時器頻率的數位鎖相迴路 |

## 版本紀錄

目前版本 v7.3。各版內容與更正過的結論見 [CHANGELOG](CHANGELOG.md)。
