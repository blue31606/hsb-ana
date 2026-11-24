# 測試資料產生器（`data_gen`、`ram_player`）

## 概要

| 模組 | 原始碼 | 用途 | 使用位置 |
|---|---|---|---|
| `data_gen` | [`data_gen/data_gen.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/data_gen/data_gen.sv)（316 行） | 在 SIF RX 前產生 PRBS 或遞增計數資料，取代感測器輸入 | `HOLOLINK_top`（`SIF_RX_DATA_GEN` 定義時，[L1380](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L1380)） |
| `prbs_lfsr_hc` | [`data_gen/prbs_lfsr_hc.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/data_gen/prbs_lfsr_hc.sv) | 展開的 PRBS-31 LFSR | `data_gen` |
| `ram_player` | [`data_gen/ram_player.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/data_gen/ram_player.sv)（344 行） | 從 APB 寫入的 RAM 重播資料 | 只有 PYNQ RFSoC 板級（`sensor_if_path.sv`） |

分析深度：`data_gen`、`ram_player` 都逐行。

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
2. 速率控制：`output_div_cnt += output_rate`，bit 16（模擬時 bit 4）每次翻轉（0→1 或 1→0）就輸出一拍，bit 16 每累加 2¹⁶ 翻轉一次，所以輸出速率 ≈ `output_rate / 2^16` 拍/時脈，`output_rate` 接近 `0xFFFF` 時約每拍輸出。
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

把 host 經 APB 寫進 RAM 的資料，以 AXIS 一段一段播放出來，取代感測器輸入。`o_ram_axis_mux = ena[0]`，板級用它切換 SIF RX 的來源。

### 位址與暫存器

[ram_player.sv#L44–L113](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/data_gen/ram_player.sv#L44-L113)：`paddr[21:20] = 00` 是暫存器，`01` 是 RAM（offset `0x10_0000` 起）。RAM 是 `s_apb_ram_dyn`，`RAM_DEPTH = 512` 個 `W_DATA`（預設 512 bit = 64 byte）的字，共 32 KB；讀取在 SIF 時脈。暫存器經 `s_apb_reg` 跨到 SIF 時脈，模組內定義，不在 `regmap_pkg`。

| Offset | 名稱 | 說明 |
|---|---|---|
| 0x00 | scratch | |
| 0x04 | ena | `[0]` 啟用、`[1]` PTP 模式、`[2]` 關閉循環、`[3]` PTP BRAM 模式 |
| 0x08 | timer | 每段之間的等待（SIF 時脈數） |
| 0x0C | window_size | 每段的 byte 數 |
| 0x10 | window_num | 段數 |

### 播放狀態機

[ram_player.sv#L183–L333](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/data_gen/ram_player.sv#L183-L333)：`IDLE → SEND_DATA ⇄ WAIT_TIME → DONE`。

| 項目 | 行為 |
|---|---|
| 啟動 | `ena[0]` 為 1 的第二個時脈開始送第一拍（第一個時脈先預讀位址 0） |
| 一段 | 每拍 `W_KEEP` byte、`tkeep` 全 1；`data_cnt ≥ window_size − W_KEEP` 那一拍帶 `tlast`。`window_size` 不是 `W_KEEP` 的倍數時最後一拍仍是整拍 |
| 段與段 | RAM 位址連續往下讀，各段在 RAM 中前後相接；每段結束後等 `timer` 個時脈（`timer = 0` 時直接送下一段） |
| 一輪結束 | 送完 `window_num` 段後位址回到 0；`timer ≠ 0` 且沒有 `loop_dis` 時等待後重播，否則進 `DONE`，直到 `ena[0]` 清掉才回 IDLE |
| 中途停止 | 在 `SEND_DATA` 中清 `ena[0]`：補送一拍 `tlast` 收尾，再回 IDLE |
| `tuser` | 固定 0 |

### 時間戳模式

[ram_player.sv#L160–L178](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/data_gen/ram_player.sv#L160-L178)、[ram_player.sv#L340–L342](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/data_gen/ram_player.sv#L340-L342)：`i_ptp`（80 bit）在 `tvalid` 剛拉高或前一拍被接受時取樣，反壓期間保持不變。

| 模式 | `tdata` |
|---|---|
| `ena[3]`（PTP BRAM） | 每段第一拍的 bit 191:128（byte 16–23）換成 `ptp[63:0]`，其餘是 RAM 內容 |
| `ena[1]`（PTP） | 每一拍都換成 `{0, window_cnt[11:0], ptp[79:0]}`，完全不用 RAM 資料 |

所以 `i_ptp` 是用來把送出時間寫進資料，而不是在指定時間播放。

### 注意事項

1. **`timer = 0` 時不會循環播放。** 一輪結束的條件是 `(timer == 0) || loop_dis` → `DONE`（[ram_player.sv#L261–L265](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/data_gen/ram_player.sv#L261-L265)），所以想要連續重播必須設 `timer ≥ 1`（R）。
2. **`window_size < W_KEEP` 時沒有 `tlast`。** `window_size − W_KEEP` 是 32-bit 無號減法，下溢成很大的值，`data_cnt` 永遠到不了，整個 RAM 一直播下去（R）。
3. **中途停止可能違反 AXIS。** 清 `ena[0]` 時如果下游沒有 ready，狀態機進 `DONE`，下一拍回 IDLE 並把 `tvalid` 拉低，收尾那一拍沒有被接受就消失了（[ram_player.sv#L247–L251](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/data_gen/ram_player.sv#L247-L251)、[ram_player.sv#L238–L242](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/data_gen/ram_player.sv#L238-L242)；R）。
4. PTP BRAM 模式的位元切片寫死 `[511:192]`，只適用於 `W_DATA = 512`。
5. 反壓處理用 `rd_data_lat` / `axis_tready_lat` 暫存 RAM 輸出，邏輯分支多；`tready` 頻繁翻轉時資料是否會重複或跳過，需要模擬確認（I）。
