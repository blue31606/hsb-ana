# `dp_pkt_top`（Data Plane 封包器）

## 概要

把所有 VP 的感測器資料切成封包，加上 header，送到對應的 host 埠。支援兩種傳輸格式：

- **RoCEv2 RDMA WRITE**：資料直接寫進 host 記憶體中的環狀 frame buffer；每個 frame 結束送一個 WRITE with Immediate 與 128 byte metadata，通知 host frame 完成。
- **IEEE 1722B CoE（Camera over Ethernet）**：L2 封包，給 Jetson Thor 等 CoE 接收端。

| 檔案 | 行數 | 功能 |
|---|---|---|
| [`dp_pkt_top.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/dp_pkt/dp_pkt_top.sv) | 1687 | 仲裁、設定與狀態 RAM、header FSM、位址計算、header 組裝 |
| [`dp_pkt.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/dp_pkt/dp_pkt.sv) | 261 | 每個 host 埠的 payload 多工、補零、frame CRC |
| [`dp_pkt_hdr.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/dp_pkt/dp_pkt_hdr.sv) | 252 | header 向量轉 AXIS |
| [`dp_pkt_ts.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/dp_pkt/dp_pkt_ts.sv) | 202 | frame 開始（SOF）的 PTP 時間戳 |

實例：[`HOLOLINK_top.sv#L1555`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L1555)（一份，非 Bridge 模式且有 SIF RX 時）。分析深度：仲裁、FSM、位址計算、CoE / metadata 組裝逐行；`dp_pkt_hdr` 只讀結構；RoCE ICRC 見 [roce.md](roce.md)。

## 參數

| 參數 | 傳入 | 說明 |
|---|---|---|
| `N_INPT` | `TOTAL_VP_WIDTH` | 所有 SIF 的 VP 總數 |
| `N_HOST` | `HOST_IF_INST` | |
| `W_DATA` | `HOST_WIDTH` | |
| `W_USER` | 17 | 輸出 `tuser`（VLAN） |
| `MTU` | `HOST_MTU` | |
| `BUFFER_4K_REG` | 1 | buffer 位址用「起點 + 增量 × 指標」，最多 4096 個 buffer |
| `DIS_COE` | `REMOVE_COE` | 合成時移除 CoE header |

| 常數 | 值 |
|---|---|
| 位址單位 | page = 128 byte（`NUM_PAD_BITS = 7`）；payload 長度都是 page 的整數倍 |
| `ROCE_HDR_WIDTH` | 560 bit（Eth 14 + IPv4 20 + UDP 8 + BTH 12 + RETH 16） |
| `COE_HDR_WIDTH` | 368 bit（46 byte） |
| `WR_IMM_SIZE` | 384 bit（metadata 本體 48 byte） |

## 介面

| 方向 | 名稱 | 說明 |
|---|---|---|
| in | `i_axis_*[N_INPT]` | 每個 VP 的資料（HIF 時脈） |
| in | `i_sof[N_INPT]` | frame 開始 |
| in | `i_cur_ptp[79:0]` | HIF 時脈的 PTP 時間 |
| in | `i_dev_mac_addr[N_HOST]`、`i_dev_ip_addr[N_HOST]` | 本機位址 |
| out | `o_axis_*[N_HOST]` | → 各 host 埠 `eth_pkt` 第 0 埠 |
| APB | `i_apb_m2s[N_HOST]` | 每個 host 埠的 `dp_pkt` 暫存器 |
| APB | `i_apb_m2s_cfg` | VP 設定 RAM（APB RAM 0） |

## 內部結構

```mermaid
flowchart TB
  VP(["VP[0..N_INPT-1]"])
  SOF(["i_sof"])
  ARB["VP 仲裁（rrarb）<br/>EOF 優先・每 host 每輪每 VP 一次"]
  FSM["Header FSM<br/>IDLE→LOAD_STS→GRANT→CALC→STORE→HDR_WAIT"]
  CFG["設定 RAM<br/>每 VP 16 word（host 寫）"]
  STS["狀態 RAM（分散式）<br/>psn、buf_ptr、vaddr、frame_num、旗標"]
  CRC["CRC RAM<br/>每 VP 的 frame CRC 中間值"]
  ETH["Eth RAM<br/>目標 MAC/IP/UDP、IPv4 checksum、VLAN"]
  TS["dp_pkt_ts<br/>SOF 時間戳 FIFO"]
  subgraph PH["每個 host 埠"]
    DP["dp_pkt<br/>取 pkt_len 拍資料・不足補 0・CRC"]
    HDR["dp_pkt_hdr<br/>header + payload 拼接"]
    BUF["輸出緩衝"]
  end
  OUT(["o_axis_*[h]"])
  VP --> ARB --> FSM
  SOF --> TS --> FSM
  CFG & STS & CRC & ETH <--> FSM
  FSM -- "pkt_len_en" --> DP
  VP --> DP
  FSM -- "header 向量" --> HDR
  DP --> HDR --> BUF --> OUT
```

