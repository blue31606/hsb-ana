# Packetizer（`packetizer_top` 與子模組）

## 概要

每個 SIF RX 一份。把感測器時脈下的 AXIS 串流（例如 MIPI CSI-2 RX 的輸出）在位元層級重新排列，拆成一或多個 Virtual Port（VP），跨到 HIF 時脈後交給 `dp_pkt_top`。用途是把感測器的打包格式（RAW10、RAW12 等）轉成 host 好處理的格式，並把同一條感測器串流分到多個目的地。

| 檔案 | 行數 | 功能 |
|---|---|---|
| [`packetizer_top.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/packetizer/packetizer_top.sv) | 600 | 暫存器、排程狀態機、模式選擇 |
| [`packetizer.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/packetizer/packetizer.sv) | 279 | 可程式化資料路徑：設定 RAM、排序網路、VP |
| [`packetizer_static.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/packetizer/packetizer_static.sv) | 254 | 固定 pattern 資料路徑：查表式位元路由 |
| [`packetizer_pkg.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/packetizer/packetizer_pkg.sv) | 121 | 固定 pattern catalog（自動產生） |
| [`odd_even_gen.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/packetizer/odd_even_gen.sv) | 90 | Batcher odd-even merge 排序網路（當作可程式化置換網路用） |
| [`virtual_port.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/packetizer/virtual_port.sv) | 257 | VP：位元累積、跨時脈 FIFO |

實例：[`HOLOLINK_top.sv#L1482`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L1482)。分析深度：`packetizer_top`、`packetizer`、`virtual_port` 逐行；`odd_even_gen` 與 `packetizer_static` 主要邏輯；pattern 內容（自動產生的常數）未逐位元檢查。

## 參數

| 參數 | `HOLOLINK_top` 來源 | 說明 |
|---|---|---|
| `DIN_WIDTH` | `SIF_RX_WIDTH[i]` | 感測器輸入寬度 |
| `DOUT_WIDTH` | `HOST_WIDTH` | |
| `PACKETIZER_ENABLE` | `SIF_RX_PACKETIZER_EN[i]` | 0 = bypass、1 = 可程式化、2 = 固定 pattern |
| `VP_COUNT` | `SIF_RX_VP_COUNT[i]` | VP 數（最多 4） |
| `VP_SIZE` | `SIF_RX_VP_SIZE[i]` | 每個 VP 的寫入寬度（bit） |
| `SORT_RESOLUTION` | `SIF_RX_SORT_RESOLUTION[i]` | 排序網路的單位（bit） |
| `NUM_CYCLES` | `SIF_RX_NUM_CYCLES[i]` | 保留幾個輸入 beat 的歷史 |
| `MIXED_VP_SIZE`、`DYNAMIC_VP` | 固定 0 | `HOLOLINK_top` 不啟用 |
| `PATTERN_MASK` | `SIF_RX_PCK_PATTERNS` | 固定 pattern 模式下保留哪些 pattern |
| `W_USER` | `DATAUSER_WIDTH` | 輸入 `tuser` 寬度 |

## 介面

| 方向 | 名稱 | 時脈 | 說明 |
|---|---|---|---|
| in | `i_axis_*` | SIF | 感測器串流。**一個 AXIS 封包 = 一個 frame**；`tuser[0]` = 這個 beat 不經過重排（bypass），`tuser[1]` = line 結束 |
| out | `o_axis_tready` | SIF | |
| out | `o_axis_*[VP_COUNT]` | HIF | 每個 VP 一條 AXIS |
| out | `o_sof[VP_COUNT]` | HIF | frame 開始脈衝（所有 VP 相同） |

## 內部結構

