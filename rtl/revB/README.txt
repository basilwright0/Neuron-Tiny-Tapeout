Rev B snapshot (byte-addressed SPI register file, 37.4k um2, hardened at 290x290 um),
copied here before the rev C rewrite. Scripts/paths are re-pointed at rtl/revB and test/revB:
  scripts/eda.sh "bash test/revB/run_tests.sh"
  scripts/eda.sh "bash rtl/revB/scripts/lint.sh"
regmap_revB.md is the rev B docs/regmap.md. synth/ holds the rev B yosys results.
