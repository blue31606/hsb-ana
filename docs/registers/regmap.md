# 暫存器表（自動產生）

本檔由 `tools/gen_regmap.py` 從 [`regmap_pkg.sv`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv) 產生，請勿手動修改。

- **Offset** = index × 4，是程式實際使用的值。
- **註解位址** 是原始碼註解裡寫的位址。兩者不同時標記 ⚠️。
- index ≥ 32 的是唯讀狀態暫存器（`stat_ofst = 32`）。
- 基底位址取自 `apb_intc_top.sv` 的 `apb_switch` 設定，並用 host 軟體常數交叉確認（見各表的「佐證」）。

## Global Register

| 項目 | 值 |
|---|---|
| RTL 模組 | `glb_ctrl_top` |
| 基底位址 | `0x0000_0000` |
| 實例間距 | - |
| 控制暫存器數 / 狀態暫存器數 | 19 / 11 |
| 佐證 | HSB_IP_VERSION = 0x80 |
| 原始碼 | [regmap_pkg.sv#L81](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L81) |

| Index | 名稱 | 類型 | Offset | 註解位址 | 註解 |
|---:|---|---|---|---|---|
| 0 | [`glb_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L87) | RW | `0x0000` | `0x0000` |  |
| 1 | [`hsb_ctrl_0`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L88) | RW | `0x0004` | `0x0004` |  |
| 2 | [`hsb_ctrl_1`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L89) | RW | `0x0008` | `0x0008` |  |
| 3 | [`gpio_o_0`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L90) | RW | `0x000C` | `0x000C` | gpio out 31:0 |
| 4 | [`gpio_o_1`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L91) | RW | `0x0010` | `0x0010` | gpio out 63:32 |
| 5 | [`gpio_o_2`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L92) | RW | `0x0014` | `0x0014` | gpio out 95:64 |
| 6 | [`gpio_o_3`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L93) | RW | `0x0018` | `0x0018` | gpio out 127:96 |
| 7 | [`gpio_o_4`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L94) | RW | `0x001C` | `0x001C` | gpio out 159:128 |
| 8 | [`gpio_o_5`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L95) | RW | `0x0020` | `0x0020` | gpio out 191:160 |
| 9 | [`gpio_o_6`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L96) | RW | `0x0024` | `0x0024` | gpio out 223:192 |
| 10 | [`gpio_o_7`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L97) | RW | `0x0028` | `0x0028` | gpio out 255:224 |
| 11 | [`gpio_t_0`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L98) | RW | `0x002C` | `0x002C` | gpio tri 31:0 |
| 12 | [`gpio_t_1`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L99) | RW | `0x0030` | `0x0030` | gpio tri 63:32 |
| 13 | [`gpio_t_2`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L100) | RW | `0x0034` | `0x0034` | gpio tri 95:64 |
| 14 | [`gpio_t_3`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L101) | RW | `0x0038` | `0x0038` | gpio tri 127:96 |
| 15 | [`gpio_t_4`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L102) | RW | `0x003C` | `0x003C` | gpio tri 159:128 |
| 16 | [`gpio_t_5`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L103) | RW | `0x0040` | `0x0040` | gpio tri 191:160 |
| 17 | [`gpio_t_6`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L104) | RW | `0x0044` | `0x0044` | gpio tri 223:192 |
| 18 | [`gpio_t_7`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L105) | RW | `0x0048` | `0x0048` | gpio tri 255:224 |
| 32 | [`hsb_ver`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L107) | RO | `0x0080` | `0x0080` | hsb_ip version |
| 33 | [`hsb_date`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L108) | RO | `0x0084` | `0x0084` | hsb_ip date |
| 34 | [`hsb_stat`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L109) | RO | `0x0088` | `0x0088` | dev_ver external |
| 35 | [`gpio_i_0`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L110) | RO | `0x008C` | `0x008C` | gpio in 31:0 |
| 36 | [`gpio_i_1`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L111) | RO | `0x0090` | `0x0090` | gpio in 63:32 |
| 37 | [`gpio_i_2`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L112) | RO | `0x0094` | `0x0094` | gpio in 95:64 |
| 38 | [`gpio_i_3`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L113) | RO | `0x0098` | `0x0098` | gpio in 127:96 |
| 39 | [`gpio_i_4`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L114) | RO | `0x009C` | `0x009C` | gpio in 159:128 |
| 40 | [`gpio_i_5`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L115) | RO | `0x00A0` | `0x00A0` | gpio in 191:160 |
| 41 | [`gpio_i_6`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L116) | RO | `0x00A4` | `0x00A4` | gpio in 223:192 |
| 42 | [`gpio_i_7`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L117) | RO | `0x00A8` | `0x00A8` | gpio in 255:224 |

## PTP Register

| 項目 | 值 |
|---|---|
| RTL 模組 | `ptp_top` |
| 基底位址 | `0x0000_0100` |
| 實例間距 | - |
| 控制暫存器數 / 狀態暫存器數 | 9 / 9 |
| 佐證 | FPGA_PTP_CTRL = 0x104 |
| 原始碼 | [regmap_pkg.sv#L120](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L120) |

| Index | 名稱 | 類型 | Offset | 註解位址 | 註解 |
|---:|---|---|---|---|---|
| 0 | [`ptp_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L126) | RW | `0x0000` | `0x0000` |  |
| 1 | [`ptp_ctrl`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L127) | RW | `0x0004` | `0x0004` |  |
| 2 | [`ptp_ctrl_profile`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L128) | RW | `0x0008` | `0x0008` |  |
| 3 | [`ptp_ctrl_dly`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L129) | RW | `0x000C` | `0x000C` |  |
| 4 | [`ptp_ctrl_dpll_cfg1`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L130) | RW | `0x0010` | `0x0010` |  |
| 5 | [`ptp_ctrl_dpll_cfg2`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L131) | RW | `0x0014` | `0x0014` |  |
| 6 | [`ptp_ctrl_avg_fact`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L132) | RW | `0x0018` | `0x0018` |  |
| 7 | [`ptp_ctrl_domain`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L133) | RW | `0x001C` | `0x001C` |  |
| 8 | [`ptp_ctrl_pcp`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L134) | RW | `0x0020` | `0x0020` |  |
| 32 | [`ptp_sync_ts_0`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L136) | RO | `0x0080` | `0x0080` |  |
| 33 | [`ptp_sync_cf_0`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L137) | RO | `0x0084` | `0x0084` |  |
| 34 | [`ptp_sync_stat`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L138) | RO | `0x0088` | `0x0088` |  |
| 35 | [`ptp_ofm`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L139) | RO | `0x008C` | `0x008C` |  |
| 36 | [`ptp_mean_dly`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L140) | RO | `0x0090` | `0x0090` |  |
| 37 | [`ptp_inc`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L141) | RO | `0x0094` | `0x0094` |  |
| 38 | [`ptp_fa_adj`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L142) | RO | `0x0098` | `0x0098` |  |
| 39 | [`ptp_dly_cf_0`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L143) | RO | `0x009C` | `0x009C` |  |
| 40 | [`ptp_ip_dly_asymm`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L144) | RO | `0x00A0` | `0x00A0` |  |

## Instruction Decoder Registers

| 項目 | 值 |
|---|---|
| RTL 模組 | `rx_parser` |
| 基底位址 | `0x0200_0000` |
| 實例間距 | 0x1_0000 / host |
| 控制暫存器數 / 狀態暫存器數 | 10 / 2 |
| 佐證 | apb_intc_top host level |
| 原始碼 | [regmap_pkg.sv#L154](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L154) |

| Index | 名稱 | 類型 | Offset | 註解位址 | 註解 |
|---:|---|---|---|---|---|
| 0 | [`inst_dec_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L160) | RW | `0x0000` | `0x0000` |  |
| 1 | [`inst_dec_ctrl`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L161) | RW | `0x0004` | `0x0004` |  |
| 2 | [`lpbk_udp_port`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L162) | RW | `0x0008` | `0x0008` |  |
| 3 | [`roce_ecb_dest_qp`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L163) | RW | `0x000C` | `0x000C` |  |
| 4 | [`inst_dec_rsvd_1`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L164) | RW | `0x0010` | `0x0010` |  |
| 5 | [`inst_dec_rsvd_2`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L165) | RW | `0x0014` | `0x0014` |  |
| 6 | [`static_hif_qp`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L166) | RW | `0x0018` | `0x0018` |  |
| 7 | [`inst_dec_ack_ctrl`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L167) | RW | `0x001C` | `0x001C` |  |
| 8 | [`ecb_udp_port`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L168) | RW | `0x0020` | `0x0020` |  |
| 9 | [`stx_udp_port`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L169) | RW | `0x0024` | `0x0024` |  |
| 32 | [`inst_dec_stat`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L171) | RO | `0x0080` | `0x0080` |  |
| 33 | [`ipv4_chksum_err_cnt`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L172) | RO | `0x0084` | `0x0084` |  |

## Ethernet Packet

| 項目 | 值 |
|---|---|
| RTL 模組 | `eth_pkt` |
| 基底位址 | `0x0200_0100` |
| 實例間距 | 0x1_0000 / host |
| 控制暫存器數 / 狀態暫存器數 | 3 / 1 |
| 佐證 | apb_intc_top host level |
| 原始碼 | [regmap_pkg.sv#L175](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L175) |

| Index | 名稱 | 類型 | Offset | 註解位址 | 註解 |
|---:|---|---|---|---|---|
| 0 | [`eth_pkt_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L181) | RW | `0x0000` | `0x0000` |  |
| 1 | [`eth_pkt_ctrl`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L182) | RW | `0x0004` | `0x0004` |  |
| 2 | [`eth_pkt_hp_cnt`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L183) | RW | `0x0008` | `0x0008` |  |
| 32 | [`eth_pkt_stat`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L186) | RO | `0x0080` | `0x0080` |  |

## ECB

| 項目 | 值 |
|---|---|
| RTL 模組 | `ecb_rdwr_ctrl` |
| 基底位址 | `0x0000_0300` |
| 實例間距 | - |
| 控制暫存器數 / 狀態暫存器數 | 6 / 1 |
| 佐證 | apb_intc_top u_apb_switch_glb port 3 |
| 原始碼 | [regmap_pkg.sv#L190](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L190) |

| Index | 名稱 | 類型 | Offset | 註解位址 | 註解 |
|---:|---|---|---|---|---|
| 0 | [`ecb_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L196) | RW | `0x0000` | `0x0000` |  |
| 1 | [`ecb_addr_lsb`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L197) | RW | `0x0004` | `0x0008` ⚠️ |  |
| 2 | [`ecb_addr_msb`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L198) | RW | `0x0008` | `0x0004` ⚠️ |  |
| 3 | [`ecb_rkey`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L199) | RW | `0x000C` | `0x000C` |  |
| 4 | [`ecb_pkey`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L200) | RW | `0x0010` | `0x0010` |  |
| 5 | [`ecb_dest_qp`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L201) | RW | `0x0014` | `0x0014` |  |
| 32 | [`ecb_stat`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L203) | RO | `0x0080` | `0x0080` |  |

## Control Bus Event

| 項目 | 值 |
|---|---|
| RTL 模組 | `ctrl_bus_evt_int` |
| 基底位址 | `0x0000_0200` |
| 實例間距 | - |
| 控制暫存器數 / 狀態暫存器數 | 13 / 2 |
| 佐證 | CTRL_EVENT = 0x0000'0200 |
| 原始碼 | [regmap_pkg.sv#L206](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L206) |

| Index | 名稱 | 類型 | Offset | 註解位址 | 註解 |
|---:|---|---|---|---|---|
| 0 | [`ctrl_evt_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L212) | RW | `0x0000` | `0x0000` |  |
| 1 | [`ctrl_evt_rising`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L213) | RW | `0x0004` | `0x0004` |  |
| 2 | [`ctrl_evt_falling`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L214) | RW | `0x0008` | `0x0008` |  |
| 3 | [`ctrl_evt_clear`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L215) | RW | `0x000C` | `0x000C` |  |
| 4 | [`ctrl_evt_host_mac_addr_lo`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L216) | RW | `0x0010` | `0x0010` |  |
| 5 | [`ctrl_evt_host_mac_addr_hi`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L217) | RW | `0x0014` | `0x0014` |  |
| 6 | [`ctrl_evt_host_ip_addr`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L218) | RW | `0x0018` | `0x0018` |  |
| 7 | [`ctrl_evt_host_udp_port`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L219) | RW | `0x001C` | `0x001C` |  |
| 8 | [`ctrl_evt_dev_udp_port`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L220) | RW | `0x0020` | `0x0020` |  |
| 9 | [`ctrl_evt_apb_interrupt_en`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L221) | RW | `0x0024` | `0x0024` |  |
| 10 | [`ctrl_evt_apb_timeout`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L222) | RW | `0x0028` | `0x0028` |  |
| 11 | [`ctrl_evt_sw_event`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L223) | RW | `0x002C` | `0x002C` |  |
| 12 | [`ctrl_evt_vlan`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L224) | RW | `0x0030` | `0x0030` |  |
| 32 | [`ctrl_evt_stat`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L226) | RO | `0x0080` | `0x0080` |  |

## Dataplane Packetizer

| 項目 | 值 |
|---|---|
| RTL 模組 | `dp_pkt_top` |
| 基底位址 | `0x0200_0300` |
| 實例間距 | 0x1_0000 / host |
| 控制暫存器數 / 狀態暫存器數 | 6 / 1 |
| 佐證 | apb_intc_top host level |
| 原始碼 | [regmap_pkg.sv#L229](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L229) |

| Index | 名稱 | 類型 | Offset | 註解位址 | 註解 |
|---:|---|---|---|---|---|
| 0 | [`dp_pkt_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L235) | RW | `0x0000` | `0x0000` |  |
| 1 | [`dp_pkt_len`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L236) | RW | `0x0004` | `0x0004` |  |
| 2 | [`dp_pkt_dev_udp_port`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L237) | RW | `0x0008` | `0x0008` |  |
| 3 | [`dp_pkt_vip_mask`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L238) | RW | `0x000C` | `0x000C` |  |
| 4 | [`dp_pkt_crc_xor`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L239) | RW | `0x0010` | `0x0010` |  |
| 5 | [`dp_pkt_1722B`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L240) | RW | `0x0014` | `0x0014` |  |
| 32 | [`dp_pkt_stat`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L242) | RO | `0x0080` |  |  |

## Packetizer Register

| 項目 | 值 |
|---|---|
| RTL 模組 | `packetizer_top` |
| 基底位址 | `0x0100_0000` |
| 實例間距 | 0x1_0000 / SIF RX |
| 控制暫存器數 / 狀態暫存器數 | 4 / 2 |
| 佐證 | enumerator.cpp sif_address |
| 原始碼 | [regmap_pkg.sv#L246](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L246) |

| Index | 名稱 | 類型 | Offset | 註解位址 | 註解 |
|---:|---|---|---|---|---|
| 0 | [`pack_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L252) | RW | `0x0000` | `0x0000` |  |
| 1 | [`pack_ram_addr`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L253) | RW | `0x0004` | `0x0004` |  |
| 2 | [`pack_ram_data`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L254) | RW | `0x0008` | `0x0008` |  |
| 3 | [`pack_ctrl`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L255) | RW | `0x000C` | `0x000C` |  |
| 32 | [`pack_tvalid_cnt`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L257) | RO | `0x0080` | `0x0080` |  |
| 33 | [`pack_psn_cnt`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L258) | RO | `0x0084` | `0x0084` |  |

## Sensor RX Data Generator

| 項目 | 值 |
|---|---|
| RTL 模組 | `data_gen` |
| 基底位址 | `0x0100_0100` |
| 實例間距 | 0x1_0000 / SIF RX |
| 控制暫存器數 / 狀態暫存器數 | 10 / 1 |
| 佐證 | apb_intc_top sensor level |
| 原始碼 | [regmap_pkg.sv#L261](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L261) |

| Index | 名稱 | 類型 | Offset | 註解位址 | 註解 |
|---:|---|---|---|---|---|
| 0 | [`sen_rx_data_gen_scratch`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L267) | RW | `0x0000` | `0x0000` |  |
| 1 | [`sen_rx_data_gen_ena`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L268) | RW | `0x0004` | `0x0004` |  |
| 2 | [`sen_rx_data_gen_mode`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L269) | RW | `0x0008` | `0x0008` |  |
| 3 | [`sen_rx_data_gen_size`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L270) | RW | `0x000C` | `0x000C` |  |
| 4 | [`sen_rx_data_gen_output_rate`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L271) | RW | `0x0010` | `0x0010` |  |
| 5 | [`sen_rx_data_gen_pps_sync`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L272) | RW | `0x0014` | `0x0014` |  |
| 9 | [`sen_rx_prbs_seed`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L273) | RW | `0x0024` | `0x0024` |  |

## 註解與程式不一致的項目

| 區塊 | 名稱 | 實際 offset | 註解位址 |
|---|---|---|---|
| ECB | [`ecb_addr_lsb`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L197) | `0x0004` | `0x0008` |
| ECB | [`ecb_addr_msb`](https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/41cecaa81ab906a55e7ec22e5e6989f7e602a4c8/fpga/nv_hsb_ip/reg_map/regmap_pkg.sv#L198) | `0x0008` | `0x0004` |
