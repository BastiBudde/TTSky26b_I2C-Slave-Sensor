module top_level #(
    parameter [7:0]  BASE_ADDR_BLOCK_A    = 8'h00, // --- Addresses 0x00..0x07 ---
    parameter        N_REGS_BLOCK_A       = 8,    
    parameter [7:0]  BASE_ADDR_BLOCK_B    = 8'h08, // --- Addresses 0x08..0x0F ---
    parameter        N_REGS_BLOCK_B       = 8,
    parameter [7:0]  BASE_ADDR_BLOCK_C    = 8'hF8, // --- Addresses 0xF8..0xFF ---
    parameter        N_REGS_BLOCK_C       = 8
) (
    input  wire clk,
    input  wire N_RST,
    input  wire SCL,
    input  wire sda_in, 
    output wire sda_oe
);

//--------------------------------------------
//----------- Internal connections -----------
//--------------------------------------------
wire [7:0]  reg_addr_i2c;
wire [7:0]  data_from_i2c;
wire [7:0]  data_to_i2c;
wire        reg_write_i2c;

wire [7:0]  reg_addr_lfsr;
wire [7:0]  data_from_lfsr;
wire        reg_write_lfsr;

// Internal wires to connect multiple register blocks to the I2C slave
wire [7:0] data_out_block_a, data_out_block_b, data_out_block_c;

// OR-Tree: only addressed register block will output data, the other will output 0
assign data_to_i2c = data_out_block_a | data_out_block_b | data_out_block_c;

//-----------------------------------------------------------------------
//------------------------------ I2C Slave ------------------------------
//-----------------------------------------------------------------------
i2c_slave i2c_inst (
    .clk        (clk),
    .N_RST      (N_RST),
    .sda_in     (sda_in),
    .sda_oe     (sda_oe),
    .SCL        (SCL),
    .reg_addr   (reg_addr_i2c),
    .data_in    (data_to_i2c),
    .data_out   (data_from_i2c),
    .reg_write  (reg_write_i2c)
);

//-----------------------------------------------------------------------
//----------------- DDS Signal source - Master readonly -----------------
//-----------------------------------------------------------------------
signal_source #(
    .BASE_ADDR (BASE_ADDR_BLOCK_B),
    .N_REGS    (N_REGS_BLOCK_B)
    // RESET_VALUES default = zeros; status slot reads 0 until implemented
) signal_source_b (
    .clk       (clk),
    .N_RST     (N_RST),
    .phase_inc (16'd1024),          // fixed for now; Block A config later
    .raddr     (reg_addr_i2c),
    .rdata     (data_out_block_b)
);

//-----------------------------------------------------------------------
//----------------- Register Block A - Master writable ------------------
//-----------------------------------------------------------------------
reg_block #(
    .BASE_ADDR      (BASE_ADDR_BLOCK_A),
    .N_REGS         (N_REGS_BLOCK_A),
    // Register:        7     6     5     4     3     2     1     0
    .RESET_VALUES   ({8'h20,8'h74,8'h96,8'h06,8'h42,8'h20,8'h94,8'h76})
) reg_block_a (
    .clk        (clk),
    .N_RST      (N_RST),
    .waddr(reg_addr_i2c), .wdata(data_from_i2c), .we(reg_write_i2c),
    .raddr(reg_addr_i2c), .rdata(data_out_block_a)
);


//-----------------------------------------------------------------------
//------- Register Block C - Constant signature (read-only, no writer) --
//-----------------------------------------------------------------------
// ASCII initials + year. Reading all 8 registers yields "SBJS2026".
//  Register:  7     6     5     4     3     2     1     0
//  Char:     '6'   '2'   '0'   '2'   'S'   'J'   'B'   'S'
reg_block #(
    .BASE_ADDR      (BASE_ADDR_BLOCK_C),
    .N_REGS         (N_REGS_BLOCK_C),
    .RESET_VALUES   ({8'h36,8'h32,8'h30,8'h32,8'h53,8'h4A,8'h42,8'h53})
) reg_block_c (
    .clk        (clk),
    .N_RST      (N_RST),
    // No write path: we tied low, so the reset values are constant
    .waddr(8'd0), .wdata(8'd0), .we(1'b0),
    .raddr(reg_addr_i2c), .rdata(data_out_block_c)
);


endmodule
