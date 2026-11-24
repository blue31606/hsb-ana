# 定向測試計畫

[issues](issues.md) 中的問題都只讀過 RTL、沒有跑過模擬。本計畫為其中能用模擬確認的項目設計定向測試，並附 SystemVerilog 草稿：

| 檔案 | 內容 |
|---|---|
| [`tests/unit/tb_spi_turnaround.sv`](../tests/unit/tb_spi_turnaround.sv) | 單獨測 `spi.sv` |
| [`tests/unit/tb_uart_rx_rate.sv`](../tests/unit/tb_uart_rx_rate.sv) | 單獨測 `uart.sv` 的接收端 |
| [`tests/unit/tb_i2s_clk_gen.sv`](../tests/unit/tb_i2s_clk_gen.sv) | 單獨測 `i2s_clk_gen.sv` |
| [`tests/system/hsb_directed_tests.svh`](../tests/system/hsb_directed_tests.svh) | 放進 `nv_hsb_ip_simple_tb` 的 task |

**草稿沒有編譯過。** 分析環境沒有任何 HDL 工具（VCS、Xcelium、Questa、Verilator、Icarus、slang 都沒有）。v7 起階層名稱、testbench 名稱、task 參數個數與單元測試的埠已由 [`tools/check_tests.py`](#靜態檢查v7) 對照原始碼確認，但語法、寬度與時序仍可能需要修改。每個測試的判斷條件寫成「依規格應有的行為」：在 commit `41cecaa` 上，標「預期失敗」的測試應該失敗，失敗就是確認了問題。

## 測試清單

| 測試 | 對應問題 | 層級 | 激勵 | 判斷 | 預期（`41cecaa`） |
|---|---|---|---|---|---|
| U1 `tb_spi_turnaround` | PE-2 | 單元 | 1 個命令 byte + turnaround `LEN` = 1、2、8、31、32、33、40、255 | `busy` 在合理時間內清除，turnaround 期間 SCK 邊緣數 = 2 × `LEN` | `LEN` ≥ 33 失敗 |
| U2 `tb_uart_rx_rate` | PE-3 | 單元 | 行為模型以 `+ERR_PPM` 偏差連續送 64 個 8N1 frame，frame 之間沒有 idle | 64 個 byte 全部正確收到 | `ERR_PPM` ≥ 116 失敗、≤ 100 通過（v7.1 由 [UART 模型](../tools/model/uart_rx_model.py) 算出：門檻約為每個 frame 快 1 個時脈） |
| U3 `tb_i2s_clk_gen` | PE-9 | 單元 | `CTRL2` = 0–9、`mclk_div` = 0、1、2、3、4、8 | BCLK 有翻轉、`bclk_en` 有脈衝、每半個 LRCLK 剛好 16 個 BCLK | `CTRL2` = 0、8、9 與 `mclk_div` = 0、1 失敗 |
| S1 `dt_ecb_single_pair_block` | CP-1 | 系統 | 先寫 `glb_scratch` 標記值，再送只帶 1 組（寫 `ptp_scratch`）的 `WR_BLOCK`，frame 補到 60 byte | `ptp_scratch` 被寫入，`glb_scratch` 不變 | `glb_scratch` 被覆寫，失敗 |
| S2 `dt_spi_read_only` | PE-1 | 系統 | `num_wr = 0`、`num_cmd = 0`、`num_rd = 4` 後 start | `status[4]` done、`status[0]` 不 busy | busy 一直為 1，失敗 |
| S3 `dt_spi_long_turnaround` | PE-2 | 系統 | 1 個命令 byte、turnaround 32 / 33 / 40、讀 1 byte | 交易完成 | 33、40 失敗 |
| S4 `dt_packetizer_latency` | DP-5 | 系統 | passthrough 設定，`pack_ctrl[27:24]` = 8 與 9，送一個 frame | packetizer 不停在 `PACK_WAIT`，frame 完整 | 8 通過、9 失敗 |
| S5 `dt_vlan_ptp_type` | DP-3 | 系統 | 不帶與帶 VLAN（TCI `0x6005`）的 Follow_Up | `is_ptp_sync_msg` 不產生脈衝 | 帶 VLAN 時被當成 Sync，失敗 |
| S6 `dt_roce_dup_ack` | TX-1 | 系統（`SIF_TX_ROCE_RC_ENABLE`、`HOST2SEN`） | 同一 PSN 的 RC SEND 送兩次 | 收到 2 個 ACK | 只有 1 個，失敗 |
| S7 `dt_eeprom_crc` | PE-8 | 系統 | EEPROM 模型的 byte 255 寫入 byte 0–254 的 Maxim CRC | `eeprom_crc_err = 0` | 為 1，失敗 |
| S8 `dt_rc_write_reth`（v7） | TX-6 | 系統（`SIF_TX_ROCE_RC_ENABLE`） | RC RDMA WRITE ONLY（`0x0A`），RETH 填 `E0`–`E7`、`DEADBEEF`、長度，資料 1024 byte `00 01 02 …` | 感測器收到剛好 1024 byte，開頭是 `00 01` | 多出 16 byte RETH，開頭是 `E0`，失敗 |
| S9 `dt_stx_overflow_boundary`（v7） | TX-7 | 系統（`SENSOR_TX_IF_INST`） | 關掉 PAUSE、感測器 `tready = 0`，送約 1.5 倍緩衝量的 1000-byte 封包（每包填自己的編號），放開後再送 2 包 | 每個輸出封包都剛好是一個輸入封包（1000 byte、內容一致）；溢位本身允許 | 有被截斷或合併的封包，失敗 |
| S10 `dt_pause_quanta`（v7） | TX-8 | 系統（`SENSOR_TX_IF_INST ≥ 2`） | sensor 0 quanta `0x1111`、不啟用 PAUSE；sensor 1 quanta `0x2222`、AFULL = 1、輸出停住，送一包給 sensor 1 | PAUSE 請求上升時 `pause_gen.i_pause_time = 0x2222` | `0x1111`，失敗 |
| S11 `dt_rx_parser_burst`（v7） | DP-1、DP-2 | 系統 | 400 個 60-byte frame 背靠背（中間沒有空拍）送往其他 MAC；之後讀 3 次 `glb_scratch` | 流量停止後 `in_pkt_cnt == out_pkt_cnt`，3 次 ECB 讀取都正確 | 計數不相等、ECB 讀取逾時或讀錯，失敗；之後到 reset 前都錯 |
| S12 `dt_eeprom_absent`（v7） | PE-7 | 系統（`ENUM_EEPROM`，獨立一次模擬） | 時間 0 `force` EEPROM 模型的 SDA 不回 ACK，不跑 `hololink_init()` | `eeprom_info` 完成後 `mac_addr = CA:FE:C0:FF:EE:00` | `X`（硬體上多半是 0），失敗 |
| S13 `dt_vp_unserved_stall`（v7.1） | DP-8 | 系統（`SENSOR_RX_IF_INST`，sensor 0 至少 2 個 VP） | pass-through pattern 同時寫進 VP 0 與 VP 1 的欄位，host 0 的 `vip_mask` 只留 VP 0，送 `nframes` 個 frame | VP 0 送出 `nframes` 個 frame 結尾 | VP 1 的 FIFO 快滿後共用的 `pack_tready` 停住，VP 0 也停，失敗 |

## 放進 `nv_hsb_ip_simple_tb`

`hsb_directed_tests.svh` 的 task 使用 testbench 既有的 `ecb_write` / `ecb_read`、`build_ethernet_frame`、`send_eth_packet`、`build_host2sen_send_frame`、`send_sensor_frame`、`program_packetizer_passthrough`，以及 DUT 階層名稱 `u_dut`、`i_eeprom_model`。接法：

1. 在 `nv_hsb_ip_simple_tb.sv` 的 `tb_lib` include 之後加 `` `include "hsb_directed_tests.svh" ``。
2. S7 需要在 reset 釋放前修改 EEPROM 模型：在一個 `initial` 裡呼叫 `dt_eeprom_patch_crc()`。
3. 在主流程 `hololink_init()` 之後依 `TEST_MODE` 呼叫各個 task，例如新增 `TEST_MODE=DIRECTED`：

```systemverilog
bit p;
dt_ecb_single_pair_block(p);
dt_spi_read_only(p);            // leaves SPI busy on the current RTL; run last or reset after
dt_spi_long_turnaround(32, p);
dt_spi_long_turnaround(33, p);
dt_vlan_ptp_type(p);
dt_eeprom_crc(p);
dt_packetizer_latency(0, 8, p);
dt_packetizer_latency(0, 9, p); // hangs sensor 0's packetizer on the current RTL
```

v7 的測試接在後面：

```systemverilog
`ifdef SENSOR_TX_IF_INST
dt_rc_write_reth(0, p);         // before S6 on the same sensor: uses PSN 0
dt_stx_overflow_boundary(0, p);
dt_pause_quanta(p);
`endif
dt_rx_parser_burst(400, p);     // leaves rx_parser inconsistent on the current RTL; run last
`ifdef SENSOR_RX_IF_INST
dt_vp_unserved_stall(8, p);     // v7.1; leaves sensor 0 stalled on the current RTL
`endif
```

S12 要獨立一次模擬：在 reset 釋放前的 `initial` 呼叫 `dt_eeprom_absent_setup()`，主流程不跑 `hololink_init()`，直接呼叫 `dt_eeprom_absent_check(p)`。

各測試需要在 `HOLOLINK_def.svh` 定義的巨集：

| 測試 | 巨集 |
|---|---|
| S4 | `SENSOR_RX_IF_INST` |
| S6 | `SIF_TX_ROCE_RC_ENABLE`、`SENSOR_TX_IF_INST`，`TEST_MODE=HOST2SEN`。**v6 寫的 `+define+ENABLE_ROCE_ACK` 是錯的**：`ENABLE_ROCE_ACK` 是 `rx_parser` 的參數，由 `SIF_TX_ROCE_RC_ENABLE` 打開 |
| S7、S12 | `ENUM_EEPROM` |
| S8 | `SIF_TX_ROCE_RC_ENABLE`、`SENSOR_TX_IF_INST` |
| S9 | `SENSOR_TX_IF_INST` |
| S10 | `SENSOR_TX_IF_INST`，至少 2 個 SIF TX（不足時自動略過） |
| S13 | `SENSOR_RX_IF_INST`；sensor 0 至少 2 個 VP 且 `VP_SIZE < DIN`（不足時自動略過）。`nframes` × frame 大小要超過 VP FIFO（約兩個封包的 payload） |

## 靜態檢查（v7）

[`tools/check_tests.py`](../tools/check_tests.py) 不需要 HDL 工具，檢查的是編譯器 elaboration 最先會抓到的錯誤：

- 單元測試：DUT 實例的每個具名埠與參數都存在於模組宣告、所有輸入埠都有接、`dut.<signal>` 探針都有宣告。
- 系統測試：用到的 testbench task、常數、變數都有宣告（或由 `HOLOLINK_pkg` import），task 呼叫的參數個數相符，每條 `u_dut.…` 階層路徑都逐層找得到，並列出需要的巨集。

```sh
python3 tools/check_tests.py ../holoscan-sensor-bridge
```

在 `41cecaa` 上全部通過。v7 的檢查找到並修正了 S6 的巨集名稱。這**不是**編譯：語法、型別寬度、時序仍然沒有檢查過。

## 需要確認的地方

| 項目 | 說明 |
|---|---|
| 階層名稱 | v7 以 `tools/check_tests.py` 逐層確認：`gen_pack_inst` 外層是 `` `ifdef `` 而不是 if-generate，所以 `u_dut.gen_pack_inst[0]` 正確 |
| ECB 回應 | S1 的 `WR_BLOCK` 回應是 `0x89`，testbench 的 `parse_ecb_response()` 只認得 `WR_DWORD` / `RD_DWORD`，可能印出警告；不影響判斷 |
| SPI 介面 | testbench 把 `i_spi_sdio` 接 0，讀回資料為 0；S2 / S3 只看狀態 |
| 卡死後的狀態 | S2、S3、S4 在現在的 RTL 上會讓對應的控制器卡住，只能 reset。建議每個會卡死的測試獨立一次模擬，或放在最後 |
| S6 / S8 的 opcode | testbench 預設送 UC SEND。`rx_parser` 的 `bth_tx_opcode_match` 在 `ENABLE_ROCE_ACK = 1` 時接受 RC SEND 與 RC WRITE（[rx_parser.sv#L541](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_parser.sv#L541)），v7 確認 |
| S11 的流量 | 真實 MAC 在 10G 板級不會背靠背送 60-byte frame；這裡是為了在模擬中重現讀出落後。Terasic S10 的 MAC 在 100G 下每 1.5 拍送一個，效果相同（DP-15） |
| S9 / S10 的 `i_sif_axis_tready` | 測試直接改 testbench 的這個變數；若同時跑 `monitor_sensor_egress()`（HOST2SEN 模式），它會在開始時把 ready 設成 1，要避免同時使用 |
| U2 的 RTS | `uart.sv` 只有在 `rts_n` 為 0 時接受 start bit，測試固定接 0 |

## 不適合定向模擬的項目

| 問題 | 原因 | 建議 |
|---|---|---|
| BR-1（Bridge 大封包） | 本 repo 沒有板級啟用 Bridge，testbench 也沒有 | 先在 `fpga_sensor_top_pkg.svh` 啟用 Bridge |
| PT-1 – PT-5（PTP） | 需要 PTP master 模型 | 寫一個送 Sync / Follow_Up / Delay_Resp 的行為模型 |
| TX-4（`roce_ack` checksum） | 觸發條件是不帶 payload 的 SEND 且 checksum ≤ 3，需刻意構造 IP header | 已用[數值驗證](verification-calcs.md)確認；模擬時可用 IP identification 欄位調整 checksum |
| PE-5（I2C 速度） | 只是頻率換算 | 已在 [peripherals](modules/peripherals.md) 計算 |
