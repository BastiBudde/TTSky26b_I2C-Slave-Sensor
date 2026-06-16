/*
 * noise_mixer.v — adds signed LFSR noise to a sample, with saturation
 *
 * noise = lfsr[3:0] - 8   -> signed range -8..+7
 * out   = saturate(sample + noise) to 0..255
 *
 * Saturation prevents the ugly wrap-around glitch when the sine peaks
 * (near 255) or troughs (near 0) would otherwise overflow.
 */
`default_nettype none

module noise_mixer (
    input  wire [7:0] sample,    // clean waveform (e.g. sine)
    input  wire [7:0] lfsr,      // raw LFSR value (noise source)
    output reg  [7:0] out
);
    // Center the low 4 LFSR bits to a signed -8..+7 noise term.
    // Work in signed 10-bit to give headroom for over/underflow detection.
    wire signed [9:0] noise  = $signed({6'b0, lfsr[3:0]}) - 10'sd8;
    wire signed [9:0] total  = $signed({2'b0, sample}) + noise;  // -8 .. 262

    always @(*) begin
        if (total > 10'sd255)
            out = 8'd255;            // saturate high
        else if (total < 10'sd0)
            out = 8'd0;              // saturate low
        else
            out = total[7:0];        // in range
    end
endmodule