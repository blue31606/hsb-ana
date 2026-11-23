# 驗證環境（`nv_hsb_ip_simple_tb`）

原始碼：[`fpga/nv_hsb_ip_simple_tb/`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/tree/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip_simple_tb)（約 5100 行）。分析深度：Makefile 與檔案結構。

## 組成

| 檔案 | 行數 | 內容 |
|---|---|---|
| `nv_hsb_ip_simple_tb.sv` | 2008 | 頂層：實例化 `HOLOLINK_top`，產生時脈、reset，執行測試流程 |
| `fpga_sensor_top_pkg.svh` | | 測試用的 `HOLOLINK_def` 設定 |
| `eeprom_i2c_model.sv` | 407 | I2C EEPROM 模型（讓 `eeprom_info` 能完成開機） |
| `tb_pkg/hololink_tb_pkg.sv` | 573 | 共用型別、log 巨集 |
| `tb_lib/hololink_ecb_tasks.svh` | 321 | 透過 Ethernet 送 ECB 讀寫 |
| `tb_lib/hololink_roce_helpers.svh` | 379 | RoCE 封包組裝與檢查 |
| `tb_lib/hololink_coe_helpers.svh` | 384 | 1722B CoE 封包檢查 |
| `tb_lib/hololink_sensor_stim.svh` | 334 | SIF RX 感測器資料激勵 |
| `tb_lib/hololink_host2sen_stim.svh` / `_scbd.svh` | 226 / 116 | host → SIF TX 激勵與 scoreboard |
| `tb_lib/hololink_monitors.svh` | 333 | HIF / SIF 監視器 |

## 測試模式

`make run` / `make coe`，以 `TEST_MODE` 選擇：

| `TEST_MODE` | 內容 |
|---|---|
| `SINGLE_SENSOR` | sensor 0 → host 0 |
| `ALL_SENSORS` | 所有 SIF RX → `TARGET_HOST` 指定的 host 埠 |
| `HOST2SEN` | host → sensor：UC RoCE SEND 經 STX 路徑到 SIF TX |

`make coe` 以 1722B CoE 格式跑 Data Plane。測試流程：等 `init_done`（含模擬 BOOTP 回應）→ 經 ECB 設定暫存器與 packetizer（pass-through）→ 送感測器資料或 host 封包 → 監視器比對。

## 需求

- 模擬器：VCS 或 Xcelium（`SIMULATOR=VCS|XCELIUM`）。
- `DUMP=1` 產生 FSDB 波形（VCS），`verdi_config_file` 為 Verdi 設定。
- `run_parallel_configs.py`：同一次編譯平行跑多個設定。
