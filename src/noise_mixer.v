/*
 * noise_mixer.v — saturating add of a signed noise term to a sample
 */
`default_nettype none

module noise_mixer (
    input  wire signed [6:0] noise,    // pre-scaled, centered: -32..+31 max
    input  wire        [7:0] sample,
    output reg         [7:0] out
);
    wire signed [9:0] total = $signed({3'b0, sample}) + noise;  // -32..+286
    always @(*) begin
        if      (total > 10'sd255) out = 8'd255;
        else if (total < 10'sd0)   out = 8'd0;
        else                       out = total[7:0];
    end
endmodule