# 共用元件庫（`lib_axis`、`misc`）

本章是 `lib_axis/`（18 個檔案，3749 行）與 `misc/`（21 個檔案，2763 行）的目錄。每個元件列出功能、主要參數與使用位置。重要的元件另有詳細說明。

原始碼：[`lib_axis/`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/tree/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/lib_axis)、[`misc/`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/tree/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/misc)

## AXIS 元件（`lib_axis`）

| 元件 | 行數 | 功能 | 使用位置 |
|---|---|---|---|
| [`axis_buffer`](#axis_buffer) | 534 | FIFO：單/雙時脈、寬度轉換、整包放行 | 幾乎所有路徑 |
| [`axis_to_vec`](#axis_to_vec) | 195 | 收封包前 N bit 成一個向量 | `rx_parser`、`ptp_ingress`、`bootp`、`routing_table`、`arp_ping_pkt_proc` |
| `vec_to_axis` | 151 | 把向量當成一個封包送出，可補到 `PADDED_WIDTH` | `bootp`、`ecb_rdwr_ctrl`、`ctrl_bus_evt_int`、`pause_gen`、`roce_ack`、`arp_ping_pkt_proc` |
| `vec_to_axis_dyn_len` | 120 | 同上，長度由輸入決定 | `ptp_egress` |
| [`axis_drop`](#axis_drop) | 175 | 去掉封包開頭 N bit 並重新對齊 | `sensor_tx_pkt_proc`、`ptp_ingress`、`roce_icrc` |
| [`axis_drop_tail`](#axis_drop_tail) | 171 | 去掉封包尾端 N bit | `sensor_tx_pkt_proc` |
| [`axis_insert`](#axis_insert) | 324 | 在固定 offset 插入 N bit（可逐封包啟用） | `eth_pkt`（VLAN） |
| `axis_remove` | 425 | 在固定 offset 移除 N bit | `rx_parser`（VLAN） |
| `axis_hdr` | 263 | 在封包前加 header | `rx_ls_parser` |
| `axis_ftr` | 185 | 在封包後加 footer | `roce_icrc`（ICRC） |
| `axis_mask` | 123 | 對封包前 N bit 做 OR / AND 遮罩 | `roce_icrc`、`bridge_pkt_proc` |
| `axis_packer` | 123 | 把 `tkeep` 不滿的 beat 壓緊成連續資料 | 板級 MIPI 接收（`mipi_bridge`、`mipi_cam_rcvr`） |
| `axis_gearbox` | 345 | 寬度轉換，比例必須是整數 | `axis_buffer`、`axis_buffer_tx` |
| `axis_arb` | 168 | 封包級仲裁（`ROUND_ROBIN` / `PRIORITY`），可選 skid / 暫存 | `eth_pkt`、`rx_ls_parser` |
| `axis_reg` | 104 | AXIS 暫存級，`SKID = 1` 時為 skid buffer | 多處 |
| `axis_checker` | 126 | 斷言：`tvalid` 時資料穩定、`tlast` 規則、封包長度（`ASSERT_ON` 時） | `HOLOLINK_top`、`eth_pkt`、`dp_pkt_top`、`ptp_*` |
| `axis_demux` | 136 | 依 index 分流 | **未使用** |
| `axis_pkg` | 81 | 型別定義 | |

## 其他元件（`misc`）

| 類別 | 元件 | 行數 | 功能 | 使用位置 |
|---|---|---|---|---|
| FIFO | [`sc_fifo`](#sc_fifo) | 210 | 單時脈 FIFO，暫存輸出 | 多處 |
| | `dc_fifo_generic` | 398 | 雙時脈 FIFO，Gray code 指標，含 reset 握手 | `dc_fifo_stub` |
| | `dc_fifo_stub` | 88 | `dc_fifo_generic` 的包裝，**預留給廠商替換成原生 FIFO** | `axis_buffer`、`axis_buffer_tx`、`streaming_cdc` |
| | `reg_fifo` | 98 | 暫存器實作的小 FIFO | `ctrl_bus_evt_fsm`、`dp_pkt_ts`、`roce_icrc` |
| | `str_fwd_fifo` | 125 | store-and-forward FIFO | **未使用** |
| CDC | [`data_sync`](#cdc-元件) | 62 | N 級同步器（每 bit 獨立） | 多處 |
| | [`pulse_sync`](#cdc-元件) | 100 | 單拍脈衝跨時脈（toggle 方式） | `packetizer_top`、`ptp_top`、`virtual_port` 等 |
| | [`reg_cdc`](#cdc-元件) | 88 | 多 bit 暫存器跨時脈（4 相握手） | `s_apb_reg`、`ptp_dly`、`bootp` 等 |
| | [`streaming_cdc`](#cdc-元件) | 151 | 連續變化的值跨時脈（PTP 時間） | `HOLOLINK_top` |
| | `cdc_reset_handshake` | 141 | 確認兩端都完成 reset 才允許傳輸 | `dc_fifo_generic`、`pulse_sync` |
| Reset | `reset_sync` | 61 | 非同步施加、同步釋放 | `reset_gen`、板級 |
| | `rst_pb_debounce` | 52 | 按鈕 reset 去彈跳 | 板級 |
| 仲裁 | `rrarb` | 251 | Round-robin（8 個一組分層），可選 sticky | `apb_switch`、`axis_arb`、`dp_pkt_top`、`routing_table`、`bridge_pkt_proc` |
| | `priority_arb` | 92 | 固定優先權（0 最高），sticky | `axis_arb`、`ctrl_bus_evt_fsm`、`dp_pkt_ts` |
| 記憶體 | `dp_ram` | 158 | 雙埠 RAM（`SIMPLE` / `TRUE`） | `i2c_ctrl_fsm`、`spi_ctrl_fsm`、`dp_pkt_ts`、`imu` |
| | `cam` | 115 | 平行比對 CAM | `routing_table` |
| 其他 | `moving_avg` | 155 | 2^n 筆移動平均 | `ptp_calc` |
| | `edge_to_pulse` | 80 | 邊緣轉脈衝 | `uart_ctrl_fsm` |
| | `glitch_filter` | 73 | 同步器 + 可設定長度的濾波 | 板級 |
| | `debouncer`、`comparator` | 62、203 | | **未使用** |

---

## `axis_buffer`

| 參數 | 說明 |
|---|---|
| `IN_DWIDTH` / `OUT_DWIDTH` | 兩端寬度；中間 FIFO 寬度取較大者 |
| `BUF_DEPTH` | FIFO entry 數（向上取 2 的冪次） |
| `WAIT2SEND` | 1 = 整包進入後才輸出 |
| `DUAL_CLOCK` | 1 = `dc_fifo_stub`，0 = `sc_fifo` |
| `NO_BACKPRESSURE` | 1 = 輸入永遠 `tready` |
| `ALMOST_FULL_DEPTH` | `o_fifo_afull` 門檻 |
| `LATENCY_CNT` | > 0 時控制封包間的固定延遲（未分析） |

- FIFO 裡 `tkeep` 存成最高有效 byte 的 index，假設 `tkeep` 是連續低位 1。
- `WAIT2SEND`：輸入端每寫入一個 `tlast` 計數 + 1，雙時脈時以 Gray code 經 2 級同步器送到輸出端；計數不同代表有完整封包可讀。送出 `tlast` 的那一拍不預讀，所以封包間至少一拍空檔。
- `NO_BACKPRESSURE = 1`：FIFO 滿時 `sc_fifo` 丟掉 beat（`wr_en = wr & ~full`），但 `WAIT2SEND` 的封包計數 `in_pkt_cnt` 加的是 `fifo_wren && tlast`，`fifo_wren` 不看 `full`。`tlast` 被丟掉時計數永遠比實際多 1，之後 `WAIT2SEND` 的保證失效，直到 reset（R + M，v7；`rx_parser` 中的後果見 [rx_parser 注意事項 5](rx_parser.md#注意事項)）。
- `NO_BACKPRESSURE = 0` 但 `o_axis_rx_tready` 沒有接出去時（Bridge 的 host RX 緩衝）：almost full 後 `gbx_axis_tready = 0`，上游送來的 beat 不會寫入，`tlast` 也不計數；被截斷的封包永遠不完整，`WAIT2SEND` 永遠不放行（[bridge 注意事項 7](bridge.md#注意事項)）。

`sensor_tx/axis_buffer_tx.sv` 是它的修改版：拿掉 `WAIT2SEND`、輸入端 `tready` 綁 1、讀出端等下游 `tready` 才預讀，讓輸出 `tvalid` 連續。

## `axis_to_vec`

把封包前 `DATA_WIDTH` bit 收成向量；第 `i` 個 beat 放在 `[i×AXI_DWIDTH +: AXI_DWIDTH]`（低位是封包開頭）。收滿或封包提早結束的下一拍 `o_valid` 脈衝。狀態：`IDLE → WAIT（收滿）→ DONE（等 tlast）`。封包結束後清除高位，所以短封包的未收部分讀到 0。

## `axis_drop`

去掉開頭 `DROP_WIDTH` bit。`VAL_BITS = DROP_WIDTH mod DWIDTH`；之後每個輸出 beat = `{本拍[VAL_BITS-1:0], 前一拍[DWIDTH-1:VAL_BITS]}`，最後可能多送一拍（`SEND_PAD`）。輸出是組合邏輯，`tready` 直接傳遞。

## `axis_drop_tail`

去掉尾端 `DROP_WIDTH` bit。用 `⌈DROP_WIDTH/DWIDTH⌉ + 1` 級延遲線，看到 `tlast` 後回頭調整最後一兩拍的 `tkeep` / `tlast`；最後一拍全部屬於被丟的部分時整拍不送。**沒有 `tready`**。

## `axis_insert`

[`axis_insert.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/lib_axis/axis_insert.sv)（逐行）：在封包的第 `INSERT_OFFSET` bit 插入 `INSERT_WIDTH` bit，之後的資料整體往後移。`eth_pkt` 用 `INSERT_OFFSET = 96`、`INSERT_WIDTH = 32`：在兩個 MAC 位址之後插入 4 byte VLAN tag。

合成時依參數算出插入點落在哪一拍、哪個位置，選用不同的狀態路徑（[L44–L71](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/lib_axis/axis_insert.sv#L44-L71)）：

| HIF 寬度 | 插入點 | 狀態路徑 | 說明 |
|---|---|---|---|
| 64 bit | 第 2 拍 bit 32（`D_CYCLES = 2`，剛好填滿到拍尾：`EVEN_FILL`） | `S_DATA → S_DATA_INSERT → S_REG_DATA …` | 第 2 拍輸出 `{VLAN, 原資料[31:0]}`，之後每拍輸出 `{本拍[31:0], 上一拍[63:32]}` |
| 512 bit | 第 1 拍 bit 96，插入後仍在同一拍內（`ENCAPSULATED`） | `S_DATA_INSERT_DATA → S_REG_DATA …` | 第 1 拍輸出 `{原資料[479:96], VLAN, 原資料[95:0]}`，之後每拍錯位 32 bit |

- **逐封包啟用**：`i_enable` 在封包第一拍時鎖進 `pkt_enable`，整個封包期間不變；未啟用時資料直接通過（[L92–L106](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/lib_axis/axis_insert.sv#L92-L106)、[L305](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/lib_axis/axis_insert.sv#L305)）。
- **最後一拍**：`tkeep_final = TKEEP_ADD | (tkeep << 4 byte)`；原本最後一拍若有超過 `W_KEEP − 4` byte 有效，錯位後放不下，需要多送一拍（`extra_cycle`，`S_REG_PAD`），這一拍對輸入拉低 `tready`（[L299–L322](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/lib_axis/axis_insert.sv#L299-L322)）。
- 所以 VLAN 插入每個封包最多只多 1 拍，不會在封包中間產生空檔。

## `sc_fifo`

- 深度向上取 2 的冪次；`dout` 是暫存輸出（`rd` 的下一拍有效，`dval` 同時拉高）。
- `empty`、`full`、`afull`、`aempty` 都是暫存輸出，比 `count` 晚一拍。
- 寫滿 / 讀空時忽略操作，`over` / `under` 指示。

## CDC 元件

分析深度：本節六個元件逐行。

### `data_sync`

[data_sync.sv#L18–L62](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/misc/data_sync.sv#L18-L62)：每個 bit 一條 `SYNC_DEPTH`（預設 2）級的移位暫存器，加上 `ASYNC_REG`、`DONT_TOUCH`、`syn_preserve` 等屬性，讓合成工具把同步鏈放在一起、不做最佳化。`RST_SYNC = "TRUE"` 用同步 reset，否則非同步 reset。

**使用條件**：每個 bit 各自同步，多 bit 匯流排在變化的瞬間，目的端可能看到新舊混合的值。只有以下情況安全：單 bit；各 bit 意義獨立；Gray code；或資料在另一個已同步的控制訊號之前就固定（「資料先固定、控制後同步」）。

### `pulse_sync`

[pulse_sync.sv#L20–L100](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/misc/pulse_sync.sv#L20-L100)：

1. 來源端：每個輸入脈衝讓 `src_pulse_reg` 翻轉一次（toggle）。
2. `data_sync` 2 級同步到目的端。
3. 目的端：偵測同步後的電位變化，輸出一拍脈衝。
4. 兩端都經 `cdc_reset_handshake` 確認 reset 完成；完成前來源端不翻轉、目的端不輸出。

**使用條件**：兩個來源脈衝之間要隔開足夠時間，讓目的端看到每一次翻轉（約 2–3 個目的端時脈）。間隔太短時兩次翻轉互相抵消，**兩個脈衝都會遺失**。檔頭註解也說明：只有來源端在 reset 時，脈衝會遺失。

### `reg_cdc`

[reg_cdc.sv#L16–L88](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/misc/reg_cdc.sv#L16-L88)：四相握手。

| 步驟 | 時脈域 | 動作 |
|---|---|---|
| 1 | A | `i_a_val` 時把資料存進 `a_reg_q`；下一拍若沒有握手在進行（`!a_val_qq`），把 `a_reg_q` 複製到 `a_reg_qq` 並拉高請求 `a_val_qq` |
| 2 | B | 請求經 3 級同步，上升緣時鎖住 `a_reg_qq`（此時它已穩定），`o_b_val` 拉高一段時間；回 `b2a_ack` |
| 3 | A | ack 經 2 級同步後放下請求 |
| 4 | B | 看到請求放下，放下 ack |

**更新會遺失的情況**（R + I）：`i_a_val` 是單拍脈衝時，

- 握手進行中（`a_val_qq = 1`）又來一次 `i_a_val`：`a_reg_q` 被更新，但不會再發起握手，B 端保留舊值，直到下一次 `i_a_val`。
- 請求剛放下、但 ack 還沒同步回來（`b2a_ack_sync[1] = 1`）時來一次 `i_a_val`：`a_reg_qq` 被更新，但請求被 ack 擋住沒有拉高，同樣不會送到 B 端。

**在 `s_apb_reg` 中的影響（v7.1，R + M）。** `s_apb_reg` 每個控制暫存器各有一個 `reg_cdc`，但 `i_a_val` 都接同一個 `reg_wdval`（[s_apb_reg.sv#L94](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/lib_apb/s_apb_reg.sv#L94)、[#L173–L185](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/lib_apb/s_apb_reg.sv#L173-L185)），它在**同一個區塊的任何一個暫存器**被寫入時都會產生脈衝。所以第一次寫入啟動了所有暫存器的握手，握手結束前第二次寫入**另一個**暫存器，那個暫存器的新值也不會送出（直到下一次寫入）。遺失與否取決於兩次寫入的間隔和兩端時脈比：

- `apb_switch` 每次 transaction 後進 `DELAY` 數到 10（[apb_switch.sv#L168](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/lib_apb/apb_switch.sv#L168)），加上 `REQUESTED`、`penable` 與 `s_apb_reg` 兩級暫存的 `pready`，同一個 master 的連續寫入至少相隔 16 個 APB 時脈。
- [`tools/model/reg_cdc_model.py`](../../tools/model/reg_cdc_model.py) 照 `reg_cdc` 逐暫存器模擬兩個時脈、掃過 B 端相位：模組時脈 ≥ 8 倍 APB 時需 ≥ 6 拍、相同頻率需 ≥ 10 拍、APB 為模組時脈 2 倍時需 ≥ 16 拍；**模組時脈低於 APB 時脈約 0.48 倍時，16 拍的間隔不夠，會遺失**。
- 板級：10G 板級的 APB 只有 19.53 MHz，所有模組時脈都比它快；PYNQ（APB 50 MHz）與 S10（APB 100 MHz）上，HIF 與 PTP 時脈都高於 0.48 倍 APB。只有 SIF 時脈低於 24 MHz（PYNQ）或 48 MHz（S10）的 SIF 區塊（例如 packetizer、`tx_stream_buffer` 的暫存器）才會觸發；SIF 時脈由板級決定，本 repo 未逐一確認。

### `streaming_cdc`

[streaming_cdc.sv#L16–L144](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/misc/streaming_cdc.sv#L16-L144)：給持續變化的值（PTP 時間）用。

| 部分 | 行為 |
|---|---|
| FIFO | `dc_fifo_stub`，深度 16、almost full 7；目的端只要非空就讀 |
| 來源較慢（`SRC_FREQ ≤ DST_FREQ`） | 每個來源時脈都寫一筆 |
| 來源較快 | 8-bit 相位累加器把寫入速率壓到目的端頻率的 99 % 以下，例如 PTP 100.45 MHz → APB 19.53 MHz：`PHASE_INCREMENT = 49`，寫入速率 = 49/256 × 100.45 ≈ 19.23 MHz |
| 起動 | 目的端離開 reset 後的 `dst_ready` 同步回來源端才開始寫 |

因為寫入速率永遠不超過讀出速率，FIFO 幾乎保持空的。一筆值從寫入到出現在 `o_dst_data` 的路徑（v7.1 逐行確認，R）：來源端寫入同一拍更新 `wr_gray` → 目的端兩級同步（`SYNC_DEPTH = 2`）→ `rdcount_nxt` 不為 0，下一拍 `empty` 清除（[dc_fifo_generic.sv#L296–L302](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/misc/dc_fifo_generic.sv#L296-L302)）→ `fifo_rd_en = !fifo_empty`（[streaming_cdc.sv#L142](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/misc/streaming_cdc.sv#L142)）→ 下一拍 `dout` 與 `dval`。共 3 個完整目的端時脈，加上寫入到第一個目的端邊緣的 0–1 個時脈，也就是 **3–4 個目的端時脈**；此外 `o_dst_data` 在兩次更新之間保持不變，來源較慢時最多再舊 1 個來源時脈（來源較快、經相位累加器降速時最多再舊 ⌈256 / `PHASE_INCREMENT`⌉ 個來源時脈）。

| 板級 | 目的端（HIF） | CDC 固定延遲 | 加上取樣保持（PTP 時脈） |
|---|---|---|---|
| CPNX100 / NV MIPI | 156.25 MHz | 19.2–25.6 ns | 19.2–35.6 ns |
| MPF200 | 156.25 MHz | 19.2–25.6 ns | 19.2–35.2 ns |
| PYNQ RFSoC | 322.27 MHz | 9.3–12.4 ns | 9.3–22.4 ns |
| Terasic S10 | 201.42 MHz | 14.9–19.9 ns | 14.9–29.8 ns |

RTL 沒有補償這段延遲；`dp_pkt_top` 的 metadata 與 CoE 時間戳都取自這個值。v6 寫的「約 20–40 ns」在 10G 板級大致吻合，但 100G 板級較短。

### `dc_fifo_generic` / `dc_fifo_stub`

[dc_fifo_generic.sv#L55–L398](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/misc/dc_fifo_generic.sv#L55-L398)：

| 項目 | 行為 |
|---|---|
| 指標 | 二進位計數器 + Gray code（`(bin >> 1) ^ bin`），位址比深度多 1 bit 區分滿 / 空 |
| 跨時脈 | Gray 指標經 `data_sync` 2 級同步，再轉回二進位算數量；每次寫或讀只變 1 bit，所以多 bit 同步是安全的 |
| 實體深度 | `2^⌈log2(FIFO_DEPTH)⌉`：例如 VP FIFO 的 `FIFO_DEPTH = 1006` 實際是 1024 筆 |
| 旗標 | `full` / `afull` 在寫端、`empty` / `aempty` 在讀端計算；用同步後（較舊）的對方指標，所以偏保守 |
| 溢位 / 下溢 | `wr & full` 時不寫、`over` 拉高；`rd & empty` 時不讀、`under` 拉高。`dc_fifo_stub` 在 `ASSERT_ON` 時對兩者下 assertion |
| reset | 兩端都要 reset。`cdc_reset_handshake` 完成前，寫端不寫、讀端 `empty` 保持 1 |
| RAM | `MEM_STYLE`：LUT、BLOCK 或 AUTO。AUTO 的判斷前後不一致：分散式用 `BUF_DEPTH < 128`、block 用 `FIFO_DEPTH ≥ 128`，`FIFO_DEPTH` 在 65–127 之間時兩者都不成立，交給合成工具自行推斷（[dc_fifo_generic.sv#L357–L370](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/misc/dc_fifo_generic.sv#L357-L370)） |

`dc_fifo_stub` 是包裝層，註解說明可替換為廠商原生 FIFO；替換後實體深度與旗標時序可能不同。

### `cdc_reset_handshake`

[cdc_reset_handshake.sv#L36–L141](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/misc/cdc_reset_handshake.sv#L36-L141)：確認兩端都經過 reset。目的端離開 reset 後送 `dest_ack`；來源端只有在自己 reset 過（`src_gate` 只在 `src_rst` 時清 0）才回 `src_ready`；目的端看到後設 `dest_ready`。只有一端 reset 時握手不會完成，對應的 FIFO / 脈衝同步器保持停用，而不是用不一致的狀態繼續工作。

### HSB 中的使用檢查

依 [overview §跨時脈地圖](../architecture/overview.md#跨時脈地圖) 列出的每個跨時脈點，對照上面的使用條件：

| 位置 | 元件 | 條件是否成立 |
|---|---|---|
| VP FIFO、`axis_buffer_tx`、`ptp_ingress` | `dc_fifo` | ✓ 標準 Gray code FIFO |
| PTP 時間 → HIF / APB | `streaming_cdc` | ✓；有固定延遲（見上） |
| `s_apb_reg` 控制暫存器 | `reg_cdc` | ✓ 前提是同一暫存器的寫入間隔大於握手時間（`apb_switch` 的 10 拍延遲保證） |
| `ptp_dly` 送出欄位、`bootp` PPS + 時間 | `reg_cdc` | ✓ 每秒或每個 Sync 一次 |
| ECB `cmd_addr` / `cmd_rddata` | `data_sync`（32 bit） | ✓ 資料先固定、控制後同步 |
| ECB `cmd_dout` | **無** | 依賴時序：資料在 `apb_send_cmd` 前固定。需要合成約束 |
| packetizer RAM 寫入 | `data_sync`（單拍脈衝，取下降緣） | 條件：SIF RX 時脈不慢於 APB 時脈，否則脈衝可能取樣不到 |
| packetizer SOF、VP 0 結尾、`axis_buffer_tx` 封包計數、PTP TX 時間戳 | `pulse_sync` | ✓ 事件間隔遠大於同步延遲（一個 frame / 封包一次） |
| `hsb_stat`（8 bit） | `data_sync` | 各 bit 意義獨立，短暫混合值只影響一次 BOOTP 的內容 |
| `ctrl_bus_evt_int` 的 24-bit `timeout` 等設定 | `data_sync` | 準靜態設定，改寫瞬間可能短暫看到混合值 |
| `init_done`、EEPROM IP valid | `data_sync` | ✓ 單 bit；IP 本身只同步 valid，資料視為靜態 |
