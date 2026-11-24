# 效能分析

本章從 RTL 參數與行為推算 HSB 的頻寬、效率、延遲與緩衝餘裕。**所有數字都沒有經過 HDL 模擬或硬體量測**；標「推斷」的項目牽涉多個模組的時序交互，誤差可能較大。§3 與 §7 的數字來自照 RTL 逐暫存器重寫的 Python 逐拍模型，可信度介於讀 RTL 與模擬之間。資源使用量（LUT、BRAM）需要合成報告，本 repo 沒有，所以不在範圍內。

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

## 3. HSB 內部的封包間隔（逐拍模型）

`dp_pkt_top` 用一個 header FSM 服務所有 host 埠（[dp_pkt_top §5](modules/dp_pkt_top.md#5-header-fsm)），下一個封包的準備工作要等目前封包快結束（`hif_not_busy_soon`）才開始。用 [`tools/model/dp_pkt_model.py`](../tools/model/dp_pkt_model.py) 把這段邏輯照 RTL 逐暫存器重寫（FSM、commit 握手、`hif_busy` / `hif_reserved` / `hif_sif_mask`、`dp_pkt` 的計數與 `near_pkt_end`、`dp_pkt_hdr` 與 header / payload 拼接），量測 `dp_pkt_top` 輸出（`dout`）上兩個資料封包之間的空拍。模型假設下游（`roce_icrc`、`eth_pkt`、MAC）永遠 ready、設定 RAM 沒有 APB 存取、VP 一直有資料、frame 很長（沒有 metadata 封包）；這些假設以外的部分沒有建模。

**一個封包的時間線**（`s` = `hif_not_busy_soon` 拉高的那一拍）：

| 拍 | 事件 |
|---|---|
| `s` | `dp_pkt` 剩 7 個 payload beat 要取（`(pkt_len − pkt_cnt) < 10` 再經 `near_pkt_end`、`hif_not_busy_soon` 兩級暫存） |
| `s + 1 + d` | `sif_req` 拉高；`d` = 0–3，見下面的 `hif_sif_mask` |
| `s + 2 + d` → `s + 9 + d` | `LOAD_STS`、`GRANT`、`CALC`（`fsm_cnt` 2 → 7，`DUMP_CLK_CYCLES = 7`） |
| `s + 8` | 目前封包在 `dout` 的 `tlast` |
| `s + 9` | `hif_busy = 0` |
| `s + 10 + d` | `pkt_commit`（`commit_arm` 先暫存一拍） |
| `s + 13 + d` | 下一個封包的第一個 header beat（`hdr_trigger` → `dp_pkt_hdr` 狀態機 → `axis_reg`） |

所以空拍 = **4 + d** 拍。

**`hif_sif_mask` 的相位。** 每個 host 的 VP 公平性遮罩由三個暫存器串成（[dp_pkt_top.sv#L668–L688](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/dp_pkt/dp_pkt_top.sv#L668-L688)）：`hif_sif_unserved ← ~hif_sif_mask`、`hif_sif_served ← ~|hif_sif_unserved`、`hif_sif_mask ← served ? 0 : (mask | sif_gnt_r)`。只有一個 VP、`sif_gnt_r` 一直指向它時，這是三級反相的環，以 6 拍為週期振盪（3 拍遮住、3 拍放開）。`hif_not_busy_soon` 拉高時剛好被遮住，`sif_req` 就晚 1–3 拍（d）。封包週期是固定的，所以相位會鎖住，每個封包的 d 都一樣，取決於封包長度除以 6 的餘數（[DP-16](issues.md#data-plane-與封包處理)）。

**單一 host、單一 VP、連續資料封包：**

| HIF | MTU | `dout` 拍數（header + payload） | 穩態空拍 | 每包拍數 | HSB 端 payload 速率 | 線速上限 |
|---|---|---|---|---|---|---|
| 64 bit / 156.25 MHz | 1500 | 185 | 7 | 192 | 9.17 Gb/s | 9.35 Gb/s |
| 64 bit / 156.25 MHz | 4096 | 505 | 5 | 510 | 9.73 Gb/s | 9.76 Gb/s |
| 512 bit / 201.42 MHz（S10） | 1500 | 24 | 6 | 30 | **75.6 Gb/s** | 93.5 Gb/s |
| 512 bit / 201.42 MHz（S10） | 4096 | 64 | 4 | 68 | 94.0 Gb/s | 97.6 Gb/s |

64 bit 時 ICRC 在最後一拍放不下，`roce_icrc` 要多送一拍；這裡假設它落在空拍裡，不增加週期（`roce_icrc` 沒有建模）。

**兩個 host、各一個 VP、同時滿載：** 每個 host 每 189 / 509 / 28 / 68 拍送一個封包，也就是兩個 host 同時達到上表 d = 0 的速率（512 bit、MTU 1500 時各 81.0 Gb/s）。VP 輪流被授權時，各 host 的遮罩不再以單一 VP 的方式振盪，d 為 0；FSM 處理一個封包約佔 14 拍，兩個 host 剛好排得下。

結論：

- 10G 板級在任何 MTU 下都接近線速；MTU 1500 時 HSB 略低（9.17 vs 9.35 Gb/s）。
- 100G 板級在 MTU 1500 時，單一 VP 只有約 76 Gb/s，兩個 VP / host 時約 81 Gb/s；要接近線速需要大 MTU。
- 這些數字不含 `roce_icrc` 與 `eth_pkt` 的行為；兩者若在封包之間再加拍數，速率會更低。

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
| header FSM | `hif_not_busy_soon` 之後 13–16 拍出第一個 header beat（與前一個封包重疊） | §3 |
| 傳送一個封包 | 64-bit、MTU 1500：186 拍 ≈ 1.2 µs | |

主要延遲來自 VP 輸出閘控：以 10 Gb/s 的感測器速率計算，累積 1.4 KB 需要約 1.1 µs。感測器越慢，這段等待越長（例如 1.33 Gb/s 時約 8.5 µs）。這是為了保證 `dp_pkt` 取資料時不斷流（[dp_pkt_top §1](modules/dp_pkt_top.md#1-輸入契約)）而付出的代價。

frame 完成通知（metadata 封包）在最後一個資料封包之後立即送出：`sif_eof` 會讓這個 VP 優先，並搶占其他 VP 正在準備的資料封包（[dp_pkt_top §5](modules/dp_pkt_top.md#5-header-fsm)）。

## 6. 緩衝與反壓鏈

| 緩衝 | 大小（CPNX100） | 滿時的行為 |
|---|---|---|
| `cam_rcvr` `axis_buffer` | 512 × 80 bit = 5 KB | `NO_BACKPRESSURE`：**資料遺失**，不會反壓到相機 |
| packetizer → VP FIFO | 1006 × 64 bit ≈ 8 KB（MTU 4096）/ 356 × 64 bit ≈ 2.8 KB（MTU 1500）；`dc_fifo` 實體深度補到 1024 / 512 筆，門檻仍以 1006 / 356 計算 | 7/8 時 `pack_tready = 0`，反壓 SIF RX |
| `rx_parser` 輸入 FIFO | 2 × MTU（512-bit 時 3 × MTU），補到 2 的冪次 | 溢位時 beat 遺失，之後資料與 metadata 永久錯開直到 reset（[rx_parser 注意事項](modules/rx_parser.md#注意事項)、§7） |
| `tx_stream_buffer` | 4096 × `max(HIF 寬度, SIF_TX_WIDTH)`（`axis_buffer_tx` 的 `CENTER_WIDTH`；CPNX100：4096 × 64 bit = 32 KB） | almost full 時送 802.3x PAUSE 給 host |

**反壓鏈的斷點（推斷）**：在 CPNX100 上，HSB 可以反壓 `cam_rcvr`，但 `cam_rcvr` 不能反壓相機。HSB 停止接收時，5 KB 的緩衝以 10 Gb/s 計算約 4 µs 就滿，之後資料遺失。可能讓 HSB 長時間停止接收的情況：

- 同一個 host 埠被其他 VP 的大量資料佔用。
- MAC 對 HSB 反壓，例如收到 PAUSE，或連結速率低於感測器速率。

相機頻寬必須低於 Ethernet 可用頻寬（§2、§3）並留有餘裕。

## 7. `rx_parser` 讀出能力（逐拍模型）

`rx_parser` 是 store-and-forward（[rx_parser §5](modules/rx_parser.md#5-store-and-forward-與讀出)），所有收進來的封包（包括最後被丟棄的）都要從輸入 FIFO 讀出一次。[`tools/model/rx_parser_model.py`](../tools/model/rx_parser_model.py) 把這段邏輯照 RTL 逐暫存器重寫成 Python（`sc_fifo` 的旗標時序、`axis_buffer` 的 `WAIT2SEND` 封包計數與預取、`axis_reg`、三個 metadata FIFO、`hdr_ready` / `buf_axis_tready` / `hdr_rden`），再餵入各板級的線速流量。只有 header 完成的時間點（±1 拍）與 MAC 的送出方式是近似的，這兩者只影響起始延遲，不影響穩態吞吐量。

```sh
python3 tools/model/rx_parser_model.py      # 約 7 秒；任何預期不符時結束碼為 1
```

**讀出速率。** 背靠背讀出時，n 拍的封包需要 n + 1 拍（64-bit 的 8、9、24、188 拍與 512-bit 的 1、2、8、24 拍都量到剛好多 1 拍）。

**各板級收 60-byte frame 線速時：**

| 板級 | MAC 每幾拍送一個 | 讀出需要 | 結果 |
|---|---|---|---|
| CPNX100 / NV MIPI / MPF200（64 bit、156.25 MHz、10G） | 10.5 | 9 | 跟得上；輸入 FIFO 最多 13 筆 |
| PYNQ RFSoC（512 bit、322.27 MHz、100G） | 2.17 | 2 | 跟得上；最多 4 筆 |
| **Terasic S10（512 bit、201.42 MHz、100G）** | **1.5** | **2** | **跟不上**：metadata FIFO 與資料 FIFO 都溢位，之後的封包配錯 metadata |

**Terasic S10 在 100G 下連續收到的封包數上限**（超過就溢位，觸發 [DP-1 / DP-2](issues.md#data-plane-與封包處理)）：

| frame 長度 | MAC 每幾拍送一個 | 讀出需要 | 溢位前可連續收 |
|---|---|---|---|
| 60 / 64 B | 1.5 | 2 | 108 個 |
| 128 B | 2.5 | 3 | 174 個 |
| 256 B | 4.67 | 5 | 456 個 |
| 512 B | 8.67 | 9 | 834 個 |
| 1024 B | 16.89 | 17 | 2286 個 |
| 1500 B | 24.67 | 25 | 720 個 |
| 2048 B 以上 | ≥ 讀出需要 | | 不會溢位（5000 個內） |

PYNQ 的 HIF 時脈有 65 % 餘裕，表中所有長度都跟得上。S10 的 HIF 頻寬只比 100G 多 3 %，每個封包多的 1 拍就吃掉了餘裕。

**溢位之後（DP-1）。** 模型重現了 [rx_parser 注意事項 5](modules/rx_parser.md#注意事項) 的機制：讀出被擋 2000 拍（Bridge 背壓）時輸入 FIFO 丟了 1129 個 beat；`in_pkt_cnt` 比 `out_pkt_cnt` 多 6；擋住結束很久之後送入的 63 個封包**全部**配到錯的 metadata，輸出中間出現 19132 個空拍。對照組（只擋 400 拍、沒有溢位）完全正常。

**Bridge host RX 緩衝（BR-1）。** 同一個腳本也模擬 `bridge_pkt_proc` 的 host RX 緩衝（`o_axis_rx_tready` 沒接、almost full 224）：先送 200、1500 byte，再送一個 2000 byte（250 拍），之後的 20 個 1500-byte frame 一個都出不來，計數停在 225；全部 1500 byte 時 23 個都正常。

## 8. 控制平面

| 項目 | 估算 |
|---|---|
| LS 路徑吞吐量 | 1 byte / HIF 時脈（8-bit 路徑）。一個 ECB 寫入請求約 60–80 byte 的封包，在 FPGA 內的解析時間約 0.5 µs（156.25 MHz） |
| APB 存取 | 每筆 addr / data 都要一次 HIF → APB → HIF 的 CDC 往返；CPNX100 的 APB 只有 19.53 MHz |
| host 端 | 同時只有一個 ECB 請求在途（mutex），每次存取的延遲由網路往返與軟體決定，遠大於 FPGA 內部延遲 |

需要多步驟的操作（例如 I2C 交易）可以用事件序列器在 FPGA 內執行，減少 ECB 往返（[event](modules/event.md)）。

## 9. 時間同步精度（推斷）

| 誤差來源 | 大小 |
|---|---|
| 時間戳解析度 | 1 個 PTP 時脈（CPNX100：9.96 ns） |
| RX 內部延遲估計 | 以參數算出的固定拍數（[ptp §2](modules/ptp.md#2-接收時間戳)）；實際上跨時脈 FIFO 的佔用量會變動，每個時脈域約 ±1–2 拍 |
| TX 時間戳位置 | `eth_pkt` 仲裁器，而不是線上的 SFD；MAC 內部延遲需要 `ptp_ctrl_dly` 補償 |
| DPLL | `fa` 解析度約 6 ppb（[ptp §7](modules/ptp.md#7-首次同步與-dpll)） |
| PTP 時間跨到 HIF | `streaming_cdc` 固定延遲約 3–4 個 HIF 時脈（約 20–40 ns），RTL 未補償；影響 metadata 的 SOF 時間與 CoE 時間戳（[lib §streaming_cdc](modules/lib.md#streaming_cdc)） |

綜合起來，HSB 與 master 之間的同步誤差大約在數十奈秒等級，絕對偏差取決於 `ptp_ctrl_dly` 是否針對板級的 MAC / PHY 校正過。
