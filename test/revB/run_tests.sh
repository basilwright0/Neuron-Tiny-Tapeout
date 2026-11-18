#!/bin/bash
# Run the cocotb suite inside the EDA container:
#   scripts/eda.sh "bash test/run_tests.sh"          (all tests)
#   scripts/eda.sh "bash test/run_tests.sh test_lif" (one module)
set -e
export LD_LIBRARY_PATH=/foss/tools/iverilog/lib:${LD_LIBRARY_PATH}
cd /work/test/revB
rm -rf sim_build results.xml
if [ -n "$1" ]; then make MODULE="$1"; else make; fi
python3 - <<'PY'
import xml.etree.ElementTree as ET
r = ET.parse("results.xml").getroot()
tc = list(r.iter("testcase"))
fail = [t.get("name") for t in tc if t.find("failure") is not None or t.find("error") is not None]
print(f"SUMMARY: {len(tc)-len(fail)} passed, {len(fail)} failed {fail}")
PY
