// Directed unit test for nv_hsb_ip/ref_design/i2s/i2s_clk_gen.sv (issue PE-9).
// For each (mclk_div, bclk_div code) pair, counts BCLK and LRCLK edges over a
// fixed window and checks:
//   - BCLK toggles at all,
//   - each LRCLK half period contains exactly slot_width BCLK periods,
//   - bclk_en pulses are produced (i2s_serdes advances only on them).
// Expected failures with the RTL at 41cecaa: bclk code 0, 8, 9; mclk_div 0, 1.
//
// DRAFT: not compiled.
//   vcs -sverilog $HSB/fpga/nv_hsb_ip/ref_design/i2s/i2s_pkg.sv \
//       $HSB/fpga/nv_hsb_ip/ref_design/i2s/i2s_clk_gen.sv tb_i2s_clk_gen.sv
`timescale 1ns/1ps
module tb_i2s_clk_gen;
  import i2s_pkg::*;
  logic clk = 0, rst = 1;
  always #5 clk = ~clk;

  logic [31:0] mclk_div, bclk_div;
  logic [1:0]  bit_depth_sel = I2S_BD_16B;
  logic        slot_mode     = I2S_SLOT_WORD;   // slot_width = 16
  logic        enable        = 1'b0;
  logic        mclk, bclk, lrclk, locked, bclk_en, lrclk_en, bclk_pe, bclk_ne;

  i2s_clk_gen dut (
    .i_ref_clk (clk), .i_rst (rst),
    .i_mclk_div (mclk_div), .i_bclk_div (bclk_div),
    .i_bit_depth_sel (bit_depth_sel), .i_slot_mode (slot_mode),
    .i_enable (enable),
    .o_mclk (mclk), .o_bclk (bclk), .o_lrclk (lrclk), .o_locked (locked),
    .o_bclk_en (bclk_en), .o_bclk_posedge (bclk_pe), .o_bclk_negedge (bclk_ne),
    .o_lrclk_en (lrclk_en));

  task automatic measure(input int md, input int bd, output bit pass);
    int bclk_rise = 0, lr_edges = 0, en_pulses = 0, rises_in_half = 0, bad_halves = 0;
    logic bclk_q, lr_q;
    mclk_div = md; bclk_div = bd;
    enable = 0; repeat (4) @(posedge clk); enable = 1;
    @(posedge clk); bclk_q = bclk; lr_q = lrclk;
    repeat (200_000) begin
      @(posedge clk);
      en_pulses += bclk_en;
      if (bclk && !bclk_q) begin bclk_rise++; rises_in_half++; end
      if (lrclk != lr_q) begin
        if (lr_edges > 0 && rises_in_half != 16) bad_halves++;   // skip first partial half
        lr_edges++; rises_in_half = 0;
      end
      bclk_q = bclk; lr_q = lrclk;
    end
    pass = (bclk_rise > 0) && (en_pulses > 0) && (lr_edges > 2) && (bad_halves == 0);
    $display("mclk_div=%0d bclk_code=%0d: BCLK rises=%0d bclk_en=%0d LRCLK edges=%0d bad halves=%0d -> %s",
             md, bd, bclk_rise, en_pulses, lr_edges, bad_halves, pass ? "PASS" : "FAIL");
  endtask

  initial begin
    bit pass; int fails = 0;
    mclk_div = 2; bclk_div = 3;
    repeat (5) @(posedge clk); rst = 0;
    for (int bd = 0; bd <= 9; bd++) begin measure(4, bd, pass); fails += !pass; end
    for (int k = 0; k < 6; k++) begin
      int md = (k == 0) ? 0 : (k == 1) ? 1 : (k == 2) ? 2 : (k == 3) ? 3 : (k == 4) ? 4 : 8;
      measure(md, 2, pass); fails += !pass;
    end
    $display("tb_i2s_clk_gen: %0d failing settings", fails);
    $finish;
  end
endmodule
