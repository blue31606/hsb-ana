// Directed unit test for nv_hsb_ip/uart/uart.sv receive path (issue PE-3).
// A behavioral transmitter sends N back-to-back 8N1 frames (no idle between
// frames) at the nominal baud rate scaled by (1 + ERR_PPM * 1e-6). The test
// checks that every byte is received. With the RTL at 41cecaa, ERR_PPM >= 116
// (sender faster than HSB by about one clock per frame at BAUD_DIV = 107) is
// expected to lose framing; tools/model/uart_rx_model.py gives the threshold.
//
// DRAFT: not compiled. Run once per +ERR_PPM=<n>, e.g. -20000, 0, 5000, 20000.
//   vcs -sverilog tb_uart_rx_rate.sv $HSB/fpga/nv_hsb_ip/uart/uart.sv
`timescale 1ns/1ps
module tb_uart_rx_rate;
  localparam real    CLK_NS   = 10.0;      // 100 MHz
  localparam int     BAUD_DIV = 107;       // 100e6 / (8 * 108) = 115.7 kbaud
  localparam int     N_BYTES  = 64;

  logic clk = 0, rst = 1;
  always #(CLK_NS/2) clk = ~clk;

  logic       uart_rx = 1'b1, uart_tx;
  logic [7:0] rx_data;
  logic       rx_valid, rx_parity_error, rx_frame_error, glitch_error, tx_ready;

  uart #(.OVERSAMPLE(8), .DATA_WIDTH(8)) dut (
    .clk, .rst,
    .baud_div        (16'(BAUD_DIV)),
    .tx_en           (1'b0),
    .rx_en           (1'b1),
    .loopback_en     (1'b0),
    .data_width      (4'd8),
    .parity_mode     (2'b00),
    .stop_bits_mode  (2'b00),
    .tx_data         (8'h00),
    .tx_valid        (1'b0),
    .tx_ready,
    .rx_data, .rx_valid,
    .rx_ready        (1'b1),
    .rx_parity_error, .rx_frame_error,
    .uart_tx,
    .uart_rx,
    .rts_n           (1'b0),               // receiver must see RTS asserted (low)
    .glitch_window_width       (4'd0),
    .glitch_start_bit_majority (4'd0),
    .glitch_data_bit_majority  (4'd0),
    .glitch_filter_en          (1'b0),
    .glitch_error);

  byte unsigned sent[$], got[$];
  int frame_errors;

  always @(posedge clk) if (rx_valid) begin
    got.push_back(rx_data);
    if (rx_frame_error) frame_errors++;
  end

  initial begin
    int   err_ppm;
    real  bit_ns;
    if (!$value$plusargs("ERR_PPM=%d", err_ppm)) err_ppm = 0;
    bit_ns = CLK_NS * 8 * (BAUD_DIV + 1) / (1.0 + err_ppm * 1e-6);
    repeat (10) @(posedge clk); rst = 0;
    #(bit_ns * 3);
    for (int n = 0; n < N_BYTES; n++) begin
      byte unsigned b = byte'($urandom);
      sent.push_back(b);
      uart_rx = 1'b0;                     #(bit_ns);   // start
      for (int i = 0; i < 8; i++) begin uart_rx = b[i]; #(bit_ns); end
      uart_rx = 1'b1;                     #(bit_ns);   // one stop bit, no idle after
    end
    #(bit_ns * 20);
    begin
      int mism = 0;
      for (int i = 0; i < N_BYTES; i++)
        if (i >= got.size() || got[i] != sent[i]) mism++;
      $display("ERR_PPM=%0d sent=%0d received=%0d mismatched=%0d frame_errors=%0d -> %s",
               err_ppm, N_BYTES, got.size(), mism, frame_errors,
               (mism == 0 && got.size() == N_BYTES) ? "PASS" : "FAIL");
    end
    $finish;
  end
endmodule
