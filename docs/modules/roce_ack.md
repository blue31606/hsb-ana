# `roce_ack`

## 概要

在 `rx_parser` 內部，只在 `SIF_TX_ROCE_RC_ENABLE` 定義時實例化。對 RoCE RC（Reliable Connection）的 STX 封包做 PSN 檢查，回 ACK / NAK / RNR NAK，並讓 `rx_parser` 丟掉失序或重複的封包。這是 STX 路徑唯一的「背壓」機制：用 RNR NAK 讓 host 暫停重送。

| 項目 | 值 |
|---|---|
| 原始碼 | [`roce/roce_ack.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv)（643 行） |
| 實例 | [`rx_parser.sv#L601`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_parser.sv#L601) |
| 時脈 | `i_pclk`（HIF） |
| 分析深度 | PSN 判斷邏輯逐行；回應封包組裝與 ICRC 只讀結構 |

## 參數

| 參數 | `rx_parser` 傳入 | 說明 |
|---|---|---|
| `W_DATA` | `AXI_DWIDTH` | |
| `W_USER` | `USER_WIDTH`（17） | VLAN 資訊，回應封包沿用 |
| `HDR_BYTES` | 54 | |
| `N_QP` | `SENSOR_TX_IF_INST` | 每個 SIF TX 一組 PSN 狀態 |
| `META_FIFO_DEPTH` / `FIFO_DEPTH` | 同 `rx_parser` | |

## 介面

| 方向 | 名稱 | 說明 |
|---|---|---|
| in | `i_eth_hdr`、`i_ip_hdr`、`i_udp_hdr`、`i_bth_hdr`、`i_hdr_valid` | `rx_parser` 抽出的 header |
| in | `i_is_stx` | 這個封包是 STX |
| in | `i_pkt_done`、`i_pkt_is_err` | 封包結束、FCS 或 LS afull 錯誤 |
| out | `o_empty`、`o_is_err`、`i_rd_en` | 每個封包一筆的錯誤 FIFO，介面和 `rx_parser` 的其他 metadata FIFO 一樣 |
| in | `i_stx_ready[N_QP-1:0]` | `tx_stream_buffer.o_stx_is_ready`（= 沒有 pause） |
| in | `i_ctrl_reg[31:0]` | `inst_dec_ack_ctrl` |
| out | `o_axis_*` | ACK/NAK 封包 → `eth_pkt` 第 2 埠 |
| APB | QP RAM | host 設定的 QP 資訊（只有 host 埠 0 的 RAM 回應 APB 讀取，見 [`HOLOLINK_top.sv#L464`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L464)） |

## 行為

### PSN 判斷

`sif_idx = dest_qp[7:1] - 1`（[L360](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv#L360)）選出狀態 RAM 的位置，RAM 存 `{has_inited, has_nacked, msn[23:0], psn_exp[23:0]}`。每個封包依序判斷（[L269–L346](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv#L269-L346)）：

| 優先順序 | 條件 | 動作 | 回應 |
|---|---|---|---|
| 1 | 不是 RC STX | 不更新狀態，錯誤 = 0 | 無 |
| 2 | `!has_inited`（第一個封包） | `psn_exp = psn + 1` | ACK（若封包要求） |
| 3 | 錯誤注入 | 封包標為錯誤 | NAK 或 RNR NAK |
| 4 | `!i_stx_ready[sif_idx] && enable_rnr` | 封包標為錯誤 | **RNR NAK** |
| 5 | `psn == psn_exp` | `psn_exp + 1`，正常 | ACK（若 BTH `A` bit = 1） |
| 6 | `psn > psn_exp` | 封包標為錯誤（失序） | NAK（每個序列只送一次） |
| 7 | 其他（`psn < psn_exp`） | 封包標為錯誤（重複） | 無 |

`o_is_err = is_err & psn_check_enable`：只有 `psn_check_enable` 時，錯誤才會讓 `rx_parser` 丟包。

### 回應封包

Ethernet + IPv4 + UDP + BTH + AETH（+ ICRC）。MAC、IP 對調；UDP 埠**不**對調（都是 4791）。AETH syndrome（[L510](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv#L510)）：

| 類型 | syndrome[7:5] | syndrome[4:0] |
|---|---|---|
| ACK | 0 | `1F`（credit 不使用） |
| RNR NAK | 1 | RNR timer |
| NAK | 3 | 0（PSN sequence error） |

## 暫存器

`inst_dec_ack_ctrl`（`0x0200_001C + host × 0x1_0000`），[L138–L143](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv#L138-L143)：

| Bit | 名稱 | 說明 |
|---|---|---|
| 0 | `ack_enable` | |
| 1 | `inj_err_en` | 錯誤注入（測試用） |
| 2 | `psn_check_enable` | 錯誤時丟包 |
| 3 | `ack_first` | |
| 4 | `inj_err_rnr_en` | 注入的錯誤用 RNR NAK |
| 5 | `enable_rnr` | `tx_stream_buffer` pause 時回 RNR NAK |

## 注意事項

1. **兩處感測器選擇的位元範圍不同。** `roce_ack` 用 `dest_qp[7:1] - 1`，`sensor_tx_pkt_proc` 用 `dest_qp[8:1] == i + 1`。QP < 256 時結果相同；QP bit 8 為 1 時兩者不一致。
2. **錯誤注入的註解與程式不符。** 註解寫「每個序列第 8 個封包注入」，程式是 8-bit `err_cnt == '1`，也就是第 256 個（[L385](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv#L385)）。
3. **PSN 比較沒有處理回捲。** `psn > psn_exp` 是 24-bit 無號比較。`psn_exp` 接近 `0xFFFFFF` 時遺失封包，下一個封包的 PSN 回捲到小值，會被當成重複而不是失序，不送 NAK（推斷）。
4. 錯誤 FIFO 每個封包都寫一筆（包括非 STX 封包），所以 `ENABLE_ROCE_ACK` 時 `rx_parser` 的讀出也要等它（`!ack_empty`）。

## 與 1722 Listener 的關係

1722 沒有 ACK/重送機制，`roce_ack` 不適用。但它示範了**怎麼把 `tx_stream_buffer` 的狀態回饋到 RX 端**：1722 Listener 如果需要在 buffer 快滿時採取動作（例如丟掉整個 frame 而不是半個），可以參考同樣的 `i_stx_ready` 接法。
