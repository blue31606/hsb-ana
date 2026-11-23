// Directed unit test for nv_hsb_ip/spi/spi.sv (issue PE-2 in docs/issues.md).
// Sends one command byte, then a turnaround of LEN SCK cycles, then stops.
// Expected (spec): busy drops after the turnaround and exactly 2*LEN SCK edges
// occur during it. With the RTL at 41cecaa, LEN >= 33 never finishes.
//
// DRAFT: not compiled. Build e.g.
//   vcs -sverilog tb_spi_turnaround.sv $HSB/fpga/nv_hsb_ip/spi/spi.sv
`timescale 1ns/1ps
module tb_spi_turnaround;
  logic clk = 0, rst = 1;
  always #5 clk = ~clk;

  logic       start, write, turnaround, read, stop;
  logic [7:0] turnaround_len, wr_data, rd_data;
  logic       cmd_ack, rd_data_valid, busy, SCK;
  logic [0:0] CS_N;
  logic [3:0] SDIO_en, SDIO_out;

  spi #(.NUM_TARGETS(1)) dut (
    .clk, .rst,
    .prescaler      (4'd1),
    .spi_mode       (2'b00),          // CPOL = 0, CPHA = 0
    .targ_sel       (3'd0),
    .start, .write, .turnaround, .read, .stop,
    .spi_width      (2'd0),
    .turnaround_len, .wr_data,
    .cmd_ack, .rd_data, .rd_data_valid, .busy,
    .CS_N, .SCK, .SDIO_en,
    .SDIO_in        (4'b0000),
    .SDIO_out);

  int sck_edges_in_ta;
  logic       sck_q;
  logic [2:0] state_q;
  localparam logic [2:0] ST_TA = 3'h3;   // STATE_SPI_TURNAROUND in spi.sv
  always @(posedge clk) begin
    sck_q   <= SCK;
    state_q <= dut.rSpiState;
    // An edge launched while entering, inside, or leaving TURNAROUND
    if ((dut.rSpiState == ST_TA || state_q == ST_TA) && SCK != sck_q)
      sck_edges_in_ta++;
  end

  task automatic run(input int len, output bit pass);
    int timeout;
    sck_edges_in_ta = 0;
    turnaround_len  = 8'(len);
    wr_data         = 8'h9F;
    {start, write, read, stop, turnaround} = 5'b11000;
    @(posedge clk iff cmd_ack); #1;      // command byte accepted
    // Next op: turnaround, and stop after it. stop must be valid when the
    // turnaround is accepted, because spi.sv latches {write, stop, read} then.
    {start, write, read, stop, turnaround} = 5'b00011;
    @(posedge clk iff cmd_ack); #1;      // turnaround accepted
    turnaround = 1'b0;
    timeout = (len + 16) * 2 * 2 * 4;    // generous: 2 clk per half period
    while (busy && timeout > 0) begin @(posedge clk); timeout--; end
    pass = !busy;
    $display("LEN=%0d busy_cleared=%0b edges_in_turnaround=%0d (expect %0d)",
             len, !busy, sck_edges_in_ta, 2*len);
    {start, write, read, stop, turnaround} = '0;
    if (busy) begin rst = 1; repeat (4) @(posedge clk); rst = 0; end
    repeat (10) @(posedge clk);
  endtask

  initial begin
    bit pass; int fails = 0;
    {start, write, read, stop, turnaround} = '0;
    turnaround_len = 0; wr_data = 0;
    repeat (5) @(posedge clk); rst = 0; repeat (5) @(posedge clk);
    for (int k = 0; k < 8; k++) begin
      int len;
      len = (k == 0) ? 1 : (k == 1) ? 2 : (k == 2) ? 8 : (k == 3) ? 31 :
            (k == 4) ? 32 : (k == 5) ? 33 : (k == 6) ? 40 : 255;
      run(len, pass);
      if (!pass) fails++;
    end
    $display("tb_spi_turnaround: %0d failing lengths (RTL 41cecaa expected: 33, 40, 255)", fails);
    $finish;
  end
endmodule
