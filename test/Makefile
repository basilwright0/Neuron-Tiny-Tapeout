# cocotb + iverilog tests for the neuron_ctrl control plane rev C (rtl/).
# Run from the repo root:  scripts/eda.sh "make -C test"
# Works with cocotb 1.8 (MODULE/TOPLEVEL) and 2.x (COCOTB_TEST_MODULES/COCOTB_TOPLEVEL).

SIM ?= icarus
TOPLEVEL_LANG ?= verilog
RTL_DIR = $(CURDIR)/../rtl

VERILOG_SOURCES += $(CURDIR)/tb.v \
                   $(RTL_DIR)/neuron_ctrl.v \
                   $(RTL_DIR)/nc_cfg.v \
                   $(RTL_DIR)/nc_sync.v \
                   $(RTL_DIR)/digital_lif.v
COMPILE_ARGS += -g2005 -I$(RTL_DIR)

TOPLEVEL = tb
COCOTB_TOPLEVEL = tb
MODULE ?= test_ctrl,test_lif
COCOTB_TEST_MODULES ?= $(MODULE)

include $(shell cocotb-config --makefiles)/Makefile.sim