```mermaid
flowchart LR
  IN(["i_axis_*<br/>SIF clk"])
  SCH["排程 FSM<br/>IDLE / WAIT / RUN / PATTERN / PAD / WAIT2"]
  PIPE["輸入歷史<br/>din_pipe[NUM_CYCLES]"]
  subgraph PROG["PACKETIZER_ENABLE = 1"]
    RAM["設定 RAM<br/>16 列 × (cycle_sel + sort_sel + vp_ctrl)"]
    SORT["odd_even_gen × NUM_CYCLES<br/>可程式化置換"]
    CSEL["cycle select<br/>每個輸出單位選歷史中的哪一拍"]
  end
  subgraph STAT["PACKETIZER_ENABLE = 2"]
    MAP["pattern map（常數）<br/>每個輸出 bit ← 歷史中的某個 bit"]
  end
  VP["virtual_port × VP_COUNT<br/>累積 → dual-clock FIFO"]
  OUT(["o_axis_*[VP]<br/>HIF clk"])
  IN --> SCH --> PIPE
  PIPE --> SORT --> CSEL --> VP
  RAM --> SORT & CSEL & VP
  PIPE --> MAP --> VP
  VP --> OUT
```

## 行為

### 1. 排程 FSM（`packetizer_top`）

設定一個「pattern」：最多 16 列（`max_addr + 1`），每列決定這一拍要不要讀新的輸入 beat（`ld_arr` 的對應 bit）。重排網路依目前列號（`ram_rd_addr`）選擇路由。

| 狀態 | 說明 |
|---|---|
| `IDLE` | 等輸入；bypass 封包直接通過 |
| `WAIT` | 啟動延遲 `latency` 拍（累積足夠歷史） |
| `RUN` | 依 pattern 逐列執行；`ld_arr[row] = 0` 的列不讀輸入（`pack_stall`），用既有歷史產生輸出 |
| `WAIT2` / `PATTERN` | line 或 frame 結束時把 pattern 剩下的列跑完 |
| `PAD` | `pad_enable` 時把 line 補到 64 byte 的整數倍 |

line 結束由輸入 `tuser[1]` 標示，frame 結束由 `tlast` 標示。

### 2. 可程式化模式（`packetizer.sv`）

