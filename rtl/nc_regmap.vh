// nc_regmap.vh -- write-only configuration map of neuron_ctrl (rev C).
// Single source of truth for the RTL; test/regmap.py mirrors it and
// docs/regmap.md documents it. Included inside the module body (after the
// parameter list).
//
// Frame (13 bit, MSB first, shifted on SCK rising edges): { ADDR[4:0], DATA[7:0] }.
// Only the last 13 bits shifted before LOAD count, so 16-bit frames with 3
// leading don't-care bits work. LOAD high writes DATA to byte ADDR.
// Every byte is a bank of transparent-high latches (latrnq), reset to 0.

localparam AW     = 5;              // address bits
localparam FW     = AW + 8;         // frame bits
localparam NREG   = 26;             // address space 0x00..0x19 (trim bytes beyond NTRIM unused)

// ----------------------------------------------------------- addresses
localparam A_IDAC0   = 5'h00;  // 0x00..0x05 IDAC0..5: [4:0] FINE  [7:5] RANGE
localparam A_VDAC0   = 5'h06;  // 0x06..0x08 VDAC0..2: [5:0] code
localparam A_ANA     = 5'h09;  // [3:0] GRP_EN [5:4] PLATEAU_EN [6] BIAS_EN
localparam A_PROBE   = 5'h0A;  // [3:0] PROBE_SEL [5:4] PROBE_SUB [6] PROBE_EN
localparam A_MODE    = 5'h0B;  // [1:0] UA0_MODE [2] OUT_MUX [7:4] RT_EN
localparam A_CLKD    = 5'h0C;  // [3:0] SC_DIV [4] LIF_EN [6:5] LIF_SRC   (clk-domain controls)
localparam A_LIF_SR  = 5'h0D;  // [3:0] LIF_SHIFT [7:4] LIF_REFR
localparam A_LIF_EL  = 5'h0E;  // EL   code (V = code << (W-8))
localparam A_LIF_VTH = 5'h0F;  // VTH  code
localparam A_LIF_VRST= 5'h10;  // VRST code
localparam A_LIF_W   = 5'h11;  // input weight (LSB units)
localparam A_TRIM0   = 5'h12;  // 0x12..0x19 TRIM0..7: [3:0] neuron 2k, [7:4] neuron 2k+1

// Bits with storage, per byte (index = address), before the NTRIM cut.
localparam [8*NREG-1:0] REG_USED = {
    {8{8'hFF}},                     // 0x19..0x12 TRIM
    8'hFF, 8'hFF, 8'hFF, 8'hFF,     // 0x11..0x0E LIF W/VRST/VTH/EL
    8'hFF,                          // 0x0D LIF_SR
    8'h7F,                          // 0x0C CLKD
    8'hF7,                          // 0x0B MODE
    8'h7F,                          // 0x0A PROBE
    8'h7F,                          // 0x09 ANA
    8'h3F, 8'h3F, 8'h3F,            // 0x08..0x06 VDAC
    {6{8'hFF}}                      // 0x05..0x00 IDAC
};

// ----------------------------------------------------------- cfg_out packing
// cfg_out carries only analog bits, packed without gaps:
localparam CFG_IDAC  = 0;           // IDAC k   at [8k+7 : 8k]       (48)
localparam CFG_VDAC  = 48;          // VDAC k   at [48+6k+5 : 48+6k]  (18)
localparam CFG_PSUB  = 66;          // PROBE_SUB [67:66]
localparam CFG_PEN   = 68;          // PROBE_EN  [68]
localparam CFG_GRP   = 69;          // GRP_EN    [72:69]
localparam CFG_PLAT  = 73;          // PLATEAU_EN[74:73]
localparam CFG_BIAS  = 75;          // BIAS_EN   [75]
localparam CFG_UA0   = 76;          // UA0_MODE  [77:76]
localparam CFG_TRIM  = 78;          // TRIM n    at [78+4n+3 : 78+4n]
// cfg_out width = CFG_TRIM + 4 * NTRIM
