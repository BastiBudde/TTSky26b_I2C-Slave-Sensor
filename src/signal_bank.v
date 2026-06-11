/*
 * signal_bank.v — Block B register file with parallel waveform capture
 *
 * Replaces the single-write-port reg_block for Block B. On every tick,
 * each data register latches its own waveform channel (all in parallel),
 * so each register represents a distinct signal rather than a FIFO of one.
 *
 * Slot layout (BASE_ADDR + offset):
 *   +0  status     (reset value for now; becomes data-ready flags later)
 *   +1  sine
 *   +2  cosine (sine + 90 deg)
 *   +3  triangle
 *   +4  sawtooth
 *   +5  square
 *   +6  noisy sine (wired in the noise step)
 *   +7  noise      (wired in the noise step)
 *
 * Read port matches reg_block so the top-level OR-tree is unchanged.
 * The channel-to-slot mapping assumes the fixed 8-register layout.
 */
`default_nettype none

module signal_bank #(
    parameter [7:0]          BASE_ADDR    = 8'h08,
    parameter                N_REGS       = 8,
    parameter [N_REGS*8-1:0] RESET_VALUES = {N_REGS*8{1'b0}}
) (
    input  wire       clk,
    input  wire       N_RST,
    input  wire       tick,           // 1-cycle pulse: capture new samples

    // Waveform channels (combinational, from waveform_gen)
    input  wire [7:0] ch_sine,
    input  wire [7:0] ch_cosine,
    input  wire [7:0] ch_triangle,
    input  wire [7:0] ch_sawtooth,
    input  wire [7:0] ch_square,
    input  wire [7:0] ch_noisy_sine,  // tie off until the noise step
    input  wire [7:0] ch_noise,       // tie off until the noise step

    // Read port (master read-only, into the OR-tree)
    input  wire [7:0] raddr,
    output wire [7:0] rdata
);
    reg [7:0] registers [0:N_REGS-1];

    integer i;
    always @(posedge clk) begin
        if (!N_RST) begin
            // Defined reset state so the configured values are observable
            // right after reset, before the first tick.
            for (i = 0; i < N_REGS; i = i + 1)
                registers[i] <= RESET_VALUES[i*8 +: 8];
        end else if (tick) begin
            // Parallel capture: every data slot gets its own waveform.
            // Slot 0 (status) is intentionally left untouched here.
            registers[1] <= ch_sine;
            registers[2] <= ch_cosine;
            registers[3] <= ch_triangle;
            registers[4] <= ch_sawtooth;
            registers[5] <= ch_square;
            registers[6] <= ch_noisy_sine;
            registers[7] <= ch_noise;
        end
    end

    // --- Read path: matches reg_block (with the $clog2 lint-clean addressing) ---
    localparam ADDR_BITS = $clog2(N_REGS);
    wire r_selected = (raddr >= BASE_ADDR) && (raddr < BASE_ADDR + N_REGS);
    wire [ADDR_BITS-1:0] r_local =
        raddr[ADDR_BITS-1:0] - BASE_ADDR[ADDR_BITS-1:0];

    assign rdata = r_selected ? registers[r_local] : 8'd0;
endmodule