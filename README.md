# hsb-ana — NVIDIA Holoscan Sensor Bridge FPGA IP 分析

本 repo 分析 NVIDIA Holoscan Sensor Bridge（HSB）的 FPGA IP（`fpga/nv_hsb_ip`）。目標是把 HSB 的 Ethernet RX 路徑改成 IEEE 1722（AVTP）Listener，把收到的資料送到 MIPI CSI-2 TX。

分析重點因此放在 **Ethernet → Sensor TX** 這條路徑：這條路徑上的模組逐行分析，其他模組只到結構層級。

## 分析基準

| 項目 | 值 |
|---|---|
| 上游 repo | [nvidia-holoscan/holoscan-sensor-bridge](https://github.com/nvidia-holoscan/holoscan-sensor-bridge) |
| 版本 | 3.0.0 |
| Commit | [`41cecaa`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/tree/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8)（2026-11-09） |
| IP 版本常數 | `HOLOLINK_REV = 16'h2609` |
| 參考板級設定 | Lattice CPNX100（`fpga/lattice/cpnx100-eth-sensor-bridge/cpnx100/rtl/top/HOLOLINK_def.svh`） |

文件中所有原始碼連結都固定在這個 commit，上游更新後連結不會失效。

## 閱讀順序

1. **[架構總覽](docs/architecture/overview.md)**：頂層方塊圖、時脈域、資料路徑、位址空間、開機流程。
2. **Listener 路徑模組**（依資料流順序，逐行分析）：

   | 順序 | 模組 | 功能 |
   |---|---|---|
   | 1 | [`rx_parser`](docs/modules/rx_parser.md) | Header 解析、分類、store-and-forward、VLAN 移除 |
   | 2 | [`roce_ack`](docs/modules/roce_ack.md) | RoCE RC 的 PSN 檢查、ACK/NAK、背壓 |
   | 3 | [`sensor_tx_pkt_proc`](docs/modules/sensor_tx_pkt_proc.md) | 去 header、依 QP 選感測器 |
   | 4 | [`tx_stream_buffer`](docs/modules/tx_stream_buffer.md) | 雙時脈 FIFO、預填、PAUSE（含 `axis_buffer_tx`、`pause_gen`） |
   | 5 | [`eth_pkt`](docs/modules/eth_pkt.md) | TX 仲裁、VLAN 插入、MAC 逾時 |

3. **其他模組**：

   | 模組 | 深度 |
   |---|---|
   | [`rx_ls_parser` / `ecb_rdwr_ctrl`](docs/modules/rx_ls_parser.md) | 主要邏輯 |
   | [`dp_pkt_top`（含 1722B Talker）](docs/modules/dp_pkt_top.md) | 主要邏輯 |
   | [`lib_axis` 共用元件](docs/modules/lib_axis.md) | 修改 Listener 時會用到的元件 |
   | [其他模組](docs/modules/others.md) | 結構層級 |

4. **參考資料**：
   - [暫存器表](docs/registers/regmap.md)（由 `tools/gen_regmap.py` 自動產生）
   - [位址空間與 RAM](docs/registers/memory-map.md)
   - [時序圖](docs/timing/)

5. **設計提案**：[1722 Listener 整合設計](design/1722-listener.md)

6. **[驗證狀態](VERIFICATION.md)**：每項結論是怎麼確認的、哪些還沒確認。

## 模組文件格式

每份模組文件都用同一個章節順序：

| 章節 | 內容 |
|---|---|
| 概要 | 一句話功能、原始碼連結、分析深度 |
| 參數 | parameter / localparam |
| 介面 | port 表 |
| 內部結構 | Mermaid 方塊圖 |
| 行為 | 依處理順序說明，附原始碼行號 |
| 時序 | 時序圖（如果有） |
| 暫存器 | 暫存器表 |
| 注意事項 | 限制、原始碼的不一致、可能的問題 |
| 與 1722 Listener 的關係 | 整合時要改什麼 |

## 工具

| 工具 | 用途 |
|---|---|
| `tools/gen_regmap.py` | 從 `regmap_pkg.sv` 產生暫存器表，並比對原始碼註解的位址 |
| `tools/wave.py` | 把 `docs/timing/*.wave.json`（WaveDrom 子集）轉成 SVG。GitHub 不支援 WaveDrom，所以 SVG 也一併 commit |

重新產生：

```sh
git clone https://github.com/nvidia-holoscan/holoscan-sensor-bridge ../holoscan-sensor-bridge
git -C ../holoscan-sensor-bridge checkout 41cecaa81ab906a55e7ec22e5e6989f7e602a4c8
python3 tools/gen_regmap.py ../holoscan-sensor-bridge > docs/registers/regmap.md
python3 tools/wave.py docs/timing/*.wave.json
```

## 名詞

| 名詞 | 意義 |
|---|---|
| HIF | Host Interface。FPGA 與 Ethernet MAC 之間的 AXIS 介面 |
| SIF RX / SIF TX | Sensor Interface。感測器 → FPGA / FPGA → 感測器 |
| STX | Sensor TX 路徑：Ethernet 資料送到 SIF TX |
| LS | Low Speed。控制封包（ECB、BOOTP、ARP、Ping、Loopback）走的 8-bit 路徑 |
| ECB | HSB 的暫存器讀寫協定（UDP 8192） |
| VP | Virtual Port。packetizer 拆出的子串流 |
| CoE | Camera over Ethernet。HSB 用 IEEE 1722B 實作的資料格式 |

## 版本紀錄

| 版本 | Commit | 說明 |
|---|---|---|
| v1 | `2a6cf26` | 依資料路徑分章的第一版 |
| v2 | 目前版本 | 改為每個模組一份文件；Listener 路徑逐行分析；加入時序圖、permalink、自動產生的暫存器表、驗證狀態；設計提案移到 `design/` |
