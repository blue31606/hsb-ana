# `roce_ack`

## 概要

在 `rx_parser` 內部，只在 `SIF_TX_ROCE_RC_ENABLE` 定義時實例化。對 RoCE RC（Reliable Connection）的 STX 封包做 PSN 檢查，回 ACK / NAK / RNR NAK，並讓 `rx_parser` 丟掉失序或重複的封包。這是 STX 路徑唯一的「背壓」機制：用 RNR NAK 讓 host 暫停重送。

| 項目 | 值 |
|---|---|
| 原始碼 | [`roce/roce_ack.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv)（643 行） |
| 實例 | [`rx_parser.sv#L601`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_parser.sv#L601) |
| 時脈 | `i_pclk`（HIF） |
| 分析深度 | 逐行 |

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

### 決策時機

[roce_ack.sv#L219–L253](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv#L219-L253)：header 解析完（`i_hdr_valid`）時讀狀態 RAM、記下 `pending_*`，但**要等整個封包收完（`i_pkt_done`）才決定**：

- `i_pkt_is_err`（FCS 錯誤等）時不更新狀態、不送回應，FIFO 照樣寫一筆；寫入的值是 PSN 判斷分支的結果 `pkt_err`，PSN 正確的封包寫入 0，不一定是「錯誤」（[roce_ack.sv#L269–L345](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv#L269-L345)）。
- 決定與狀態回寫在同一拍完成（[roce_ack.sv#L256–L358](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv#L256-L358)）：`sts_ram_wren` 時 RAM 位址切到寫入位址。
- 狀態 RAM 每筆 50 bit：`[23:0]` 期望 PSN、`[47:24]` MSN、`[48]` 已送過 NAK、`[49]` 已初始化。`N_QP` 筆，用分散式 RAM，reset 清 0。

NAK 只送一次：送出 NAK 或 RNR NAK 後設 `has_nacked`，之後同一個 QP 的錯誤都不再回應，直到下一個依序封包被 ACK（`is_nacked` 在 ACK 時清 0，[roce_ack.sv#L376](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv#L376)）。

### 回應封包

[roce_ack.sv#L476–L538](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv#L476-L538)：`vec_to_axis` 送出 58 byte header，經 `roce_icrc` 附加 ICRC，再進輸出 `axis_buffer`。

| 層 | 欄位 | 值 |
|---|---|---|
| Ethernet | dest / src | 請求的 src / dest MAC（對調） |
| IPv4 | 版本、DSCP、ID、flags、TTL、protocol | **從請求複製** |
| | total length | 48（UDP 8 + BTH 12 + AETH 4 + ICRC 4 + IP 20） |
| | checksum | 增量更新：`請求的 checksum + 請求的 length − 48`，再折回進位（見注意事項 6） |
| | src / dest IP | 對調 |
| UDP | 埠 | **不對調**（兩邊都是 4791）；checksum 0 |
| BTH | opcode | `0x11`（RC Acknowledge） |
| | dest QP | QP RAM（`0x0000_3000` 起）的 `[23:0]`：host 端 QP。**只有 2 個 word**：`u_host_qp_ram` 固定 `R_CTRL = 2`，與 `N_QP` 無關（[roce_ack.sv#L549–L573](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv#L549-L573)）。內部讀取位址 `i_addr` 只有 `$clog2(2) = 1` bit，`sif_idx` 被截成最低位，所以 SIF TX 2、3 會讀到 SIF TX 0、1 的 host QP 與 RNR timer；APB 寫入 word 2 以上則回 `pslverr` / `0xBADADD12`（[s_apb_ram.sv#L85](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/lib_apb/s_apb_ram.sv#L85)）。目前沒有板級定義 `ENABLE_ROCE_ACK`，而 PYNQ 有 4 個 SIF TX，所以這是潛在問題（R） |
| | PSN | 狀態 RAM 中的期望 PSN：ACK 時等於被確認封包的 PSN；NAK 時是 HSB 期望的下一個 PSN |
| AETH | syndrome | 見下表 |
| | MSN | 更新後的 MSN（每個 `*_LAST` / `*_ONLY` 封包加 1） |

| 類型 | syndrome[7:5] | syndrome[4:0] |
|---|---|---|
| ACK | 0 | `1F`（credit 不使用） |
| RNR NAK | 1 | QP RAM 的 `[28:24]`（RNR timer） |
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
2. **錯誤注入的註解與程式不符。** 註解寫「每個序列第 8 個封包注入」，程式是 8-bit `err_cnt == '1`；序列的第一個封包只清除計數、不計入，所以是第 257 個（[L385](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv#L385)）。
3. **PSN 比較沒有處理回捲。** `psn > psn_exp` 是 24-bit 無號比較。`psn_exp` 接近 `0xFFFFFF` 時遺失封包，下一個封包的 PSN 回捲到小值，會被當成重複而不是失序，不送 NAK；反方向，回捲後才到的舊封包（例如 `psn_exp = 0x000001` 時的 `0xFFFFFF`）被當成超前，回一個 sequence error NAK（R + M，以 [逐拍模型](../../tools/model/roce_ack_model.py) 重現）。
4. 錯誤 FIFO 每個封包都寫一筆（包括非 STX 封包），所以 `ENABLE_ROCE_ACK` 時 `rx_parser` 的讀出也要等它（`!ack_empty`）。
5. **重複封包沒有回應。** `psn < psn_exp` 時只丟包，不送 ACK。InfiniBand 規格要求 responder 對重複的請求回 ACK，讓 requester 在 ACK 遺失時能前進；這裡如果某個 ACK 在網路上遺失，requester 重送的封包都會被當成重複而丟掉（R + M，以 [逐拍模型](../../tools/model/roce_ack_model.py) 重現；requester 之後只能等到重試次數用完，這部分依 InfiniBand 規格推論）。
6. **IPv4 checksum 增量更新在借位時差 2。** 計算是 17 bit 二補數 `checksum + old_len − 48`，再把 bit 16 加回來。結果為負時正確做法是減 1，這裡卻加 1。只在 `checksum + old_len < 48` 時發生：帶 RETH 的 RDMA WRITE 最短 60 byte，不會觸發；只有不帶 payload 的 SEND（44 byte）且 checksum ≤ 3 時才會。已用 [數值驗證](../verification-calcs.md) 確認（R + 數值）。
7. **第一個封包的 ACK 帶 PSN 0。** 未初始化時狀態 RAM 的期望 PSN 是 reset 值 0，而回應的 PSN 欄位取自這個值，不是封包本身的 PSN。host 的初始 PSN 不是 0 時，第一個 ACK 的 PSN 會錯（R + M）。和第 5 項合起來：requester 若因 PSN 不符而不接受這個 ACK 並重送，重送的封包已經是「重複」，永遠不會再得到回應（[逐拍模型](../../tools/model/roce_ack_model.py)）。`sts_ram_data` 只在新封包的 header 到達時讀取（`sts_ram_rden = i_hdr_valid`），所以回應中的 PSN 是該封包 header 到達時讀到的值。
