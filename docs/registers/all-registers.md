# 完整暫存器索引（自動產生）

本檔由 `tools/gen_allregs.py` 產生，請勿手動修改。

所有 APB 可存取的暫存器依絕對位址排列（多實例的區塊列實例 0 的位址）。

- 位元細節請點各區塊的文件連結。`regmap_pkg.sv` 內的暫存器名稱連到原始碼那一行；位址 = 基底 + index × 4，index ≥ 32 是狀態暫存器（`stat_ofst = 32`）；原始碼註解寫的位址不同時標 ⚠️。
- 基底位址取自 `apb_intc_top.sv` 的 `apb_switch` 設定，host 的位址常數由 `tools/check_host_regs.py` 逐一比對。
- 類型：RW = 控制暫存器；RO = 狀態暫存器（`s_apb_reg` 的 index ≥ 32）；RW* = RTL 也會寫入；W = 只寫。
- 未定義位址讀回 `0xBADADD12`（[apb.md](../modules/apb.md#watchdog)）。

## 區塊總覽

| 基底 | 區塊 | RTL | 間距 / 數量 | 暫存器數 |
|---|---|---|---|---:|
| `0x0000_0000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) | `glb_ctrl_top` | - | 30 |
| `0x0000_0100` | [PTP Register](../modules/ptp.md#暫存器) | `ptp_top` | - | 18 |
| `0x0000_0200` | [Control Bus Event](../modules/event.md#暫存器) | `ctrl_bus_evt_int` | - | 14 |
| `0x0000_0300` | [ECB](../modules/rx_ls_parser.md#暫存器) | `ecb_rdwr_ctrl` | - | 7 |
| `0x0000_1000` | [Data Plane 設定 RAM（APB RAM 0）](../modules/dp_pkt_top.md#4-設定-ram) | `dp_pkt_top` | 0x40 / VP（最多 32 個） | 13 |
| `0x0000_2000` | [事件序列 RAM（APB RAM 1）](../modules/event.md#2-序列器apb-時脈) | `ctrl_bus_evt_fsm` | 1024 word | 1 |
| `0x0000_3000` | [RoCE QP RAM（APB RAM 2）](../modules/roce_ack.md) | `roce_ack` | - | 1 |
| `0x0100_0000` | [Packetizer Register](../modules/packetizer.md#暫存器) | `packetizer_top` | 0x1_0000 / SIF RX（SENSOR_RX_IF_INST 個） | 6 |
| `0x0100_0100` | [Sensor RX Data Generator](../modules/data_gen.md#暫存器) | `data_gen` | 0x1_0000 / SIF RX（SENSOR_RX_IF_INST 個） | 7 |
| `0x0120_0000` | [SIF TX（tx_stream_buffer）](../modules/tx_stream_buffer.md#暫存器) | `tx_stream_buffer` | 0x1_0000 / SENSOR_TX_IF_INST | 8 |
| `0x0200_0000` | [Instruction Decoder Registers](../modules/rx_parser.md#暫存器) | `rx_parser` | 0x1_0000 / host（HOST_IF_INST 個） | 12 |
| `0x0200_0100` | [Ethernet Packet](../modules/eth_pkt.md#暫存器) | `eth_pkt` | 0x1_0000 / host（HOST_IF_INST 個） | 4 |
| `0x0200_0300` | [Dataplane Packetizer](../modules/dp_pkt_top.md#暫存器) | `dp_pkt_top` | 0x1_0000 / host（HOST_IF_INST 個） | 7 |
| `0x0300_0000` | [SPI](../modules/peripherals.md#spi--qspi) | `spi_ctrl_fsm` | -（SPI_INST 條匯流排共用） | 7 |
| `0x0300_0200` | [I2C](../modules/peripherals.md#i2c) | `i2c_ctrl_fsm` | -（I2C_INST 條匯流排共用） | 8 |
| `0x0300_0400` | [UART](../modules/peripherals.md#uart) | `uart_ctrl_fsm` | - | 10 |
| `0x0600_0000` | [Bridge（BRIDGE_IF_INST）](../modules/bridge.md#暫存器) | `bridge_pkt_proc` | - | 3 |
| `0x7000_0000` | [vsync_gen（CPNX100 使用者 APB）](../modules/ref_design.md#vsync_gen) | `vsync_gen` | - | 6 |
| `0x7000_0800` | [delayed_io（CPNX100 使用者 APB）](../modules/ref_design.md#delayed_io) | `delayed_io` | - | 10 |
| `0x8000_0000` | [i2s_top（CPNX100 使用者 APB）](../modules/ref_design.md#i2s_top) | `i2s_top` | - | 13 |

## 全部暫存器

Reset 欄：`s_apb_reg` 控制暫存器的 `RST_VAL`（沒有給的區塊為 0）；空白表示不是 `s_apb_reg` 的控制暫存器，reset 值見各區塊文件。

| 位址 | 名稱 | 類型 | Reset | 區塊 | 說明 |
|---|---|---|---|---|---|
| `0x0000_0000` | [`glb_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L87) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0004` | [`hsb_ctrl_0`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L88) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0008` | [`hsb_ctrl_1`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L89) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_000C` | [`gpio_o_0`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L90) | RW | 板級 `GPIO_RESET_VALUE`（S10 `0x0000000F`，其他 0） | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0010` | [`gpio_o_1`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L91) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0014` | [`gpio_o_2`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L92) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0018` | [`gpio_o_3`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L93) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_001C` | [`gpio_o_4`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L94) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0020` | [`gpio_o_5`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L95) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0024` | [`gpio_o_6`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L96) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0028` | [`gpio_o_7`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L97) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_002C` | [`gpio_t_0`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L98) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0030` | [`gpio_t_1`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L99) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0034` | [`gpio_t_2`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L100) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0038` | [`gpio_t_3`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L101) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_003C` | [`gpio_t_4`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L102) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0040` | [`gpio_t_5`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L103) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0044` | [`gpio_t_6`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L104) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0048` | [`gpio_t_7`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L105) | RW | `0x00000000` | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0080` | [`hsb_ver`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L107) | RO |  | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0084` | [`hsb_date`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L108) | RO |  | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0088` | [`hsb_stat`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L109) | RO |  | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_008C` | [`gpio_i_0`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L110) | RO |  | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0090` | [`gpio_i_1`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L111) | RO |  | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0094` | [`gpio_i_2`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L112) | RO |  | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0098` | [`gpio_i_3`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L113) | RO |  | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_009C` | [`gpio_i_4`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L114) | RO |  | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_00A0` | [`gpio_i_5`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L115) | RO |  | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_00A4` | [`gpio_i_6`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L116) | RO |  | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_00A8` | [`gpio_i_7`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L117) | RO |  | [Global Register](../modules/boot_and_reset.md#glb_ctrl_top) |  |
| `0x0000_0100` | [`ptp_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L126) | RW | `0x00000000` | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_0104` | [`ptp_ctrl`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L127) | RW | `0x00000003` | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_0108` | [`ptp_ctrl_profile`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L128) | RW | `0x00000000` | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_010C` | [`ptp_ctrl_dly`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L129) | RW | `0x00000038` | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_0110` | [`ptp_ctrl_dpll_cfg1`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L130) | RW | `0x00000002` | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_0114` | [`ptp_ctrl_dpll_cfg2`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L131) | RW | `0x00000002` | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_0118` | [`ptp_ctrl_avg_fact`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L132) | RW | `0x00000003` | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_011C` | [`ptp_ctrl_domain`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L133) | RW | `0x00000000` | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_0120` | [`ptp_ctrl_pcp`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L134) | RW | `0x00000000` | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_0180` | [`ptp_sync_ts_0`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L136) | RO |  | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_0184` | [`ptp_sync_cf_0`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L137) | RO |  | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_0188` | [`ptp_sync_stat`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L138) | RO |  | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_018C` | [`ptp_ofm`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L139) | RO |  | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_0190` | [`ptp_mean_dly`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L140) | RO |  | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_0194` | [`ptp_inc`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L141) | RO |  | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_0198` | [`ptp_fa_adj`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L142) | RO |  | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_019C` | [`ptp_dly_cf_0`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L143) | RO |  | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_01A0` | [`ptp_ip_dly_asymm`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L144) | RO |  | [PTP Register](../modules/ptp.md#暫存器) |  |
| `0x0000_0200` | [`ctrl_evt_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L212) | RW | `0x00000000` | [Control Bus Event](../modules/event.md#暫存器) |  |
| `0x0000_0204` | [`ctrl_evt_rising`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L213) | RW | `0x00000000` | [Control Bus Event](../modules/event.md#暫存器) |  |
| `0x0000_0208` | [`ctrl_evt_falling`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L214) | RW | `0x00000000` | [Control Bus Event](../modules/event.md#暫存器) |  |
| `0x0000_020C` | [`ctrl_evt_clear`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L215) | RW | `0x00000000` | [Control Bus Event](../modules/event.md#暫存器) |  |
| `0x0000_0210` | [`ctrl_evt_host_mac_addr_lo`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L216) | RW | `0x00000000` | [Control Bus Event](../modules/event.md#暫存器) |  |
| `0x0000_0214` | [`ctrl_evt_host_mac_addr_hi`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L217) | RW | `0x00000000` | [Control Bus Event](../modules/event.md#暫存器) |  |
| `0x0000_0218` | [`ctrl_evt_host_ip_addr`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L218) | RW | `0x00000000` | [Control Bus Event](../modules/event.md#暫存器) |  |
| `0x0000_021C` | [`ctrl_evt_host_udp_port`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L219) | RW | `0x00000000` | [Control Bus Event](../modules/event.md#暫存器) |  |
| `0x0000_0220` | [`ctrl_evt_dev_udp_port`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L220) | RW | `0x00000000` | [Control Bus Event](../modules/event.md#暫存器) |  |
| `0x0000_0224` | [`ctrl_evt_apb_interrupt_en`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L221) | RW | `0x00000000` | [Control Bus Event](../modules/event.md#暫存器) |  |
| `0x0000_0228` | [`ctrl_evt_apb_timeout`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L222) | RW | `0x00000000` | [Control Bus Event](../modules/event.md#暫存器) |  |
| `0x0000_022C` | [`ctrl_evt_sw_event`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L223) | RW | `0x00000000` | [Control Bus Event](../modules/event.md#暫存器) |  |
| `0x0000_0230` | [`ctrl_evt_vlan`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L224) | RW | `0x00000000` | [Control Bus Event](../modules/event.md#暫存器) |  |
| `0x0000_0280` | [`ctrl_evt_stat`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L226) | RO |  | [Control Bus Event](../modules/event.md#暫存器) |  |
| `0x0000_0300` | [`ecb_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L196) | RW | `0x00000000` | [ECB](../modules/rx_ls_parser.md#暫存器) |  |
| `0x0000_0304` | [`ecb_addr_lsb`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L197) | RW | `0x00000000` | [ECB](../modules/rx_ls_parser.md#暫存器) | ⚠️ 原始碼註解寫 `0x0008` |
| `0x0000_0308` | [`ecb_addr_msb`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L198) | RW | `0x00000000` | [ECB](../modules/rx_ls_parser.md#暫存器) | ⚠️ 原始碼註解寫 `0x0004` |
| `0x0000_030C` | [`ecb_rkey`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L199) | RW | `0x00000000` | [ECB](../modules/rx_ls_parser.md#暫存器) |  |
| `0x0000_0310` | [`ecb_pkey`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L200) | RW | `0x00000000` | [ECB](../modules/rx_ls_parser.md#暫存器) |  |
| `0x0000_0314` | [`ecb_dest_qp`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L201) | RW | `0x00000000` | [ECB](../modules/rx_ls_parser.md#暫存器) |  |
| `0x0000_0380` | [`ecb_stat`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L203) | RO |  | [ECB](../modules/rx_ls_parser.md#暫存器) |  |
| `0x0000_1000` | `DP_QP` | RW |  | [Data Plane 設定 RAM（APB RAM 0）](../modules/dp_pkt_top.md#4-設定-ram) | [23:0] dest QP（CoE：[5:0] channel）、[24] 1722B、[31:25] line 長度 log2 |
| `0x0000_1004` | `DP_RKEY` | RW |  | [Data Plane 設定 RAM（APB RAM 0）](../modules/dp_pkt_top.md#4-設定-ram) | RETH R_Key |
| `0x0000_1008` | `DP_PAGE_LSB` | RW |  | [Data Plane 設定 RAM（APB RAM 0）](../modules/dp_pkt_top.md#4-設定-ram) | [31:7] buffer 起點（page） |
| `0x0000_100C` | `DP_PAGE_MSB` | RW |  | [Data Plane 設定 RAM（APB RAM 0）](../modules/dp_pkt_top.md#4-設定-ram) | [0] 起點 page bit 25、[31:1] VA[63:33] |
| `0x0000_1010` | `DP_PAGE_INC` | RW |  | [Data Plane 設定 RAM（APB RAM 0）](../modules/dp_pkt_top.md#4-設定-ram) | buffer 間距（page） |
| `0x0000_1014` | `DP_MAX_BUFF` | RW |  | [Data Plane 設定 RAM（APB RAM 0）](../modules/dp_pkt_top.md#4-設定-ram) | [27:16] 起始 / [11:0] 結束 buffer 指標 |
| `0x0000_1018` | `DP_BUFFER_LENGTH` | RW |  | [Data Plane 設定 RAM（APB RAM 0）](../modules/dp_pkt_top.md#4-設定-ram) | frame byte 數 |
| `0x0000_1020` | `DP_HOST_MAC_LOW` | RW |  | [Data Plane 設定 RAM（APB RAM 0）](../modules/dp_pkt_top.md#4-設定-ram) | host MAC [31:0] |
| `0x0000_1024` | `DP_HOST_MAC_HIGH` | RW |  | [Data Plane 設定 RAM（APB RAM 0）](../modules/dp_pkt_top.md#4-設定-ram) | host MAC [47:32] |
| `0x0000_1028` | `DP_HOST_IP` | RW |  | [Data Plane 設定 RAM（APB RAM 0）](../modules/dp_pkt_top.md#4-設定-ram) | host IPv4 |
| `0x0000_102C` | `DP_HOST_UDP_PORT` | RW |  | [Data Plane 設定 RAM（APB RAM 0）](../modules/dp_pkt_top.md#4-設定-ram) | [15:0] UDP 埠、[16] md_disable |
| `0x0000_1034` | `DP_VLAN` | RW |  | [Data Plane 設定 RAM（APB RAM 0）](../modules/dp_pkt_top.md#4-設定-ram) | [15:0] TCI、[16] 插入 VLAN |
| `0x0000_103C` | `PSN` | RW* |  | [Data Plane 設定 RAM（APB RAM 0）](../modules/dp_pkt_top.md#4-設定-ram) | FSM 回寫目前 PSN |
| `0x0000_2000` | `程式 / 資料` | RW |  | [事件序列 RAM（APB RAM 1）](../modules/event.md#2-序列器apb-時脈) | 每個事件一段序列：POLL / WRITE / READ / NOP；READ 結果寫回 RAM |
| `0x0000_3000` | `QP 資訊` | RW |  | [RoCE QP RAM（APB RAM 2）](../modules/roce_ack.md) | SIF_TX_ROCE_RC_ENABLE 時使用；只有 host 0 的 RAM 回應讀取 |
| `0x0100_0000` | [`pack_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L252) | RW | `0x00000000` | [Packetizer Register](../modules/packetizer.md#暫存器) |  |
| `0x0100_0004` | [`pack_ram_addr`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L253) | RW | `0x00000000` | [Packetizer Register](../modules/packetizer.md#暫存器) |  |
| `0x0100_0008` | [`pack_ram_data`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L254) | RW | `0x00000000` | [Packetizer Register](../modules/packetizer.md#暫存器) |  |
| `0x0100_000C` | [`pack_ctrl`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L255) | RW | `0x00000000` | [Packetizer Register](../modules/packetizer.md#暫存器) |  |
| `0x0100_0080` | [`pack_tvalid_cnt`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L257) | RO |  | [Packetizer Register](../modules/packetizer.md#暫存器) |  |
| `0x0100_0084` | [`pack_psn_cnt`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L258) | RO |  | [Packetizer Register](../modules/packetizer.md#暫存器) |  |
| `0x0100_0100` | [`sen_rx_data_gen_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L267) | RW | `0x00000000` | [Sensor RX Data Generator](../modules/data_gen.md#暫存器) |  |
| `0x0100_0104` | [`sen_rx_data_gen_ena`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L268) | RW | `0x00000000` | [Sensor RX Data Generator](../modules/data_gen.md#暫存器) |  |
| `0x0100_0108` | [`sen_rx_data_gen_mode`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L269) | RW | `0x00000000` | [Sensor RX Data Generator](../modules/data_gen.md#暫存器) |  |
| `0x0100_010C` | [`sen_rx_data_gen_size`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L270) | RW | `0x00000000` | [Sensor RX Data Generator](../modules/data_gen.md#暫存器) |  |
| `0x0100_0110` | [`sen_rx_data_gen_output_rate`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L271) | RW | `0x00000000` | [Sensor RX Data Generator](../modules/data_gen.md#暫存器) |  |
| `0x0100_0114` | [`sen_rx_data_gen_pps_sync`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L272) | RW | `0x00000000` | [Sensor RX Data Generator](../modules/data_gen.md#暫存器) |  |
| `0x0100_0124` | [`sen_rx_prbs_seed`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L273) | RW | `0x00000000` | [Sensor RX Data Generator](../modules/data_gen.md#暫存器) |  |
| `0x0120_0000` | `ctrl` | RW | `0x00000000` | [SIF TX（tx_stream_buffer）](../modules/tx_stream_buffer.md#暫存器) | [0] 輸出啟用、[1] pause、[2] 程式化門檻、[4] 統計 reset、[8] 除錯清空 |
| `0x0120_0004` | `sw_almost_full_thresh` | RW | `0x00000000` | [SIF TX（tx_stream_buffer）](../modules/tx_stream_buffer.md#暫存器) |  |
| `0x0120_0008` | `sw_almost_empty_thresh` | RW | `0x00000000` | [SIF TX（tx_stream_buffer）](../modules/tx_stream_buffer.md#暫存器) |  |
| `0x0120_000C` | `host_pause_mapping` | RW | `0x00000000` | [SIF TX（tx_stream_buffer）](../modules/tx_stream_buffer.md#暫存器) | 哪些 host 埠送 PAUSE |
| `0x0120_0010` | `pause_quanta` | RW | `0x00000000` | [SIF TX（tx_stream_buffer）](../modules/tx_stream_buffer.md#暫存器) | [15:0] |
| `0x0120_0080` | `high_watermark` | RO |  | [SIF TX（tx_stream_buffer）](../modules/tx_stream_buffer.md#暫存器) |  |
| `0x0120_0084` | `low_watermark` | RO |  | [SIF TX（tx_stream_buffer）](../modules/tx_stream_buffer.md#暫存器) |  |
| `0x0120_0088` | `status` | RO |  | [SIF TX（tx_stream_buffer）](../modules/tx_stream_buffer.md#暫存器) | [1] overflow、[0] underflow |
| `0x0200_0000` | [`inst_dec_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L160) | RW | `0x00000000` | [Instruction Decoder Registers](../modules/rx_parser.md#暫存器) |  |
| `0x0200_0004` | [`inst_dec_ctrl`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L161) | RW | `0x00000000` | [Instruction Decoder Registers](../modules/rx_parser.md#暫存器) |  |
| `0x0200_0008` | [`lpbk_udp_port`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L162) | RW | `0x00000000` | [Instruction Decoder Registers](../modules/rx_parser.md#暫存器) |  |
| `0x0200_000C` | [`roce_ecb_dest_qp`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L163) | RW | `0x00001000` | [Instruction Decoder Registers](../modules/rx_parser.md#暫存器) |  |
| `0x0200_0010` | [`inst_dec_rsvd_1`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L164) | RW | `0x00000000` | [Instruction Decoder Registers](../modules/rx_parser.md#暫存器) |  |
| `0x0200_0014` | [`inst_dec_rsvd_2`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L165) | RW | `0x00000000` | [Instruction Decoder Registers](../modules/rx_parser.md#暫存器) |  |
| `0x0200_0018` | [`static_hif_qp`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L166) | RW | `0x00000000` | [Instruction Decoder Registers](../modules/rx_parser.md#暫存器) |  |
| `0x0200_001C` | [`inst_dec_ack_ctrl`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L167) | RW | `0x00000000` | [Instruction Decoder Registers](../modules/rx_parser.md#暫存器) |  |
| `0x0200_0020` | [`ecb_udp_port`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L168) | RW | `0x00002000` | [Instruction Decoder Registers](../modules/rx_parser.md#暫存器) |  |
| `0x0200_0024` | [`stx_udp_port`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L169) | RW | `0x000012B7` | [Instruction Decoder Registers](../modules/rx_parser.md#暫存器) |  |
| `0x0200_0080` | [`inst_dec_stat`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L171) | RO |  | [Instruction Decoder Registers](../modules/rx_parser.md#暫存器) |  |
| `0x0200_0084` | [`ipv4_chksum_err_cnt`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L172) | RO |  | [Instruction Decoder Registers](../modules/rx_parser.md#暫存器) |  |
| `0x0200_0100` | [`eth_pkt_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L181) | RW | `0x00000000` | [Ethernet Packet](../modules/eth_pkt.md#暫存器) |  |
| `0x0200_0104` | [`eth_pkt_ctrl`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L182) | RW | `0x00000000` | [Ethernet Packet](../modules/eth_pkt.md#暫存器) |  |
| `0x0200_0108` | [`eth_pkt_hp_cnt`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L183) | RW | `0x00000000` | [Ethernet Packet](../modules/eth_pkt.md#暫存器) |  |
| `0x0200_0180` | [`eth_pkt_stat`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L186) | RO |  | [Ethernet Packet](../modules/eth_pkt.md#暫存器) |  |
| `0x0200_0300` | [`dp_pkt_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L235) | RW | `0x00000000` | [Dataplane Packetizer](../modules/dp_pkt_top.md#暫存器) |  |
| `0x0200_0304` | [`dp_pkt_len`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L236) | RW | `0x000005CE` | [Dataplane Packetizer](../modules/dp_pkt_top.md#暫存器) |  |
| `0x0200_0308` | [`dp_pkt_dev_udp_port`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L237) | RW | `0x00003000` | [Dataplane Packetizer](../modules/dp_pkt_top.md#暫存器) |  |
| `0x0200_030C` | [`dp_pkt_vip_mask`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L238) | RW | `0x00000000` | [Dataplane Packetizer](../modules/dp_pkt_top.md#暫存器) |  |
| `0x0200_0310` | [`dp_pkt_crc_xor`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L239) | RW | `0x00000000` | [Dataplane Packetizer](../modules/dp_pkt_top.md#暫存器) |  |
| `0x0200_0314` | [`dp_pkt_1722B`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L240) | RW | `0x00000000` | [Dataplane Packetizer](../modules/dp_pkt_top.md#暫存器) |  |
| `0x0200_0380` | [`dp_pkt_stat`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L242) | RO |  | [Dataplane Packetizer](../modules/dp_pkt_top.md#暫存器) |  |
| `0x0300_0000` | `ctrl` | RW | `0x00000000` | [SPI](../modules/peripherals.md#spi--qspi) | [0] start |
| `0x0300_0004` | `bus_en` | RW | `0x00000000` | [SPI](../modules/peripherals.md#spi--qspi) | 選擇匯流排 |
| `0x0300_0008` | `len` | RW | `0x00000000` | [SPI](../modules/peripherals.md#spi--qspi) | [15:0] 寫入 / [31:16] 讀取 byte 數 |
| `0x0300_000C` | `cfg` | RW | `0x00000000` | [SPI](../modules/peripherals.md#spi--qspi) | [3:0] prescaler、[5:4] mode、[9:8] 資料線寬度 |
| `0x0300_0010` | `cmd` | RW | `0x00000000` | [SPI](../modules/peripherals.md#spi--qspi) | [7:0] turnaround、[15:8] 命令 byte 數 |
| `0x0300_0080` | `status` | RO |  | [SPI](../modules/peripherals.md#spi--qspi) | [0] busy、[1] 命令錯誤、[4] done |
| `0x0300_0100` | `data` | RW |  | [SPI](../modules/peripherals.md#spi--qspi) | 資料緩衝 |
| `0x0300_0200` | `ctrl` | RW | `0x00000000` | [I2C](../modules/peripherals.md#i2c) | [0] start、[1] 10-bit 位址、[25:16] 裝置位址 |
| `0x0300_0204` | `bus_en` | RW | `0x00000000` | [I2C](../modules/peripherals.md#i2c) | 選擇匯流排 |
| `0x0300_0208` | `len` | RW | `0x00000000` | [I2C](../modules/peripherals.md#i2c) | [15:0] 寫入 / [31:16] 讀取 byte 數 |
| `0x0300_020C` | `clk_cnt` | RW | `0x00000000` | [I2C](../modules/peripherals.md#i2c) | [15:0] SCL 分頻 |
| `0x0300_0210` | `stretch_timeout` | RW | `0x004C4B40` | [I2C](../modules/peripherals.md#i2c) | reset 5,000,000 |
| `0x0300_0214` | `num_trans` | RW | `0x00000000` | [I2C](../modules/peripherals.md#i2c) | [7:0] |
| `0x0300_0280` | `status` | RO |  | [I2C](../modules/peripherals.md#i2c) | [0] busy、[2] arbitration lost、[3] NACK、[4] done |
| `0x0300_0300` | `data` | RW |  | [I2C](../modules/peripherals.md#i2c) | 資料緩衝 |
| `0x0300_0400` | `ctrl` | RW | `0x00000000` | [UART](../modules/peripherals.md#uart) | 啟用、TX / RX、loopback、資料位元、parity、FIFO reset、stop bit |
| `0x0300_0404` | `baud / thresh` | RW | `0x00000000` | [UART](../modules/peripherals.md#uart) | [15:0] 鮑率除數、[23:16] / [31:24] TX FIFO 門檻 |
| `0x0300_0408` | `int_en` | RW | `0x00000000` | [UART](../modules/peripherals.md#uart) |  |
| `0x0300_040C` | `int_clr` | RW | `0x00000000` | [UART](../modules/peripherals.md#uart) |  |
| `0x0300_0410` | `glitch` | RW | `0x00000000` | [UART](../modules/peripherals.md#uart) | [3:0] 視窗寬度、[7:4] / [11:8] start / data 多數決門檻、[16] 濾波啟用 |
| `0x0300_0480` | `status` | RO |  | [UART](../modules/peripherals.md#uart) |  |
| `0x0300_0484` | `int_status` | RO |  | [UART](../modules/peripherals.md#uart) |  |
| `0x0300_0540` | `tx_data` | W |  | [UART](../modules/peripherals.md#uart) | 讀回：TX FIFO 滿時 0xFF |
| `0x0300_0544` | `rx_data` | RO |  | [UART](../modules/peripherals.md#uart) | 讀取時彈出 RX FIFO |
| `0x0300_0548` | `last_rx` | RO |  | [UART](../modules/peripherals.md#uart) | 最後收到的 byte（`ctrl[10]` 清除） |
| `0x0600_0000` | `broadcast_ports` | RW | `0x00000000` | [Bridge（BRIDGE_IF_INST）](../modules/bridge.md#暫存器) | [NUM_HOST-1:0] 廣播 / PTP 埠 |
| `0x0600_0004` | `host0_fwd_mask` | RW | `0x00000000` | [Bridge（BRIDGE_IF_INST）](../modules/bridge.md#暫存器) | index 2h+1：host h 可轉送的 host 埠 |
| `0x0600_0008` | `host0_sub_mask` | RW | `0x00000000` | [Bridge（BRIDGE_IF_INST）](../modules/bridge.md#暫存器) | index 2h+2：host h 訂閱的 SIF 埠 |
| `0x7000_0000` | `VSYNC_CONTROL` | RW | `0x00000000` | [vsync_gen（CPNX100 使用者 APB）](../modules/ref_design.md#vsync_gen) | [0] 啟用 |
| `0x7000_0004` | `VSYNC_FREQUENCY` | RW | `0x00000000` | [vsync_gen（CPNX100 使用者 APB）](../modules/ref_design.md#vsync_gen) | [3:0] 模式 |
| `0x7000_0008` | `VSYNC_DELAY` | RW | `0x00000000` | [vsync_gen（CPNX100 使用者 APB）](../modules/ref_design.md#vsync_gen) | 相對秒起點的延遲（ns） |
| `0x7000_000C` | `VSYNC_START` | RW | `0x00000000` | [vsync_gen（CPNX100 使用者 APB）](../modules/ref_design.md#vsync_gen) | [0] 初始電位 |
| `0x7000_0010` | `VSYNC_EXPOSURE` | RW | `0x00000000` | [vsync_gen（CPNX100 使用者 APB）](../modules/ref_design.md#vsync_gen) | 脈衝寬度 |
| `0x7000_0014` | `VSYNC_GPIO` | RW | `0x00000000` | [vsync_gen（CPNX100 使用者 APB）](../modules/ref_design.md#vsync_gen) | [9:0] GPIO 多工（host 的 `I2S_CLOCK_CTRL` 也寫這個位址） |
| `0x7000_0804` | `delay_us` | RW |  | [delayed_io（CPNX100 使用者 APB）](../modules/ref_design.md#delayed_io) | 延遲（µs），reset 1000 |
| `0x7000_0808` | `set_now` | W |  | [delayed_io（CPNX100 使用者 APB）](../modules/ref_design.md#delayed_io) | 立即設 1（位元遮罩） |
| `0x7000_080C` | `clr_now` | W |  | [delayed_io（CPNX100 使用者 APB）](../modules/ref_design.md#delayed_io) | 立即清 0（位元遮罩） |
| `0x7000_0814` | `set_delayed` | W |  | [delayed_io（CPNX100 使用者 APB）](../modules/ref_design.md#delayed_io) | 延遲後設 1 |
| `0x7000_0818` | `clr_delayed` | W |  | [delayed_io（CPNX100 使用者 APB）](../modules/ref_design.md#delayed_io) | 延遲後清 0 |
| `0x7000_0820` | `cancel` | W |  | [delayed_io（CPNX100 使用者 APB）](../modules/ref_design.md#delayed_io) | 取消尚未執行的延遲操作 |
| `0x7000_0880` | `out_state` | RO |  | [delayed_io（CPNX100 使用者 APB）](../modules/ref_design.md#delayed_io) | 目前輸出狀態 |
| `0x7000_0884` | `pending` | RO |  | [delayed_io（CPNX100 使用者 APB）](../modules/ref_design.md#delayed_io) | 計數中的輸出 |
| `0x7000_08F0` | `enable` | RW |  | [delayed_io（CPNX100 使用者 APB）](../modules/ref_design.md#delayed_io) | [0] 全域啟用 |
| `0x7000_08F8` | `cycles_per_us` | RO |  | [delayed_io（CPNX100 使用者 APB）](../modules/ref_design.md#delayed_io) | 除錯 |
| `0x8000_0000` | `CTRL0` | RW | `0x00000000` | [i2s_top（CPNX100 使用者 APB）](../modules/ref_design.md#i2s_top) | [0] TX、[1] RX 啟用 |
| `0x8000_0004` | `CTRL1` | RW | `0x00000002` | [i2s_top（CPNX100 使用者 APB）](../modules/ref_design.md#i2s_top) | MCLK 分頻 |
| `0x8000_0008` | `CTRL2` | RW | `0x00000003` | [i2s_top（CPNX100 使用者 APB）](../modules/ref_design.md#i2s_top) | BCLK 分頻代碼 |
| `0x8000_000C` | `CTRL3` | RW | `0x00000002` | [i2s_top（CPNX100 使用者 APB）](../modules/ref_design.md#i2s_top) | [1:0] 位元深度、[3:2] 格式 |
| `0x8000_0010` | `CTRL4` | RW | `0x00000000` | [i2s_top（CPNX100 使用者 APB）](../modules/ref_design.md#i2s_top) | [0] mono、[2] loopback |
| `0x8000_0014` | `CTRL5` | RW | `0x00000040` | [i2s_top（CPNX100 使用者 APB）](../modules/ref_design.md#i2s_top) | RX 封包拍數 |
| `0x8000_0018` | `CTRL6` | RW | `0x00000000` | [i2s_top（CPNX100 使用者 APB）](../modules/ref_design.md#i2s_top) | 中斷啟用（未使用） |
| `0x8000_001C` | `CTRL7` | RW | `0x00000000` | [i2s_top（CPNX100 使用者 APB）](../modules/ref_design.md#i2s_top) | LRCLK 極性 |
| `0x8000_0020` | `CTRL8` | RW | `0x00000001` | [i2s_top（CPNX100 使用者 APB）](../modules/ref_design.md#i2s_top) | slot 模式 |
| `0x8000_0800` | `STAT0` | RO |  | [i2s_top（CPNX100 使用者 APB）](../modules/ref_design.md#i2s_top) | locked（固定 1）；`W_OFST = 12`，狀態區從 0x800 開始 |
| `0x8000_0804` | `STAT1` | RO |  | [i2s_top（CPNX100 使用者 APB）](../modules/ref_design.md#i2s_top) |  |
| `0x8000_0808` | `STAT2` | RO |  | [i2s_top（CPNX100 使用者 APB）](../modules/ref_design.md#i2s_top) | [0] TX underrun、[1] RX overrun |
| `0x8000_080C` | `STAT3` | RO |  | [i2s_top（CPNX100 使用者 APB）](../modules/ref_design.md#i2s_top) |  |

## 註解與程式不一致的項目

| 區塊 | 名稱 | 實際 offset | 註解位址 |
|---|---|---|---|
| ECB | [`ecb_addr_lsb`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L197) | `0x0004` | `0x0008` |
| ECB | [`ecb_addr_msb`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L198) | `0x0008` | `0x0004` |
