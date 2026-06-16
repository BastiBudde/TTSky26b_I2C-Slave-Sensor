/*
 * signal_bank.v — Block B register file with parallel capture + data-ready flags
 *
 * Slot 0 (BASE_ADDR+0) is a status register: 7 data-ready flags, one per
 * data register (bit 0 -> reg+1, ... bit 6 -> reg+7). A flag is SET when the
 * generator writes new samples (every tick) and CLEARED when the master reads
 * the corresponding data register. Set wins over clear on a same-cycle race.
 * Reading the status register itself does NOT clear any flag.
 *
 * Fixed 8-register layout (1 status + 7 data channels).
 */
`default_nettype none

module signal_bank #(
    parameter [7:0]          BASE_ADDR    = 8'h08,
    parameter                N_REGS       = 8,
    parameter [N_REGS*8-1:0] RESET_VALUES = {N_REGS*8{1'b0}}
) (
    input  wire       clk,
    input  wire       N_RST,
    input  wire       tick,

    input  wire [7:0] ch_sine,
    input  wire [7:0] ch_cosine,
    input  wire [7:0] ch_triangle,
    input  wire [7:0] ch_sawtooth,
    input  wire [7:0] ch_square,
    input  wire [7:0] ch_noisy_sine,
    input  wire [7:0] ch_noise,

    // Read port + read-strobe for data-ready clearing
    input  wire [7:0] raddr,
    input  wire       read_strobe,   // 1-cycle pulse: a byte was read out
    input  wire [7:0] read_addr,     // which register sourced that byte
    output wire [7:0] rdata
);
    // --- Data registers (slot 1..7), parallel capture on tick ---
    reg [7:0] registers [0:N_REGS-1];
    integer i;
    always @(posedge clk) begin
        if (!N_RST) begin
            for (i = 0; i < N_REGS; i = i + 1)
                registers[i] <= RESET_VALUES[i*8 +: 8];
        end else if (tick) begin
            registers[1] <= ch_sine;
            registers[2] <= ch_cosine;
            registers[3] <= ch_triangle;
            registers[4] <= ch_sawtooth;
            registers[5] <= ch_square;
            registers[6] <= ch_noisy_sine;
            registers[7] <= ch_noise;
        end
    end

    // --- Data-ready flags: one little FSM per data register ---
    // flags[g-1] tracks the register at BASE_ADDR + g (g = 1..7).
    reg [N_REGS-2:0] flags;   // 7 bits for the 7 data registers

    genvar g;
    generate
        for (g = 1; g < N_REGS; g = g + 1) begin : gen_flags
            localparam [7:0] DATA_ADDR = BASE_ADDR + g[7:0];
            always @(posedge clk) begin
                if (!N_RST)
                    flags[g-1] <= 1'b0;                       // no fresh data yet
                else if (tick)
                    flags[g-1] <= 1'b1;                       // set wins
                else if (read_strobe && (read_addr == DATA_ADDR))
                    flags[g-1] <= 1'b0;                       // clear on read
            end
        end
    endgenerate

    // --- Read path: slot 0 returns the status byte; others the registers ---
    localparam ADDR_BITS = $clog2(N_REGS);
    wire r_selected = (raddr >= BASE_ADDR) && (raddr < BASE_ADDR + N_REGS);
    wire [ADDR_BITS-1:0] r_local =
        raddr[ADDR_BITS-1:0] - BASE_ADDR[ADDR_BITS-1:0];

    wire [7:0] status_byte = {1'b0, flags};   // bit 7 unused; bit i -> reg i+1
    wire [7:0] read_value  = (r_local == {ADDR_BITS{1'b0}}) ? status_byte
                                                            : registers[r_local];
    assign rdata = r_selected ? read_value : 8'd0;
endmodule