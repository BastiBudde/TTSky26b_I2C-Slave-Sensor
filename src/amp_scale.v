/*
 * amp_scale.v — center-relative amplitude scaling by power-of-2 attenuation
 * shift 0 = full, 1 = half, 2 = quarter, 3 = eighth. No DC drift, no overflow.
 */
`default_nettype none

module amp_scale (
    input  wire [7:0] sample,
    input  wire [1:0] shift,
    output wire [7:0] scaled
);
    wire signed [8:0] centered = $signed({1'b0, sample}) - 9'sd128;
    wire signed [8:0] shifted  = centered >>> shift;     // arithmetic
    assign scaled = shifted[7:0] + 8'd128;
endmodule