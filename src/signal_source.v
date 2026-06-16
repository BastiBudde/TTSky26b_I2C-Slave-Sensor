/*
 * signal_source.v — DDS pseudo-sensor for Block B
 *
 * Drop-in replacement for (lfsr_writer + reg_block_b). Generates a tick,
 * runs the phase accumulator, derives all waveforms, and captures them
 * into the signal_bank in parallel. Exposes a reg_block-style read port.
 */
`default_nettype none

module signal_source #(
    parameter [7:0]          BASE_ADDR    = 8'h08,
    parameter                N_REGS       = 8,
    parameter [N_REGS*8-1:0] RESET_VALUES = {N_REGS*8{1'b0}},
    parameter                TICK_DIVIDER = 4096,
    parameter                ACC_WIDTH    = 16,
    parameter [7:0]          LFSR_SEED    = 8'hA5
) (
    input  wire                 clk,
    input  wire                 N_RST,
    input  wire [ACC_WIDTH-1:0] phase_inc,   // frequency word (Block A later)
    input  wire [7:0]           raddr,
    output wire [7:0]           rdata,
    input  wire                 read_strobe,
    input  wire [7:0]           read_addr
);
    // --- Tick generator: one pulse every TICK_DIVIDER clocks ---
    localparam CNT_WIDTH = $clog2(TICK_DIVIDER);
    localparam [CNT_WIDTH-1:0] TICK_MAX = TICK_DIVIDER - 1;

    reg [CNT_WIDTH-1:0] tick_counter;
    wire tick = (tick_counter == TICK_MAX);

    always @(posedge clk) begin
        if (!N_RST)        tick_counter <= {CNT_WIDTH{1'b0}};
        else if (tick)     tick_counter <= {CNT_WIDTH{1'b0}};
        else               tick_counter <= tick_counter + 1'b1;
    end

    // --- Phase accumulator ---
    wire [7:0] phase;
    phase_accumulator #(.ACC_WIDTH(ACC_WIDTH)) u_phase (
        .clk       (clk),
        .N_RST     (N_RST),
        .tick      (tick),
        .phase_inc (phase_inc),
        .phase     (phase)
    );

    // --- Waveforms ---
    wire [7:0] w_sine, w_cosine, w_triangle, w_sawtooth, w_square;
    waveform_gen u_wave (
        .phase    (phase),
        .sine     (w_sine),
        .cosine   (w_cosine),
        .triangle (w_triangle),
        .sawtooth (w_sawtooth),
        .square   (w_square)
    );

    // --- Noise source (free-running) ---
    wire [7:0] w_noise;
    lfsr8 #(.SEED(LFSR_SEED)) u_lfsr (
        .clk   (clk),
        .N_RST (N_RST),
        .value (w_noise)
    );

    // --- Noisy sine: clean sine + saturated LFSR noise ---
    wire [7:0] w_noisy_sine;
    noise_mixer u_mixer (
        .sample (w_sine),
        .lfsr   (w_noise),
        .out    (w_noisy_sine)
    );

    // --- Register bank ---
    signal_bank #(
        .BASE_ADDR    (BASE_ADDR),
        .N_REGS       (N_REGS),
        .RESET_VALUES (RESET_VALUES)
    ) u_bank (
        .clk           (clk),
        .N_RST         (N_RST),
        .tick          (tick),
        .ch_sine       (w_sine),
        .ch_cosine     (w_cosine),
        .ch_triangle   (w_triangle),
        .ch_sawtooth   (w_sawtooth),
        .ch_square     (w_square),
        .ch_noisy_sine (w_noisy_sine),
        .ch_noise      (w_noise),
        .raddr         (raddr),
        .rdata         (rdata),
        .read_strobe (read_strobe),
        .read_addr   (read_addr)
    );
endmodule