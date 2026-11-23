# RoCE 元件（`roce_icrc`、`lfsr_hc`、`roce_ack`）

| 檔案 | 行數 | 功能 | 使用位置 | 分析深度 |
|---|---|---|---|---|
| [`roce/roce_icrc.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_icrc.sv) | 363 | 計算並附加 RoCEv2 ICRC | `dp_pkt_top`（每 host）、`rx_ls_parser`（RoCE-ECB 回應）、`roce_ack` | 逐行 |
| [`roce/lfsr_hc.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/lfsr_hc.sv) | 425 | 平行 CRC-32（多項式 `0x04C11DB7`，由 `gen_lfsr.py` 產生） | `roce_icrc`、`dp_pkt`（frame CRC） | 結構逐行（自動產生的 XOR 方程式未逐項驗算） |
| [`roce/roce_ack.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv) | 643 | RC 模式 PSN 檢查與 ACK / NAK | `rx_parser`（`SIF_TX_ROCE_RC_ENABLE`） | 逐行 |

## `roce_icrc`

RoCEv2 的 ICRC 是 CRC-32，計算範圍從 IP header 開始，前面加上一個 8 byte 全 1 的「假 LRH」，並把傳輸途中會改變的欄位當作全 1。

實作（[roce_icrc.sv#L84–L362](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_icrc.sv#L84-L362)）：

1. `axis_drop` 去掉 Ethernet header 的前 6 byte（dest MAC），剩下的 8 byte（src MAC + EtherType）正好佔住假 LRH 的位置。
2. `axis_mask`（OR）把這些位置設成全 1（[roce_icrc.sv#L106–L117](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_icrc.sv#L106-L117)）：

   | 遮罩 | 欄位 |
   |---|---|
   | 8 byte | 假 LRH |
   | IPv4 TOS | DSCP / ECN |
   | IPv4 TTL、checksum | |
   | UDP checksum | |
   | BTH F / B / Rsrv6 | |

3. **CRC 計算**（[roce_icrc.sv#L181–L228](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_icrc.sv#L181-L228)）：`W_KEEP` 個 `lfsr_hc` 平行計算「這一拍的前 1、2、…、`W_KEEP` byte」之後的 CRC 狀態。整拍有效時用最後一個更新狀態；最後一拍依有效 byte 數選對應的那一個，取反後就是 ICRC。
4. **最後一拍只支援固定的幾種長度**（[roce_icrc.sv#L162–L177](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_icrc.sv#L162-L177)）：`tkeep` 必須等於以下其中之一，否則當成整拍有效：

   | 封包 | 計算範圍（扣掉 6 byte） | 64-bit 時最後一拍 | 512-bit 時最後一拍 |
   |---|---|---|---|
   | RDMA WRITE（header 70 + n × 128） | 64 + n × 128 | 8 byte（整拍） | 64 byte（整拍） |
   | WRITE with Immediate（74 + n × 128） | 68 + n × 128 | 4 byte | 4 byte |
   | 32 byte frame 的 WRITE with Immediate | 100 | 4 byte | 36 byte |
   | ACK（BTH + AETH） | 52 | 4 byte | 52 byte |

   這些長度正好是 HSB 自己產生的所有 RoCE 封包（Data Plane 的 payload 都是整數拍，見 [dp_pkt_top §11](dp_pkt_top.md#11-header-與-payload-拼接)）。LS 路徑（RoCE-ECB 回應）是 8-bit，每拍只有 1 byte，不受這個限制。
5. 原始資料經 4 級 `axis_reg` 延遲線對齊，CRC 存進 2 筆的 `reg_fifo`；同時在途的 CRC 達 2 個時暫停接收新封包（`fifo_tready`）。最後用 `axis_ftr` 在封包尾端附加 4 byte ICRC（[roce_icrc.sv#L248–L362](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_icrc.sv#L248-L362)）。
6. `i_crc_en = 0` 的封包（例如 1722B CoE）直接通過，不附加 ICRC。

## `lfsr_hc`

由 `gen_lfsr.py` 產生的平行 CRC-32（多項式 `0x04C11DB7`）。模組邊界把狀態與資料的位元順序反轉（[lfsr_hc.sv#L416–L423](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/lfsr_hc.sv#L416-L423)）。

只產生了 `DATA_WIDTH` = 8、16、32、64、128、256、288、416、512、544、1024 的方程式；**其他寬度直接輸出輸入狀態（CRC 不變）**（[lfsr_hc.sv#L408–L411](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/lfsr_hc.sv#L408-L411)）。`roce_icrc` 會為每個 byte 數各實例化一個 `lfsr_hc`（64-bit 時 8、16、…、64），其中沒有方程式的寬度（例如 24、40）就是空殼。但上表需要的寬度（64-bit：32、64；512-bit：32、288、416、512）都有方程式：288 = 36 byte、416 = 52 byte 就是為 32 byte frame 與 ACK 準備的。

`dp_pkt` 的 frame CRC 也用 `lfsr_hc`（`DATA_WIDTH = W_DATA`，整拍計算）。

## 注意事項

1. `roce_icrc` 不是通用的 ICRC 模組：最後一拍的有效 byte 數只支援上表幾種。改變 header 長度（例如加入 GRH 或其他 extension header）或讓 payload 不是整數拍時，ICRC 會算錯且不會報錯。
2. 新的資料寬度需要重新產生 `lfsr_hc`，否則沒有方程式的寬度會靜默地不計算 CRC。

## `roce_ack`

見 [roce_ack.md](roce_ack.md)。
