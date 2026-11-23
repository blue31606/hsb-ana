# `lib_axis` 與 `misc` 共用元件

改造 Listener 時最可能直接沿用的元件。只記錄已經讀過、並且影響上層行為的特性。

| 元件 | 原始碼 | 分析深度 |
|---|---|---|
| [`axis_to_vec`](#axis_to_vec) | [`lib_axis/axis_to_vec.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/lib_axis/axis_to_vec.sv) | 逐行 |
| [`axis_buffer`](#axis_buffer) | [`lib_axis/axis_buffer.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/lib_axis/axis_buffer.sv) | FIFO 與 `WAIT2SEND` 逐行；latency 控制只讀結構 |
| [`axis_drop`](#axis_drop) | [`lib_axis/axis_drop.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/lib_axis/axis_drop.sv) | 逐行 |
| [`axis_drop_tail`](#axis_drop_tail) | [`lib_axis/axis_drop_tail.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/lib_axis/axis_drop_tail.sv) | 主要邏輯 |
| [`sc_fifo`](#sc_fifo) | [`misc/sc_fifo.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/misc/sc_fifo.sv) | 逐行 |

---

## `axis_to_vec`

把 AXIS 封包的前 `DATA_WIDTH` bit 收進一個寬向量。

| 參數 | 說明 |
|---|---|
| `AXI_DWIDTH` | 輸入寬度 |
| `DATA_WIDTH` | 要收的 bit 數；收 `D_CYCLES = ⌈DATA_WIDTH / AXI_DWIDTH⌉` 個 beat |

| Port | 說明 |
|---|---|
| `i_done` | 上層處理完向量後拉高；`rx_parser` 綁 1 |
| `o_data` | 收到的向量。第 `i` 個 beat 放在 `[i*AXI_DWIDTH +: AXI_DWIDTH]`，**低位是封包開頭** |
| `o_valid` | 收滿 `D_CYCLES` 個 beat 的下一拍，或封包提早結束（`tlast`）的下一拍，脈衝 |
| `o_byte_cnt` | 收到的 byte 數 |

狀態機：`IDLE`（收資料）→ `WAIT`（收滿，`o_valid`）→ `DONE`（等封包 `tlast`）→ `IDLE`。`i_done = 1` 時 `WAIT` 只停一拍。封包比 `DATA_WIDTH` 短時，沒收到的部分會被清成 0（`clear_r`），所以短封包的高位欄位讀到的是 0，不是上一個封包的殘值。

## `axis_buffer`

AXIS FIFO，可選單 / 雙時脈、寬度轉換、整包放行。

| 參數 | 說明 |
|---|---|
| `IN_DWIDTH` / `OUT_DWIDTH` | 兩端寬度；中間 FIFO 寬度取較大者，轉換用 `axis_gearbox` |
| `BUF_DEPTH` | FIFO entry 數（實際深度向上取 2 的冪次） |
| `WAIT2SEND` | 1 = 整包進入 FIFO 後才開始輸出 |
| `DUAL_CLOCK` | 1 = 用 `dc_fifo_stub`，否則 `sc_fifo` |
| `NO_BACKPRESSURE` | 1 = 輸入永遠 `tready`，即使 FIFO 已滿 |
| `ALMOST_FULL_DEPTH` | `o_fifo_afull` 門檻 |
| `OUTPUT_SKID` | 輸出端 skid |

`WAIT2SEND` 的實作：

- 輸入端每寫入一個 `tlast` beat，`in_pkt_cnt` + 1；輸出端每送出一個 `tlast`，`out_pkt_cnt` + 1。
- 雙時脈時 `in_pkt_cnt` 先轉 Gray code、暫存一拍，再經 2 級同步器到輸出端。
- `packet_available = (同步後的 in_pkt_cnt != out_pkt_cnt_nxt)`，暫存成 `clear_to_send`。
- 讀 FIFO 條件包含 `!out_pkt_done`：送出 `tlast` 的那一拍不預讀下一包，所以**封包之間至少有一拍空檔**。

`NO_BACKPRESSURE = 1` 時：

- `gbx_axis_tready` 永遠 1，FIFO 滿時 `sc_fifo` 的 `wr_en = wr & ~full` 丟掉 beat。
- `in_pkt_cnt` 依「`gbx` 端寫入」計數，不管 FIFO 有沒有真的寫進去。所以 `tlast` beat 被丟時計數仍會增加，輸出端以為多了一個完整封包（推斷，需模擬確認）。

## `axis_drop`

從封包開頭去掉 `DROP_WIDTH` bit，剩下的資料重新對齊到 beat 起點。

| 參數 | 說明 |
|---|---|
| `DROP_WIDTH` | 去掉的 bit 數，需為 8 的倍數 |
| `DWIDTH` | 匯流排寬度 |
| `W_USER` | `tuser` 寬度；`tuser` 跟著資料走，最後一拍用暫存值 |

| 衍生常數 | 意義 |
|---|---|
| `DROP_CYCLES = ⌈DROP_WIDTH / DWIDTH⌉` | 涉及的 beat 數 |
| `VAL_BITS = DROP_WIDTH mod DWIDTH`（0 時 = `DWIDTH`） | 最後一個涉及 beat 裡屬於 header 的 bit 數 |
| `NXT_BITS = DWIDTH − VAL_BITS` | 該 beat 裡屬於 payload 的 bit 數 |

狀態：`IDLE` → `DROP`（丟整拍）→ `SEND`（輸出 `{本拍[VAL_BITS-1:0], 前一拍[DWIDTH-1:VAL_BITS]}`）→ 視最後一拍剩餘 byte 進 `SEND_PAD`（多送一拍）→ `IDLE`。`DROP_WIDTH` 剛好是 `DWIDTH` 倍數時用 `SEND_EVEN`，不需要重新對齊。

特性：

- 輸出是**組合邏輯**，與輸入同一拍。
- `o_axis_rx_tready = i_axis_tx_tready`，背壓直接傳遞。
- 有處理「`SEND_PAD` 的同一拍新封包進來」與「單拍封包」的情況（RTL 註解說明）。

## `axis_drop_tail`

從封包尾端去掉 `DROP_WIDTH` bit。

- 結構是 `DROP_CYCLES = ⌈DROP_WIDTH / DWIDTH⌉ + 1` 級延遲線（32 bit、64-bit 匯流排時為 2 級）。
- 看到輸入 `tlast` 後，依 `tkeep` 算出輸出端最後一拍的位置與 `tkeep`。最後一拍若全部屬於被丟的部分，就不送，`tlast` 移到前一拍。
- **沒有 `tready`**，只能用在不會背壓的路徑。
- 有處理「前一包 `tlast` 還在延遲線裡、下一包 `tlast` 又進來」的情況（`tlast_pending`）。

## `sc_fifo`

單時脈 FIFO。

| 特性 | 說明 |
|---|---|
| 深度 | `2^⌈log2(FIFO_DEPTH)⌉` |
| 讀出 | **暫存輸出**：`rd` 那一拍的下一拍 `dout` 有效，`dval` 同時拉高 |
| 寫入 / 讀取保護 | `wr_en = wr & ~full`、`rd_en = rd & ~empty`；`over` / `under` 指示 |
| 旗標 | `empty`、`full`、`afull`、`aempty` 都是暫存輸出，比 `count` 晚一拍反應 |
| Reset | 預設同步 reset（`RST_SYNC = "TRUE"`） |

`rx_parser` 的 metadata FIFO 都是 `sc_fifo`：寫入後下一拍 `empty` 才變 0，讀取後下一拍 `dout` 才更新。這是 [rx_parser 讀出時序](rx_parser.md#時序) 裡空檔的來源。
