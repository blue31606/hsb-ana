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
| `axis_insert` | 324 | 在固定 offset 插入 N bit（可逐封包啟用） | `eth_pkt`（VLAN） |
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
- `NO_BACKPRESSURE = 1`：FIFO 滿時 `sc_fifo` 丟掉 beat（`wr_en = wr & ~full`），但 `WAIT2SEND` 的封包計數仍依「輸入端接受」計算。`tlast` 被丟掉時計數與實際內容會不一致（推斷）。

`sensor_tx/axis_buffer_tx.sv` 是它的修改版：拿掉 `WAIT2SEND`、輸入端 `tready` 綁 1、讀出端等下游 `tready` 才預讀，讓輸出 `tvalid` 連續。

## `axis_to_vec`

把封包前 `DATA_WIDTH` bit 收成向量；第 `i` 個 beat 放在 `[i×AXI_DWIDTH +: AXI_DWIDTH]`（低位是封包開頭）。收滿或封包提早結束的下一拍 `o_valid` 脈衝。狀態：`IDLE → WAIT（收滿）→ DONE（等 tlast）`。封包結束後清除高位，所以短封包的未收部分讀到 0。

## `axis_drop`

去掉開頭 `DROP_WIDTH` bit。`VAL_BITS = DROP_WIDTH mod DWIDTH`；之後每個輸出 beat = `{本拍[VAL_BITS-1:0], 前一拍[DWIDTH-1:VAL_BITS]}`，最後可能多送一拍（`SEND_PAD`）。輸出是組合邏輯，`tready` 直接傳遞。

## `axis_drop_tail`

去掉尾端 `DROP_WIDTH` bit。用 `⌈DROP_WIDTH/DWIDTH⌉ + 1` 級延遲線，看到 `tlast` 後回頭調整最後一兩拍的 `tkeep` / `tlast`；最後一拍全部屬於被丟的部分時整拍不送。**沒有 `tready`**。

## `sc_fifo`

- 深度向上取 2 的冪次；`dout` 是暫存輸出（`rd` 的下一拍有效，`dval` 同時拉高）。
- `empty`、`full`、`afull`、`aempty` 都是暫存輸出，比 `count` 晚一拍。
- 寫滿 / 讀空時忽略操作，`over` / `under` 指示。

## CDC 元件

| 元件 | 方式 | 適用 |
|---|---|---|
| `data_sync` | 每 bit 一條 N 級同步鏈（`ASYNC_REG`、`DONT_TOUCH`） | 單 bit，或各 bit 獨立 / 準靜態的匯流排 |
| `pulse_sync` | 來源端把脈衝轉成 toggle，目的端同步後偵測變化 | 單拍事件；兩次脈衝間隔需大於同步延遲 |
| `reg_cdc` | `i_a_val` 上升緣鎖住資料，送 valid 過去；目的端收到後鎖資料並回 ack | 多 bit 值，更新頻率低 |
| `streaming_cdc` | 小型雙時脈 FIFO，來源端以約目的端頻率 99% 的速率寫入 | 連續變化的多 bit 值（PTP 時間） |

`dc_fifo_generic` 與 `pulse_sync` 都用 `cdc_reset_handshake`：兩端都完成 reset 後才開始工作，避免只有一端 reset 時誤判。

觀察：部分地方用 `data_sync` 跨多 bit 的準靜態設定值（例如 `ctrl_bus_evt_int` 的 24-bit `timeout`）。值改變的瞬間目的端可能短暫看到混合值；這類設定通常在使用前寫好，所以影響有限。
