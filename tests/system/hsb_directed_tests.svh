// Directed system tests for nv_hsb_ip_simple_tb (see docs/test-plan.md).
//
// DRAFT: not compiled, not run. No HDL simulator was available when this was
// written. Each test is a task meant to be `include`d inside module
// nv_hsb_ip_simple_tb (after the tb_lib includes) and called from the main
// initial block after hololink_init(). Hierarchical names refer to commit
// 41cecaa81ab906a55e7ec22e5e6989f7e602a4c8 and must be re-checked.
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
// T6 (TX-1): duplicate RC packet must be ACKed (needs +define+ENABLE_ROCE_ACK
// and TEST_MODE=HOST2SEN). Sends PSN p, then PSN p again, then counts ACKs.
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
