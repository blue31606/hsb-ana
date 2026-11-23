# Bridge 模式（`routing_table`、`bridge_pkt_proc`）

## 概要

定義 `BRIDGE_IF_INST` 時，HSB 不再是「感測器 → 封包」的轉換器，而是一個小型 Ethernet switch：SIF 介面被當作額外的 Ethernet 埠（例如接另一顆 PHY），封包在 host 埠與 SIF 埠之間轉送，並對 PTP 做透明時鐘（transparent clock）修正。

| 檔案 | 行數 | 功能 |
|---|---|---|
| [`routing_table/routing_table.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/routing_table/routing_table.sv) | 240 | MAC 學習與查詢（CAM） |
| [`routing_table/bridge_pkt_proc.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/routing_table/bridge_pkt_proc.sv) | 785 | 轉送、緩衝、PTP residence time |

實例：[`HOLOLINK_top.sv#L1168–L1330`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/top/HOLOLINK_top.sv#L1168-L1330)。分析深度：`routing_table` 逐行；`bridge_pkt_proc` 轉送規則與 PTP 部分。

Bridge 模式下被移除：`packetizer`、`dp_pkt_top`、`sensor_tx_pkt_proc`、`tx_stream_buffer`、`pause_gen`；`ptp_top` 的 TX 被關掉（只收不送）。

## 架構

```mermaid
flowchart LR
  HRX(["host 埠 RX<br/>rx_parser.o_btx<br/>（dest MAC ≠ 本機）"])
  SRX(["SIF RX[n]<br/>axis_buffer 2×MTU"])
  RT["routing_table<br/>64 筆 CAM<br/>key = MAC、data = SIF 埠"]
  BP["bridge_pkt_proc<br/>仲裁・多工・PTP 修正"]
  HTX(["host 埠 TX<br/>eth_pkt 第 5 埠"])
  STX(["SIF TX[n]"])
  SRX -- "學習 src MAC" --> RT
  HRX -- "查 dest MAC" --> RT --> BP
  HRX --> BP
  SRX --> BP
  BP --> HTX & STX
```

## `routing_table`

- **學習**：只從 SIF 埠學。每個 SIF 封包的前 16 byte 被攤平，取 src MAC 寫入 CAM（data = 來源 SIF 的 one-hot）。CAM 已有相同 key 時不重寫；CAM 滿了就不再學。**沒有老化，也沒有刪除**（`cam_del` 恆為 0）。
- **查詢**：host 埠的封包用 dest MAC 查 CAM，查詢優先於學習。

  | dest MAC | 目的埠 |
  |---|---|
  | `FF:FF:FF:FF:FF:FF`、PTP multicast | 全部 |
  | 全 0 | 丟棄 |
  | CAM 命中 | 對應 SIF 埠 |
  | CAM 未命中 | **丟棄**（不 flooding） |

- 同時辨識 SIF 端的 PTP Delay_Req（`o_is_del_req`），給 residence time 計算用。

CAM（`misc/cam.sv`）是平行比對的暫存器陣列，比對與寫入各有一拍暫存。

## `bridge_pkt_proc`

### 轉送規則

| 方向 | 規則 |
|---|---|
| host → SIF | 依 `routing_table` 查詢結果 |
| host → host | 查詢結果中的 host 位元 & `ctrl_reg[2h+1]`，並排除來源自己 |
| SIF → host | 不看 MAC：host `j` 接收 SIF `i` 的條件是 `ctrl_reg[2j+2][i] = 1`（訂閱）；PTP 封包改看 `ctrl_reg[0][j]`（廣播埠） |
| SIF → SIF | 不支援 |

一個來源只有在所有目的埠都不忙、緩衝也不快滿時才被授權（`will_rec` 檢查），一次送到多個目的埠時同時寫入。

host → SIF 方向：host 封包要等 CAM 回應才知道去哪，所以 `bridge_pkt_proc` 在查詢期間對 `rx_parser` 背壓（`o_hif_axis_tready = 0`）。這是 `rx_parser` 唯一會被背壓的輸出。

### PTP 透明時鐘

- 計算 PTP Sync 在 host 埠的 residence time（從收到到轉出）與 SIF 端 Delay_Req 的 residence time，以拍數 × 時脈週期換算成奈秒。
- 轉出 Follow_Up 時把 host 端 residence time OR 進 correctionField；轉出 Delay_Resp 時加 SIF 端的值（`axis_mask`）。
- `rx_parser` 把 PTP 訊息類型編碼在 `o_btx_axis_tuser`（1 = Sync、2 = Follow_Up、3 = Delay_Resp）供這裡使用。

## 暫存器

基底 `0x0600_0000`。`bridge_nctrl = 2 × NUM_HOST + 1`：

| Index | 說明 |
|---|---|
| 0 | `[NUM_HOST-1:0]` 哪些 host 埠是廣播 / PTP 埠 |
| 2h + 1 | host `h` 的封包可以轉給哪些 host 埠 |
| 2h + 2 | host `h` 訂閱哪些 SIF 埠 |

## 注意事項

1. 未知 unicast 一律丟棄；CAM 沒有老化與刪除，裝置更換 MAC 後要 reset 才能重新學習。
2. correctionField 的修正是用 `axis_mask` 的 **OR**（`OP = "OR"`），不是加法。只有在原本的 correctionField 對應位元為 0 時結果才等於相加；master 送來的 correctionField 不為 0 時，修正值會出錯（推斷，需以實際封包驗證）。
3. `rx_parser` 帶 VLAN 的 PTP 封包，messageType 從錯誤的 byte 讀出（見 [rx_parser 注意事項 3](rx_parser.md#注意事項)），會影響這裡的 PTP 類型編碼。
