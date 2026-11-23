# 周邊控制器（I2C、SPI、UART、GPIO）

## 概要

三個周邊控制器都掛在 APB 周邊區（`0x0300_0000`），在 APB 時脈下運作，結構相同：

- 控制 / 狀態暫存器（APB 位址 bit 8 = 0）
- 資料緩衝 RAM（APB 位址 bit 8 = 1，offset 0x100 起）
- 一個協定引擎
- 多組實體匯流排共用一個控制器，用 `bus_en` 選擇目前驅動哪一組

| 控制器 | 原始碼 | 行數 | 基底 | 實例 |
|---|---|---|---|---|
| I2C | [`i2c/i2c_ctrl_fsm.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/i2c/i2c_ctrl_fsm.sv)、`i2c.sv` | 378 + 304 | `0x0300_0200` | [`HOLOLINK_top.sv#L1105`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L1105) |
| SPI / QSPI | [`spi/spi_ctrl_fsm.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/spi/spi_ctrl_fsm.sv)、`spi.sv` | 341 + 324 | `0x0300_0000` | [L1055](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L1055) |
| UART | [`uart/uart_ctrl_fsm.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/uart/uart_ctrl_fsm.sv)、`uart.sv` | 628 + 690 | `0x0300_0400` | [L1137](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L1137) |
| GPIO | [`glb_ctrl/glb_ctrl_top.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/glb_ctrl/glb_ctrl_top.sv) | 131 | `0x0000_0000` | [L776](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L776) |

分析深度：暫存器定義與控制器頂層逐行；位元層級的協定引擎（`i2c.sv`、`spi.sv`、`uart.sv`）只讀結構。

## 匯流排多工（`HOLOLINK_top`）

[L1036–L1131](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L1036-L1131)：

| | 選中的匯流排 | 未選中的匯流排 |
|---|---|---|
| SPI | 驅動 CS、SCK、SDIO | CS = 1、SCK = 0、SDIO 不驅動 |
| I2C | SCL / SDA 由控制器驅動 | `*_en = 1`（釋放，open-drain 拉高） |

一次只能使用一組匯流排。

## I2C

| Offset | 位元 | 說明 |
|---|---|---|
| 0x00 | `[0]` | start |
| | `[1]` | 10-bit 位址 |
| | `[25:16]` | 裝置位址 |
| 0x04 | `[log2(N):0]` | `bus_en`：選擇匯流排 |
| 0x08 | `[15:0]` / `[31:16]` | 寫入 byte 數 / 讀取 byte 數 |
| 0x0C | `[15:0]` | `clk_cnt`：SCL 分頻 |
| 0x10 | | SCL stretch 逾時（reset `0x004C_4B40` = 5,000,000） |
| 0x14 | `[7:0]` | `num_trans` |
| 0x80 | `[0]` busy、`[2]` arbitration lost、`[3]` NACK、`[4]` done | 狀態 |
| 0x100– | | 資料緩衝：先寫入要送出的 byte，交易後讀回收到的 byte |

一次交易：送裝置位址（寫）→ 寫 `num_wr_bytes` → 若 `num_rd_bytes > 0`，repeated start 送裝置位址（讀）→ 讀 `num_rd_bytes`。host 軟體常數：`I2C_REG_BUS_EN = 4`、`I2C_REG_NUM_BYTES = 8`、`I2C_REG_CLK_CNT = 0xC`、`I2C_REG_STATUS = 0x80`、`I2C_REG_DATA_BUFFER = 0x100`。

`eeprom_info` 開機時也用這組暫存器讀 EEPROM（裝置位址 0x50），見 [boot_and_reset.md](boot_and_reset.md)。

## SPI / QSPI

| Offset | 位元 | 說明 |
|---|---|---|
| 0x00 | `[0]` | start |
| 0x04 | | `bus_en` |
| 0x08 | `[15:0]` / `[31:16]` | 寫入 / 讀取 byte 數 |
| 0x0C | `[3:0]` | prescaler |
| | `[5:4]` | SPI mode（CPOL / CPHA） |
| | `[9:8]` | 資料線寬度（1 / 2 / 4 線，只在資料階段） |
| 0x10 | `[7:0]` | turnaround 拍數 |
| | `[15:8]` | 命令 byte 數（命令階段固定單線） |
| 0x80 | `[0]` busy、`[1]` 命令錯誤、`[4]` done | 狀態 |
| 0x100– | | 資料緩衝 |

交易分三段：命令（`num_cmd_bytes`）→ turnaround → 資料（寫或讀）。`num_wr_bytes < num_cmd_bytes` 時回報命令錯誤。

## UART

| Offset | 說明 |
|---|---|
| 0x00 | `[0]` 啟用、`[1]` TX、`[2]` RX、`[3]` loopback、`[5:4]` 資料位元（8/7/6/5）、`[7:6]` parity（無 / 奇 / 偶）、`[8]` / `[9]` TX / RX FIFO reset、`[13:12]` stop bit（1 / 1.5 / 2）、`[14]` 硬體流控、`[23:16]` / `[31:24]` RX FIFO almost full / empty 門檻 |
| 0x04 | `[15:0]` 鮑率除數、`[23:16]` / `[31:24]` TX FIFO 門檻 |
| 0x08 | 中斷啟用 |
| 0x0C | 中斷清除 |
| 0x80 / 0x84 | 狀態 / 中斷狀態 |
| 0x140 | TX 資料 |

FIFO 深度 256（模擬 64）。`uart_irq` 進事件向量 bit 4。暫存器說明取自 RTL 與 `hololink.cpp` 第 85 行起的註解。

## GPIO（`glb_ctrl_top`）

| Offset | 名稱 | 說明 |
|---|---|---|
| 0x0C–0x28 | `gpio_o_0..7` | 輸出值（最多 256 個） |
| 0x2C–0x48 | `gpio_t_0..7` | 方向（`o_gpio_dir`，極性由板級決定） |
| 0x8C–0xA8 | `gpio_i_0..7` | 輸入值 |

reset 時 `gpio_o` = `GPIO_RESET_VALUE`（`HOLOLINK_def.svh`），`gpio_t` = 0。GPIO 輸入沒有同步器，跨時脈處理由 `s_apb_reg` 的狀態暫存器路徑負責（推斷）。

`glb_ctrl_top` 的其他暫存器見 [boot_and_reset.md](boot_and_reset.md#glb_ctrl_top)。
