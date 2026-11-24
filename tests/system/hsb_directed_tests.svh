// Directed system tests for nv_hsb_ip_simple_tb (see docs/test-plan.md).
//
// DRAFT: not compiled, not run. No HDL simulator was available when this was
// written. Each test is a task meant to be `include`d inside module
// nv_hsb_ip_simple_tb (after the tb_lib includes) and called from the main
// initial block after hololink_init(). Hierarchical names refer to commit
// 41cecaa81ab906a55e7ec22e5e6989f7e602a4c8.
//
// v7: every testbench task / constant, task argument count and hierarchical
// path used below has been checked against that commit with
// tools/check_tests.py (not a compile: syntax and timing are still unchecked).
// Defines needed in HOLOLINK_def.svh, per test:
//   T4 packetizer_latency  SENSOR_RX_IF_INST
//   T6 roce_dup_ack        SIF_TX_ROCE_RC_ENABLE, SENSOR_TX_IF_INST
//   T7 eeprom_crc          ENUM_EEPROM
//   T8-T13 (v7)            see each test's header
//
// Every test prints "DIRECTED <name>: PASS|FAIL" and returns pass = 1 when the
// RTL behaves as the specification says. With the RTL at 41cecaa, the tests
// marked "expected FAIL" are expected to fail; that is the point of the test.

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
localparam logic [31:0] DT_GLB_SCRATCH = 32'h0000_0000;  // glb_ctrl offset 0
localparam logic [31:0] DT_PTP_SCRATCH = 32'h0000_0100;  // ptp block offset 0
localparam logic [31:0] DT_SPI_BASE    = 32'h0300_0000;
localparam logic [7:0]  DT_ECB_WR_BLOCK = 8'h09;

task automatic dt_report(input string name, input bit pass);
    $display("DIRECTED %s: %s", name, pass ? "PASS" : "FAIL");
endtask

// Send a raw ECB payload to host port 0 (frame is padded to 60 B by
// build_ethernet_frame, as a host NIC would).
task automatic dt_send_ecb_payload(input logic [7:0] pl[]);
    logic [7:0] frame[];
    int         size;
    build_ethernet_frame(pl, pl.size(), DEFAULT_FPGA_MAC, TB_HOST_MAC,
                         TB_FPGA_IP, TB_HOST_IP, ETH_UDP_CMD_PORT, ETH_UDP_CMD_PORT,
                         frame, size);
    send_eth_packet(0, frame, size);
endtask

// ---------------------------------------------------------------------------
// T1 (CP-1): single-pair WR_BLOCK must not issue a second APB write.
// Expected FAIL at 41cecaa: the 4 padding bytes become a second pair with
// addr = 0 and data = previous pair's data, so glb_scratch is overwritten.
// ---------------------------------------------------------------------------
task automatic dt_ecb_single_pair_block(output bit pass);
    logic [7:0]  pl[];
    logic [31:0] rd;
    const logic [31:0] marker = 32'h1111_1111;
    const logic [31:0] data   = 32'hA5A5_5A5A;

    ecb_write(DT_GLB_SCRATCH, marker);

    pl = new[14];
    pl[0] = DT_ECB_WR_BLOCK;
    pl[1] = 8'h01;                                // ACK_REQUEST
    pl[2] = ecb_sequence_id[15:8];
    pl[3] = ecb_sequence_id[7:0];
    pl[4] = 8'h00; pl[5] = 8'h00;
    {pl[6], pl[7], pl[8], pl[9]}     = DT_PTP_SCRATCH;
    {pl[10], pl[11], pl[12], pl[13]} = data;
    dt_send_ecb_payload(pl);
    ecb_sequence_id++;
    repeat (2000) @(posedge hif_clk);             // let the APB accesses finish

    ecb_read(DT_PTP_SCRATCH, rd);
    pass = (rd == data);
    ecb_read(DT_GLB_SCRATCH, rd);
    pass &= (rd == marker);
    $display("  glb_scratch = 0x%08x (expect 0x%08x)", rd, marker);
    dt_report("ecb_single_pair_block", pass);
endtask

