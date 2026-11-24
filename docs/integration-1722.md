# 1722 listener 整合：HSB 端會碰到的限制

本文件**不屬於**中立的 IP 分析，是給一個特定用途看的：把 HSB 的 Ethernet 接收路徑（`rx_parser` → `sensor_tx_pkt_proc` → `tx_stream_buffer` → SIF TX）改成 IEEE 1722（AVTP）listener，把收到的串流送到 MIPI 輸出。內容只引用 [問題清單](issues.md) 與各模組文件已有的結論，標出哪些會碰到、為什麼、要怎麼處理。原始碼基準同 README（`41cecaa`）。

> 這份文件假設的流量形態寫在 [§1](#1-假設)。實際的 1722 格式（subtype、是否帶 VLAN、stream 數、速率、封包長度）不同時，部分結論要重看；需要確認的項目列在 [§6](#6-需要確認的項目)。

## 1. 假設

| 項目 | 假設 |
|---|---|
| 收到的封包 | L2 AVTP（EtherType `0x22F0`），可能帶 802.1Q（TSN 常用 PCP 分級） |
| 目的 MAC | AVTP stream 常用 multicast（例如 `91:E0:F0:00:xx:xx`），也可能是本機 unicast |
| 板級 | 10G 板級（CPNX100 / NV MIPI 參考，64 bit × 156.25 MHz） |
| 輸出 | SIF TX → MIPI TX；MIPI 端需要知道 line / frame 邊界 |
| 流量控制 | talker 不理會 802.3x PAUSE（TSN 串流靠 credit-based shaper），中間的 switch 也可能不轉送 PAUSE |

## 2. 現在的路徑收不到 1722

`rx_parser` 只把 RoCEv2（UDP 4791）的 UC SEND、以及 `ENABLE_ROCE_ACK` 時的 RC SEND / WRITE 送往 Sensor TX（`is_stx`，[rx_parser.sv#L560](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_parser.sv#L560)）。AVTP 封包的結果（[rx_parser §不屬於 HSB 的流量](modules/rx_parser.md#不屬於-hsb-的流量)）：

| 目的 MAC | 分類 | 結果 |
|---|---|---|
| 本機 unicast | 所有旗標為 0 | 丟棄 |
| multicast | `is_btx` | 非 Bridge 模式下 `brx_axis_tready` 固定為 1，丟棄 |

所以至少要改兩個地方：

1. **`rx_parser` 加一個分類**，例如 `is_avtp = (ethertype == 0x22F0) && (dest MAC 符合本機或設定的 stream multicast)`，併入 `is_stx` 或另開一條輸出。注意：
   - 欄位要用 `is_vlan` 位移後的位置讀。`eth_hdr_i.ethertype` 已經處理了（[L252](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_parser.sv#L252)），但直接用 `hdr_array[n]` 的寫法會重蹈 [DP-3](issues.md#data-plane-與封包處理)（PTP messageType 沒有位移）的覆轍。
   - `HDR_BYTES = 58` 足夠：Ethernet + VLAN + AVTP stream header 是 14 + 4 + 24 = 42 byte。`stream_id` 在 AVTP header 的 byte 4–11（VLAN 時是整個 frame 的 byte 22–29），可以放進 `hdr_din` 的 `bth_dest_qp` 欄位位置，一路帶到 `sensor_tx_pkt_proc` 選感測器。
   - multicast 目的 MAC 在現在的邏輯會先成為 `is_btx`；新的分類要排除在 `is_btx` 之外，否則 Bridge 模式下會被轉送，VLAN 也不會被移除（移除條件是 `buf_is_vlan && !buf_is_btx`，[rx_parser §7](modules/rx_parser.md#7-vlan-移除)）。
2. **`sensor_tx_pkt_proc` 依格式去 header。** 現在固定去掉 54 byte header 與 4 byte ICRC，並用 `QP[8:1]` 選感測器（[sensor_tx_pkt_proc.sv#L44–L50](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/sensor_tx/sensor_tx_pkt_proc.sv#L44-L50)）。AVTP 沒有 ICRC，header 長度依 subtype 而定（VLAN 已被 `rx_parser` 移除，所以是 14 + AVTP header）。這和 [TX-6](issues.md#host--感測器sif-tx與-roce-ack)（RC WRITE 的 RETH 沒去掉）是同一類問題：去掉的長度應該依封包類型決定，而不是常數。

## 3. 會直接碰到的問題

| ID | 問題 | 對 1722 listener 的影響 | 建議 |
|---|---|---|---|
| [TX-7](issues.md#host--感測器sif-tx與-roce-ack) | `tx_stream_buffer` 滿時丟 beat，`tlast` 遺失時兩個封包接成一個 | **最主要的風險。** talker 不會因 PAUSE 減速，SIF 端（MIPI）消耗稍慢或暫停，緩衝就溢位；被截斷或合併的封包會讓 MIPI 端的 line 錯位。好消息是這裡 `WAIT2SEND = 0`，不會像 `rx_parser` 一樣永久錯位，影響只到溢位當下的封包 | 改成溢位時丟整包並記數；`FIFO_DEPTH` 依「最長 MIPI 停頓 × 串流速率 + 網路抖動」決定；把 `saw_overflow` 接到 host 可讀的位置並修正 TX-9 |
| [TX-8](issues.md#host--感測器sif-tx與-roce-ack)、PAUSE | 只有 sensor 0 的 quanta 有效 | PAUSE 對 1722 talker 通常無效，這個問題影響不大；但 PAUSE 若打開，會擋住同一個 host 埠的**所有**流量（包括 ECB） | 1722 用途建議 `pause_ena = 0`，靠緩衝大小吸收 |
| `tx_stream_buffer` 預填閘門 | 輸出要等 `buffer_count` 第一次到 AFULL 才打開（`afull_seen`），之後一直打開；`tx_data_output_ena = 0` 期間送來的資料照樣寫入（[tx_stream_buffer 注意事項 2](modules/tx_stream_buffer.md#注意事項)） | MIPI 輸出的起點取決於預填量，而不是 frame 邊界；串流先到、輸出後開，啟用前的資料會先填滿再溢位。underflow 後不會重新預填 | 在 frame 邊界（AVTP header 的 frame / line 旗標）重新對齊；啟用輸出前不接收（或丟到 frame 開頭） |
| [sensor_tx 注意事項 4](modules/sensor_tx_pkt_proc.md#注意事項) | 輸出只保留 Ethernet 封包邊界（`tlast`） | MIPI 需要的 frame start / line start / 資料型態都必須從 AVTP header 或 payload 取出 | 在去 header 時把 AVTP 的 frame / line 資訊轉成 `tuser` 側帶；`tx_stream_buffer` 的 `W_USER` 目前只有 1 bit，要加寬 |
| [DP-1、DP-2](issues.md#data-plane-與封包處理) | `rx_parser` 輸入 FIFO 溢位後資料與 metadata 永久錯開 | 10G 板級的讀出在任何封包長度下都跟得上線速（[performance §7](performance.md#7-rx_parser-讀出能力逐拍模型)），只有 Bridge 背壓會觸發。但一旦觸發，之後所有封包（包括 1722 串流與 ECB）都會被誤分類，直到 reset | 不啟用 Bridge；若要移植到 100G 板級（S10），先看 [DP-15](issues.md#data-plane-與封包處理) |
| [DP-4](issues.md#data-plane-與封包處理) | IP 類分類不檢查 EtherType | AVTP（非 IP）封包在 IP / UDP 欄位的位置剛好出現相符的值時會被誤判成 ECB 或 STX；機率極低 | 新的 `is_avtp` 與既有的 IP 類條件互斥（IP 類加上 `ethertype == 0x0800`） |

## 4. 時間同步（presentation time）

1722 listener 要依 `avtp_timestamp`（presentation time）決定何時輸出，需要與 talker 同步的 gPTP（802.1AS）時間。HSB 的 PTP 支援 gPTP profile，但有幾個限制會直接影響 listener：

| ID | 限制 | 影響 |
|---|---|---|
| [PT-1](issues.md#ptp-與時間) | 沒有 BMCA，忽略 Announce | 802.1AS 網路有多個 time-aware system 時，HSB 不會選出 grandmaster，可能被輪流拉動。點對點或單一 GM 的網路沒問題 |
| [PT-4](issues.md#ptp-與時間) | 不支援 one-step Pdelay_Resp | 鄰居（TSN switch）用 one-step 時，link delay 量不到 |
| [PT-7](issues.md#ptp-與時間) | PTP 時間跨到 HIF 端固定晚約 20–40 ns，沒有補償 | 在 HIF 時脈域比較 presentation time 時多出這段偏差；對影像（µs 等級）通常可忽略 |
| [PT-2、PT-3](issues.md#ptp-與時間) | correctionField / offset 只用 24 bit（±8.4 ms 回捲） | 多級 TSN switch 時 correctionField 累加，一般仍在範圍內 |
| [DP-3](issues.md#data-plane-與封包處理) | 帶 VLAN 的 PTP messageType 讀錯 | gPTP 規定不帶 VLAN，通常不影響 |

`avtp_timestamp` 只有 32 bit（ns，約 4.29 s 回捲），比對時要用 gPTP 時間的低 32 bit。presentation time 的比對與等待緩衝必須新增；HSB 現在的 Sensor TX 路徑沒有依時間放行的機制（`tx_stream_buffer` 只看水位）。

## 5. 反方向：HSB 已經是 1722 talker

HSB 的 Data Plane（感測器 → host）已經支援 IEEE 1722B CoE（Camera over Ethernet），46 byte header（[dp_pkt_top §8](modules/dp_pkt_top.md#8-1722b-coe-header)）。若要同時做 talker 與 listener：

- CoE 的 timestamp 是**送出時間**，不是 presentation time（[dp_pkt_top 注意事項](modules/dp_pkt_top.md#注意事項)）。
- `dp_pkt_1722B` 暫存器沒有被使用（NT-6）。
- 兩個方向共用同一個 host 埠的 `eth_pkt` 仲裁與 `rx_parser`。listener 若啟用 PAUSE，連結上送往 HSB 的所有流量（包括 ECB）都會被暫停（見 §3）。

## 6. 需要確認的項目

| 項目 | 為什麼重要 |
|---|---|
| AVTP subtype 與 header 長度 | 決定 `sensor_tx_pkt_proc` 要去掉多少 byte、frame / line 資訊放在哪裡 |
| 是否帶 VLAN | 帶 VLAN 時要確認新分類用的是位移後的欄位；`rx_parser` 會移除 tag |
| 目的 MAC（unicast / multicast） | multicast 要從 `is_btx` 排除，並決定是否用暫存器設定可接受的 stream MAC |
| stream 數與 `stream_id` → SIF TX 的對應 | 取代現在的 `QP[8:1]` |
| 串流速率、封包長度、MIPI 端最長停頓 | 決定 `tx_stream_buffer` 的 `FIFO_DEPTH`；10G 板級上 `rx_parser` 本身不是瓶頸 |
| 是否需要依 presentation time 輸出 | 需要時要新增時間比對與等待緩衝（§4） |
| 是否會用到 Bridge 模式或 100G 板級 | 會觸發 DP-1 / DP-15 / BR-1 |

## 7. 建議的驗證順序

1. 先在 `nv_hsb_ip_simple_tb` 跑 [S9 `dt_stx_overflow_boundary`](test-plan.md#測試清單)（TX-7）與 [S11 `dt_rx_parser_burst`](test-plan.md#測試清單)（DP-1），確認兩個最相關的問題在模擬中成立。
2. 加入 `is_avtp` 分類後，把 S9 改成送 AVTP 封包，確認去 header 長度與 `stream_id` 選擇。
3. 在 SIF TX 端接一個 MIPI 輸出的行為模型，依 AVTP 的 frame / line 旗標檢查輸出的 frame 結構，並在 SIF 端插入停頓，量測不溢位所需的 `FIFO_DEPTH`。
