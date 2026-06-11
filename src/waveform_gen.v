/*
 * waveform_gen.v — derives multiple waveforms from one phase value
 *
 * Pure combinational. All outputs are functions of the same 8-bit phase,
 * so they stay phase-coherent. Sine and cosine form a quadrature pair
 * (cosine leads sine by 90 deg = 64/256 of a period).
 *
 * Outputs are 8-bit unsigned, full scale 0..255, centered at 127.5.
 */
`default_nettype none

module waveform_gen (
    input  wire [7:0] phase,
    output wire [7:0] sine,
    output wire [7:0] cosine,
    output wire [7:0] triangle,
    output wire [7:0] sawtooth,
    output wire [7:0] square
);
    // --- Sine via the verified quarter-wave LUT ---
    sine_lut u_sine (
        .phase     (phase),
        .amplitude (sine)
    );

    // --- Cosine = sine shifted by 90 deg (64 of 256). Second LUT instance. ---
    sine_lut u_cosine (
        .phase     (phase + 8'd64),
        .amplitude (cosine)
    );

    // --- Triangle: rising over phase 0..127, falling over 128..255 ---
    // doubled = {phase[6:0], 1'b0}; invert in the upper half to fold it.
    wire [7:0] doubled = {phase[6:0], 1'b0};
    assign triangle = phase[7] ? ~doubled : doubled;

    // --- Sawtooth: the phase itself (rises 0..255, wraps) ---
    assign sawtooth = phase;

    // --- Square: 50% duty from the phase MSB ---
    assign square = phase[7] ? 8'hFF : 8'h00;
endmodule