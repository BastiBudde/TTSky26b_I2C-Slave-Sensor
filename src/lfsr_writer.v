module lfsr_writer #(
    parameter [7:0] BASE_ADDR    = 8'h08,
    parameter       N_REGS       = 8,
    parameter [7:0] SEED         = 8'h01,
    parameter       TICK_DIVIDER = 4096    // alle ~4096 Takte ein neuer Schreibvorgang
) (
    input  wire        clk,
    input  wire        N_RST,
    output reg  [7:0]  waddr,
    output wire [7:0]  wdata,
    output reg         we
);
    // --- LFSR: läuft auf jeder clk-Flanke ---
    reg [7:0] lfsr;
    wire feedback = lfsr[7] ^ lfsr[5] ^ lfsr[4] ^ lfsr[3];

    always @(posedge clk) begin
        if (!N_RST)
            lfsr <= SEED;                 // Seed != 0!
        else
            lfsr <= {lfsr[6:0], feedback};
    end

    assign wdata = lfsr;

    // --- Tick-Zähler: legt fest, WANN geschrieben wird ---
    reg [11:0] tick_counter;              // 12 Bit reichen für 4096
    wire tick = (tick_counter == TICK_DIVIDER - 1);

    always @(posedge clk) begin
        if (!N_RST)
            tick_counter <= 0;
        else if (tick)
            tick_counter <= 0;
        else
            tick_counter <= tick_counter + 1;
    end

    // --- Schreib-Adresse: läuft beim Tick eins weiter, dann wieder von vorn ---
    always @(posedge clk) begin
        if (!N_RST)
            waddr <= BASE_ADDR;
        else if (tick) begin
            if (waddr == BASE_ADDR + N_REGS - 1)
                waddr <= BASE_ADDR;
            else
                waddr <= waddr + 8'd1;
        end
    end

    // --- Write-Enable: genau einen Takt lang beim Tick ---
    always @(posedge clk) begin
        if (!N_RST)
            we <= 1'b0;
        else
            we <= tick;
    end


//---------------------------------------------------------------------------------
//----------------------------- Formal Verification -------------------------------
//---------------------------------------------------------------------------------

`ifdef FORMAL
    reg f_past_valid = 0;

            initial assume(N_RST == 0);
            always @(posedge clk) begin
                    f_past_valid <= 1;

                    if(f_past_valid) begin

                        // Cover Mode Checks
                        _c_reset: cover($past(N_RST) == 0 && lfsr == SEED);
                        _c_active_writing: cover($past(lfsr) != lfsr);
                        _c_max_pattern: cover(lfsr == 8'hFF);

                        // BMC checks
                        if(tick == 1)
                            _a_generate_write_signal: assert(we == 1);
                    end
            end
    `endif


endmodule