# 控制平面封包處理（`rx_ls_parser`、`ecb_rdwr_ctrl`、`bootp`、`arp_ping_pkt_proc`）

## 概要

`rx_ls_parser` 匯集所有 host 埠的低速（LS）封包，分派給四個處理器，並把它們的回應統一加上 Ethernet / IPv4 / UDP header 送回對應的 host 埠。整條路徑是 8-bit 寬。

| 檔案 | 行數 | 功能 |
|---|---|---|
| [`rx_parser/rx_ls_parser.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_ls_parser.sv) | 643 | 輸入 / 輸出仲裁、UDP header 組裝 |
| [`ecb/ecb_rdwr_ctrl.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/ecb/ecb_rdwr_ctrl.sv) | 776 | ECB 暫存器讀寫協定 |
| [`ecb/ecb_pkg.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/ecb/ecb_pkg.sv) | 33 | 命令碼 |
| [`bootp/bootp.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/bootp/bootp.sv) | 481 | 裝置宣告（enumeration）與 IP 指派 |
| [`rx_parser/arp_ping_pkt_proc.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/arp_ping_pkt_proc.sv) | 279 | ARP、ICMP echo、UDP loopback |
| `ctrl_bus_evt_int` | | 中斷封包（只送不收），見 [event.md](event.md) |

實例：[`HOLOLINK_top.sv#L466`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L466)。分析深度：四個檔案逐行。

## 內部結構

```mermaid
flowchart LR
  subgraph IN["每個 host 埠一條 8-bit LS"]
    H0["rx_parser[0].o_ls"]
    H1["rx_parser[1].o_ls"]
  end
  ARBI["u_inp_axis_arb<br/>Round-robin（依 host）"]
  DEMUX{"tuser[5:0]<br/>LS 旗標"}
  APP["arp_ping_pkt_proc"]
  ECB["ecb_rdwr_ctrl"]
  BOOT["bootp"]
  EVT["ctrl_bus_evt_int"]
  ARBO["u_out_axis_arb<br/>Round-robin（依來源）"]
  HDR["加 Eth/IPv4/UDP header<br/>IPv4 checksum"]
  OUT(["o_axis_*<br/>tvalid[NUM_HOST]"])
  APBM(["m_apb[0]"])
  H0 --> ARBI
  H1 --> ARBI --> DEMUX
  DEMUX -- "0 Loopback / 3 Ping / 4 ARP" --> APP
  DEMUX -- "2 ECB / 5 RoCE-ECB" --> ECB
  DEMUX -- "1 BOOTP" --> BOOT
  ECB --> APBM
  APP & ECB & BOOT & EVT --> ARBO --> HDR --> OUT
```

| RX index | 來源 | TX index | 來源 |
|---|---|---|---|
| 0 | Loopback | 0 | ECB 回應 |
| 1 | BOOTP | 1 | Event 中斷 |
| 2 | ECB | 2 | BOOTP |
| 3 | Ping | 3 | ARP / Ping / Loopback |
| 4 | ARP | | |
| 5 | RoCE-ECB | | |

## `rx_ls_parser`

| 步驟 | 行為 | 原始碼 |
|---|---|---|
| 輸入仲裁 | `axis_arb`（round-robin，依 host，有 skid）。輸出 `o_axis_idx` 記下來源 host，回應時用它選本機 MAC / IP 與輸出埠 | [rx_ls_parser.sv#L145–L171](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_ls_parser.sv#L145-L171) |
| 分派 | `tuser[5:0]` 是 `rx_parser` 產生的 one-hot 類別；只有對應處理器的 `tvalid` 拉高，`tready` 也只看那個處理器 | [rx_ls_parser.sv#L169–L171](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_ls_parser.sv#L169-L171) |
| 輸出仲裁 | 4 個來源（ECB、事件、BOOTP、ARP/Ping）round-robin | [rx_ls_parser.sv#L357–L381](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_ls_parser.sv#L357-L381) |
| Header | ARP / Ping / Loopback 自帶完整封包（`hdr_en = 0`）；其他來源只給 payload 與位址欄位，這裡組 42 byte header | [rx_ls_parser.sv#L407–L551](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_ls_parser.sv#L407-L551) |
| ICRC | RoCE-ECB 的回應經 `roce_icrc` 附加 ICRC | [rx_ls_parser.sv#L554–L583](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_ls_parser.sv#L554-L583) |
| 輸出緩衝 | `axis_buffer`：8 bit → HIF 寬度、深度 2 × MTU、`WAIT2SEND = 1`（store-and-forward） | [rx_ls_parser.sv#L596–L623](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_ls_parser.sv#L596-L623) |
| 輸出 | 資料線所有 host 共用，`tvalid` 只對目標 host 拉高，`tready` 也只取目標 host 的 | [rx_ls_parser.sv#L626–L635](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_ls_parser.sv#L626-L635) |

組出的 header：

| 層 | 欄位 |
|---|---|
| Ethernet | dest = 請求者 MAC、src = 本機 MAC（依來源 host）、type `0x0800` |
| IPv4 | version 4、IHL 5、DSCP / ECN 0、total length = payload + 28、ID 0、flags `010`（DF）、TTL 64、protocol 17 |
| UDP | src = 本機埠、dest = 請求者埠、length = payload + 8、checksum 0 |

IPv4 checksum 用 4 級管線算 `src IP + dst IP + 0xC52D + pld_len`（[rx_ls_parser.sv#L499–L514](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_ls_parser.sv#L499-L514)），常數與 `dp_pkt_top` 相同（見 [dp_pkt_top §7](dp_pkt_top.md#7-rocev2-header)）。每個封包開始時 `ipv4_chksum_state` 先數 4 拍，等 checksum 算好才放行輸出。

## `ecb_rdwr_ctrl`（ECB 協定）

ECB 是 host 讀寫 HSB 所有暫存器的協定。每個 ECB 封包被拆成一或多個 APB transaction，由 `m_apb[0]` 執行。

### 請求格式

offset 從 Ethernet header 開頭算（VLAN 已由 `rx_parser` 移除）：

| Offset | 一般 ECB（UDP 8192） | RoCE-ECB（UDP 4791 + BTH，dest QP = `roce_ecb_dest_qp`） |
|---|---|---|
| 6–11 | host MAC | 同左 |
| 26–29 | host IP | 同左 |
| 34–37 | UDP 埠（回應時對調） | UDP 埠（回應時不對調） |
| 38–39 | UDP length | 同左 |
| 42 | cmd | BTH opcode |
| 43 | flags | |
| 44–45 | sequence | |
| 46–47 | 保留 | |
| 54 / 55 / 56–57 | | cmd / flags / sequence |
| 48（RoCE：60）起 | `{addr[31:0], data[31:0]}` × N，big endian | 同左 |

N = `(udp_len − 22) >> 3`（RoCE：`(udp_len − 38) >> 3`）。

### 命令、flags、回應碼

| 命令 | 值 | 支援 |
|---|---|---|
| `WR_DWORD` | 0x04 | ✓（一組 addr/data） |
| `WR_BLOCK` | 0x09 | ✓（多組） |
| `RD_DWORD` | 0x14 | ✓ |
| `RD_BLOCK` | 0x19 | ✓ |
| 其他（`WR_BYTE`、`WR_WORD`、`RMW_BYTE`、`RD_BYTE`、`RD_WORD`、`GET_INFO`） | | ✗：回 `INVALID_CMD` |

| Flags | 意義 |
|---|---|
| bit 0 | `ACK_REQUEST`：**寫入命令沒有設這個 bit 時不送回應**（`drop_packet = !(flags[0] \|\| 讀取)`，[ecb_rdwr_ctrl.sv#L715](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/ecb/ecb_rdwr_ctrl.sv#L715)）；讀取命令一律回應 |
| bit 1 | `SEQUENCE_CHECK`：要求 `sequence == seq_num_latch + 1`。`seq_num_latch` 在 header 檢查通過時更新為這次的 sequence；之後若 APB 回錯誤，恢復成前一個值，host 可以用同一個 sequence 重送（[ecb_rdwr_ctrl.sv#L329–L347](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/ecb/ecb_rdwr_ctrl.sv#L329-L347)、[ecb_rdwr_ctrl.sv#L387–L389](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/ecb/ecb_rdwr_ctrl.sv#L387-L389)） |
| bit 7:2 | 必須為 0，否則回 `INVALID_FLAGS` |

回應碼（[L558–L574](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/ecb/ecb_rdwr_ctrl.sv#L558-L574)），依優先順序：

| 條件 | 回應碼 |
|---|---|
| 命令不支援 | 0x04 `INVALID_CMD` |
| flags 保留位元不為 0 | 0x06 `INVALID_FLAGS` |
| sequence 檢查失敗 | 0x0B `SEQUENCE_CHECK_FAIL` |
| APB 回 `pserr`（例如位址不存在、逾時） | 0x03 `INVALID_ADDR` |
| 其他 | 0x00 `SUCCESS` |

host 軟體另外定義了 0x02、0x05、0x07–0x0A，RTL 沒有產生這些值。

### 回應格式

[ecb_rdwr_ctrl.sv#L697–L765](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/ecb/ecb_rdwr_ctrl.sv#L697-L765)：

| 部分 | 長度 | 內容 |
|---|---|---|
| （RoCE-ECB）RoCE header | BTH + RETH + ImmDt | 見下 |
| header | 6 byte | `{cmd_code, flags, sequence[15:0], resp_code, 0x00}` |
| pairs | 8 byte × N | 每組 `{addr, data}`。addr 是請求中的位址原樣送回；data 寫入時為 0、讀取時為讀回值 |
| sequence | 2 byte | `seq_num_latch`：最後一次被接受的 sequence |
| 補齊 | 0 或 2 byte | N ≤ 1 時補 2 byte 0，讓 UDP payload 固定 18 byte（整個 Ethernet frame 60 byte） |

- `cmd_code`：命令有效時為 `{3'b100, is_read, cmd[3:0]}`，例如 `WR_DWORD` → 0x84、`RD_DWORD` → 0x94；無效時原樣送回。
- `pld_len = 6 + 2 + 8 × N`（N ≤ 1 時固定 18）。
- 回應的 pairs 先寫進 `axis_buffer`（深度 MTU、`WAIT2SEND = 1`），整個請求處理完才開始送，所以回應一定在所有 APB 存取之後。
- header 檢查就失敗時（命令、flags、sequence 錯誤），FSM 進 `DCD_FLUSH` 時仍會寫 8 byte 到 pairs 緩衝區（`apb_cnt` 0–7），所以錯誤回應也帶一組 pair；data 為 0，addr 位置是 flush 當下的輸入 byte（推斷：即第一組 addr 的內容）。
- APB 在 block 命令中途回錯誤：已完成的 pairs 與出錯的那一組都在回應中，之後的 pairs **不執行**，回應碼 `INVALID_ADDR`。

**RoCE-ECB 回應**（[ecb_rdwr_ctrl.sv#L598–L643](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/ecb/ecb_rdwr_ctrl.sv#L598-L643)）：前面加 BTH + RETH + ImmDt，整個回應以 **RDMA WRITE with Immediate**（opcode `0x2B`）寫到 host 記憶體：

| 欄位 | 來源 |
|---|---|
| dest QP / P_Key / R_Key | `ecb_dest_qp` / `ecb_pkey` / `ecb_rkey` 暫存器 |
| VA | `{ecb_addr_msb, ecb_addr_lsb}`（每次都寫同一個位址） |
| PSN | 內部計數，每送一個 RoCE-ECB 回應加 1 |
| ImmDt | `{16'h0, sequence}` |
| UDP 埠 | 不對調（來源埠仍是請求的來源埠） |

### 兩個狀態機

**解碼（HIF 時脈，[L277–L424](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/ecb/ecb_rdwr_ctrl.sv#L277-L424)）**：

| 狀態 | 動作 |
|---|---|
| `DCD_IDLE` | 等 ECB 或 RoCE-ECB 封包 |
| `DCD_HDR` | 逐 byte 收 header 到 byte 47（RoCE：59） |
| `DCD_CHK_HDR` | 檢查 cmd / flags / sequence；有錯直接 `DCD_FLUSH` 並送回應 |
| `DCD_DATA` | 收 8 byte addr/data |
| `DCD_WAIT` | 送 APB 命令到 APB 時脈，等完成 |
| `DCD_WAIT_STATUS` | APB 錯誤 → `DCD_FLUSH`；block 命令且還有資料 → `DCD_LATCH_WRITE` 再回 `DCD_DATA`；否則 `DCD_FLUSH` |
| `DCD_FLUSH` | 吃掉封包剩餘部分，送出回應 |

**APB（APB 時脈，[L437–L482](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/ecb/ecb_rdwr_ctrl.sv#L437-L482)）**：`CMD_IDLE → CMD_SEND → CMD_DONE`，一次一個 APB transaction。位址低 2 bit 強制為 0（只支援 32-bit 對齊）。

握手是四相式（[ecb_rdwr_ctrl.sv#L651–L692](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/ecb/ecb_rdwr_ctrl.sv#L651-L692)）：HIF 端拉高 `apb_send_cmd` 並保持 → APB 端同步後執行一次 transaction，`CMD_DONE` 拉高 `apb_cmd_done` → HIF 端同步後放下 `apb_send_cmd` → APB 端看到放下才回 `CMD_IDLE`。每組 addr/data 都要一次完整往返（2 個方向各 2 級同步），所以 ECB 的吞吐量受 APB 時脈與 CDC 延遲限制。

跨時脈的資料：

| 訊號 | 方向 | 處理 | 為什麼安全 |
|---|---|---|---|
| `cmd_addr` | HIF → APB | 32 bit `data_sync` | 在 `apb_send_cmd` 拉高前至少 5 個 HIF 時脈就已固定；APB 端在 `send_cmd` 同步完成後再過 1 拍才拉 `psel` |
| `cmd_dout`（寫入資料） | HIF → APB | **沒有同步**，直接接到 `pwdata` | 視為靜態資料：在 `apb_send_cmd` 之前固定，整個 transaction 期間不變。合成時需要對這條路徑下 false path / max delay 約束（推斷） |
| `cmd_rddata` | APB → HIF | 32 bit `data_sync` | 在 `apb_cmd_done` 拉高前一個 APB 時脈就已鎖住 |
| `cmd_err` | APB → HIF | 與 `apb_cmd_done` 同一個 `data_sync` | 同時設定 |

**邊界情況**（R + I）：

| 情況 | 行為 |
|---|---|
| 封包在 header 收完前結束 | `DCD_HDR` 看到 `tlast` → `DCD_DONE`：**不回應**、不執行 |
| 封包在一組 pair 中途結束 | `DCD_DATA` 看到 `tlast` → `DCD_WAIT`：用不完整的 addr / data（未收到的 byte 在 `DCD_IDLE` 時清為 0）**仍然執行一次 APB 存取** |
| 一般 ECB 的 pair 數 | 由 `tlast` 決定，不看 UDP length；Ethernet 最小長度補齊的 byte 會被當成下一組 pair 的開頭。例如 `WR_BLOCK` 只帶 1 組時封包被補到 60 byte，多出的 4 byte 會觸發一次位址不完整的額外存取（推斷） |
| RoCE-ECB 的 pair 數 | 由 `total_pairs = (udp_len − 38) >> 3` 決定，ICRC 不會被當成資料 |
| UDP length < 22 | `total_pairs` 下溢成很大的值（只影響 RoCE-ECB） |

## `bootp`

HSB 用 BOOTP 格式向 host 宣告自己，host 軟體的 `Enumerator` 收這些封包來找裝置。

### 傳送

- 狀態機（[bootp.sv#L258–L302](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/bootp/bootp.sv#L258-L302)）：`IDLE` 等 `i_init` → `BOOTP_REQ` 觸發一個封包 → `BOOTP_WAIT` 等送完、換下一個 host 埠 → `BOOTP_RPT`。一輪（所有 host 埠各一次）還沒送完時立即送下一個；一輪送完後等下一個 PPS（`ptp_sync_vld` 是 PPS 經 `reg_cdc` 的結果）。PTP 計時器即使沒有同步也會自由執行、產生 PPS，所以 BOOTP 一定每秒重送。
- 每輪結束 `psn` 加 1。
- 目的：廣播 MAC / IP，UDP 12268 → 12267。
- BOOTP 本體 300 byte（`pld = 0x12C`）：op = 1、htype 1、hlen 6、xid = host 埠號、secs = PTP 秒的低 16 bit、**ciaddr = 這個埠目前的 IP**、chaddr = 本機 MAC（[bootp.sv#L236–L252](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/bootp/bootp.sv#L236-L252)）。vendor 欄位（[L344–L375](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/bootp/bootp.sv#L344-L375)）：

| 欄位 | 內容 |
|---|---|
| tag | `0xE0`、長度、`"NVDA"`、埠號、enumeration 版本 2 |
| backward compat rev | `HOLOLINK_BACKWARD_COMPAT_REV`（0x2603） |
| UUID | `HOLOLINK_def.svh` 的 `UUID` |
| 封包計數 | 這個 host 埠送出的封包數（24 bit，來自 `eth_pkt.o_pkt_inc`） |
| enumeration 資料 | board 版本、SN、HSB 版本等（`i_enum_data`） |
| PTP 時間 | |
| PSN | BOOTP 輪次 |
| `hsb_stat` | `[0]` = DPLL 啟用後收到 Sync（`ptp_top.o_ptp_en_sync_rx`） |

### 接收

`rx_parser` 把 dest MAC = 本機、UDP dest 埠 = 12268 的封包歸為 BOOTP（不檢查 dest IP，因為 HSB 此時可能還沒有正確的 IP）。`bootp` 的輸入 `tready` 固定為 1；收到 op = 2（BOOTP reply）時，**不檢查 xid 或 chaddr**，直接取 byte 58–61（BOOTP `yiaddr`）當作收到它的 host 埠的 IP（[L454–L460](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/bootp/bootp.sv#L454-L460)）。

IP 來源優先順序：BOOTP reply > EEPROM（`ip_addr_vld` 上升緣，host 埠 k 用 EEPROM IP + k）> 預設 `192.168.0.2 + k`。

## `arp_ping_pkt_proc`

`rx_parser` 先過濾（[rx_parser.sv#L558–L565](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_parser.sv#L558-L565)）：

| 類別 | 條件 |
|---|---|
| ARP | EtherType `0x0806`、dest MAC 為本機或廣播、**target IP = 本機 IP** |
| Ping | IPv4、protocol 1、ICMP type 8、dest IP 與 dest MAC 都是本機 |
| Loopback | UDP、dest 埠 4096、dest IP 與 dest MAC 都是本機 |

`arp_ping_pkt_proc` 把前 42 byte header 攤平，逐 byte 重排後換掉原封包的 header，payload 原樣送回（[arp_ping_pkt_proc.sv#L148–L191](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/arp_ping_pkt_proc.sv#L148-L191)）：

| 封包 | header 改寫 |
|---|---|
| ARP | Ethernet dest = 請求者 MAC、src = 本機 MAC；opcode 改 2；sender = 本機 MAC + 請求中的 target IP；target = 請求者的 sender MAC / IP |
| Ping | MAC、IP 對調；ICMP type 改 0；checksum 增量更新 `+0x0800`（one's complement，含進位折回，[arp_ping_pkt_proc.sv#L193–L196](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/arp_ping_pkt_proc.sv#L193-L196)）；IPv4 checksum 不變（只對調位址） |
| Loopback | MAC、IP、UDP 埠對調，其餘不變 |

## 暫存器

| 區塊 | 基底 | 內容 |
|---|---|---|
| ECB | `0x0000_0300` | `ecb_addr_lsb`（0x04）、`ecb_addr_msb`（0x08）、`ecb_rkey`（0x0C）、`ecb_pkey`（0x10）、`ecb_dest_qp`（0x14）：RoCE-ECB 回應用 |

## 注意事項

1. `regmap_pkg.sv` 的 `ecb_addr_lsb` / `ecb_addr_msb` 註解位址寫反（[regmap.md](../registers/regmap.md#註解與程式不一致的項目)）。
2. `bootp` 的 IP 變數名為 `ciaddr`：它是送出 BOOTP request 時填在 ciaddr 欄位的「目前 IP」，收到 reply 時從 `yiaddr` 更新。命名與用途一致，不是錯誤（v3 的說明有誤）。
3. LS 路徑吞吐量 = 1 byte / HIF 時脈。
4. ECB 寫入命令預設沒有回應，host 需要確認寫入時必須設 `ACK_REQUEST`。
5. 封包在 pair 中途結束時仍會執行一次不完整的 APB 存取。具體情境（推斷，未模擬確認）：host 的批次寫入（`write_uint32(WriteData&)`）一律用 `WR_BLOCK`；只帶 1 組時 UDP payload 14 byte，frame 56 byte，被 MAC 補到 60 byte。多出的 4 byte 0 會被當成第二組的 addr，`tlast` 隨即到來，FSM 以 `addr = 0x0000_0000`、`data = 上一組的資料`（`cmd_dout` 只在 IDLE / FLUSH 清除）執行一次寫入，也就是寫到 `glb_scratch`；回應也會多一組 pair。前提是板級 MAC 不移除補齊 byte，且封包沒有 VLAN。
6. 任何送到 UDP 12268、dest MAC 為本機的 BOOTP reply 都會改變 HSB 的 IP，沒有 xid / chaddr 驗證。
7. `cmd_dout` 跨時脈沒有同步器，依賴「資料先固定、控制後同步」的時序；需要合成約束。
8. `rx_ls_parser` 是所有 host 埠共用的單一路徑：一個長的 `WR_BLOCK` 在執行期間（每組都要 APB 往返）會擋住其他 host 埠的 ARP、BOOTP、Ping；輸出緩衝也是共用的，某個 host 埠的 `eth_pkt` 不收時會擋住其他埠的回應（推斷）。
