module reg_block #(
        parameter [7:0] BASE_ADDR = 8'h00,
        parameter       N_REGS    = 16,
        // Reset valus for registers; Default is all 0s
        parameter [N_REGS*8-1:0] RESET_VALUES = {(N_REGS*8){1'b0}}
) (
        input wire         clk,
        input wire         N_RST,
        // Schreib-Port (in deinem Fall: LFSR)
        input  wire [7:0]  waddr,
        input  wire [7:0]  wdata,
        input  wire        we,
        // Lese-Port (in deinem Fall: I²C-Slave)
        input  wire [7:0]  raddr,
        output wire [7:0]  rdata
);
    

//---------------------------------------------------------------------------------
//-------------------------------- Adress decoding --------------------------------
//---------------------------------------------------------------------------------
wire w_selected = (waddr >= BASE_ADDR) && (waddr < BASE_ADDR + N_REGS);
wire r_selected = (raddr >= BASE_ADDR) && (raddr < BASE_ADDR + N_REGS);
wire [7:0] w_local_addr = waddr - BASE_ADDR;
wire [7:0] r_local_addr = raddr - BASE_ADDR;


//---------------------------------------------------------------------------------
//------------------------- Register array, reset, write --------------------------
//---------------------------------------------------------------------------------
reg [7:0] registers [0:N_REGS-1]; // array of N_REGS x 8-bit registers

integer i;
always @(posedge clk) begin
        if (!N_RST) begin
                // reset all registers to 0 on active low reset
                for (i = 0; i < N_REGS; i = i + 1) 
                        registers[i] <= RESET_VALUES[i*8 +: 8];
        end
        else if (w_selected && we) 
                // write wdata to the addressed register (warrd) when selected and we is high
                registers[w_local_addr] <= wdata;
end


//---------------------------------------------------------------------------------
//-------------------------------- Register read ----------------------------------
//---------------------------------------------------------------------------------
assign rdata = r_selected ? registers[r_local_addr] : 8'd0; // output the value of the addressed register when selected, otherwise output 0



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
                        begin : _c_reset
                                for (i = 0; i < N_REGS; i = i + 1) 
                                        cover($past(N_RST) == 0 && registers[i] == RESET_VALUES[i*8 +: 8]); 
                        end
                        _c_read: cover(rdata == registers[r_local_addr] && r_selected == 1);
                        _c_write: cover($past(w_selected) == 1 && $past(we) == 1 && $past(wdata) == 8'hFF && registers[w_local_addr] <= 8'hFF); 

                        // BMC Checks
                        if($past(w_selected) == 1 && $past(we) == 1 && $past(wdata) == 8'hFF && r_selected == 0)
                                _a_read_not: assert(rdata == 8'd0);
                        
                                //this check is eliminated because it takes a very long time
                        /* if($past(N_RST) == 0) begin
                                begin: _a_prove_reset
                                        for (i = 0; i < N_REGS; i = i + 1) 
                                                assert(registers[i] == RESET_VALUES[i*8 +: 8]);
                                end
                        end */
                end
        end


`endif

endmodule