# 參考設計模組（`ref_design/`）

`nv_hsb_ip/ref_design/` 裡的模組不在 `HOLOLINK_top` 內，是給板級 top 選用的周邊。它們都以使用者 APB（`0x1000_0000` 以上）掛到 HSB。

| 模組 | 原始碼 | 行數 | 功能 | 使用的板級 |
|---|---|---|---|---|
| `vsync_gen` | [`vsync/vsync_gen.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/ref_design/vsync/vsync_gen.sv) | 215 | 以 PTP 時間同步的相機觸發訊號 | CPNX100、nv_mipi_ref_design |
| `delayed_io` | [`delayed_io/`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/tree/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/ref_design/delayed_io) | 350 + 124 | 延遲指定微秒後設定輸出腳位 | CPNX100 |
| `i2s_top` | [`i2s/`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/tree/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/ref_design/i2s) | 1600 | I2S 音訊 TX / RX，經 SIF 與 host 交換資料 | CPNX100 |
| `imu_top` | [`imu/`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/tree/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/ref_design/imu) | 733 | 經 I2C 讀 IMU，每筆樣本附 PTP 時間戳，以 AXIS 輸出 | 本 repo 的板級未使用 |

分析深度：`vsync_gen` 主要邏輯；其他只讀介面與註解。

## `vsync_gen`

依 PTP 時間產生週期性觸發（vsync / strobe）給相機：

| 暫存器 | 位元 | 說明 |
|---|---|---|
| ctrl 0 | `[0]` | 啟用 |
| ctrl 1 | `[3:0]` | 模式：0 = 10 Hz、1 = 30 Hz、2 = 60 Hz、3 = 90 Hz、4 = 120 Hz、5 = 1 Hz（單次） |
| ctrl 2 | | 相對秒起點的延遲（ns） |
| ctrl 3 | `[0]` | 觸發訊號的初始電位 |
| ctrl 4 | | 曝光時間（觸發脈衝寬度） |
| ctrl 5 | `[9:0]` | GPIO 多工選擇 |

運作：每個 PPS 後，等奈秒計數到達延遲值時翻轉觸發訊號，之後依模式的週期產生固定次數的脈衝，下一個 PPS 重新對齊。因為以 PTP 秒為基準，多個同步到同一 grandmaster 的 HSB 可以同時觸發相機。

host 軟體佐證：`VSYNC_CONTROL = 0x7000_0000`、`VSYNC_FREQUENCY = 0x7000_0004`、`VSYNC_DELAY = 0x7000_0008`、`VSYNC_START = 0x7000_000C`、`VSYNC_EXPOSURE = 0x7000_0010`、`VSYNC_GPIO = 0x7000_0014`（CPNX100 板級把它放在使用者 APB `0x7000_0000`）。

## `delayed_io`

在 APB 時脈與處理時脈兩個時脈域運作。暫存器 0x04 = 延遲（µs）、0x08 = 立即設定。CPNX100 板級與 `vsync_gen` 共用同一個使用者 APB slave，以位址 bit 11 區分（[`FPGA_top.sv#L503`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/lattice/cpnx100-eth-sensor-bridge/cpnx100/rtl/top/FPGA_top.sv#L503)）。

## `i2s_top`

| 子模組 | 功能 |
|---|---|
| `i2s_clk_gen` | 從參考時脈產生 MCLK（256 × LRCLK）、BCLK、LRCLK；取樣率 8 k – 192 kHz |
| `i2s_serdes` | I2S 序列化 / 反序列化，MSB first，支援多種格式；8 / 16 / 24 / 32 bit |
| `i2s_axis_buffer_tx` / `rx` | `axis_buffer` 包裝：寬度轉換與跨時脈 |

TX 方向接 HSB 的 SIF TX（host 送來 32-bit 樣本串流），RX 方向接 SIF RX。

## `imu_top`

`imu` 經 I2C 週期性讀取 IMU 暫存器（讀取序列存在 RAM，`RAM_DEPTH = 128`），每筆樣本附加 PTP 時間戳（`reg_cdc` 跨時脈），經 `axis_buffer` 以 AXIS 輸出，可接到 SIF RX 走 Data Plane。
