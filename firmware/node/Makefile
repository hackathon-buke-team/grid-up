# ==========================================================================
# PANO GOZ - edge node firmware
#
#   make host      build panogoz_node for this machine with gcc  <-- default
#   make run       build and run the 'drift' scenario
#   make test      build and run the fixed-point unit self-test
#   make all-demo  build and run every scenario
#   make target    build panogoz_node.elf for STM32WLE5CC (needs
#                  arm-none-eabi-gcc; fails if absent)
#   make clean
#
# The SAME .c files build both ways.  The only difference is which
# implementation of the hal_* layer is linked:
#   host   -> host_sim.c            (a small deterministic virtual panel)
#   target -> port/stm32wle5/*.c    (vendored ST HAL/CMSIS, real peripherals)
#
# On Windows the MinGW make is called mingw32-make; everything below is
# plain POSIX make syntax and works with either.
# ==========================================================================

# GNU make PREDEFINES CC as "cc", so `CC ?= gcc` would not take effect and the
# build would look for a compiler that does not exist on a MinGW box.  Only
# override the built-in default, never an explicit CC= from the command line
# or the environment.
ifeq ($(origin CC),default)
CC := gcc
endif

BIN     := panogoz_node

# C99, no GNU extensions, warnings as errors.  -ffreestanding is NOT used for
# the host build because host_sim.c legitimately uses stdio; the firmware
# sources themselves include nothing but <stdint.h> and <stddef.h>.
CFLAGS  := -std=c99 -Wall -Wextra -Werror -O2 -g \
           -Wno-unused-parameter -DPG_HOST=1

# The firmware core.  These four files must never gain a float, a libm call
# or a malloc; -Wdouble-promotion catches the first, and the link line has no
# -lm to catch the second.
CORE    := main.c theta_edge.c prpd_bin.c radio.c power.c
HOSTSRC := $(CORE) host_sim.c
HDRS    := node.h

.PHONY: host run test all-demo target clean help

host: $(BIN)

$(BIN): $(HOSTSRC) $(HDRS)
	$(CC) $(CFLAGS) -Wdouble-promotion -o $(BIN) $(HOSTSRC)
	@echo "built $(BIN)"

run: $(BIN)
	./$(BIN) --scenario drift

test: $(BIN)
	./$(BIN) --selftest

all-demo: $(BIN)
	./$(BIN) --scenario all

# --------------------------------------------------------------------------
# Reproducible target build on Windows or POSIX. ARM_GCC_BIN may name the
# directory containing the toolchain when it is not already on PATH.
# --------------------------------------------------------------------------
PYTHON ?= python

target:
	$(PYTHON) build_target.py

clean:
	rm -f $(BIN) $(BIN).exe $(BIN).elf $(BIN).map *.o *.su

help:
	@echo "make host | run | test | all-demo | target | clean"
