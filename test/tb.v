`default_nettype none
`timescale 1ns / 1ps

/* This testbench just instantiates the module and makes some convenient wires
   that can be driven / tested by the cocotb test.py.
*/
module tb ();

  // Dump the signals to a FST file. You can view it with gtkwave or surfer.
  // initial begin
  //   $dumpfile("tb.fst");
  //   $dumpvars(0, tb);
  //   #1;
  //   $dumpvars(0, user_project.top_level_inst.reg_block_a.registers[0]);
  //   $dumpvars(0, user_project.top_level_inst.reg_block_a.registers[1]);
  //   $dumpvars(0, user_project.top_level_inst.reg_block_a.registers[2]);
  //   $dumpvars(0, user_project.top_level_inst.reg_block_a.registers[3]);
  //   $dumpvars(0, user_project.top_level_inst.reg_block_a.registers[4]);
  //   $dumpvars(0, user_project.top_level_inst.reg_block_a.registers[5]);
  //   $dumpvars(0, user_project.top_level_inst.reg_block_a.registers[6]);
  //   $dumpvars(0, user_project.top_level_inst.reg_block_a.registers[7]);

  //   $dumpvars(0, user_project.top_level_inst.reg_block_b.registers[0]);
  //   $dumpvars(0, user_project.top_level_inst.reg_block_b.registers[1]);
  //   $dumpvars(0, user_project.top_level_inst.reg_block_b.registers[2]);
  //   $dumpvars(0, user_project.top_level_inst.reg_block_b.registers[3]);
  //   $dumpvars(0, user_project.top_level_inst.reg_block_b.registers[4]);
  //   $dumpvars(0, user_project.top_level_inst.reg_block_b.registers[5]);
  //   $dumpvars(0, user_project.top_level_inst.reg_block_b.registers[6]);
  //   $dumpvars(0, user_project.top_level_inst.reg_block_b.registers[7]);
  // end

  // Wire up the inputs and outputs:
  reg clk;
  reg rst_n;
  reg ena;
  reg [7:0] ui_in;
  wire [7:0] uo_out;
  wire [7:0] uio_out;
  wire [7:0] uio_oe;

  // --- I2C bus modeling -----------------------------------------------------
  // The cocotb master controls these two signals (1 = released, 0 = pull low).
  reg scl_master_drive;
  reg sda_master_drive;

  // The slave inside the DUT drives uio_oe[3] high to pull SDA low.
  // Bus is low if either the master or the slave pulls low; otherwise high.
  wire scl_bus = scl_master_drive;                 // master is the only driver
  wire sda_bus = sda_master_drive & ~uio_oe[3];    // master AND slave released

  // uio_in is what the chip "sees" on its bidirectional pins.
  // Bits 0 and 1 are the I2C bus; the rest are tied to 0 (pulled inputs).
  wire [7:0] uio_in = {4'b0000, sda_bus, 2'b00, scl_bus};
  // --------------------------------------------------------------------------


`ifdef GL_TEST
  wire VPWR = 1'b1;
  wire VGND = 1'b0;
`endif

  // Replace tt_um_example with your module name:
  tt_um_BastiBudde_chip_design_i2c_slave user_project (

      // Include power ports for the Gate Level test:
`ifdef GL_TEST
      .VPWR(VPWR),
      .VGND(VGND),
`endif

      .ui_in  (ui_in),    // Dedicated inputs
      .uo_out (uo_out),   // Dedicated outputs
      .uio_in (uio_in),   // IOs: Input path
      .uio_out(uio_out),  // IOs: Output path
      .uio_oe (uio_oe),   // IOs: Enable path (active high: 0=input, 1=output)
      .ena    (ena),      // enable - goes high when design is selected
      .clk    (clk),      // clock
      .rst_n  (rst_n)     // not reset
  );

endmodule
