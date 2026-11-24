# 問題清單

本文件把散在各模組「注意事項」與 [VERIFICATION](../VERIFICATION.md) 的 RTL 問題集中在一起，每項列出嚴重度、觸發條件、確認方法與建議修正。**沒有任何一項經過模擬或硬體確認**；「確認方法」欄說明要怎麼確認，對應的定向測試見 [test-plan](test-plan.md)。

## 分級

| 等級 | 定義 |
|---|---|
| **高** | 正常設定下就可能觸發，造成資料錯誤、資料遺失或功能卡住，而且不容易從 host 端察覺 |
| **中** | 需要特定設定、邊界條件、或不正常的網路狀況才會觸發；觸發後影響明顯 |
| **低** | 影響小、只在少用的功能或極端條件下出現，或有明確的軟體迴避方式 |
| **註** | 註解、命名、死碼、沒有接的訊號；不影響功能 |

方法代號沿用 VERIFICATION：**R** 讀 RTL、**X** 與 host 軟體交叉比對、**I** 推斷、**N** 已用 [數值驗證](verification-calcs.md) 確認、**M** 已用[逐拍模型](../tools/model/)重現（v7 新增）。

## 總表

### Data Plane 與封包處理

| ID | 等級 | 模組 | 問題 | 觸發條件 | 方法 | 建議修正 |
|---|---|---|---|---|---|---|
| DP-1 | 中 | `rx_parser` | 輸入 FIFO 滿時丟 beat，但 `in_pkt_cnt` 照樣計入被丟的 `tlast`；之後每個封包都配到前一包的 metadata、`WAIT2SEND` 失效，**直到 reset** | 讀出停滯讓輸入 FIFO 填滿：Bridge 背壓，或 Terasic S10 在 100G 下連續收到短封包（DP-15） | R + M | 改成整包丟棄：在 SOF 檢查剩餘空間 ≥ MTU，不夠就丟整包並計數；`in_pkt_cnt` 只計實際寫入的 `tlast` |
| DP-2 | 中 | `rx_parser` | metadata FIFO（32 筆）比資料 FIFO（128–256 個最小封包）先滿；三個 metadata FIFO 寫入時間不同、各自丟，彼此錯開 | 讀出落後於輸入（同 DP-1）；10G 板級與 PYNQ 不會發生 | R + M | 加深 metadata FIFO 到與資料 FIFO 的最小封包數相同，或在任一 metadata FIFO almost full 時整包丟棄 |
| DP-3 | 中 | `rx_parser` | 帶 VLAN 的 PTP 封包從 byte 14 讀 messageType（那是 VLAN TCI） | 網路上的 PTP 帶 802.1Q tag | R | 見[修正草稿 F-4](#f-4rx_parser-vlan-ptp-messagetype) |
| DP-4 | 低 | `rx_parser` | 分類不檢查 EtherType == 0x0800 | 非 IP 封包剛好在 protocol / IP 位置出現相符的值 | R | 在 IP 類條件中加 `ethertype == 0x0800`（VLAN 時看內層） |
| DP-5 | 中 | `packetizer` | `latency_cnt` 只有 3 bit，`latency ≥ 9` 時 FSM 停在 `WAIT` | 軟體設定 `pack_ctrl[27:24] ≥ 9`；host 目前固定 1 | R | 見 [F-3](#f-3packetizer-latency_cnt-寬度) |
| DP-6 | 低 | `packetizer` | `last_buf` 只用 VP 0 的 `tlast`（`out_is_last = o_axis_tvalid[0] && o_axis_tlast[0] && ...`）遞減；只用 VP 1 以上時每個 frame 只加不減，2 個 frame 後 `last_tready = 0`，SIF 輸入永久停住 | `tuser[3:2]` 分流且 VP 0 沒有流量 | R | 對每個 VP 各自追蹤，或改成 OR 所有啟用 VP 的 `tlast` |
| DP-7 | 低 | `packetizer` | 串流中寫設定 RAM 會打亂當前 line 的排程 | 串流進行中改 pattern | R | 軟體規範：先停 VP 再改；或加 shadow RAM，在 SOF 切換 |
| DP-8 | 中 | `packetizer` | VP FIFO 不反壓；`dp_pkt_top` 長時間不讀某個 VP 時整個 SIF 輸入被停住 | 某個 VP 的 host 不接收（`vp_mask` 移除後仍有資料） | R | 被停用的 VP 改成直接丟棄而不是停住共用的 `pack_tready` |
| DP-9 | 低 | `dp_pkt` | 不檢查 VP `tvalid`，VP 中途斷流時把無效資料當 payload | 違反 VP 契約（正常情況下 `virtual_port` 的閘控避免） | R | 加 assertion；payload 讀取時 `tvalid` 為 0 就設錯誤旗標 |
| DP-10 | 低 | `dp_pkt_ts` | 每 VP 4 筆的 SOF 時間戳環狀 RAM 用 2-bit 指標，沒有滿的檢查：第 5 個未讀的 SOF 覆寫最舊的一筆，該 frame 的 metadata 拿到 4 個 frame 之後的時間戳（之後的 frame 不受影響）。前端 `reg_fifo` 滿時不寫入，SOF 遺失 | 一個 VP 累積超過 4 個未送 metadata 的 frame | R | 寫指標追上讀指標時設溢位旗標到狀態暫存器 |
| DP-11 | 低 | `dp_pkt_top` | 同一個 VP 被多個 host 的 `vp_mask` 選中時只送給編號最大的 host | 軟體設定重疊的 `vp_mask` | R | 文件化為非法設定，或在設定時偵測並回報 |
| DP-12 | 中 | `flow`（host + RTL） | buffer 環不能跨 8 GB 對齊邊界：RTL 位址是 26-bit page 運算，`VA[63:33]` 固定取 `DP_PAGE_MSB[31:1]`，跨界時 `VA[32:0]` 回捲；host 只檢查最高 page 編號放得進 32 bit | host 配置的 buffer 跨過 8 GB 邊界（取決於執行時配置到的位址） | R + X | host 配置時檢查；或 RTL 把 page 位址擴到完整寬度 |
| DP-13 | 低 | `eth_pkt` | 逾時恢復時 MAC 送出「停住那一刻的封包開頭 + 仲裁器當下封包的後半段」接成的一個 frame | 某個輸入源或 MAC 在封包中途停住超過逾時 | R | 逾時時補送 `tlast` 並標記錯誤（`tuser`），恢復後從封包邊界開始 |
| DP-14 | 低 | `roce_icrc` / `lfsr_hc` | 只支援固定幾種最後一拍長度；沒有方程式的資料寬度靜默不算 CRC | 改 header 長度（GRH 等）或新增 HIF 寬度 | R + N | 加 elaboration 期檢查（`$error`），不支援的組合直接編譯失敗 |
| DP-15 | 中（S10） | `rx_parser` | n 拍封包讀出需要 n + 1 拍；512-bit / 201.42 MHz 時連續短封包的讀出比 100G 線速慢，輸入緩衝逐漸填滿，接著觸發 DP-1、DP-2 | Terasic S10，100G 連續收到 2 KB 以下的封包：60 byte 約 108 個、1500 byte 約 720 個之後溢位 | R + M | 讀出改成背靠背（`eop` 同拍讀下一筆 metadata），或提高 HIF 時脈 |
| DP-16 | 低 | `dp_pkt_top` | 只有一個 VP 送往某個 host 時，`hif_sif_mask` / `hif_sif_unserved` / `hif_sif_served` 三個暫存器形成以 6 拍為週期的振盪，`sif_req` 每 6 拍被遮住 3 拍；下一個封包的準備最多晚 3 拍，相位隨封包長度鎖住（512 bit、MTU 1500：每包 30 拍而不是 28，75.6 vs 81.0 Gb/s） | 單一 VP、連續資料封包 | R + M | 只有一個待服務 VP 時不設遮罩（`served` 時直接清除），或遮罩只在有其他 VP 等待時生效 |

### Host → 感測器（SIF TX）與 RoCE ACK

標「啟用時」的項目只在定義 `SIF_TX_ROCE_RC_ENABLE`（`rx_parser` 的 `ENABLE_ROCE_ACK = 1`）時存在；`41cecaa` 的板級設定都沒有定義它，host 軟體送往 HSB 的也只有 UC SEND（v7.1 確認）。

| ID | 等級 | 模組 | 問題 | 觸發條件 | 方法 | 建議修正 |
|---|---|---|---|---|---|---|
| TX-1 | 中（啟用時） | `roce_ack` | 重複封包（`psn < psn_exp`）不回 ACK；InfiniBand 規格要求 responder 對重複請求重新回應 | ACK 在網路上遺失，requester 重送 | R + M | 見 [F-5](#f-5roce_ack-重複封包回-ack) |
| TX-2 | 中（啟用時） | `roce_ack` | 第一個 ACK 的 PSN 取自狀態 RAM 的 reset 值 0，不是封包的 PSN；requester 若不接受而重送，重送的封包被當成重複（TX-1），之後永遠沒有回應 | host 初始 PSN ≠ 0 | R + M | 狀態未初始化時用封包的 PSN 初始化 `psn_exp` 並回應該 PSN |
| TX-3 | 低（啟用時） | `roce_ack` | PSN 比較是 24-bit 無號，不處理回捲：回捲後超前的封包被當成重複（不送 NAK），回捲前的舊封包被當成超前（送 sequence error NAK） | 在 PSN 回捲點附近遺失或重送封包 | R + M | 改用 24-bit 序列號比較：`diff = psn − psn_exp`，`diff[23]` 為 1 表示舊封包 |
| TX-4 | 低（啟用時） | `roce_ack` | IPv4 checksum 增量更新在借位時差 2 | 請求 IPv4 長度 < 48（只有不帶 payload 的 SEND）且 checksum ≤ 3 | R + N | 見 [F-2](#f-2roce_ack-ipv4-checksum) |
| TX-5 | 低（啟用時） | `roce_ack` / `sensor_tx_pkt_proc` | 感測器選擇的 QP 位元範圍不同（`[7:1]` vs `[8:1]`） | QP bit 8 為 1 | R | 統一成同一個函式 / 參數 |
| TX-6 | 低（啟用時） | `sensor_tx_pkt_proc` | header 長度寫死 54 byte，RC WRITE 的 16 byte RETH 留在送給感測器的資料裡 | `ENABLE_ROCE_ACK` 且 requester 用 RC WRITE。host 軟體送往 HSB 的只有 UC SEND（`cpu_roce_frame_transmitter`、`roce_transmitter_op`），所以只有第三方 requester 會觸發 | R + X | 依 opcode 決定要去掉的長度（WRITE_FIRST / ONLY 多 16 byte） |
| TX-7 | 中 | `sensor_tx_pkt_proc` / `tx_stream_buffer` | 路徑沒有 `tready`（`axis_buffer_tx` 的 `gbx_axis_tready` 寫死 1），FIFO 滿時遺失 beat；`tlast` 遺失時兩個封包接成一個。不會造成之後的封包永久錯位 | host 送得比感測器消耗快且 PAUSE 未啟用；或 `tx_data_output_ena = 0` 期間就有資料送入 | R | FIFO 滿時丟整包並補 `tlast`；或在 SOF 檢查空間；啟用前的資料直接丟棄 |
| TX-8 | 中 | `HOLOLINK_top` / `tx_stream_buffer` | 每個 `pause_gen` 都接 `tx_pause_quanta[0]`，其他 SIF TX 的 quanta 無效 | 多個 SIF TX 設定不同的 quanta | R | 見 [F-6](#f-6pause-quanta-索引) |
| TX-9 | 低 | `tx_stream_buffer` | `saw_overflow` 判斷早一格，且預填期間溢位不記錄 | 預填期間 FIFO 就滿 | R | 改用實際寫入失敗（`wr_en && full`）設旗標 |
| TX-10 | 低（啟用時） | `roce_ack` | host QP RAM 固定 2 個 word，SIF TX 2 以上與 0、1 共用 host QP / RNR timer | `ENABLE_ROCE_ACK` 且 SIF TX ≥ 3（目前沒有板級符合） | R | `R_CTRL` 改成 `N_QP`（或 SIF TX 數） |

### Control Plane（ECB、BOOTP、LS 路徑）

| ID | 等級 | 模組 | 問題 | 觸發條件 | 方法 | 建議修正 |
|---|---|---|---|---|---|---|
| CP-1 | 低 | `rx_ls_parser`（ECB） | 封包在 pair 中途結束仍執行一次 APB 存取；只帶 1 組的 `WR_BLOCK`（14 byte payload，frame 56 byte）被補到 60 byte 時，多出的 4 byte 0 會觸發一次寫往位址 0（`glb_scratch`）的額外存取 | **host 預設設定下每一次單一暫存器寫入**：enumeration 預設 `block_enable = 1`，`write_uint32(address, value)` 一律走單組 `WR_BLOCK` | R + X | 見 [F-7](#f-7ecb-不完整的-pair) |
| CP-2 | 低 | `rx_ls_parser`（ECB） | 寫入命令沒有 `ACK_REQUEST` 時不回應 | 第三方 host 軟體不設該旗標 | R + X | 文件化；host 端一律設定（目前已是） |
| CP-3 | 低 | `rx_ls_parser`（ECB） | `cmd_dout` 跨時脈沒有同步器 | 合成約束不完整 | R | 加 `set_max_delay -datapath_only` 或改用 `reg_cdc` |
| CP-4 | 低 | `bootp` | 任何送到 UDP 12268 的 BOOTP reply 都會改 IP，沒有 xid / chaddr 檢查 | 網路上有其他 BOOTP server 或惡意封包 | R | 比對 xid 與 chaddr |
| CP-5 | 低 | `rx_ls_parser` | 所有 host 埠共用一個 `rx_ls_parser`：輸入以封包為單位 round-robin（`u_inp_axis_arb`），ECB / ARP / BOOTP 引擎與輸出仲裁（`u_out_axis_arb`）都只有一份，一個埠的長 `WR_BLOCK` 會擋住其他埠的 ARP / Ping | 多 host 埠同時使用 | R | 每埠一個輸出緩衝，或把 ECB 與 ARP / ICMP 分開 |
| CP-6 | 低 | `reg_cdc` / `s_apb_reg` | 握手進行中的更新會遺失；`s_apb_reg` 所有控制暫存器共用 `reg_wdval` 觸發，所以連續寫同一區塊的**不同**暫存器也會遺失 | 兩次寫入間隔小於握手時間；`apb_switch` 保證 ≥ 16 個 APB 時脈，只在模組時脈低於約 0.48 倍 APB 時脈時不足（例如 S10 上低於 48 MHz 的 SIF 時脈） | R + M | 每個暫存器只在自己被寫入時觸發，或改用帶 FIFO 的 CDC |

### PTP 與時間

| ID | 等級 | 模組 | 問題 | 觸發條件 | 方法 | 建議修正 |
|---|---|---|---|---|---|---|
| PT-1 | 中 | `ptp` | 沒有 BMCA、忽略 Announce，多個 master 時被輪流拉動 | 網路上有多個 PTP master | R | 至少依 Announce 鎖定一個 master 的 clockIdentity |
| PT-2 | 低 | `ptp` | correctionField 只用低 24 bit，offset / delay 加上後超過約 ±8.4 ms 會回捲（負值本身處理正確） | correctionField 很大（多級透明時鐘、長距離） | R | 使用完整 48-bit 整數奈秒，或在超出範圍時捨棄該筆量測 |
| PT-3 | 低 | `ptp` | offset 只取 24 bit，> ±8.4 ms 回捲 | master 時間跳動 | R | 靠既有的重新 latch 機制；或擴寬並在超出範圍時直接設定時間 |
| PT-4 | 低 | `ptp` | P2P / gPTP 不支援 one-step Pdelay_Resp | 鄰居使用 one-step | R | 收到 one-step 時從 Pdelay_Resp 的 correctionField 取 turnaround |
| PT-5 | 低 | `ptp` | Delay 量測與 Sync 之間沒有配對，用最近一次 Sync 的值 | Sync 與 Delay_Req 交錯且延遲變動 | R | 記錄 Delay_Req 送出時對應的 Sync sequenceId |
| PT-6 | 低 | `ptp` | 秒只有 32 bit，2106 年回捲 | — | R | — |
| PT-7 | 低 | `streaming_cdc` | HIF 端的 PTP 時間固定晚 3–4 個 HIF 時脈（10G 板級 19.2–25.6 ns、S10 14.9–19.9 ns、PYNQ 9.3–12.4 ns），再加最多 1 個 PTP 時脈的取樣保持；沒有補償 | 需要數十 ns 以下精度的應用 | R | 在 HIF 端加上固定補償值（可由暫存器設定） |

### Bridge（本 repo 沒有板級啟用）

| ID | 等級 | 模組 | 問題 | 觸發條件 | 方法 | 建議修正 |
|---|---|---|---|---|---|---|
| BR-1 | 高（啟用時） | `bridge` | host RX 緩衝的 `o_axis_rx_tready` 沒有接，almost full 後 beat 被靜默丟棄；被截斷的封包永遠不算完整，這個 host 埠的 bridge 路徑停擺或之後的 frame 合併、路由錯開，直到 reset。`rx_parser` 不受影響 | 啟用 Bridge，64-bit 下單一封包 > 約 1.8 KB，或輸出暫停時累積 > 224 beat | R + M | 接上 `o_axis_rx_tready` 並讓 `rx_parser` 尊重它；或 host RX 緩衝深度 ≥ 最大 MTU + 餘裕、改成整包丟棄 |
| BR-2 | 中（啟用時） | `bridge` | 透明時鐘用 OR 而不是加法修正 correctionField（`axis_mask` 的 `OP = "OR"`：`tdata |= mask`）；原本的 correctionField 與修正值有任何相同位元為 1 時結果錯誤 | master 的 correctionField ≠ 0 | R | 加一個 48-bit 加法器；`axis_mask` 只有 OR / AND，沒有加法 |
| BR-3 | 低 | `bridge` | residence time 16 bit 拍數，> 419 µs 回捲；只保留 24 bit ns | 長時間排隊 | R | 擴寬計數器 |
| BR-4 | 低 | `bridge` | host 端 Sync 一律量到 SIF 0 | Sync 送往其他 SIF 埠 | R | 每埠各自量測 |
| BR-5 | 低 | `bridge` | 只支援 Layer 2 PTP；未知 unicast 與一般 multicast 丟棄；CAM 不老化 | IPv6、mDNS、裝置換 MAC | R | 依需求加入 flood 與老化 |
| BR-6 | 低 | `bridge` | host 來源固定優先於 SIF | host 流量持續 | R | round-robin |
| BR-7 | 中（啟用時） | `eth_pkt` / `bridge` | `o_del_req_val` 用 `out_idx == 4`（PAUSE）判斷，Bridge 是 index 5；Bridge 轉送的 Delay_Req 不會停止 residence time 量測；記錄來源的 `ptp_del_req_buffer` 只依 host 0 讀出（`ptp_port = 0`），轉往 host 1 的 Delay_Req 會讓它錯位 | 啟用 Bridge 且 SIF 端裝置送 Delay_Req | R + I | 比較改成 Bridge 的 index（`'d5`），最好用具名參數；`rd_ptp_fifo` 改看所有 host 的 `i_del_req_val` |
| BR-8 | 中（啟用時） | `cam` / `routing_table` | 未命中時輸出 `ram[0]`；CAM 填滿 64 筆後，未知目的位址都送往 entry 0 的埠 | SIF 端學到 64 個以上 MAC | R | `routing_table` 依 `cam_data_val` 決定，未命中時丟棄 |
| BR-9 | 低 | `routing_table` | SIF 學習請求與 host 查詢同一拍時，授權照給、寫入被壓掉，學習遺失 | SIF 與 host 流量同時存在 | R | 仲裁器的 `idle` 接 `!(|i_mac_req)`，或 `mac_valid` 只在 `cam_wr` 時清除 |

### 周邊

| ID | 等級 | 模組 | 問題 | 觸發條件 | 方法 | 建議修正 |
|---|---|---|---|---|---|---|
| PE-1 | 中 | `spi_ctrl_fsm` | 只讀不寫（`num_cmd = num_wr = 0`）的交易永遠不開始，`busy` 一直為 1，只能整體 reset | host `spi_transaction()` 傳空的命令與寫入 | R | 見 [F-8](#f-8spi-卡死) |
| PE-2 | 中 | `spi` | `turnaround_len ≥ 33` 時 TURNAROUND 永不結束 | 設定大的 dummy cycle（host 允許到 255） | R | 見 [F-8](#f-8spi-卡死) |
| PE-3 | 中 | `uart` | 接收端等完整 stop bit 才結束，只有最後一個 tick 剛好看到下降緣才接著收；對方稍快且連續送出時漏掉下一個 start bit，之後錯位 | 對方鮑率比 HSB 快約 `10⁶ / (10 × 8 × (baud_div + 1))` ppm 以上（115.7 kbaud 時 116 ppm）、frame 間沒有 idle | R + M | 見 [F-9](#f-9uart-stop-bit) |
| PE-4 | 低 | `uart` | 取樣點約在 bit 的 5/8；2 stop bit 不檢查第二個；假 start bit 仍佔用一整個 frame | 鮑率誤差大、雜訊 | R + M | 取樣點改在 `cnt == 3`；假 start 直接回 IDLE |
| PE-5 | 中 | `i2c` | host 的 `set_i2c_clock()` 不分板級固定寫 `clk_cnt = 0x19`，APB 50 / 100 MHz 的板級上 SCL 約 1 / 2 MHz | PYNQ、Terasic S10 板級 | R + X | host 依 enumeration 的 APB 頻率計算 `clk_cnt` |
| PE-6 | 低 | `i2c` | 10-bit 位址讀取在 repeated start 後走 `I2C_RS_10b_DEV_ADDR → I2C_RS_DEV_ADDR`，又寫出一次低 8 bit 位址；I2C 規格在 Sr 後只送第一個位址 byte（讀取位元為 1） | 使用 10-bit 位址的裝置 | R | `I2C_RS_DEV_ADDR` 在 10-bit 模式跳過 |
| PE-7 | 中 | `eeprom_info` | EEPROM 不存在時 MAC 變成 I2C 資料緩衝 RAM 的上電內容（多數 FPGA 為 0），不保留預設 `CA:FE:C0:FF:EE:00`；`eeprom_info` 不檢查 NACK | 板子沒有 EEPROM 或 EEPROM 沒回應 | R | 輪詢完成後檢查 `status[3]`（NACK），NACK 時保留預設值並設錯誤旗標 |
| PE-8 | 低 | `eeprom_info` | CRC 計算跳過 byte 255 又檢查是否為 0，正確燒錄的 EEPROM 約 99.6 % 判為錯誤；`eeprom_crc_err` 沒有接 | 每次開機 | R + X + N | 見 [F-1](#f-1eeprom-crc) |
| PE-9 | 低 | `i2s_clk_gen` | `CTRL2 = 8`、`CTRL2 ∉ 1–8`、`mclk_div ≤ 1` 時 BCLK 不動 | 軟體設定超出範圍 | R | 見 [F-10](#f-10i2s-除數) |
| PE-10 | 低 | `i2s_serdes` / `i2s_axis_buffer_rx` | PCM 格式等同 LJ；RX 的 L / R 沒有標記，RX 緩衝 almost full 時樣本不寫入（`i_rx_ready` 沒有使用），丟掉奇數個樣本後左右對調直到 reset | 使用 PCM / RX 溢位 | R | 實作 DSP 短 frame sync；RX 輸出加聲道位元（例如 `tuser`），或溢位時成對丟棄 |
| PE-11 | 低 | `ram_player` | `timer = 0` 時不循環；`window_size < W_KEEP` 時沒有 `tlast`；中途停止時收尾拍可能未被接受就撤回 | 測試設定 | R | 循環條件只看 `loop_dis`；`DONE` 時保持 `tvalid` 直到 `tready` |
| PE-12 | 低 | `imu_top` | `axis_buffer` 輸入不看 `tready`，下游反壓時遺失；每 frame 多 1 個樣本 | 使用 `imu_top`（目前沒有板級使用） | R | 接上 `tready`；比較改成 `samples_per_frame − 1` |
| PE-13 | 低 | `delayed_io` | 取消與立即設定不會停止計數器；計數中送出的新延遲操作在舊的到期時間執行 | 取消後馬上重新排程 | R | 計數器加 `cancel` 輸入，或新要求時重新載入計數 |
| PE-14 | 低 | `delayed_io` | CPNX100 用預設 `CLK_FREQ`，`CYCLES_PER_US` 進位成 20，延遲多 2.4 % | 需要精確延遲 | R | 板級傳入實際 APB 頻率，並用定點數換算 |
| PE-15 | 低 | `i2s_top`（host + RTL） | host 讀 I2S 狀態用 `I2S_APB + 0x24`–`0x30`，RTL（`W_OFST = 12`）的狀態區在 `0x800`；host 的讀取得到 `pslverr` / ECB 回應碼 0x03，`clock_locked()`、`tx_underrun()`、`rx_overrun()` 都無法正常運作 | CPNX100 使用 I2S | R + X | host 改用 `0x800`–`0x80C`；或 `i2s_top` 傳 `W_OFST = 8` 並把 host 位址改為 `0x80` 起 |
| PE-16 | 低 | `ctrl_bus_evt`（host + RTL） | `ctrl_evt_apb_timeout` 以 APB 時脈計數（`timer_cnt` 在 `i_aclk = i_apb_clk` 上加一），host 卻固定用 51.2 ns 換算（`APB_TIMEOUT_SCALE = 1 / 51.2e-9`、`0x3937` 註解「750us」），這只對 19.53 MHz 的 APB 成立。PYNQ（50 MHz）的實際逾時是預期的 0.41 倍，S10（100 MHz）是 0.20 倍；I2C 等事件序列可能在 host 認為還沒逾時前就被中止並觸發錯誤事件 | PYNQ、S10 使用事件序列（I2C 交易） | R + X | host 依板級的 APB 頻率換算；或 RTL 加一個固定 51.2 ns 的 tick |

### 註解與死碼（不影響功能）

| ID | 位置 | 內容 |
|---|---|---|
| NT-1 | `HOLOLINK_top` | `eth_pkt` 輸入埠的註解順序與實際不符（[overview §6](architecture/overview.md#6-eth_pkt-輸入埠分配)） |
| NT-2 | `regmap_pkg` | `ecb_addr_lsb` / `ecb_addr_msb` 註解寫反 |
| NT-3 | `rx_parser` | `inst_dec_stat_rst` 借用 `eth_pkt_ctrl` 常數；`lpbk_udp_port` 暫存器沒有作用 |
| NT-4 | `roce_ack` | 錯誤注入註解寫第 8 個，實際第 257 個（第一個封包只清除計數） |
| NT-5 | `packetizer` | `PACK_DELAY` 死碼；暫存器跨到 SIF 時脈而非 HIF |
| NT-6 | `dp_pkt` | `ROCE_WR_IMM` 死碼；檔頭的設定 RAM 註解過時；`dp_pkt_1722B` 暫存器沒有使用；`dp_pkt_len` reset 值只用低 8 bit |
| NT-7 | `dpll` | 增益註解與實際（暫存器）不符；`ptp_ctrl_pcp`、`i_enable` 沒有作用 |
| NT-8 | `i2c` | `status[2]` 名為 arbitration lost，實際是逾時 |
| NT-9 | `uart` | 埠註解寫 16x oversampling，參數是 8 |
| NT-10 | `eeprom_info` | 檔頭寫 CRC 多項式 0xB0，程式是 0x8C（N） |
| NT-11 | `tx_stream_buffer` | `HALF_SECOND` heartbeat 沒有使用 |
| NT-12 | `lib` | `axis_demux`、`comparator`、`debouncer`、`str_fwd_fifo` 沒有被引用；`dc_fifo` AUTO RAM 判斷條件前後不一致 |
| NT-13 | `i2s` | `I2S_CTRL_RST_VAL` 註解寫 TX/RX enabled、loopback，實際 reset 都是 0；CTRL6 中斷啟用、CTRL4[1] 時脈來源沒有作用；`o_locked` 固定 1；CPNX100 的 RX 埠註解寫「Not connected」但實際有連；`clk_gen` 的 posedge / negedge 命名相反 |
| NT-14 | `event` | `event_vec` bit 2、3 在 `HOLOLINK_top` 是 0，實際值在 `ctrl_bus_evt_int` 內取代 |

## 修正草稿

以下是建議的 RTL 改法，只是草稿：**沒有編譯、沒有模擬**。行號對應 commit `41cecaa`。

### F-1：EEPROM CRC

[eeprom_info.sv#L301–L322](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/sys_init/eeprom_info.sv#L301-L322)。Maxim CRC-8 是反射、初值 0、沒有 final XOR，把存放的 CRC byte 一起算進去，合法映像的餘數一定是 0（[數值驗證 1d](verification-calcs.md)）。所以只要刪掉跳過 byte 255 的條件：

```diff
   else if ((state == SEQ_BYTES) && (byte_cntr[1:0] == 2'b11)) begin
-    //Don't include last byte in CRC calc
-    if (!(byte_cntr[7:2]==6'b111111)) begin
-      eeprom_crc <= nextCRC(read_data[31:24], eeprom_crc);
-    end
+    // Include byte 255 (stored CRC): a valid image leaves a zero residue
+    eeprom_crc <= nextCRC(read_data[31:24], eeprom_crc);
   end
```

同時把檔頭註解改成 0x31 / 反射 0x8C。若要讓 CRC 錯誤有作用，還要在 `HOLOLINK_top` 把 `eeprom_crc_err` 接到狀態暫存器，並決定錯誤時是否改用預設 MAC。

### F-2：roce_ack IPv4 checksum

[roce_ack.sv#L524–L538](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv#L524-L538)。用 RFC 1624 的 one's complement 形式 `chk + old_len + ~new_len`，再折兩次（[數值驗證 3c](verification-calcs.md)）：

```diff
-logic [16:0]                          ipv4_calc_stage1;
+logic [17:0]                          ipv4_calc_stage1;
 logic [16:0]                          ipv4_calc_stage2;
 ...
-    ipv4_calc_stage1 <= {1'b0,ip_hdr_r.chksum[15:0]} + {1'b0,ip_hdr_r.length[15:0]} - {1'b0,ipv4_len[15:0]};
-    ipv4_calc_stage2 <= ipv4_calc_stage1[15:0] + ipv4_calc_stage1[16];
+    ipv4_calc_stage1 <= {2'b0,ip_hdr_r.chksum[15:0]} + {2'b0,ip_hdr_r.length[15:0]} + {2'b0,~ipv4_len[15:0]};
+    ipv4_calc_stage2 <= ipv4_calc_stage1[15:0] + ipv4_calc_stage1[17:16];
 ...
-assign ipv4_chksum = ipv4_calc_stage2[15:0];
+assign ipv4_chksum = ipv4_calc_stage2[15:0] + ipv4_calc_stage2[16];
```

最後一次折疊是組合邏輯；若時序吃緊可再加一級管線，`ipv4_chksum` 的使用點要配合延後一拍。

### F-3：packetizer `latency_cnt` 寬度

[packetizer_top.sv#L117](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/packetizer/packetizer_top.sv#L117)：

```diff
-logic [2:0]          latency_cnt;
+logic [3:0]          latency_cnt;   // must cover reg_latency[3:0]
```

合法範圍變成 0–15。若要保留 3 bit，至少在 host 端限制 `latency ≤ 8`。

### F-4：rx_parser VLAN PTP messageType

[rx_parser.sv#L536](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_parser.sv#L536)：依 `is_vlan` 位移 4 byte。

```diff
-      rx_msg_type_ptp_hdr    <= hdr_array[14][3:0];
+      rx_msg_type_ptp_hdr    <= is_vlan ? hdr_array[18][3:0] : hdr_array[14][3:0];
```

同一段的 `eth_type_ptp` 已經用 VLAN 位移後的 `eth_hdr_i.ethertype`（[L252](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_parser.sv#L252)），不需要改；`VLAN_DISABLE` 時 `is_vlan = 0`，這行改動也不影響。

### F-5：roce_ack 重複封包回 ACK

重複封包（`psn < psn_exp`）目前只丟包。依 InfiniBand 規格，responder 應對重複的 RC WRITE 回 ACK（PSN = 最後完成的 PSN），資料本身不再寫入。改法：在判斷重複的分支同樣送出 ACK，PSN 欄位填 `psn_exp − 1`，但不寫入資料 FIFO、不更新 `psn_exp`。需要確認 `rx_parser` 的資料路徑在重複時確實丟棄資料（錯誤 FIFO 每個封包都有一筆，可用來標記）。

### F-6：pause quanta 索引

[HOLOLINK_top.sv#L1747](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L1747)：`pause_gen` 是每個 host 埠一份，而 quanta 是每個 SIF TX 一份。正確的接法取決於 pause 要求來自哪個 SIF TX：

```diff
-          .i_pause_time           ( tx_pause_quanta[0]                    ),
+          .i_pause_time           ( tx_pause_quanta[pause_src_idx[i]]     ),  // SIF TX that raised host_pause_req[i]
```

`pause_src_idx` 需要在產生 `host_pause_req` 的地方一併記錄。如果一個 host 埠只對應一個 SIF TX，可以直接用固定的對應表。

### F-7：ECB 不完整的 pair

兩種改法擇一：

1. 和 RoCE-ECB 一樣用 UDP length 算 pair 數：`total_pairs = (udp_len − 8 − ECB_HDR_BYTES) >> 3`，到數後忽略剩下的 byte（包括 MAC 補齊的 0）。
2. `DCD_DATA` 在一組 pair 收滿 8 byte 前看到 `tlast` 時，不發 APB 存取，直接結束。

第 1 種同時解決「補齊 byte 被當成 pair」與「pair 中途結束」兩個問題。

### F-8：SPI 卡死

[spi_ctrl_fsm.sv#L256–L270](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/spi/spi_ctrl_fsm.sv#L256-L270)：讓 `SPI_READ` 也能啟動引擎，並把沒有任何 byte 的交易直接結束。

```diff
-assign start      = ((state == SPI_CMD) || (state == SPI_WRITE));
+assign start      = ((state == SPI_CMD) || (state == SPI_WRITE) || (state == SPI_READ));
 ...
-          state_nxt = (num_cmd_bytes == 3'h0) ?
-                      (num_wr_bytes == '0)    ? SPI_READ  :
+          state_nxt = (num_cmd_bytes == 3'h0) ?
+                      (num_wr_bytes == '0)    ? ((num_rd_bytes == '0) ? SPI_DONE : SPI_READ) :
                                                 SPI_WRITE :
                                                  SPI_CMD  ;
```

`spi.sv` 的 `start` 註解要求「Must have write = 1 at the same time」，但 IDLE 分支其實已經處理 `write = 0`（`SDIO_en = 0`），所以讀取起頭應可運作，需模擬確認。`busy` 的設定條件也要涵蓋直接進 `SPI_DONE` 的情況。

[spi.sv#L295](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/spi/spi.sv#L295)：計數器加寬到能涵蓋 8-bit 的 `turnaround_len`。

```diff
-reg [5:0]                    rSentCnt;
+reg [8:0]                    rSentCnt;   // turnaround needs up to (255-1)*2 = 508
```

`rSentCntMax` 與其他比較也要跟著改成 9 bit。另一個做法是 TURNAROUND 用獨立的計數器。

### F-9：UART stop bit

[uart.sv#L609–L636](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/uart/uart.sv#L609-L636)：在 stop bit 的取樣點（中間）就完成 frame 並回到 IDLE，讓下一個下降緣不論何時出現都能被 IDLE 接住；設定 2 stop bit 時在第二個 stop bit 中間再檢查一次。對應地，`rx_start_lock` 的第二個條件可以拿掉。

### F-10：I2S 除數

[i2s_clk_gen.sv#L82–L125](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/ref_design/i2s/i2s_clk_gen.sv#L82-L125)：

```diff
-  logic [7:0]              bclk_div;
+  logic [8:0]              bclk_div;    // holds 256 for CTRL2 = 8
 ...
-  logic [7:0]              bclk_counter;
+  logic [8:0]              bclk_counter;
```

並把 `mclk_div < 2` 鉗制成 2，或在 APB 寫入時拒絕。
