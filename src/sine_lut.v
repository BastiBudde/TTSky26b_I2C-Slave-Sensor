/*
 * sine_lut.v — 8-bit sine wave via quarter-wave symmetry
 *
 * Maps an 8-bit phase (0..255 = 0..2*pi) to an 8-bit unsigned amplitude
 * (0..255, centered at 127.5). Only the first quadrant (64 magnitudes)
 * is stored; the other three quadrants are derived by mirroring the low
 * 6 phase bits (~pos) and negating around the center (quadrant MSBs).
 *
 * Max error vs. a full 256-entry table: 1 LSB (rounding only).
 */
`default_nettype none

module sine_lut (
    input  wire [7:0] phase,
    output reg  [7:0] amplitude
);
    wire [1:0] quadrant = phase[7:6];
    wire [5:0] pos      = phase[5:0];

    // Mirror the position for the descending quadrants.
    // ~pos == 63 - pos for 6-bit values, so this is the exact mirror.
    wire [5:0] index = (quadrant == 2'd1 || quadrant == 2'd3) ? ~pos : pos;

    // First-quadrant magnitude (0..127), midpoint-sampled
    reg [7:0] q;
    always @(*) begin
        case (index)
            6'd0 : q = 8'd2;
            6'd1 : q = 8'd5;
            6'd2 : q = 8'd8;
            6'd3 : q = 8'd11;
            6'd4 : q = 8'd14;
            6'd5 : q = 8'd17;
            6'd6 : q = 8'd20;
            6'd7 : q = 8'd23;
            6'd8 : q = 8'd26;
            6'd9 : q = 8'd29;
            6'd10: q = 8'd32;
            6'd11: q = 8'd36;
            6'd12: q = 8'd39;
            6'd13: q = 8'd41;
            6'd14: q = 8'd44;
            6'd15: q = 8'd47;
            6'd16: q = 8'd50;
            6'd17: q = 8'd53;
            6'd18: q = 8'd56;
            6'd19: q = 8'd59;
            6'd20: q = 8'd61;
            6'd21: q = 8'd64;
            6'd22: q = 8'd67;
            6'd23: q = 8'd70;
            6'd24: q = 8'd72;
            6'd25: q = 8'd75;
            6'd26: q = 8'd77;
            6'd27: q = 8'd80;
            6'd28: q = 8'd82;
            6'd29: q = 8'd84;
            6'd30: q = 8'd87;
            6'd31: q = 8'd89;
            6'd32: q = 8'd91;
            6'd33: q = 8'd93;
            6'd34: q = 8'd96;
            6'd35: q = 8'd98;
            6'd36: q = 8'd100;
            6'd37: q = 8'd101;
            6'd38: q = 8'd103;
            6'd39: q = 8'd105;
            6'd40: q = 8'd107;
            6'd41: q = 8'd109;
            6'd42: q = 8'd110;
            6'd43: q = 8'd112;
            6'd44: q = 8'd113;
            6'd45: q = 8'd115;
            6'd46: q = 8'd116;
            6'd47: q = 8'd117;
            6'd48: q = 8'd118;
            6'd49: q = 8'd120;
            6'd50: q = 8'd121;
            6'd51: q = 8'd122;
            6'd52: q = 8'd122;
            6'd53: q = 8'd123;
            6'd54: q = 8'd124;
            6'd55: q = 8'd125;
            6'd56: q = 8'd125;
            6'd57: q = 8'd126;
            6'd58: q = 8'd126;
            6'd59: q = 8'd127;
            6'd60: q = 8'd127;
            6'd61: q = 8'd127;
            6'd62: q = 8'd127;
            6'd63: q = 8'd127;
            default: q = 8'd0;
        endcase
    end

    // Combine quadrant: upper half adds to center, lower half subtracts.
    always @(*) begin
        case (quadrant)
            2'd0:    amplitude = 8'd128 + q;  // 0..90   ascending  positive
            2'd1:    amplitude = 8'd128 + q;  // 90..180 descending positive
            2'd2:    amplitude = 8'd127 - q;  // 180..270 descending negative
            2'd3:    amplitude = 8'd127 - q;  // 270..360 ascending  negative
            default: amplitude = 8'd128;
        endcase
    end
endmodule