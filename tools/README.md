# 工具

所有工具都只用 Python 標準函式庫，對固定 commit 的上游原始碼執行：

```sh
git clone https://github.com/nvidia-holoscan/holoscan-sensor-bridge ../holoscan-sensor-bridge
git -C ../holoscan-sensor-bridge checkout 41cecaa81ab906a55e7ec22e5e6989f7e602a4c8
python3 tools/check_all.py ../holoscan-sensor-bridge             # 全部檢查，約 10 秒
python3 tools/check_all.py ../holoscan-sensor-bridge --models    # 加上逐拍模型，約 2 分鐘
python3 tools/check_all.py ../holoscan-sensor-bridge --regen     # 重新產生暫存器索引、板級設定表、時序圖
```

`check_all.py` 每個工具印一行摘要，接著比對 VERIFICATION 等文件中寫死的數字與工具輸出（`FACTS` 清單）；任何一項失敗、產生的檔案過期或文件數字對不上時結束碼為 1。各工具也可以單獨執行（參數都是上游路徑，`-h` 或不帶參數會印出說明）。

## 產生文件

| 工具 | 產生 |
|---|---|
| `gen_allregs.py` | [完整暫存器索引](../docs/registers/all-registers.md)：解析 `regmap_pkg.sv`（offset = index × 4，並比對原始碼註解的位址），加上模組內暫存器、RAM、周邊、參考設計；`s_apb_reg` 控制暫存器的 reset 值取自各區塊的 `RST_VAL` |
| `gen_board_table.py` | [boards.md](../docs/boards.md#設定比較) 設定比較表中由 `HOLOLINK_def.svh` 決定的列；不加 `--write` 時只比對 |
| `wave.py` | 把 `docs/timing/*.wave.json`（WaveDrom 子集）轉成 SVG。GitHub 不支援 WaveDrom，所以 SVG 也一併 commit |

## 數值驗證與逐拍模型

| 工具 | 內容 |
|---|---|
| `verify/verify_calcs.py` | 照 RTL 重寫可計算的運算（checksum、CRC、排程、版面），與獨立參考實作比對（[結果](../docs/verification-calcs.md)） |
| `model/rx_parser_model.py` | `rx_parser` 讀出路徑與 Bridge host RX 緩衝，重現 DP-1、DP-2、DP-15、BR-1 並計算各板級的線速餘裕；`--wave` 產生 `rx_parser_readout` 時序圖 |
| `model/dp_pkt_model.py` | `dp_pkt_top` header FSM 與封包交接，計算 Data Plane 封包間隔與速率（performance §3、DP-16） |
| `model/uart_rx_model.py` | UART 接收端（PE-3、PE-4） |
| `model/roce_ack_model.py` | `roce_ack` 回應決策，封包層級（TX-1、TX-2、TX-3） |
| `model/reg_cdc_model.py` | `reg_cdc` 兩時脈，算出 `s_apb_reg` 寫入不遺失所需的間隔（CP-6） |

模型照 RTL 逐暫存器人工轉寫，每個腳本都列出建模範圍與假設；任何預期不符時結束碼為 1。

## 靜態檢查

| 工具 | 檢查 |
|---|---|
| `check_links.py` | 文件中每個原始碼連結的 commit、檔案、行號範圍，以及引用處的識別字是否出現在所引行內 |
| `check_host_regs.py` | host 軟體的位址常數逐一對照 RTL 暫存器索引；`--bits` 檢查 host 寫入的常數值是否只用到 RTL 實際讀取的位元；`--reads` 檢查 host 讀取後測試的位元是否由 RTL 驅動（兩者加 `--table` 列出明細） |
| `check_unused.py` | host 從未存取的暫存器、host 定義了卻沒有使用的位址常數（分類見 [memory-map](../docs/registers/memory-map.md#host-沒有存取的暫存器)） |
| `check_issue_refs.py` | 問題編號：文件引用的編號都存在、每個編號都在模組文件中有描述、`issues.md` 的編號連到該處（`--write` 更新連結）；印出問題數量統計 |
| `check_tests.py` | `tests/` 草稿用到的埠、參數、testbench 名稱、task 參數個數與階層路徑 |
| `check_coverage.py` | `nv_hsb_ip` 每個檔案與模組是否出現在文件中；文件表格的「行數」欄與 reset 值；所有 Markdown 表格依 GitHub 切法的欄數 |
| `scan_ports.py` | 所有實例中空接的握手 / 狀態埠與綁常數的輸入；`--all` 列出全部 |
| `scan_cdc.py` | 檔案內跨時脈的粗篩（含經過組合邏輯者） |
| `scan_cdc_ports.py` | 模組之間（經由埠）的跨時脈：由下而上整理每個模組的時脈埠、輸出時脈與輸入取樣時脈，在父模組比對；也找出同步在錯誤時脈上的輸入 |

`check_links.py`、`check_host_regs.py --reads`、`scan_ports.py`、`scan_cdc.py`、`scan_cdc_ports.py` 找到、但人工讀過分類的項目列在 [`reviewed.txt`](reviewed.txt)（格式見檔頭），之後不再列出；有未分類的新項目時結束碼為 1。
