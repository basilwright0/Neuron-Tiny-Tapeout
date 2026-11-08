#!/bin/bash
# Local Tiny Tapeout precheck (same checks as the GitHub action @ttgf26c).
# Requires .tools/tt-support-tools (git clone https://github.com/TinyTapeout/tt-support-tools .tools/tt-support-tools)
set -e
TOP=$(grep -oP 'top_module:\s*"\K[^"]+' info.yaml)
cp src/project.v gds/$TOP.v
python3 -c "import gdstk, yaml, klayout" 2>/dev/null || pip install -q --target /work/.tools/pydeps gdstk==0.9.52 pyyaml klayout==0.30.11 yowasp-yosys
cd .tools/tt-support-tools/precheck && python3 precheck.py --gds /work/gds/$TOP.gds --tech gf180mcuD 2>&1 | tail -25
