/*
 * lfsr8.v — 8-bit LFSR noise source, advances on enable
 * Taps [7,5,4,3], period 255. Seed must be non-zero.
 */
`default_nettype none

module lfsr8 #(
    parameter [7:0] SEED = 8'hA5
) (
    input  wire       clk,
    input  wire       N_RST,
    input  wire       en,         // advance one step when high
    output wire [7:0] value
);
    reg [7:0] lfsr;
    wire fb = lfsr[7] ^ lfsr[5] ^ lfsr[4] ^ lfsr[3];

    always @(posedge clk) begin
        if (!N_RST)
            lfsr <= SEED;             // non-zero seed required
        else if (en)
            lfsr <= {lfsr[6:0], fb};
    end

    assign value = lfsr;
endmodule