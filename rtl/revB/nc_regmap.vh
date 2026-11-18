// nc_regmap.vh -- byte-addressed register map of neuron_ctrl (rev B).
// Single source of truth for the RTL; test/regmap.py mirrors it and
// docs/regmap.md documents it. Included inside module bodies.
//
// SPI frame (16 bit, MSB first): { RW, ADDR[6:0], DATA[7:0] }   RW=1 read.
// Writable registers 0x00..0x13 (latches, reset 0), read-only 0x14..0x19.

localparam NREG    = 20;        // writable bytes -> cfg_out[8*NREG-1:0]
localparam CHIP_ID = 8'hA2;     // rev B

// ----------------------------------------------------------- addresses
localparam A_CTRL     = 7'h00;  // [0] SPK_MODE [2:1] CNT_MODE [4:3] CNT_SRC
localparam A_RT       = 7'h01;  // [3:0] RT_EN  [7:4] TRIM_EN (analog, provisional)
localparam A_SEL0     = 7'h02;  // [4:0] neuron on uo[0]
localparam A_SEL1     = 7'h03;  // [4:0] neuron on uo[1]
localparam A_SEL2     = 7'h04;  // [4:0] neuron on uo[2]
localparam A_SEL3     = 7'h05;  // [4:0] neuron on uo[3]
localparam A_PROBE    = 7'h06;  // [4:0] PROBE_SEL [6:5] PROBE_SUB [7] PROBE_EN
localparam A_GRP      = 7'h07;  // [7:0] GRP_EN (4 neurons / group)
localparam A_DAC_LEAK = 7'h08;  // provisional
localparam A_DAC_VTH  = 7'h09;  // provisional
localparam A_DAC_VRST = 7'h0A;  // provisional
localparam A_DAC_WSYN = 7'h0B;  // provisional
localparam A_SC       = 7'h0C;  // [3:0] SC_DIV log2 (0=off) [7:6] PLATEAU_EN
localparam A_ANA      = 7'h0D;  // [0] BIAS_EN [2:1] UA0_MODE
localparam A_LIF0     = 7'h0E;  // [0] EN [2:1] SRC [3] STEP [7:4] PRESC
localparam A_LIF1     = 7'h0F;  // [3:0] SHIFT [7:4] REFR
localparam A_LIF_EL   = 7'h10;  // EL   code (V = code << (W-8))
localparam A_LIF_VTH  = 7'h11;  // VTH  code
localparam A_LIF_VRST = 7'h12;  // VRST code
localparam A_LIF_W    = 7'h13;  // input weight (LSB units)
// read-only
localparam A_CNT_L    = 7'h14;  // counter [7:0]  (reading captures CNT_H into HOLD)
localparam A_CNT_H    = 7'h15;  // HOLD
localparam A_LIFV_L   = 7'h16;  // V[7:0]        (reading captures {REF, V[11:8]} into HOLD)
localparam A_LIFV_H   = 7'h17;  // HOLD
localparam A_STATUS   = 7'h18;  // {cnt_gate, cnt_sat, probe_valid, lif_en, lif_pend, lif_busy, 2'b0}
localparam A_ID       = 7'h19;  // CHIP_ID

// Bits with storage, per writable byte (index = address).
localparam [8*NREG-1:0] REG_USED = {
    8'hFF, 8'hFF, 8'hFF, 8'hFF,     // 0x13..0x10 LIF codes
    8'hFF, 8'hFF,                   // 0x0F LIF1, 0x0E LIF0
    8'h07,                          // 0x0D ANA
    8'hCF,                          // 0x0C SC
    8'hFF, 8'hFF, 8'hFF, 8'hFF,     // 0x0B..0x08 DACs
    8'hFF,                          // 0x07 GRP
    8'hFF,                          // 0x06 PROBE
    8'h1F, 8'h1F, 8'h1F, 8'h1F,     // 0x05..0x02 SEL3..SEL0
    8'hFF,                          // 0x01 RT/TRIM
    8'h1F                           // 0x00 CTRL
};
