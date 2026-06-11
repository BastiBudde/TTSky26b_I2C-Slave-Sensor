/*
 * phase_accumulator.v — DDS phase accumulator
 *
 * Adds phase_inc to a free-running accumulator on every tick. The top
 * 8 bits form the phase index into the sine LUT. Output frequency is
 *
 *     f_out = (phase_inc / 2^ACC_WIDTH) * f_tick
 *
 * so phase_inc is the frequency control word.
 */
`default_nettype none

module phase_accumulator #(
    parameter ACC_WIDTH = 16
) (
    input  wire                  clk,
    input  wire                  N_RST,
    input  wire                  tick,        // 1-cycle pulse: advance the phase
    input  wire [ACC_WIDTH-1:0]  phase_inc,   // frequency control word
    output wire [7:0]            phase         // top 8 bits -> sine LUT index
);
    reg [ACC_WIDTH-1:0] acc;

    always @(posedge clk) begin
        if (!N_RST)
            acc <= {ACC_WIDTH{1'b0}};
        else if (tick)
            acc <= acc + phase_inc;
    end

    // The top 8 bits of the accumulator index the LUT
    assign phase = acc[ACC_WIDTH-1 -: 8];
endmodule