## 行為

### 1. VP → host 對應與仲裁

每個 host 埠的 `dp_pkt_vip_mask` 是一個 bitmask，標示這個 host 服務哪些 VP（[L145](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/dp_pkt/dp_pkt_top.sv#L145)）。仲裁規則（[L649–L737](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/dp_pkt/dp_pkt_top.sv#L649-L737)）：

| 規則 | 說明 |
|---|---|
| EOF 優先 | 有 VP 的 frame 剛結束（`sif_eof`）時，只讓這些 VP 請求，以便盡快送出 metadata |
| 公平性 | `hif_sif_mask`：同一個 host 埠在一輪內每個 VP 只服務一次，所有有資料的 VP 都服務過才清除 |
| host 忙碌 | host 埠正在送封包（`hif_busy`）且不是快結束（`hif_not_busy_soon`）時，它的 VP 不參與 |
| 仲裁器 | `rrarb` round-robin，只在 FSM 為 `IDLE` 時給新 grant |

`hif_not_busy_soon`（`dp_pkt.sv`）：封包剩下不到 10 拍時拉高，讓 FSM 提前為下一個封包讀設定、算位址，header 計算和前一個封包的資料傳送重疊。

### 2. 設定 RAM

基底 `0x0000_1000`，每個 VP `0x40` byte。位置以 host 軟體 `data_channel.hpp` 為準（`hololink.hpp` 的 `FPGA_SENSOR_VP_VLAN_BASE = 0x1034`、`FPGA_SENSOR_VP_STRIDE = 0x40` 佐證）：

| Offset | Host 名稱 | 內容 |
|---|---|---|
| 0x00 | `DP_QP` | `[23:0]` RoCE dest QP（CoE：低 6 bit = channel）、`[24]` 1722B、`[31:25]` line 長度 log2（CoE line 結束旗標用） |
| 0x04 | `DP_RKEY` | RoCE rkey |
| 0x08 | `DP_PAGE_LSB` | `[31:7]` buffer 起點 page |
| 0x0C | `DP_PAGE_MSB` | `[0]` buffer 起點 bit 25、`[31:1]` 位址固定高位 |
| 0x10 | `DP_PAGE_INC` | 每個 buffer 的 page 增量 |
| 0x14 | `DP_MAX_BUFF` | `[27:16]` 起始 / `[11:0]` 結束 buffer 指標 |
| 0x18 | `DP_BUFFER_LENGTH` | frame 長度（byte） |
| 0x20 / 0x24 | `DP_HOST_MAC_LOW` / `HIGH` | |
| 0x28 | `DP_HOST_IP` | |
| 0x2C | `DP_HOST_UDP_PORT` | `[15:0]` UDP 埠、`[16]` `md_disable` |
| 0x34 | `DP_VLAN` | `[15:0]` TCI、`[16]` 插入 VLAN |
| 0x3C | （PSN） | FSM 回寫目前 PSN（`cfg_ram_wr_en`，[L924](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/dp_pkt/dp_pkt_top.sv#L924)） |

**讀取順序經過重排**（[L269–L300](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/dp_pkt/dp_pkt_top.sv#L269-L300)）。FSM 的計數 `fsm_cnt` 經查表轉成 RAM word，讓「同一個 frame 的後續封包」只需要讀前 7 個 word（`DUMP_CLK_CYCLES = 7`）：

| `fsm_cnt` | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | A | B |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RAM word | 6 | 4 | 2 | 3 | 0 | 1 | 5 | A | B | 8 | 9 | D |
| 內容 | 長度 | 增量 | 起點 | 高位 | QP | rkey | 指標 | IP | UDP | MAC lo | MAC hi | VLAN |

RAM 讀取延遲 1 拍，所以程式碼裡 `cfg_ram_addr[3:0] == N` 拿到的是 `fsm_cnt = N − 1` 的資料（例如 `N = 5` 時是 QP 與 `is_1722b`）。

frame 開始、最後一個封包、metadata 封包或第一次執行時，讀完整 18 個；同一 frame 的中間封包只讀 7 個，其餘沿用 Eth RAM 的快取值。

### 3. Header FSM

[L776–L917](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/dp_pkt/dp_pkt_top.sv#L776-L917)：

| 狀態 | 動作 |
|---|---|
| `ROCE_IDLE` | 有 VP 請求時鎖定 VP 與 host，讀狀態 RAM |
| `ROCE_LOAD_STS` | 判斷這是資料封包還是 metadata 封包（`pkt_is_imm = sif_eof[vp]`）；決定封包長度 `dp_pkt_len` |
| `ROCE_GRANT` | 決定 header 類型、要讀幾個設定 word |
| `ROCE_CALC` | 逐拍讀設定、計算位址；到達 commit 點時若 host 埠空閒且 VP 有資料，`pkt_commit`：啟動 `dp_pkt` 與 header 輸出 |
| `ROCE_STORE` | 回寫狀態 RAM |
| `ROCE_HDR_WAIT` | 等 header 送完 |

**搶占**（`fsm_preempt`，[L952](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/dp_pkt/dp_pkt_top.sv#L952)）：計算中途若同一 host 有其他 VP 的 frame 結束、而目前的 VP 沒有，或目前 VP 已經沒有資料，就放棄這次計算回到 `IDLE`，讓 EOF 先處理。

### 4. 位址與長度計算

[L985–L1036](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/dp_pkt/dp_pkt_top.sv#L985-L1036)，單位都是 page：

```
buffer 起點 = DP_PAGE_LSB + DP_PAGE_INC × buf_ptr
目前位址    = frame 開始 ? buffer 起點 : 狀態 RAM 裡的下一個位址
封包長度    = 單封包 frame ? frame 長度 : 最後一個封包 ? 剩餘長度 : dp_pkt_len
metadata 位址 = buffer 起點 + ⌈frame 長度 / 128⌉
RETH VA[63:33] = DP_PAGE_MSB[31:1]，VA[32:0] = 目前位址 × 128
```

`buf_ptr` 在 metadata 封包後前進：到 `DP_MAX_BUFF` 的結束值時回到起始值（[L1052–L1056](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/dp_pkt/dp_pkt_top.sv#L1052-L1056)）。host 因此可以配置一個 frame buffer 環，HSB 依序填入。

### 5. Payload 多工（`dp_pkt`）

每個 host 埠一份。收到 `pkt_len_en` 後，從被選中的 VP 取 `pkt_len` 拍資料：

- VP 的 `tlast`（frame 結束）比預期早到時，剩下的拍數補 0（`pkt_pad`），並設定 `unsync`。這種 frame 在 metadata 的 `flags` 裡標示。
- 每拍資料進 `lfsr_hc` 更新 frame CRC。CRC 中間值存在 `crc_ram`，每個 VP 一筆，所以多個 VP 交錯傳送時各自的 CRC 不會混在一起。frame 開始時 CRC 初值全 1，metadata 裡的 CRC = 結果 XOR `dp_pkt_crc_xor`。

### 6. Header 類型

`hdr_type = {pkt_is_imm, pkt_is_1722b}`：

| `hdr_type` | 封包 | 內容 |
|---|---|---|
| `00` | RoCEv2 RDMA WRITE | 70 byte header + payload + ICRC |
| `01` | 1722B CoE | 46 byte header + payload，**沒有 ICRC** |
| `10` | RoCEv2 WRITE with Immediate | header + 4 byte IMM + 128 byte metadata |
| `11` | 1722B CoE + metadata | 46 byte header + metadata |

`md_disable = 1` 時不送獨立的 metadata 封包，frame 的最後一個資料封包直接帶 Immediate（`is_data_wr_imm`）。

Immediate 值：`{psn[19:0], buf_ptr[11:0]}`（`BUFFER_4K_REG = 1`）。

### 7. Metadata 格式

[L1310](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/dp_pkt/dp_pkt_top.sv#L1310)，48 byte，補到 128 byte。與 host 軟體的 `parse_frame_metadata()`（`src/hololink/core/frame_metadata_parser.hpp`）一致：

| Byte | 欄位 | RTL 來源 | Host 名稱 |
|---|---|---|---|
| 0–3 | flags | `{30'h0, bpw_only, unsync}` | `flags` |
| 4–7 | PSN | `{8'h0, psn}` | `psn` |
| 8–11 | frame CRC | `frame_crc` | `crc` |
| 12–19 | SOF 秒 | `{16'h0, sof_ptp[79:32]}` | `timestamp_s` |
| 20–23 | SOF 奈秒 | `sof_ptp[31:0]` | `timestamp_ns` |
| 24–31 | 有效 byte 數 | `roce_val_addr` | `bytes_written` |
| 32–33 | 保留 | 0 | |
| 34–35 | frame 編號 | `frame_num` | `frame_number` |
| 36–43 | metadata 送出時的秒 | `{16'h0, cur_ptp[79:32]}` | `metadata_s` |
| 44–47 | metadata 送出時的奈秒 | `cur_ptp[31:0]` | `metadata_ns` |

`flags[0]`（unsync）：frame 比 `DP_BUFFER_LENGTH` 短。`flags[1]`：frame 結尾沒有對齊封包邊界。

### 8. 1722B CoE header

[L1193–L1269](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/dp_pkt/dp_pkt_top.sv#L1193-L1269)。host 軟體把 46 byte 分成 `14 Ethernet + 12 avtpdu + 12 gisf + 8 coe`（`data_channel.cpp#L315`）：

| Byte | 欄位 | 值 / 來源 |
|---|---|---|
| 0–5 | dest MAC | `DP_HOST_MAC` |
| 6–11 | src MAC | 本機 MAC |
| 12–13 | EtherType | `0x22F0` |
| 14 | subtype | `0x82` |
| 15–17 | `sv`(1) + 23 bit | `sv = 1` |
| 18–25 | stream_id | 常數 `0x0000_0000_AAAA_AAAA` |
| 26 | ACF msg type | `0x0C` |
| 27 | ACF msg length | 0 |
| 28 | `pad[1:0]`、`mtv`、5'b0 | `mtv = 1` |
| 29 | image_sensor_id | VP index |
| 30–37 | timestamp | `cur_ptp[63:0]` |
| 38 | sequence_number | `psn[7:0]` |
| 39–40 | `e`、`se`、`fcv`、`version`、`exposure`、3'b0、`channel_number[5:0]` | channel = `DP_QP[5:0]` |
| 41 | flags | `[3:0]`：1 = frame 開始、2 = metadata、0 = 其他；`[7:4]`：1 = line 結束 |
| 42–45 | `2'b00`、`frame_num[1:0]`、`byte_offset[27:0]` | frame 內 byte 位置 |

line 結束：`DP_QP[31:25]` 給 line 長度的 log2，FSM 比較下一個位址在該位元是否改變（`nxt_pkt_le`），也就是封包跨過 line 邊界時設旗標。

### 9. SOF 時間戳（`dp_pkt_ts`）

`i_sof` 任一 VP 拉高時，把 `{VP 遮罩, PTP 時間[63:0]}` 推入小 FIFO；FSM 處理對應 VP 時讀出。同一拍多個 VP 的 SOF 共用一筆，所有 VP 讀過才彈出。

## 暫存器

| 區塊 | 基底 | 內容 |
|---|---|---|
| `dp_pkt`（每 host） | `0x0200_0300 + h × 0x1_0000` | 見下表 |
| VP 設定 RAM | `0x0000_1000 + VP × 0x40` | 見 §2 |

| Offset | 名稱 | Reset | 說明 |
|---|---|---|---|
| 0x04 | `dp_pkt_len` | `0x5CE` | `[7:0]` 每個資料封包的 page 數。host 以 `PAGES(payload_size)` 寫入 |
| 0x08 | `dp_pkt_dev_udp_port` | `0x3000`（12288） | 本機 UDP 來源埠（host `DATA_SOURCE_UDP_PORT`） |
| 0x0C | `dp_pkt_vip_mask` | 0 | 這個 host 服務的 VP |
| 0x10 | `dp_pkt_crc_xor` | 0 | frame CRC 最後 XOR 的值 |
| 0x14 | `dp_pkt_1722B` | 0 | 未分析 |

## 注意事項

1. `dp_pkt_len` 的 reset 值 `0x5CE` 只有低 8 bit 被使用（`0xCE` = 206 page = 26 KB），超過 MTU，必須由軟體設定。
2. CoE header 的 VLAN 欄位在 concat 中被註解掉；VLAN 由 `eth_pkt` 依 `DP_VLAN` 插入。
3. CoE 的 `stream_id`、ACF msg type 等是常數，與 IEEE 1722b 規格的逐欄對照不在本文件範圍。
