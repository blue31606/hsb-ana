# 測試資料產生器（`data_gen`、`ram_player`）

## 概要

| 模組 | 原始碼 | 用途 | 使用位置 |
|---|---|---|---|
| `data_gen` | [`data_gen/data_gen.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/data_gen/data_gen.sv)（316 行） | 在 SIF RX 前產生 PRBS 或遞增計數資料，取代感測器輸入 | `HOLOLINK_top`（`SIF_RX_DATA_GEN` 定義時，[L1380](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L1380)） |
| `prbs_lfsr_hc` | [`data_gen/prbs_lfsr_hc.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/data_gen/prbs_lfsr_hc.sv) | 展開的 PRBS-31 LFSR | `data_gen` |
| `ram_player` | [`data_gen/ram_player.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/data_gen/ram_player.sv)（344 行） | 從 APB 寫入的 RAM 重播資料 | 只有 PYNQ RFSoC 板級（`sensor_if_path.sv`） |

分析深度：`data_gen` 逐行；`ram_player` 只讀介面與暫存器。

## `data_gen`

### 介面

| 方向 | 名稱 | 說明 |
|---|---|---|
| out | `o_axis_*` | SIF 時脈，`W_DATA` 寬 |
| out | `o_data_gen_axis_mux` | = `data_gen_ena`。`HOLOLINK_top` 用它在感測器輸入與測試資料之間切換，並把感測器端 `tready` 綁 0 |
| in | `i_pps` | `HOLOLINK_top` 綁 0 |

### 行為

狀態機 `IDLE → GEN_DATA → DONE`：

1. `data_gen_ena` 上升緣進入 `GEN_DATA`。
2. 速率控制：`output_div_cnt += output_rate`，每當 bit 16（模擬時 bit 4）翻轉就輸出一拍，所以輸出速率 ≈ `output_rate / 2^17` 拍/時脈。
3. 非連續模式：累計輸出 `data_gen_size` byte 後送 `tlast`，回到 `IDLE`。連續模式（`ena[1]`）：持續輸出直到 `data_gen_ena` 清 0。
4. 資料：
   - PRBS（`mode = 0`）：16-bit PRBS（seed 取 `prbs_seed[30:0]`），整個匯流排由同一個值加上段落 index 組成（`prbs + k`）。
   - 計數（`mode = 1`）：每 16-bit 一個遞增值。

### 暫存器

基底 `0x0100_0100 + SIF × 0x1_0000`。

| Offset | 名稱 | 說明 |
|---|---|---|
| 0x04 | `sen_rx_data_gen_ena` | `[0]` 啟用、`[1]` 連續模式 |
| 0x08 | `sen_rx_data_gen_mode` | `[1:0]` 0 = PRBS、1 = 計數 |
| 0x0C | `sen_rx_data_gen_size` | 每個 frame 的 byte 數 |
| 0x10 | `sen_rx_data_gen_output_rate` | `[15:0]` 速率 |
| 0x14 | `sen_rx_data_gen_pps_sync` | ⚠️ 程式碼中被註解掉（`pps_sync_mode = 0`） |
| 0x24 | `sen_rx_prbs_seed` | PRBS 初值 |

## `ram_player`

暫存器（模組內定義，不在 `regmap_pkg`）：`ena`（`[0]` 啟用、`[1]` PTP 模式、`[2]` 關閉循環、`[3]` PTP BRAM）、`timer`、`window_size`、`window_num`。輸入 `i_ptp`，推測用來在指定 PTP 時間播放資料。
