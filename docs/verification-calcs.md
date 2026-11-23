# 數值驗證

本文件記錄 `tools/verify/verify_calcs.py` 的結果。腳本照 RTL 原樣重寫每一段運算（位元寬度、截斷、進位都照抄），再和獨立寫成的參考實作比對。這些檢查不需要 HDL 模擬器，但只驗證**運算本身**，不驗證時序與控制流程。

```sh
python3 tools/verify/verify_calcs.py <holoscan-sensor-bridge 路徑>
```

腳本每項印出 PASS / FAIL / RESULT（RESULT 表示只計算數值、沒有對錯判定），有任何 FAIL 時結束碼為 1。下表是 commit `41cecaa` 上的結果，全部 PASS。

## 結果

| # | 檢查 | RTL 位置 | 參考 | 結果 |
|---|---|---|---|---|
| 1a | EEPROM CRC 演算法 | [eeprom_info.sv L276–L322](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/sys_init/eeprom_info.sv#L276-L322) | CRC-8/MAXIM 目錄 check 值 0xA1 | PASS：`"123456789"` → 0xA1，確認是 CRC-8/MAXIM（多項式 0x31，反射 0x8C，初值 0） |
| 1b | 檔頭註解的多項式 0xB0 | 同上 | 用 0xB0 算同一輸入 | PASS：得到 0x6E，與程式不同，註解錯誤 |
| 1c | 正確燒錄的 EEPROM 是否通過 RTL 檢查 | 同上 + `eeprom_utility.py` | 10000 個隨機映像，byte 255 由工具寫入 CRC | RESULT：**9964 / 10000 判為 CRC 錯誤**（預期 255/256）。RTL 算出的 CRC 每次都**等於** byte 255，所以應該比較兩者，而不是檢查是否為 0 |
| 1d | 修正方案：CRC 計算包含 byte 255 | 同上 | 反射 CRC、初值 0、無 xorout 的性質 | PASS：10000 個合法映像全部得到 0，所以只要刪掉「跳過最後一個 byte」的條件，`(CRC ≠ 0)` 的判斷就正確（見 [issues](issues.md)） |
| 2 | IPv4 checksum 常數 `0xC52D` | [dp_pkt_top.sv L1173–L1188](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/dp_pkt/dp_pkt_top.sv#L1173-L1188)、[rx_ls_parser.sv L499–L514](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/rx_parser/rx_ls_parser.sv#L499-L514) | RFC 791 從頭計算 | PASS：20000 組隨機 IP / 長度，0 個無效 header |
| 3a | `roce_ack` 增量 checksum，一般情況 | [roce_ack.sv L524–L538](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_ack.sv#L524-L538) | 產生合法請求 header，換成 ACK 欄位後檢查 | PASS：200000 組隨機請求，0 個無效 |
| 3b | `roce_ack` 借位情況 | 同上 | RFC 1624 one's complement 減法 | PASS（確認缺陷）：`chk + old_len < 48` 的 10 種組合全部錯，**每次都差 +2** |
| 3c | 修正方案：18-bit one's complement 加法 | 同上 | 同 3a、3b | PASS：`chk + old_len + ~48` 折兩次，隨機 header 與借位區全部正確（見 [issues](issues.md)） |
| 4a | RAW10 排程 `0x11F1FFF7` | `packetizer_program.cpp` | 解碼 `pack_ctrl` | PASS：16 列中 15 列讀輸入，120 B 進、128 B 出 |
| 4b | RAW10 1920 px line | `Csi10ToPacked10::get_output_size()` | 排程換算 | PASS：2400 B → 2560 B |
| 4c | RAW12 排程 `0x11210007` | 同上 | 解碼 | PASS：3 列都讀輸入 |
| 5a | `ODD_EVEN_SIZE` 表 | [packetizer.sv](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/packetizer/packetizer.sv) | 遞迴計算 Batcher odd-even merge sort 的比較器數 | PASS：n = 2…1024 全部一致 |
| 5b | 各板級 packetizer RAM 數 | packetizer.sv L69–L134 | 公式代入 | RESULT：CPNX100 / NV MIPI 為 2 / 18 / 1，共 21 個、336 次寫入；Terasic S10 為 1 / 6 / 1，共 8 個、128 次寫入。與 [packetizer §4](modules/packetizer.md#4-可程式化資料路徑packetizersv) 的表一致 |
| 6a | header 長度與拍數 | `dp_pkt_hdr.sv` | 欄位相加 | PASS：RoCE 70 B、CoE 46 B、RoCE metadata 202 B、CoE metadata 174 B、RoCE+Imm 74 B |
| 6b | ICRC 最後一拍長度 | [roce_icrc.sv](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/roce_icrc.sv) | 去掉前 6 B 後的長度 | RESULT：64-bit 時 8 / 4 / 4 / 4，512-bit 時 64 / 4 / 36 / 52（WRITE / WRITE+Imm / 32 B frame / ACK） |
| 7 | `lfsr_hc` 8-bit 方程式 | [lfsr_hc.sv](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/roce/lfsr_hc.sv) | 標準反射 CRC-32（0xEDB88320）逐 byte | PASS：從原始碼解析 32 條方程式，加上模組邊界的位元反轉後，5000 次隨機步驟全部一致 |
| 8 | DPLL `fa` 單位 | `dpll.sv` | 2⁻²⁴ ns / 時脈週期 | PASS：100.446545 MHz 時 5.99 ppb，±2²³ 對應 ±5 % |
| 8 | `streaming_cdc` 相位增量 | `misc/streaming_cdc.sv` | 參數代入 | RESULT：49，寫入率 19.23 MHz（低於 19.53 MHz） |
| 8 | I2C `clk_cnt = 0x19` | `i2c/i2c.sv` | `f_APB / (2 × clk_cnt)` | RESULT：19.53 MHz 時 391 kHz |
| 8 | RoCE MTU 效率 | `compute_payload_size()` | 公式代入 | RESULT：MTU 1500 → 1408 B、93.5 %；MTU 4096 → 3968 B、97.6 %。與 [performance](performance.md) 一致 |
| 9 | flow 範例（1920 × 1080 RAW10、MTU 1500） | [flow §6](flow.md) | 逐步計算 | PASS：每 line 2560 B、frame 2,764,800 B、1964 個封包、最後一包 896 B（7 page）、IPv4 total length 1468 |

## 對文件的影響

- [boot_and_reset 注意事項](modules/boot_and_reset.md#注意事項) 的 EEPROM CRC 不一致從「讀 RTL」升級為**數值確認**：正確燒錄的 EEPROM 約 99.6 % 會讓 `eeprom_crc_err = 1`。這個訊號沒有接到任何地方，所以目前沒有功能影響。
- [roce_ack 注意事項 6](modules/roce_ack.md#注意事項) 的「借位時差 2」為**數值確認**，觸發範圍是 `chk + old_len < 48`，也就是請求的 IPv4 total length 小於 48。帶 RETH 的 RDMA WRITE 最短 60 byte，**永遠不會觸發**；只有不帶 payload 的 SEND（BTH only，44 byte）且 checksum ≤ 3 時才會發生（`roce_ack` 對所有 RC opcode 都回應）。
- `0xC52D` 公式、`lfsr_hc` CRC-32、`ODD_EVEN_SIZE` 表、RAW10 / RAW12 排程、header 長度、flow 範例的數字都通過獨立比對。

## 沒有涵蓋的部分

- 時序：拍數、管線延遲、FSM 轉換都需要模擬。測試計畫見 [test-plan](test-plan.md)。
- `lfsr_hc` 只檢查了 8-bit。其他寬度的方程式格式相同，但沒有逐一比對。
- 沒有驗證 `roce_icrc` 對最後一拍的遮罩與位元組順序。
