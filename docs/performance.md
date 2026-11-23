# 效能分析

本章從 RTL 參數與行為推算 HSB 的頻寬、效率、延遲與緩衝餘裕。**所有數字都是由 RTL 推導的估算，沒有經過模擬或硬體量測**；標「推斷」的項目牽涉多個模組的時序交互，誤差可能較大。資源使用量（LUT、BRAM）需要合成報告，本 repo 沒有，所以不在範圍內。

## 1. 介面頻寬

| 板級 | HIF 寬度 × 時脈 | HIF 頻寬 | Ethernet | 餘裕 |
|---|---|---|---|---|
| CPNX100 / NV MIPI 參考 / MPF200 | 64 bit × 156.25 MHz | 10.0 Gb/s | 10G | 0：HIF 與線速完全相等 |
| Terasic S10 | 512 bit × 201.42 MHz | 103.1 Gb/s | 100G | 3 % |
| PYNQ RFSoC | 512 bit × 322.27 MHz | 165 Gb/s | 100G | 65 % |

10G 板級的 HIF 頻寬剛好等於線速，所以 HSB 內部任何一拍空檔都直接降低可達到的吞吐量。

## 2. Data Plane 封包效率

每個資料封包在線上的額外開銷：

- RoCE：70 byte header + 4 byte ICRC + 4 byte FCS + 20 byte preamble / IFG，共 98 byte。
- CoE：46 byte header + 4 byte FCS + 20 byte preamble / IFG，共 70 byte。

payload 由 host 依 `floor((MTU − overhead) / 128) × 128` 決定（overhead：RoCE 74、CoE 46）：

| 協定 | MTU | payload | `dp_pkt_len`（page） | 線上 byte | 效率 | 10G 可用頻寬 |
|---|---|---|---|---|---|---|
| RoCE | 1500 | 1408 | 11 | 1506 | 93.5 % | 9.35 Gb/s |
| RoCE | 4096 | 3968 | 31 | 4066 | 97.6 % | 9.76 Gb/s |
| CoE | 1500 | 1408 | 11 | 1478 | 95.3 % | 9.53 Gb/s |
| CoE | 4096 | 3968 | 31 | 4038 | 98.3 % | 9.83 Gb/s |

每個 frame 另有一個 metadata 封包（RoCE 206 byte、CoE 174 byte），對大 frame 可以忽略。payload 必須是 128 byte 的整數倍，所以 MTU 1500 時浪費了 1500 − 74 − 1408 = 18 byte。

