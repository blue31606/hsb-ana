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

分析深度：I2C 控制器與位元引擎逐行；SPI 控制器逐行、位元引擎讀時脈與 CS 部分；UART 讀暫存器、鮑率產生器與流控。

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

### I2C 交易狀態機（`i2c_ctrl_fsm`）

[i2c_ctrl_fsm.sv#L125–L136](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/i2c/i2c_ctrl_fsm.sv#L125-L136)、[i2c_ctrl_fsm.sv#L286–L367](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/i2c/i2c_ctrl_fsm.sv#L286-L367)：

```mermaid
stateDiagram-v2
  [*] --> IDLE
  IDLE --> DEV_ADDR: start、wr > 0（10-bit 先經 10b_DEV_ADDR）
  IDLE --> RS_DEV_ADDR: start、wr = 0（10-bit 先經 RS_10b_DEV_ADDR）
  DEV_ADDR --> WRITE
  WRITE --> RS_DEV_ADDR: 寫完、rd > 0
  WRITE --> DONE: 寫完、rd = 0
  RS_DEV_ADDR --> READ
  READ --> DONE: 讀完（最後一個 byte 回 NACK）
  WRITE --> PERI_NACK: 對方 NACK
  DEV_ADDR --> PERI_NACK: 對方 NACK
  PERI_NACK --> DONE
  DONE --> IDLE: 還有 num_trans，或 start 已清 0
```

| 項目 | 行為 | 原始碼 |
|---|---|---|
| 啟動條件 | `ctrl[0] = 1` 且 `cmd_valid`；`num_trans ≠ 0` 時要求 `num_wr_bytes ≥ num_rd_bytes` | [i2c_ctrl_fsm.sv#L278](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/i2c/i2c_ctrl_fsm.sv#L278)、[i2c_ctrl_fsm.sv#L293–L298](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/i2c/i2c_ctrl_fsm.sv#L293-L298) |
| 狀態前進 | 位元引擎每完成一個 byte（`cmd_ack` 上升緣）前進一次 | [i2c_ctrl_fsm.sv#L353–L354](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/i2c/i2c_ctrl_fsm.sv#L353-L354) |
| 對方 NACK | 寫入階段收到 NACK → `PERI_NACK` → STOP，`status[3]` | [i2c_ctrl_fsm.sv#L288–L290](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/i2c/i2c_ctrl_fsm.sv#L288-L290) |
| 讀取 | 最後一個 byte 回 NACK（`ack_in`），之後 STOP | [i2c_ctrl_fsm.sv#L369–L370](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/i2c/i2c_ctrl_fsm.sv#L369-L370) |
| 資料緩衝 | 128 word（512 byte）BRAM。寫入資料從 byte 0 依序取出；**讀回的資料也從 byte 0 寫回**，覆蓋原本的寫入資料 | [i2c_ctrl_fsm.sv#L161–L216](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/i2c/i2c_ctrl_fsm.sv#L161-L216) |
| `num_trans` | 一次啟動執行多筆相同格式的交易，緩衝指標不歸 0，依序使用後面的 byte | [i2c_ctrl_fsm.sv#L357–L365](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/i2c/i2c_ctrl_fsm.sv#L357-L365) |
| busy 期間讀緩衝 | 讀回 0 | [i2c_ctrl_fsm.sv#L215](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/i2c/i2c_ctrl_fsm.sv#L215) |

**位元引擎**（`i2c.sv`，[i2c.sv#L148–L187](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/i2c/i2c.sv#L148-L187)）：每個 SCL 週期分 4 個相位（`pcnt`），每個相位約 `clk_cnt / 2` 個 APB 時脈，所以

```
f_SCL ≈ f_APB / (2 × clk_cnt)
```

host 軟體固定寫 `clk_cnt = 0x19`（註解「400 kHz」，`hololink.cpp` `set_i2c_clock()`）。以 CPNX100 的 APB 19.53 MHz 計算是 390 kHz，與註解一致（X）。對方拉低 SCL（clock stretching）時分頻計數暫停。

**逾時**（[i2c.sv#L126](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/i2c/i2c.sv#L126)、[i2c.sv#L179](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/i2c/i2c.sv#L179)）：交易中 SDA 低、SCL 低或位元組傳送中，`timeout_cnt` 都會累加；到達 0x10 的值（預設 5,000,000 個 APB 時脈 ≈ 256 ms）時設 `al`，FSM 直接回 `IDLE` / `DONE`。**`status[2]`「arbitration lost」實際上是這個逾時**，RTL 沒有多 master 仲裁偵測。

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

### SPI 交易狀態機（`spi_ctrl_fsm`）

[spi_ctrl_fsm.sv#L261–L341](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/spi/spi_ctrl_fsm.sv#L261-L341)：`IDLE → CMD → WRITE → TURN → READ → DONE`，各段長度為 0 時跳過。

| 項目 | 行為 |
|---|---|
| 命令段 | `num_cmd_bytes` 個 byte，固定單線；命令 byte 也算在 `num_wr_bytes` 內（`num_wr_bytes ≥ num_cmd_bytes`，否則 `status[1]`） |
| 寫入段 | 剩下的 `num_wr_bytes − num_cmd_bytes` 個 byte，線寬依 `0x0C[9:8]` |
| turnaround | `0x10[7:0]` 個時脈，用於 QSPI flash 的 dummy cycle |
| 讀取段 | `num_rd_bytes` 個 byte；讀取計數在命令段就開始累加，所以讀回資料放在緩衝區 `num_cmd_bytes` 之後（推斷） |
| CS | 第一個 SCK 邊緣前固定等 2 個 SCK 週期（`spi.sv` 註解） |

時脈：`prescaler` 是每個 SCK 半週期的 APB 時脈數減 1，`f_SCK = f_APB / (2 × (prescaler + 1))`。`spi_mode = {CPHA, CPOL}`，CPOL 必須在新命令前至少一拍改好。

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

### UART 細節

| 項目 | 值 | 原始碼 |
|---|---|---|
| 鮑率 | 每 `baud_div + 1` 個 APB 時脈產生一次 `baud_tick`，每個位元 8 次取樣（`OVERSAMPLE = 8`）：`baud = f_APB / (8 × (baud_div + 1))`。埠的註解寫「16x oversampling」，與參數不符 | [uart.sv#L17](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/uart/uart.sv#L17)、[uart.sv#L64–L80](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/uart/uart.sv#L64-L80) |
| FIFO | TX、RX 各 256 byte；門檻 0 時預設 almost full 252、almost empty 4 | [uart_ctrl_fsm.sv#L21](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/uart/uart_ctrl_fsm.sv#L21)、[uart_ctrl_fsm.sv#L157–L160](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/uart/uart_ctrl_fsm.sv#L157-L160) |
| 流控 | `0x00[14]` 啟用時，CTS 為高就停止送出；RTS = RX FIFO almost full（或 RX 未啟用）；RTS 為高時接收端也不接受新的 start bit（[uart_ctrl_fsm.sv#L518](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/uart/uart_ctrl_fsm.sv#L518)） | [uart_ctrl_fsm.sv#L400–L404](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/uart/uart_ctrl_fsm.sv#L400-L404) |
| 雜訊濾波 | `0x10`：`[3:0]` 視窗、`[7:4]` start bit 多數決門檻、`[11:8]` 資料位元多數決門檻、`[16]` 啟用；多數決失敗設 glitch error | [uart_ctrl_fsm.sv#L213–L216](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/uart/uart_ctrl_fsm.sv#L213-L216) |
| 資料暫存器 | `0x140` TX（讀：FIFO 滿時 `0xFF`）、`0x144` RX、`0x148` 最後收到的 byte | [uart_ctrl_fsm.sv#L581–L600](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/uart/uart_ctrl_fsm.sv#L581-L600) |
| 狀態 `0x80` | `[0]` TX busy、`[1]` RX busy、`[2]` TX 滿、`[3]` TX 空、`[4]` RX 滿、`[5]` RX 非空、`[6]` parity error、`[7]` frame error、`[8]` / `[9]` TX / RX overflow、`[10]` last RX 有效、`[11]` CTS、`[12]` RTS、`[13]` glitch error | [uart_ctrl_fsm.sv#L220–L233](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/uart/uart_ctrl_fsm.sv#L220-L233) |
| 中斷 `0x08` / `0x84` | `[0]` TX 空、`[1]` TX almost full、`[2]` TX almost empty、`[3]` RX 非空、`[4]` glitch error | [uart_ctrl_fsm.sv#L200–L204](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/uart/uart_ctrl_fsm.sv#L200-L204)、[uart_ctrl_fsm.sv#L236–L240](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/uart/uart_ctrl_fsm.sv#L236-L240) |

## GPIO（`glb_ctrl_top`）

| Offset | 名稱 | 說明 |
|---|---|---|
| 0x0C–0x28 | `gpio_o_0..7` | 輸出值（最多 256 個） |
| 0x2C–0x48 | `gpio_t_0..7` | 方向（`o_gpio_dir`，極性由板級決定） |
| 0x8C–0xA8 | `gpio_i_0..7` | 輸入值 |

reset 時 `gpio_o` = `GPIO_RESET_VALUE`（`HOLOLINK_def.svh`），`gpio_t` = 0。GPIO 輸入沒有同步器，跨時脈處理由 `s_apb_reg` 的狀態暫存器路徑負責（推斷）。

`glb_ctrl_top` 的其他暫存器見 [boot_and_reset.md](boot_and_reset.md#glb_ctrl_top)。

## 注意事項

1. I2C 的 10-bit 位址讀取不符合 I2C 規格：repeated start 後送出 `11110xx1`，接著又**寫出**一次低 8 bit 位址（`I2C_RS_DEV_ADDR` 狀態一律是寫入），規格中這時應該開始讀資料（R + I：只依程式推論，未對照實際裝置）。
2. I2C `status[2]` 名為 arbitration lost，實際是 SCL / SDA 逾時。
3. host 固定寫 `clk_cnt = 0x19`。APB 時脈較高的板級（PYNQ 50 MHz、Terasic S10 100 MHz）上 SCL 會是約 1 MHz、2 MHz，超過 Fast-mode 400 kHz（推斷；未確認那些板級的軟體是否另行設定）。
4. I2C 讀回資料覆蓋緩衝區開頭的寫入資料，連續使用時要重新寫入。
