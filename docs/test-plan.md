# 定向測試計畫

[issues](issues.md) 中的問題都只讀過 RTL、沒有跑過模擬。本計畫為其中能用模擬確認的項目設計定向測試，並附 SystemVerilog 草稿：

| 檔案 | 內容 |
|---|---|
| [`tests/unit/tb_spi_turnaround.sv`](../tests/unit/tb_spi_turnaround.sv) | 單獨測 `spi.sv` |
| [`tests/unit/tb_uart_rx_rate.sv`](../tests/unit/tb_uart_rx_rate.sv) | 單獨測 `uart.sv` 的接收端 |
| [`tests/unit/tb_i2s_clk_gen.sv`](../tests/unit/tb_i2s_clk_gen.sv) | 單獨測 `i2s_clk_gen.sv` |
| [`tests/system/hsb_directed_tests.svh`](../tests/system/hsb_directed_tests.svh) | 放進 `nv_hsb_ip_simple_tb` 的 task |

**草稿沒有編譯過。** 分析環境沒有任何 HDL 工具（VCS、Xcelium、Questa、Verilator、Icarus、slang 都沒有），所以語法、階層名稱、時序都可能需要修改。每個測試的判斷條件寫成「依規格應有的行為」：在 commit `41cecaa` 上，標「預期失敗」的測試應該失敗，失敗就是確認了問題。

## 測試清單

| 測試 | 對應問題 | 層級 | 激勵 | 判斷 | 預期（`41cecaa`） |
|---|---|---|---|---|---|
| U1 `tb_spi_turnaround` | PE-2 | 單元 | 1 個命令 byte + turnaround `LEN` = 1、2、8、31、32、33、40、255 | `busy` 在合理時間內清除，turnaround 期間 SCK 邊緣數 = 2 × `LEN` | `LEN` ≥ 33 失敗 |
| U2 `tb_uart_rx_rate` | PE-3 | 單元 | 行為模型以 `+ERR_PPM` 偏差連續送 64 個 8N1 frame，frame 之間沒有 idle | 64 個 byte 全部正確收到 | `ERR_PPM` > 0 失敗；≤ 0 通過 |
| U3 `tb_i2s_clk_gen` | PE-9 | 單元 | `CTRL2` = 0–9、`mclk_div` = 0、1、2、3、4、8 | BCLK 有翻轉、`bclk_en` 有脈衝、每半個 LRCLK 剛好 16 個 BCLK | `CTRL2` = 0、8、9 與 `mclk_div` = 0、1 失敗 |
| S1 `dt_ecb_single_pair_block` | CP-1 | 系統 | 先寫 `glb_scratch` 標記值，再送只帶 1 組（寫 `ptp_scratch`）的 `WR_BLOCK`，frame 補到 60 byte | `ptp_scratch` 被寫入，`glb_scratch` 不變 | `glb_scratch` 被覆寫，失敗 |
| S2 `dt_spi_read_only` | PE-1 | 系統 | `num_wr = 0`、`num_cmd = 0`、`num_rd = 4` 後 start | `status[4]` done、`status[0]` 不 busy | busy 一直為 1，失敗 |
| S3 `dt_spi_long_turnaround` | PE-2 | 系統 | 1 個命令 byte、turnaround 32 / 33 / 40、讀 1 byte | 交易完成 | 33、40 失敗 |
| S4 `dt_packetizer_latency` | DP-5 | 系統 | passthrough 設定，`pack_ctrl[27:24]` = 8 與 9，送一個 frame | packetizer 不停在 `PACK_WAIT`，frame 完整 | 8 通過、9 失敗 |
| S5 `dt_vlan_ptp_type` | DP-3 | 系統 | 不帶與帶 VLAN（TCI `0x6005`）的 Follow_Up | `is_ptp_sync_msg` 不產生脈衝 | 帶 VLAN 時被當成 Sync，失敗 |
| S6 `dt_roce_dup_ack` | TX-1 | 系統（`ENABLE_ROCE_ACK`、`HOST2SEN`） | 同一 PSN 的 RC SEND 送兩次 | 收到 2 個 ACK | 只有 1 個，失敗 |
| S7 `dt_eeprom_crc` | PE-8 | 系統 | EEPROM 模型的 byte 255 寫入 byte 0–254 的 Maxim CRC | `eeprom_crc_err = 0` | 為 1，失敗 |

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

S6 要另外編譯 `+define+ENABLE_ROCE_ACK`，並在 `TEST_MODE=HOST2SEN` 下執行。

## 需要確認的地方

| 項目 | 說明 |
|---|---|
| 階層名稱 | `u_dut.spi_ctrl_inst`、`u_dut.gen_pack_inst[0].packetizer_top_inst`、`u_dut.is_ptp_sync_msg`、`u_dut.ack_axis_*`、`u_dut.u_eeprom_info` 是依 `41cecaa` 的原始碼寫的；`gen_pack_inst` 外層若還有 if-generate，名稱要補上 |
| ECB 回應 | S1 的 `WR_BLOCK` 回應是 `0x89`，testbench 的 `parse_ecb_response()` 只認得 `WR_DWORD` / `RD_DWORD`，可能印出警告；不影響判斷 |
| SPI 介面 | testbench 把 `i_spi_sdio` 接 0，讀回資料為 0；S2 / S3 只看狀態 |
| 卡死後的狀態 | S2、S3、S4 在現在的 RTL 上會讓對應的控制器卡住，只能 reset。建議每個會卡死的測試獨立一次模擬，或放在最後 |
| S6 的 opcode | testbench 預設送 UC SEND；`roce_ack` 只對 RC opcode 回應，所以 S6 用 RC SEND ONLY（`0x04`），`rx_parser` 是否接受需要確認 |
| U2 的 RTS | `uart.sv` 只有在 `rts_n` 為 0 時接受 start bit，測試固定接 0 |

## 不適合定向模擬的項目

| 問題 | 原因 | 建議 |
|---|---|---|
| DP-1、DP-2（`rx_parser` 溢位） | 需要長時間讓讀出停滯 | 用 `force` 把 `rx_parser` 讀出端的 ready 拉低數千拍，再送大量最小封包 |
| BR-1（Bridge 大封包） | 本 repo 沒有板級啟用 Bridge，testbench 也沒有 | 先在 `fpga_sensor_top_pkg.svh` 啟用 Bridge |
| PT-1 – PT-5（PTP） | 需要 PTP master 模型 | 寫一個送 Sync / Follow_Up / Delay_Resp 的行為模型 |
| TX-4（`roce_ack` checksum） | 觸發條件是不帶 payload 的 SEND 且 checksum ≤ 3，需刻意構造 IP header | 已用[數值驗證](verification-calcs.md)確認；模擬時可用 IP identification 欄位調整 checksum |
| PE-5（I2C 速度） | 只是頻率換算 | 已在 [peripherals](modules/peripherals.md) 計算 |
