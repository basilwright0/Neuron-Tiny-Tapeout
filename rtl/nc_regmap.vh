// nc_regmap.vh -- write-only configuration map of neuron_ctrl (rev E).
// Single source of truth for the RTL; test/regmap.py mirrors it and
// docs/regmap.md documents it. Included inside the module body (after the
// parameter list). rtl/scripts/gen_bias_if.py reads A_IDAC / A_VDAC / A_ANA /
// A_MODE from this file.
//
// Frame (13 bit, MSB first, shifted on SCK rising edges): { ADDR[4:0], DATA[7:0] }.
// Only the last 13 bits shifted before LOAD count, so 16-bit frames with 3
// leading don't-care bits work. LOAD high writes DATA to byte ADDR.
// Every byte is a bank of transparent-high latches (latrnq), reset to 0.

localparam AW     = 5;              // address bits
localparam FW     = AW + 8;         // frame bits
localparam NREG   = 23;             // address space 0x00..0x16 (trim bytes beyond NTRIM unused)

// ----------------------------------------------------------- addresses
localparam A_IDAC    = 5'h00;  // 0x00..0x04: eight 5-bit current-DAC codes packed LSB first
                               //   as one 40-bit word (code k = bits [5k+4:5k]); 0 = off
localparam A_VDAC    = 5'h05;  // [5:0] voltage-DAC code (vth_ref)
localparam A_ANA     = 5'h06;  // [3:0] GRP_EN [4] PLATEAU_EN [5] D1_CHAIN [6] BIAS_EN [7] D1_BSEL
localparam A_PROBE   = 5'h07;  // [3:0] PROBE_SEL [5:4] PROBE_SUB [6] PROBE_EN
localparam A_MODE    = 5'h08;  // [1:0] UA0_MODE [2] OUT_MUX [3] IB_X2 [7:4] RT_EN
localparam A_LIF_CTL = 5'h09;  // [0] LIF_EN [2:1] LIF_SRC        (clk-domain controls)
localparam A_LIF_SR  = 5'h0A;  // [3:0] LIF_SHIFT [7:4] LIF_REFR
localparam A_LIF_EL  = 5'h0B;  // EL   code (V = code << (W-8))
localparam A_LIF_VTH = 5'h0C;  // VTH  code
localparam A_LIF_VRST= 5'h0D;  // VRST code
localparam A_LIF_W   = 5'h0E;  // input weight (LSB units)
localparam A_TRIM0   = 5'h0F;  // 0x0F..0x16 TRIM0..7: [3:0] nibble 2k, [7:4] nibble 2k+1

// Bits with storage, per byte (index = address), before the NTRIM / TRIM_MASK cut.
localparam [8*NREG-1:0] REG_USED = {
    {8{8'hFF}},                     // 0x16..0x0F TRIM
    8'hFF, 8'hFF, 8'hFF, 8'hFF,     // 0x0E..0x0B LIF W/VRST/VTH/EL
    8'hFF,                          // 0x0A LIF_SR
    8'h07,                          // 0x09 LIF_CTL
    8'hFF,                          // 0x08 MODE
    8'h7F,                          // 0x07 PROBE
    8'hFF,                          // 0x06 ANA
    8'h3F,                          // 0x05 VDAC
    {5{8'hFF}}                      // 0x04..0x00 IDAC
};

// ----------------------------------------------------------- analog outputs
// IDAC/VDAC/master lines go to bias_b1 as named ports (nc_bias_ports.vh,
// generated). The probe has its own ports. cfg_out carries the rest, packed:
localparam CFG_GRP   = 0;           // GRP_EN     [3:0]
localparam CFG_PLAT  = 4;           // PLATEAU_EN [4]   (D1 plateau enable)
localparam CFG_CHAIN = 5;           // D1_CHAIN   [5]   (0 star / 1 chain)
localparam CFG_BSEL  = 6;           // D1_BSEL    [6]   (stim B: 0 clustered -> d1, 1 distributed -> d2)
localparam CFG_TRIM  = 7;           // TRIM n     at [7+4n+3 : 7+4n]
// cfg_out width = CFG_TRIM + 4 * NTRIM