每個 pattern 列的設定包含三部分，存在 16 深的分散式 RAM 裡（[L69–L123](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/packetizer/packetizer.sv#L69-L123)）：

| 欄位 | 寬度 | 作用 |
|---|---|---|
| cycle select（CLEAR） | `(DIN_WIDTH / SORT_RESOLUTION) × ⌈log2(NUM_CYCLES+1)⌉` | 每個輸出單位取自歷史中的第幾拍；0 = 填 0 |
| sort select | `CTRL_WIDTH_SORT × NUM_CYCLES` | 每個 `odd_even_gen` 的交換開關 |
| VP control | `CTRL_WIDTH_VP × VP_COUNT` | 這一列的結果寫入哪個 VP、寫多少 |

**`odd_even_gen`** 是 Batcher odd-even merge 排序網路的結構，但比較器換成由設定位元控制的交換開關，所以它是一個可程式化的置換網路：任何輸入單位都可以搬到任何輸出位置。每 3 級插一級暫存器（`PIPE_DEPTH = 3`）。開關數 `ODD_EVEN_SIZE_VEC` 與級數 `ODD_EVEN_DEPTH_VEC` 依 `DIN_WIDTH / SORT_RESOLUTION` 查表（例如 32 個單位：191 個開關、15 級）。

設定寫入：host 先寫 `pack_ram_addr`，再寫 `pack_ram_data`。`packetizer_top` 偵測對 offset 0x08 的 APB 寫入（[L140](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/packetizer/packetizer_top.sv#L140)），經 3 級同步器到 SIF 時脈，在下降緣寫入 RAM。`pack_ram_addr[15:4]` 選 RAM 區塊、`[3:0]` 選列。

VP 選擇的特殊情況：`CTRL_WIDTH_VP == 2` 且 `W_USER > 2` 時，VP 由輸入 `tuser[3:2]` 決定（[L239–L241](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/packetizer/packetizer.sv#L239-L241)），可以讓感測器端用 tuser 把資料導到不同 VP（例如依 MIPI virtual channel 分流）。

### 3. 固定 pattern 模式（`packetizer_static.sv`）

pattern 在合成時就固定，存在 `packetizer_pkg.sv`（由工具產生）：

| ID | Pattern | 支援的 `DIN_WIDTH` |
|---|---|---|
| 0 | bypass | 全部 |
| 1 | `CSI2_RAW10` | 8 / 16 / 32 / 64 |
| 2 | `CSI2_RAW12` | 8 / 16 / 32 / 64 |

每個 pattern 是一個常數向量：`[63:0]` header（`NUM_CYCLES`、`LD_ARR`、`MAX_ADDR`、`LATENCY`、`PATTERN_ROWS`），之後是每列每個輸出 bit 的來源 index（`input_cycle × DIN_WIDTH + input_bit`，全 1 = 清 0）。合成後每個輸出 bit 只是一個依列號選擇的多工器，沒有排序網路。

執行時用 `pack_scratch[5:0]` 選 pattern；不支援的 ID 自動退回 bypass。

### 4. Virtual Port（`virtual_port.sv`）

`DYNAMIC_VP = 0`（`HOLOLINK_top` 的設定）時，VP control = `{select, commit}`：`commit` 時把重排結果的第 `select` 段（`VP_SIZE` bit）寫入 FIFO。FIFO 是雙時脈 `axis_buffer`（`VP_SIZE` → `DOUT_WIDTH`），深度約 2 個 MTU 的資料量。

輸出 `tvalid` 有額外閘控（[L256](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/packetizer/virtual_port.sv#L256)）：FIFO 不是 almost empty、或下游 ready、或 FIFO 裡有完整 frame 結尾時才放行。這讓 `dp_pkt` 每次拿到的資料盡量連續。

Bypass 模式（`PACKETIZER_ENABLE = 0`）只有 `virtual_port`；`duplicate = 1` 時同一份資料寫入所有 VP。

### 5. 流量控制

`o_axis_tready = last_tready & buf_rd_req`（[L598](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/packetizer/packetizer_top.sv#L598)）：

- `pack_tready = !(|vp_almost_full)`：任一 VP 快滿就停。
- `last_tready`：在途的 frame 結尾最多 2 個（`last_buf` 計數，HIF 端送出 `tlast` 時經 `pulse_sync` 回來減 1）。

### 6. SOF

`sif_sof` = frame 的第一個 beat 被接受（[L242](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/packetizer/packetizer_top.sv#L242)），經 `pulse_sync` 到 HIF 時脈，所有 VP 共用。`dp_pkt_ts` 用它記錄 frame 開始的 PTP 時間。

## 暫存器

基底 `0x0100_0000 + SIF × 0x1_0000`（[regmap.md](../registers/regmap.md#packetizer-register)）。

| Offset | 名稱 | 位元 | 說明 |
|---|---|---|---|
| 0x00 | `pack_scratch` | [5:0] | 固定 pattern 模式的 pattern ID |
| 0x04 | `pack_ram_addr` | [15:0] | 設定 RAM 位址 |
| 0x08 | `pack_ram_data` | [31:0] | 寫入即觸發 RAM 寫入 |
| 0x0C | `pack_ctrl` | [15:0] | `ld_arr`（可程式化模式） |
| | | [16] | `pad_enable`：line 補到 64 byte |
| | | [17] | `duplicate`：寫入所有 VP |
| | | [23:20] | `max_addr` |
| | | [27:24] | `latency` |
| | | [28] | 啟用 packetizer（0 = bypass） |
| 0x80 | `pack_tvalid_cnt` | | 輸入 `tvalid` 拍數 |
| 0x84 | `pack_psn_cnt` | | 輸入 frame 數 |

## 注意事項

1. 暫存器的 `s_apb_reg` 跨到 SIF 時脈（`i_pclk = i_sclk`），不是 HIF。
2. `PAD_CYCLES = 64 / (DIN_WIDTH/8)`：line 補齊是以輸入寬度計算。
3. host 軟體的 `PacketizerProgram`（`src/hololink/core/packetizer_program.cpp`）負責產生可程式化模式的 RAM 內容；release notes 提到它的 `get_output_size()` 以「整數個 pattern 循環」計算輸出大小。