// ---------------------------------------------------------------------------
// T2 (PE-1): SPI read-only transaction (no command, no write bytes).
// Expected FAIL at 41cecaa: spi_ctrl_fsm stays in SPI_READ, busy never clears.
// ---------------------------------------------------------------------------
task automatic dt_spi_read_only(output bit pass);
    logic [31:0] st;
    ecb_write(DT_SPI_BASE + 32'h00, 32'h0);              // clear start
    ecb_write(DT_SPI_BASE + 32'h0C, 32'h0000_0003);      // prescaler 3, mode 0, 1-wire
    ecb_write(DT_SPI_BASE + 32'h08, 32'h0004_0000);      // wr = 0, rd = 4
    ecb_write(DT_SPI_BASE + 32'h10, 32'h0000_0000);      // cmd = 0, turnaround = 0
    ecb_write(DT_SPI_BASE + 32'h04, 32'h0);              // bus 0
    ecb_write(DT_SPI_BASE + 32'h00, 32'h1);              // start
    repeat (20_000) @(posedge hif_clk);
    ecb_read(DT_SPI_BASE + 32'h80, st);
    pass = st[4] && !st[0];                              // done, not busy
    $display("  SPI status = 0x%08x (bit4 done, bit0 busy); SPI FSM state = %0d",
             st, u_dut.spi_ctrl_inst.state);
    ecb_write(DT_SPI_BASE + 32'h00, 32'h0);
    dt_report("spi_read_only", pass);
endtask

// ---------------------------------------------------------------------------
// T3 (PE-2): SPI turnaround longer than 32 cycles.
// Expected FAIL at 41cecaa for len >= 33.
// ---------------------------------------------------------------------------
task automatic dt_spi_long_turnaround(input int len, output bit pass);
    logic [31:0] st;
    ecb_write(DT_SPI_BASE + 32'h00, 32'h0);
    ecb_write(DT_SPI_BASE + 32'h100, 32'h0000_000B);     // command byte 0x0B (fast read)
    ecb_write(DT_SPI_BASE + 32'h0C, 32'h0000_0000);
    ecb_write(DT_SPI_BASE + 32'h08, 32'h0001_0001);      // wr = 1 (the command), rd = 1
    ecb_write(DT_SPI_BASE + 32'h10, (32'h1 << 8) | 32'(len)); // cmd = 1, turnaround = len
    ecb_write(DT_SPI_BASE + 32'h00, 32'h1);
    repeat (40_000) @(posedge hif_clk);
    ecb_read(DT_SPI_BASE + 32'h80, st);
    pass = st[4] && !st[0];
    $display("  turnaround=%0d SPI status = 0x%08x", len, st);
    ecb_write(DT_SPI_BASE + 32'h00, 32'h0);
    dt_report($sformatf("spi_turnaround_%0d", len), pass);
endtask

// ---------------------------------------------------------------------------
// T4 (DP-5): packetizer latency field 8 (control) and 9.
// Expected: latency 8 passes; latency 9 FAILS at 41cecaa (FSM stuck in WAIT,
// the frame never completes). Call before sending sensor frames, replacing
// program_packetizer_passthrough() for the sensor under test. The state probe
// uses gen_pack_inst[0] because a generate index must be a constant, so run
// it with sensor_id = 0.
// ---------------------------------------------------------------------------
task automatic dt_packetizer_latency(input int sensor_id, input int latency, output bit pass);
    logic [31:0] pack_base, cfg;
    program_packetizer_passthrough(sensor_id);           // RAM contents
    pack_base = REG_PACK_CTRL_BASE + (sensor_id * REG_PACK_CTRL_STRIDE);
    ecb_read(pack_base + PACK_OFF_PACK_CFG, cfg);
    cfg[PACK_CFG_LATENCY_LSB +: 4] = 4'(latency);
    ecb_write(pack_base + PACK_OFF_PACK_CFG, cfg);
    send_sensor_frame(sensor_id, 0);
    repeat (200_000) @(posedge hif_clk);
    // The existing scoreboard reports incomplete frames at the end of the test;
    // here only the packetizer FSM is checked directly.
    // PACK_WAIT = 7'b0000010 in packetizer_top.sv; the instance sits under the
    // generate loop gen_pack_inst in HOLOLINK_top (re-check any enclosing if-generate).
    pass = (u_dut.gen_pack_inst[0].packetizer_top_inst.state != 7'b0000010);
    $display("  latency=%0d packetizer state=%0d", latency,
             u_dut.gen_pack_inst[0].packetizer_top_inst.state);
    dt_report($sformatf("packetizer_latency_%0d", latency), pass);
endtask

// ---------------------------------------------------------------------------
// T5 (DP-3): VLAN-tagged PTP Follow_Up must not be classified as Sync.
// TCI = 0x6005: rx_parser reads hdr_array[14] = 0x60 -> messageType 0 = Sync.
// Expected FAIL at 41cecaa.
// ---------------------------------------------------------------------------
int dt_sync_pulses;
always @(posedge hif_clk) if (u_dut.is_ptp_sync_msg[0]) dt_sync_pulses++;

task automatic dt_build_ptp(input bit vlan, input logic [3:0] msg_type,
                            output logic [7:0] f[]);
    int n = 0;
    f = new[vlan ? 64 : 60];
    foreach (f[i]) f[i] = 8'h00;
    {f[0],f[1],f[2],f[3],f[4],f[5]} = 48'h01_1B_19_00_00_00;
    {f[6],f[7],f[8],f[9],f[10],f[11]} = TB_HOST_MAC;
    n = 12;
    if (vlan) begin f[n++] = 8'h81; f[n++] = 8'h00; f[n++] = 8'h60; f[n++] = 8'h05; end
    f[n++] = 8'h88; f[n++] = 8'hF7;
    f[n++] = {4'h0, msg_type};          // transportSpecific | messageType
    f[n++] = 8'h02;                     // versionPTP
    f[n++] = 8'h00; f[n++] = 8'd44;     // messageLength
endtask

task automatic dt_vlan_ptp_type(output bit pass);
    logic [7:0] f[];
    int before;
    before = dt_sync_pulses;
    dt_build_ptp(0, 4'h8, f); send_eth_packet(0, f, f.size());    // untagged Follow_Up
    repeat (500) @(posedge hif_clk);
    pass = (dt_sync_pulses == before);
    before = dt_sync_pulses;
    dt_build_ptp(1, 4'h8, f); send_eth_packet(0, f, f.size());    // tagged Follow_Up
    repeat (500) @(posedge hif_clk);
    pass &= (dt_sync_pulses == before);
    $display("  Sync pulses for tagged Follow_Up: %0d (expect 0)", dt_sync_pulses - before);
    dt_report("vlan_ptp_type", pass);
endtask

// ---------------------------------------------------------------------------
// T6 (TX-1): duplicate RC packet must be ACKed. Needs `define SIF_TX_ROCE_RC_ENABLE
// in HOLOLINK_def.svh (that is what sets rx_parser.ENABLE_ROCE_ACK = 1; there is
// no ENABLE_ROCE_ACK define) and TEST_MODE=HOST2SEN. Sends PSN p, then PSN p
// again, then counts ACKs.
// Expected FAIL at 41cecaa: only the first packet is ACKed.
// ---------------------------------------------------------------------------
int dt_ack_count;
always @(posedge hif_clk)
    if (u_dut.ack_axis_tvalid[0] && u_dut.ack_axis_tready[0] && u_dut.ack_axis_tlast[0])
        dt_ack_count++;

task automatic dt_roce_dup_ack(input int sensor_id, output bit pass);
    logic [7:0] pl[], f[];
    int size, before;
    const logic [7:0]  RC_SEND_ONLY = 8'h04;
    const logic [23:0] psn = 24'h000100;
    pl = new[64];
    foreach (pl[i]) pl[i] = 8'(i);
    before = dt_ack_count;
    build_host2sen_send_frame(sensor_id, pl, 64, RC_SEND_ONLY, psn, f, size);
    send_eth_packet(0, f, size);
    repeat (2000) @(posedge hif_clk);
    send_eth_packet(0, f, size);                          // same PSN again
    repeat (2000) @(posedge hif_clk);
    pass = (dt_ack_count - before == 2);
    $display("  ACKs for original + duplicate: %0d (expect 2)", dt_ack_count - before);
    dt_report("roce_dup_ack", pass);
endtask

// ---------------------------------------------------------------------------
// T7 (PE-8): a correctly programmed EEPROM must not raise eeprom_crc_err.
// Writes the Maxim CRC-8 of bytes 0..254 into byte 255 of the EEPROM model
// right after the model's own initialisation, as eeprom_utility.py does.
// Expected FAIL at 41cecaa (signal is unconnected, so only the probe sees it).
// Call dt_eeprom_patch_crc() from an initial block before reset is released.
// ---------------------------------------------------------------------------
function automatic logic [7:0] dt_crc8_maxim(input logic [7:0] b, input logic [7:0] crc);
    for (int i = 0; i < 8; i++) begin
        logic odd = (b[0] ^ crc[0]);
        crc = crc >> 1; b = b >> 1;
        if (odd) crc ^= 8'h8C;
    end
    return crc;
endfunction

task automatic dt_eeprom_patch_crc();
    logic [7:0] crc = 8'h00;
    #1;                                                   // after the model's initial block
    for (int i = 0; i < 255; i++) crc = dt_crc8_maxim(i_eeprom_model.eeprom_memory[i], crc);
    i_eeprom_model.eeprom_memory[255] = crc;
    $display("  EEPROM byte 255 <= 0x%02x", crc);
endtask

task automatic dt_eeprom_crc(output bit pass);
    pass = (u_dut.u_eeprom_info.eeprom_crc_err == 1'b0);
    $display("  eeprom_crc_err = %0b (expect 0)", u_dut.u_eeprom_info.eeprom_crc_err);
    dt_report("eeprom_crc", pass);
endtask

// ===========================================================================
// v7 additions: T8-T12. Same conventions as above. Checked with
// tools/check_tests.py against 41cecaa; not compiled.
// ===========================================================================

`ifdef SENSOR_TX_IF_INST
// ---------------------------------------------------------------------------
// Sensor-TX egress capture shared by T8-T10. Records every egress byte and the
// byte length of every tlast-delimited egress packet, per sensor.
// ---------------------------------------------------------------------------
logic [7:0] dt_egress     [`SENSOR_TX_IF_INST][$];
int         dt_egress_len [`SENSOR_TX_IF_INST][$];
int         dt_egress_cur [`SENSOR_TX_IF_INST];

for (genvar gs = 0; gs < `SENSOR_TX_IF_INST; gs++) begin : g_dt_egress
    initial dt_egress_cur[gs] = 0;
    always @(posedge i_sif_tx_clk[gs]) begin
        if (o_sif_axis_tvalid[gs] && i_sif_axis_tready[gs]) begin
            for (int lane = 0; lane < `DATAKEEP_WIDTH; lane++)
                if (o_sif_axis_tkeep[gs][lane]) begin
                    dt_egress[gs].push_back(o_sif_axis_tdata[gs][lane*8 +: 8]);
                    dt_egress_cur[gs]++;
                end
            if (o_sif_axis_tlast[gs]) begin
                dt_egress_len[gs].push_back(dt_egress_cur[gs]);
                dt_egress_cur[gs] = 0;
            end
        end
    end
end

task automatic dt_egress_clear(input int s);
    dt_egress[s].delete();
    dt_egress_len[s].delete();
    dt_egress_cur[s] = 0;
endtask

// ---------------------------------------------------------------------------
// T8 (TX-6): RC RDMA WRITE ONLY must deliver only the payload, not the RETH.
// Needs SIF_TX_ROCE_RC_ENABLE and SENSOR_TX_IF_INST. Uses PSN 0, so run it
// on a sensor whose QP has not carried RC traffic since reset (before T6, or
// on another sensor).
// Expected FAIL at 41cecaa: sensor_tx_pkt_proc strips a fixed 54 + 4 bytes, so
// the 16-byte RETH (E0..E7, DEADBEEF, length) reaches the sensor first.
// ---------------------------------------------------------------------------
task automatic dt_rc_write_reth(input int s, output bit pass);
    logic [7:0] pl[], f[];
    int size;
    const logic [7:0] RC_RDMA_WRITE_ONLY = 8'h0A;
    const int         DATA_BYTES = 1024;       // >= the AFULL gate program_tx_strm_buff() sets
    program_tx_strm_buff();
    dt_egress_clear(s);
    pl = new[16 + DATA_BYTES];
    for (int i = 0; i < 8; i++) pl[i] = 8'hE0 + 8'(i);           // RETH VA
    {pl[8], pl[9], pl[10], pl[11]}  = 32'hDEAD_BEEF;              // RETH R_Key
    {pl[12], pl[13], pl[14], pl[15]} = 32'(DATA_BYTES);           // RETH DMA length
    for (int i = 0; i < DATA_BYTES; i++) pl[16 + i] = 8'(i);      // 00 01 02 ...
    build_host2sen_send_frame(s, pl, pl.size(), RC_RDMA_WRITE_ONLY, 24'h0, f, size);
    send_eth_packet(0, f, size);
    repeat (20_000) @(posedge hif_clk);
    pass = (dt_egress[s].size() == DATA_BYTES) &&
           (dt_egress[s].size() >= 2) && (dt_egress[s][0] == 8'h00) && (dt_egress[s][1] == 8'h01);
    $display("  sensor %0d egress %0d bytes (expect %0d), first bytes %02x %02x (expect 00 01)",
             s, dt_egress[s].size(), DATA_BYTES,
             (dt_egress[s].size() > 0) ? dt_egress[s][0] : 8'hxx,
             (dt_egress[s].size() > 1) ? dt_egress[s][1] : 8'hxx);
    dt_report("rc_write_reth", pass);
endtask

// ---------------------------------------------------------------------------
// T9 (TX-7): when tx_stream_buffer overflows, every egress packet must still
// be exactly one ingress packet (whole packets dropped, never cut or merged).
// PAUSE is disabled and the sensor stops accepting, so the buffer is forced
// to overflow; that loss itself is expected. Each ingress packet is filled
// with its own index so a cut or a merge is visible. Two more packets are
// sent after the drain so a packet that lost its tlast gets merged into them.
// Needs SENSOR_TX_IF_INST.
// Expected FAIL at 41cecaa: beats (and tlast) are dropped individually.
// ---------------------------------------------------------------------------
task automatic dt_stx_overflow_boundary(input int s, output bit pass);
    logic [7:0] pl[], f[];
    int size, entry_bytes, depth, npkts, bad, idx;
    const int PKT_BYTES = 1000;                                   // not a multiple of any entry size
    entry_bytes = ((`HOST_WIDTH > SIF_TX_WIDTH[s]) ? `HOST_WIDTH : SIF_TX_WIDTH[s]) / 8;
    depth       = SIF_TX_BUF_SIZE[s];
    npkts       = (3 * depth * entry_bytes) / (2 * PKT_BYTES) + 2; // about 1.5x the buffer
    ecb_write(reg_tx_strm_buff(s, TX_STRM_OFF_PAUSE_MAP), 32'h0);
    ecb_write(reg_tx_strm_buff(s, TX_STRM_OFF_AFULL),     32'h1);
    ecb_write(reg_tx_strm_buff(s, TX_STRM_OFF_AEMPTY),    32'h1);
    ecb_write(reg_tx_strm_buff(s, TX_STRM_OFF_CTRL),      32'h0);  // reset afull_seen
    ecb_write(reg_tx_strm_buff(s, TX_STRM_OFF_CTRL),      32'h5);  // enable + latch, no pause
    ecb_write(reg_tx_strm_buff(s, TX_STRM_OFF_CTRL),      32'h1);  // enable, no pause
    dt_egress_clear(s);
    i_sif_axis_tready[s] = 1'b0;                                   // sensor stops accepting
    for (int p = 0; p < npkts + 2; p++) begin
        if (p == npkts) begin                                      // drain, then two more
            repeat (2000) @(posedge hif_clk);
            i_sif_axis_tready[s] = 1'b1;
            repeat (depth * 16 + 20_000) @(posedge hif_clk);
        end
        pl = new[PKT_BYTES];
        foreach (pl[i]) pl[i] = 8'(p);
        build_host2sen_send_frame(s, pl, PKT_BYTES, ROCE_OP_SEND_ONLY,
                                  host2sen_psn[s][23:0], f, size);
        host2sen_psn[s]++;
        send_eth_packet(0, f, size);
    end
    repeat (depth * 16 + 20_000) @(posedge hif_clk);
    bad = 0;
    idx = 0;
    foreach (dt_egress_len[s][k]) begin
        bit uniform = 1;
        for (int b = 1; b < dt_egress_len[s][k]; b++)
            if (dt_egress[s][idx + b] != dt_egress[s][idx]) uniform = 0;
        if (dt_egress_len[s][k] != PKT_BYTES || !uniform) begin
            bad++;
            $display("  egress packet %0d: %0d bytes, first index %0d, uniform %0b",
                     k, dt_egress_len[s][k], dt_egress[s][idx], uniform);
        end
        idx += dt_egress_len[s][k];
    end
    pass = (bad == 0) && (dt_egress_len[s].size() > 0);
    $display("  sent %0d x %0d B, egress packets %0d, cut or merged %0d (expect 0)",
             npkts + 2, PKT_BYTES, dt_egress_len[s].size(), bad);
    program_tx_strm_buff();                                        // restore the normal setup
    dt_report("stx_overflow_boundary", pass);
endtask

// ---------------------------------------------------------------------------
// T10 (TX-8): a PAUSE requested by sensor 1 must carry sensor 1's quanta.
// Sensor 0 quanta = 0x1111 (pause disabled), sensor 1 quanta = 0x2222 with a
// 1-entry AFULL and its egress stalled, so only sensor 1 requests a PAUSE.
// The quanta is sampled at pause_gen's input when the request rises.
// Needs SENSOR_TX_IF_INST >= 2 (skipped otherwise).
// Expected FAIL at 41cecaa: every pause_gen reads tx_pause_quanta[0].
// ---------------------------------------------------------------------------
logic [15:0] dt_pause_time_q[$];
logic        dt_pause_req_q = 1'b0;
always @(posedge hif_clk) begin
    dt_pause_req_q <= u_dut.host_pause_req[0];
    if (u_dut.host_pause_req[0] && !dt_pause_req_q)
        dt_pause_time_q.push_back(u_dut.gen_pause[0].u_pause_gen.i_pause_time);
end

task automatic dt_pause_quanta(output bit pass);
    logic [7:0] pl[], f[];
    int size;
    if (`SENSOR_TX_IF_INST < 2) begin
        $display("  skipped: needs at least 2 sensor TX interfaces");
        pass = 1;
        dt_report("pause_quanta", pass);
        return;
    end
    ecb_write(reg_tx_strm_buff(0, TX_STRM_OFF_QUANTA),    32'h0000_1111);
    ecb_write(reg_tx_strm_buff(0, TX_STRM_OFF_CTRL),      32'h1);  // sensor 0: no pause
    ecb_write(reg_tx_strm_buff(1, TX_STRM_OFF_PAUSE_MAP), 32'h1);
    ecb_write(reg_tx_strm_buff(1, TX_STRM_OFF_AFULL),     32'h1);
    ecb_write(reg_tx_strm_buff(1, TX_STRM_OFF_AEMPTY),    32'h0);
    ecb_write(reg_tx_strm_buff(1, TX_STRM_OFF_QUANTA),    32'h0000_2222);
    ecb_write(reg_tx_strm_buff(1, TX_STRM_OFF_CTRL),      32'h0);
    ecb_write(reg_tx_strm_buff(1, TX_STRM_OFF_CTRL),      32'h7);  // enable + pause + latch
    ecb_write(reg_tx_strm_buff(1, TX_STRM_OFF_CTRL),      32'h3);
    i_sif_axis_tready[1] = 1'b0;
    dt_pause_time_q.delete();
    pl = new[512];
    foreach (pl[i]) pl[i] = 8'(i);
    build_host2sen_send_frame(1, pl, 512, ROCE_OP_SEND_ONLY, host2sen_psn[1][23:0], f, size);
    host2sen_psn[1]++;
    send_eth_packet(0, f, size);
    repeat (5000) @(posedge hif_clk);
    pass = (dt_pause_time_q.size() > 0) && (dt_pause_time_q[0] == 16'h2222);
    $display("  PAUSE requests %0d, first quanta 0x%04x (expect 0x2222)",
             dt_pause_time_q.size(), (dt_pause_time_q.size() > 0) ? dt_pause_time_q[0] : 16'hxxxx);
    i_sif_axis_tready[1] = 1'b1;
    repeat (5000) @(posedge hif_clk);
    program_tx_strm_buff();
    dt_report("pause_quanta", pass);
endtask
`endif // SENSOR_TX_IF_INST

// ---------------------------------------------------------------------------
// T11 (DP-1, DP-2): after a burst that overflows rx_parser's buffers, the
// parser must return to a consistent state once traffic stops.
// Drives back-to-back 60-byte frames, one beat after another with no idle
// cycle, to a foreign unicast MAC (classified is_btx and discarded outside
// Bridge mode). rx_parser reads out n + 1 cycles per n-beat packet, so any
// gap-free burst outruns it; on Terasic S10 the MAC itself delivers 60-byte
// frames every 1.5 cycles at 100G, which is the same situation (DP-15).
// Checks, after the burst has drained:
//   - u_axis_inp_buffer.in_pkt_cnt == out_pkt_cnt
//   - three ECB reads of glb_scratch all return the marker written before.
// Expected FAIL at 41cecaa: dropped tlast / metadata leave the counters
// apart and pair later packets with the wrong metadata until reset. Run it
// last, or reset afterwards.
// ---------------------------------------------------------------------------
task automatic dt_rx_parser_burst(input int nframes, output bit pass);
    logic [7:0]  f[60];
    logic [31:0] rd, in_cnt, out_cnt;
    int          beats, ok_reads;
    const logic [31:0] marker = 32'h5EED_0001;
    ecb_write(DT_GLB_SCRATCH, marker);
    foreach (f[i]) f[i] = 8'h00;
    {f[0], f[1], f[2], f[3], f[4], f[5]}   = 48'h02_00_00_00_00_01;  // not the FPGA
    {f[6], f[7], f[8], f[9], f[10], f[11]} = TB_HOST_MAC;
    {f[12], f[13]} = 16'h88B5;                                       // local experimental EtherType
    beats = (60 + (`HOST_WIDTH/8) - 1) / (`HOST_WIDTH/8);
    hif_tx_sem.get(1);
    @(posedge hif_clk);
    for (int p = 0; p < nframes; p++) begin
        f[14] = 8'(p);
        for (int w = 0; w < beats; w++) begin
            logic [`HOST_WIDTH-1:0]     d = '0;
            logic [`HOSTKEEP_WIDTH-1:0] k = '0;
            for (int j = 0; j < (`HOST_WIDTH/8); j++)
                if (w * (`HOST_WIDTH/8) + j < 60) begin
                    d[j*8 +: 8] = f[w * (`HOST_WIDTH/8) + j];
                    k[j]        = 1'b1;
                end
            i_hif_axis_tvalid[0] <= 1'b1;
            i_hif_axis_tdata[0]  <= d;
            i_hif_axis_tkeep[0]  <= k;
            i_hif_axis_tlast[0]  <= (w == beats - 1);
            i_hif_axis_tuser[0]  <= '0;
            @(posedge hif_clk);
        end
    end
    i_hif_axis_tvalid[0] <= 1'b0;
    i_hif_axis_tlast[0]  <= 1'b0;
    hif_tx_sem.put(1);
    repeat (5000) @(posedge hif_clk);
    in_cnt  = 32'(u_dut.gen_rx_parser[0].rx_parser.u_axis_inp_buffer.in_pkt_cnt);
    out_cnt = 32'(u_dut.gen_rx_parser[0].rx_parser.u_axis_inp_buffer.out_pkt_cnt);
    ok_reads = 0;
    for (int r = 0; r < 3; r++) begin
        rd = 32'hX;
        ecb_read(DT_GLB_SCRATCH, rd);
        if (rd === marker) ok_reads++;
    end
    pass = (in_cnt == out_cnt) && (ok_reads == 3);
    $display("  %0d frames x %0d beats: in_pkt_cnt %0d, out_pkt_cnt %0d (expect equal); ECB reads OK %0d / 3",
             nframes, beats, in_cnt, out_cnt, ok_reads);
    dt_report("rx_parser_burst", pass);
endtask

// ---------------------------------------------------------------------------
// T12 (PE-7): with no EEPROM answering, the MAC must stay at the reset value
// CA:FE:C0:FF:EE:00. Standalone run: the rest of the testbench addresses the
// FPGA by DEFAULT_FPGA_MAC and cannot run after this.
//   initial dt_eeprom_absent_setup();            // at time 0, before reset release
//   ... then, instead of hololink_init():
//   dt_eeprom_absent_check(p);
// Needs ENUM_EEPROM.
// Expected FAIL at 41cecaa: eeprom_info ignores the NACK and copies I2C data-
// buffer words that were never written: X in simulation (block RAM power-up
// content, usually 0, on hardware).
// ---------------------------------------------------------------------------
task automatic dt_eeprom_absent_setup();
    force i_eeprom_model.eeprom_sda_drive = 1'b1;              // never ACK
endtask

task automatic dt_eeprom_absent_check(output bit pass);
    fork
        wait (u_dut.u_eeprom_info.eeprom_dval === 1'b1);
        begin
            repeat (20_000_000) @(posedge hif_clk);
            $display("  eeprom_info did not finish");
        end
    join_any
    disable fork;
    pass = (u_dut.u_eeprom_info.mac_addr === 48'hCAFE_C0FF_EE00);
    $display("  mac_addr = %012x (expect cafec0ffee00)", u_dut.u_eeprom_info.mac_addr);
    release i_eeprom_model.eeprom_sda_drive;
    dt_report("eeprom_absent", pass);
endtask