host 預設 MTU 是 1500（見 [flow §注意事項](flow.md#注意事項)）。即使板級 `HOST_MTU = 4096`，沒有在 enumeration metadata 指定 `mtu` 時效率仍是 93.5 %。

## 3. HSB 內部的封包間隔（推斷）

`dp_pkt_top` 用一個 header FSM 服務所有 host 埠（[dp_pkt_top §5](modules/dp_pkt_top.md#5-header-fsm)），下一個封包的準備工作要等目前封包快結束（`hif_not_busy_soon`，剩不到 10 拍）才開始：

| 步驟 | 約略拍數 |
|---|---|
| `hif_not_busy_soon` 拉高（`near_pkt_end` 再打一拍） | 封包結束前約 8 拍 |
| `IDLE → LOAD_STS → GRANT` | 3–4 |
| `CALC` 從 `fsm_cnt = 2` 到 commit 點 7 | 5 |
| `commit_arm` → `pkt_commit` | 2 |
| 合計：從開始準備到 commit | 約 11 |

所以兩個資料封包之間大約有 3 拍空檔，`eth_pkt` 再加 1 拍（Data Plane 每個封包後強制讓出一拍，見 [eth_pkt §1](modules/eth_pkt.md#1-data-plane-間隔)）：

| HIF | MTU | 封包拍數（header + payload + ICRC） | 加上空檔 | HSB 端 payload 速率 | 線速上限 | 瓶頸 |
|---|---|---|---|---|---|---|
| 64 bit / 156.25 MHz | 1500 | 186 | 約 190 | 約 9.26 Gb/s | 9.35 Gb/s | 兩者接近，HSB 略低 |
| 64 bit / 156.25 MHz | 4096 | 506 | 約 510 | 約 9.72 Gb/s | 9.76 Gb/s | 兩者接近 |
| 512 bit / 201.42 MHz（S10） | 1500 | 24 | 約 28 | 約 81 Gb/s | 93.5 Gb/s | **HSB**：封包太短，FSM 的固定開銷佔比大 |
| 512 bit / 201.42 MHz（S10） | 4096 | 64 | 約 68 | 約 94 Gb/s | 97.6 Gb/s | 兩者接近 |

結論：

- 10G 板級在任何 MTU 下都接近線速。
- 100G 板級要用大 MTU 才能接近線速，MTU 1500 時大約只有 80 Gb/s。
- `HOST_IF_INST = 2` 且兩個埠同時滿載時，FSM 必須輪流服務。每個封包約佔 FSM 12–15 拍，512-bit、MTU 1500 時兩個埠合計需要的 FSM 時間超過封包本身的長度，兩埠無法同時達到線速。

## 4. 感測器端

| 項目 | 值 | 說明 |
|---|---|---|
| CPNX100 SIF RX | 64 bit × 感測器時脈 | CLNX17 → CPNX100 LVDS：11 lane × 1 Gbps，扣掉 metadata / tuser 後資料 80 bit / 88 bit = 10 Gb/s |
| packetizer RAW10 排程 | 每 16 拍有 1 拍不收資料 | 感測器端最大輸入速率 = 15/16 × 64 bit × SIF 時脈 |
| RAW10 輸出膨脹 | 120 → 128 byte（+6.7 %） | line 再補到 64 byte 的倍數 |
| RAW12 排程 | `ld_arr = 0x7`、`max_addr = 2` | 每拍都收資料 |

**範例**：1920 × 1080 RAW10、60 fps。packetizer 輸出每 frame 2,764,800 byte（見 [flow §7](flow.md#7-一個-frame-的傳送)），60 fps 為 1.33 Gb/s，佔 10G 的 14 %。以 9.26 Gb/s 計算，這種 frame 最多約 418 fps。

## 5. 延遲（推斷）

感測器資料從 SIF RX 進入到第一個封包離開 HSB：

| 段落 | 延遲 | 來源 |
|---|---|---|
| packetizer 管線 | `latency` + 排序網路約 `PACK_PIPE_COUNT + 3` 拍（CPNX100：約 8 個 SIF 時脈） | [packetizer §4](modules/packetizer.md#4-可程式化資料路徑packetizersv) |
| VP FIFO 跨時脈 | `dc_fifo` 同步約 3–4 拍 | |
| **VP 輸出閘控** | FIFO 累積到 `AE_FLAG`（約一個封包的 payload）或看到 frame 結尾才放行 | [packetizer §6](modules/packetizer.md#6-virtual-portvirtual_portsv) |
| header FSM | 約 11 拍 | §3 |
| 傳送一個封包 | 64-bit、MTU 1500：186 拍 ≈ 1.2 µs | |

主要延遲來自 VP 輸出閘控：以 10 Gb/s 的感測器速率計算，累積 1.4 KB 需要約 1.1 µs。感測器越慢，這段等待越長（例如 1.33 Gb/s 時約 8.5 µs）。這是為了保證 `dp_pkt` 取資料時不斷流（[dp_pkt_top §1](modules/dp_pkt_top.md#1-輸入契約)）而付出的代價。

frame 完成通知（metadata 封包）在最後一個資料封包之後立即送出：`sif_eof` 會讓這個 VP 優先，並搶占其他 VP 正在準備的資料封包（[dp_pkt_top §5](modules/dp_pkt_top.md#5-header-fsm)）。

## 6. 緩衝與反壓鏈

| 緩衝 | 大小（CPNX100） | 滿時的行為 |
|---|---|---|
| `cam_rcvr` `axis_buffer` | 512 × 80 bit = 5 KB | `NO_BACKPRESSURE`：**資料遺失**，不會反壓到相機 |
| packetizer → VP FIFO | 1006 × 64 bit ≈ 8 KB（MTU 4096）/ 356 × 64 bit ≈ 2.8 KB（MTU 1500）；`dc_fifo` 實體深度補到 1024 / 512 筆，門檻仍以 1006 / 356 計算 | 7/8 時 `pack_tready = 0`，反壓 SIF RX |
| `rx_parser` 輸入 FIFO | 2 × MTU | 溢位時 beat 遺失（[rx_parser 注意事項](modules/rx_parser.md#注意事項)） |
| `tx_stream_buffer` | `SIF_TX_BUF_SIZE` × `SIF_TX_WIDTH`（CPNX100：4096 × 32 bit = 16 KB） | almost full 時送 802.3x PAUSE 給 host |

**反壓鏈的斷點（推斷）**：在 CPNX100 上，HSB 可以反壓 `cam_rcvr`，但 `cam_rcvr` 不能反壓相機。HSB 停止接收時，5 KB 的緩衝以 10 Gb/s 計算約 4 µs 就滿，之後資料遺失。可能讓 HSB 長時間停止接收的情況：

- 同一個 host 埠被其他 VP 的大量資料佔用。
- MAC 對 HSB 反壓，例如收到 PAUSE，或連結速率低於感測器速率。

相機頻寬必須低於 Ethernet 可用頻寬（§2、§3）並留有餘裕。

## 7. 控制平面

| 項目 | 估算 |
|---|---|
| LS 路徑吞吐量 | 1 byte / HIF 時脈（8-bit 路徑）。一個 ECB 寫入請求約 60–80 byte 的封包，在 FPGA 內的解析時間約 0.5 µs（156.25 MHz） |
| APB 存取 | 每筆 addr / data 都要一次 HIF → APB → HIF 的 CDC 往返；CPNX100 的 APB 只有 19.53 MHz |
| host 端 | 同時只有一個 ECB 請求在途（mutex），每次存取的延遲由網路往返與軟體決定，遠大於 FPGA 內部延遲 |

需要多步驟的操作（例如 I2C 交易）可以用事件序列器在 FPGA 內執行，減少 ECB 往返（[event](modules/event.md)）。

## 8. 時間同步精度（推斷）

| 誤差來源 | 大小 |
|---|---|
| 時間戳解析度 | 1 個 PTP 時脈（CPNX100：9.96 ns） |
| RX 內部延遲估計 | 以參數算出的固定拍數（[ptp §2](modules/ptp.md#2-接收時間戳)）；實際上跨時脈 FIFO 的佔用量會變動，每個時脈域約 ±1–2 拍 |
| TX 時間戳位置 | `eth_pkt` 仲裁器，而不是線上的 SFD；MAC 內部延遲需要 `ptp_ctrl_dly` 補償 |
| DPLL | `fa` 解析度約 6 ppb（[ptp §7](modules/ptp.md#7-首次同步與-dpll)） |
| PTP 時間跨到 HIF | `streaming_cdc` 固定延遲約 3–4 個 HIF 時脈（約 20–40 ns），RTL 未補償；影響 metadata 的 SOF 時間與 CoE 時間戳（[lib §streaming_cdc](modules/lib.md#streaming_cdc)） |

綜合起來，HSB 與 master 之間的同步誤差大約在數十奈秒等級，絕對偏差取決於 `ptp_ctrl_dly` 是否針對板級的 MAC / PHY 校正過。
