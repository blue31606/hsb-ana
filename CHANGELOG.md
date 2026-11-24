# 版本紀錄

## 版本

| 版本 | Commit | 說明 |
|---|---|---|
| v1 | `2a6cf26` | 依資料路徑分章的第一版 |
| v2 | `0158d91` | 每個模組一份文件；加入時序圖、permalink、自動產生的暫存器表、驗證狀態 |
| v3 | `932292c` | 改為完整、中立的全 IP 分析：新增 PTP、packetizer、事件、APB、開機、周邊、Bridge、RoCE、共用元件、參考設計、板級、驗證環境等文件；`dp_pkt_top`、`rx_ls_parser` 重寫為主要邏輯深度；移除特定應用的設計提案 |
| v4 | `ddb130a` | `packetizer`、`dp_pkt_top`、PTP 補到逐行並加時序圖；新增端到端流程、效能分析、完整暫存器索引；周邊狀態機與時脈公式；板級感測器接收路徑；testbench 流程與檢查項目 |
| v5 | `fc2b904` | 重畫頂層方塊圖並新增跨時脈地圖、控制平面 / Data Plane 全貌；`rx_ls_parser`、`roce_icrc`、`roce_ack`、Bridge、APB、開機與 reset 補到逐行；CDC 元件逐行並逐一檢查使用處 |
| v6 | `1981132` | 新增問題清單（分級、觸發條件、修正草稿）、數值驗證腳本、定向測試計畫與 SV 草稿；SPI / UART 位元引擎、`ram_player`、I2S、IMU 補到逐行或主要邏輯；獨立稽核後修正 20 多處錯誤（見下方[結論更正](#結論更正)），並新增 Bridge 的 `del_req_val` 與 CAM 未命中兩個 RTL 問題；之後補上 `lfsr_hc` 全部寬度的數值驗證、追完稽核留下的 2 項、`delayed_io` 逐行 |
| v7 | `37a2b9c` | 推斷項目重新追 RTL：DP-1、DP-2、BR-1、DP-13、TX-7、PE-7 全部升為 R 或 R + M，BR-1 與 `rx_parser` 讀出空檔更正；新增逐拍模型（方法 M）與 DP-15（Terasic S10 在 100G 下連續短封包溢位）；新增測試草稿靜態檢查並修正 S6 的巨集名稱；新增 S8–S12 定向測試（TX-6、TX-7、TX-8、DP-1 / DP-2、PE-7） |
| v7.1 | `804ebda` | 剩餘推斷項目追完 RTL（DP-6、DP-10、CP-1、CP-5、TX-6、BR-2、PE-5、PE-6 等升為 R 或 R + X）；新增 `dp_pkt_top`、UART、`roce_ack` 模型，Data Plane 封包間隔改由模型計算並更正「兩埠無法同時達到線速」，新增 DP-16；RC 相關項目標為「啟用時」；`rx_parser` 模型改為精確並產生時序圖；新增 S13（DP-8） |
| v7.1.1 | `3cc940b` | 以讀碼與文字解析補強：DP-12、CP-6、PT-7、PE-10 升為 R / R + X / R + M；新增原始碼連結檢查與 host 位址常數比對；暫存器索引補上 UART 遺漏的 3 個暫存器與 `delayed_io`、`i2s_top` 兩個區塊；找到 host 讀 I2S 狀態的位址與 RTL 不一致（PE-15） |
| v7.1.2 | `e1a8ac5` | 再以文字解析補強：新增埠空接掃描（找到 Bridge `ptp_del_req_buffer` 只依 host 0 讀出，併入 BR-7）、文件涵蓋率與行數檢查、板級設定表自動產生（補 9 列）、host 寫入值與 RTL 位元比對、檔案內跨時脈粗篩；找到事件序列逾時的單位只對 19.53 MHz APB 成立（PE-16）；更正 `axis_pkg` 描述 |
| v7.2 | 目前版本 | 精簡：VERIFICATION 不再重複問題清單；移除內文的版本註記（歷史只留在本檔）；README 的工具說明移到 [tools/README](tools/README.md)，新增 `tools/check_all.py` 一次跑完所有檢查；`check_host_bits.py` 併入 `check_host_regs.py --bits`；三份人工確認清單合為 `tools/reviewed.txt`；`regmap.md` 併入 [完整暫存器索引](docs/registers/all-registers.md)（名稱連到原始碼、註解位址不一致標 ⚠️），`gen_regmap.py` 併入 `gen_allregs.py` |

## 結論更正

各版找到並更正的錯誤結論。

| 項目 | 舊 | 新 |
|---|---|---|
| `dp_pkt_top` 設定 RAM | v1 誤把 RTL 的比對值當成 word 位置 | v3 以 host 軟體 offset 為準，並列出 RTL 的讀取位址重映射表與 1 拍延遲 |
| `inst_dec` index 6 | v1 寫成「未使用」 | 名稱為 `static_hif_qp`，RTL 與軟體都沒有引用 |
| PTP 秒寬度 | v3 寫 48 bit | v4：內部 32 bit，輸出補 0 到 48 bit |
| E2E Delay_Resp 配對 | v3 寫「沒有 sequenceId 檢查」 | v4：Delay_Resp 有 sequenceId 與 requestingPortIdentity 檢查；沒有配對的是 Delay 量測與 Sync |
| `dp_pkt_ts` | v3 寫「所有 VP 讀過才彈出」 | v4：FIFO 項目分配到每個 VP 的 4 筆環狀 RAM 後就彈出；讀指標在 metadata 後前進 |
| metadata `flags[1]` | v3 寫「frame 結尾沒有對齊封包邊界」 | v4：buffer 寫滿但還沒看到 VP 的 `tlast`（`bpw_only`） |
| `bootp` 的 `ciaddr` | v3 列為「名稱與內容不符」 | v5：它是 BOOTP request 的 ciaddr 欄位（目前 IP），從 reply 的 `yiaddr` 更新，命名正確 |
| EEPROM 每次讀取長度 | v3 寫 28 byte（照抄原始碼註解） | v5：程式實際設定 32 byte |
| ECB `ACK_REQUEST` | v3 寫「host 軟體定義」 | v5：RTL 依此決定寫入命令是否回應 |
| 頂層方塊圖 | v2–v4 只部分標示實例化次數 | v5：每個模組都標示份數，並列出共用資源對效能的影響 |
| `hsb_ctrl_1` | v2 未說明極性 | `o_sw_sen_rst = ~hsb_ctrl_1`，實際極性由板級決定 |
| `dp_pkt_top` §5 單封包 + `md_disable` | v5 寫 `fsm_cnt_max = 7` | v6：18（前一輪必為 metadata，`is_new = 1`） |
| packetizer `duplicate` | v5 寫「全 1」 | v6：`'b1` = `{select 0, commit 1}`，每個 VP 收到 VP 0 的資料 |
| Terasic S10 `VP_SIZE` | v5 寫 256 | v6：預設 128（256 只在 `JESD_HIGH_PERF`、1024-bit） |
| PTP correctionField | v5 寫「無號、負值算錯」 | v6：mod 2²⁴ 運算，負值正確，只有超過 ±8.4 ms 回捲 |
| ECB `total_pairs` | v5 寫成 N | v6：等於 N − 1，與完成數比較；只用於 RoCE-ECB |
| BOOTP / EEPROM IP 優先順序 | v5 寫「BOOTP > EEPROM」 | v6：最後發生的事件勝出，同拍才是 BOOTP 優先 |
| `data_gen` 速率 | v5 寫 `/ 2^17` | v6：`/ 2^16` |
| `tx_stream_buffer` 容量（performance） | v5 寫 16 KB | v6：4096 × 64 bit = 32 KB |
| 事件序列器 opcode `11` | v5 寫 NOP | v6：不是空操作，會對 addr 做 POLL |
| Bridge CAM 未命中 | v5 寫「丟棄」 | v6：CAM 填滿後轉送到 entry 0 的埠 |
| `eth_pkt` skid 設定 | v5 照抄註解 | v6：依 index 是 DP / PTP / LS |
| `ram_player` 的 `i_ptp` | v3 推測「在指定 PTP 時間播放」 | v6：把送出時間寫進資料 |
| `rx_parser` 封包間空檔 | v6 寫「至少 2 拍」 | v7：背靠背時 1 拍，n 拍封包讀出需 n + 1 拍（M） |
| `rx_parser` 溢位後果 | v6 寫「封包邊界可能錯位」（推斷） | v7：`in_pkt_cnt` 計入被丟的 `tlast`，之後每個封包都配到前一包的 metadata，直到 reset |
| Bridge host RX 緩衝 | v6 寫「almost full 時對 `rx_parser` 反壓，經 `rx_parser` 擋住同埠所有流量」 | v7：`o_axis_rx_tready` 沒接，沒有反壓；beat 被靜默丟棄，該埠 bridge 路徑停擺，`rx_parser` 不受影響 |
| 測試草稿 S6 的巨集 | v6 寫 `+define+ENABLE_ROCE_ACK` | v7：`SIF_TX_ROCE_RC_ENABLE`（`ENABLE_ROCE_ACK` 是 `rx_parser` 的參數） |
| `rx_parser` 封包收完到輸出 | v6 寫約 7 拍 | v7.1：8 拍（M） |
| Data Plane 封包間隔 | v6 估約 3 拍 + `eth_pkt` 1 拍；「兩埠無法同時達到線速」 | v7.1：4 + d 拍（d = 0–3）；兩個 host 各一個 VP 時可同時達到單一 host 的速率（M） |
| BR-2 修正建議 | v6 寫「用 `axis_mask` 的 `OP = "ADD"`」 | v7.1：`axis_mask` 只有 OR / AND，需要另加加法器 |
| UART U2 測試預期 | v6 寫「`ERR_PPM` > 0 失敗」 | v7.1：約 116 ppm 以上才失敗（M） |
| `axis_pkg` | v3 寫「型別定義」 | v7.1.2：byte 反轉與 one-hot 轉換函式（`tools/check_coverage.py` 找到） |
