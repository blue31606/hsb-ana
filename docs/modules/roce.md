# RoCE 元件（`roce_icrc`、`lfsr_hc`、`roce_ack`）

| 檔案 | 行數 | 功能 | 使用位置 | 分析深度 |
|---|---|---|---|---|
| [`roce/roce_icrc.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_icrc.sv) | 363 | 計算並附加 RoCEv2 ICRC | `dp_pkt_top`（每 host）、`rx_ls_parser`（RoCE-ECB 回應）、`roce_ack` | 主要邏輯 |
| [`roce/lfsr_hc.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/lfsr_hc.sv) | 425 | 平行 CRC-32（多項式 `0x04C11DB7`，由 `gen_lfsr.py` 產生） | `roce_icrc`、`dp_pkt`（frame CRC） | 介面 |
| [`roce/roce_ack.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv) | 643 | RC 模式 PSN 檢查與 ACK / NAK | `rx_parser`（`SIF_TX_ROCE_RC_ENABLE`） | PSN 邏輯逐行 |

## `roce_icrc`

RoCEv2 的 ICRC 是 CRC-32，計算範圍從 IP header 開始，前面加上一個 8 byte 全 1 的「假 LRH」，並把傳輸途中會改變的欄位當作全 1。

實作（[L84–L231](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_icrc.sv#L84-L231)）：

1. `axis_drop` 去掉 Ethernet header 的前 6 byte，剩下的 8 byte（src MAC + EtherType）正好佔住假 LRH 的位置。
2. `axis_mask`（OR）把這些位置設成全 1：

   | 遮罩 | 欄位 |
   |---|---|
   | 8 byte | 假 LRH |
   | IPv4 TOS | DSCP / ECN |
   | IPv4 TTL、checksum | |
   | UDP checksum | |
   | BTH F / B / Rsrv6 | |

3. `lfsr_hc` 逐拍更新 CRC；最後一拍的位元組數依封包類型（RDMA WRITE / WRITE IMM / 32-byte WRITE IMM / AETH）用固定 `tkeep` 處理。
4. 原始資料經延遲線對齊後，用 `axis_ftr` 在封包尾端附加 4 byte ICRC。
5. `i_crc_en = 0` 的封包（例如 1722B CoE）直接通過，不附加 ICRC。

## `roce_ack`

見 [roce_ack.md](roce_ack.md)。
