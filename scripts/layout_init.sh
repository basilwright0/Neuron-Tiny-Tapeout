#!/bin/bash
# Re-create the empty 1x2 GF analog frame (pins + power stripes). Overwrites mag/<top>.mag!
set -e
cd mag && magic -dnull -noconsole -rcfile $PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc init_project.tcl <<< "quit -noprompt"
mkdir -p ../gds ../lef && mv -f gds/*.gds ../gds/ && mv -f lef/*.lef ../lef/ && rmdir gds lef
