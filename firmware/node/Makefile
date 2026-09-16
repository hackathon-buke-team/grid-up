# firmware/node/Makefile -- K1 1.4 (CLAUDE.md Sec.9 Hizli Komutlar):
#   cd firmware/node && make host && ./panogoz_node --selftest
#
# Two independent toolchains, neither installed via an admin-requiring
# installer (see docs/07-FIRMWARE.md Sec.2 for the full story):
#   HOST_CC -- native C99 compiler, builds the --selftest test binary that
#              runs on THIS machine (proves the algorithm, not the MCU).
#              Defaults to tcc (TinyCC), NOT gcc: the portable winlibs
#              MinGW-w64 gcc's cc1.exe fails to execute in this environment
#              (reproducible -- exits immediately with NTSTATUS-shaped code
#              0xC0E90002, no diagnostic text; smaller winlibs tools like
#              as.exe/objdump.exe run fine, so it is specific to cc1.exe,
#              not a blanket toolchain block -- see docs/07 Sec.2). tcc has
#              no such issue and is a real, independent C99 compiler.
#   ARM_CC  -- arm-none-eabi-gcc (xPack build), cross-compiles the real
#              STM32WLE5CC target (proves it fits/links for the real MCU --
#              flash/RAM report). This one works with no issues.
# Override on the command line if the toolchains are not on PATH, e.g.:
#   make target ARM_CC=/path/to/arm-none-eabi-gcc
#   make host HOST_CC=/path/to/gcc   (if your gcc doesn't hit the tcc issue)

HOST_CC ?= tcc
ARM_CC ?= arm-none-eabi-gcc
ARM_SIZE ?= arm-none-eabi-size

CFLAGS_COMMON = -std=c99 -Wall -Wextra -Iinclude

HOST_BIN = panogoz_node
HOST_SRCS = src/theta_fixed.c src/max31855.c src/selftest.c

# -mfloat-abi=soft is deliberate, not the STM32WLE5's default: it forces the
# compiler to emit zero VFP/float instructions even though the real Cortex-M4
# core has an FPU, matching CLAUDE.md's firmware constraint ("float/malloc
# yok") as something make target can actually verify (see the objdump check
# in docs/07-FIRMWARE.md Sec.3), not just a promise kept by not calling
# <math.h> in this file.
TARGET_MCU_FLAGS = -mcpu=cortex-m4 -mthumb -mfloat-abi=soft
TARGET_CFLAGS = $(CFLAGS_COMMON) $(TARGET_MCU_FLAGS) -ffreestanding -fno-builtin -Os -ffunction-sections -fdata-sections
# -nostdlib drops libc (no OS underneath, correctly excluded) but also
# drops libgcc, which is where the compiler's own 64-bit divide helper
# (__aeabi_ldivmod, used by theta_fixed.c's int64_t arithmetic -- the
# Cortex-M4 has no hardware instruction for a 64-bit integer divide) lives.
# -lgcc adds ONLY that pure-computation runtime helper library back in (no
# syscalls, no heap, still float/malloc-free) -- it MUST come after every
# object file on the command line (below, in each target's recipe), not in
# this flags variable: ld resolves a library's symbols only against object
# files it has already seen, so -lgcc ahead of the .c inputs silently fails
# to resolve __aeabi_ldivmod (this was tried first and produced exactly
# that failure -- see docs/07-FIRMWARE.md Sec.3).
TARGET_LDFLAGS = $(TARGET_MCU_FLAGS) -T stm32wle5cc.ld -nostdlib -Wl,--gc-sections

.PHONY: all host target clean

all: host target

host: $(HOST_BIN)

$(HOST_BIN): $(HOST_SRCS)
	$(HOST_CC) $(CFLAGS_COMMON) -O2 -o $@ $^

# 3 real boards (hardware/kicad/{tc-node,ir-pd-node,gateway}), same shared
# algorithm files (theta_fixed.c/max31855.c/startup.c), different main_*.c.
target: tc-node.elf ir-pd-node.elf gateway.elf

tc-node.elf: src/startup.c src/theta_fixed.c src/max31855.c src/main_tc.c stm32wle5cc.ld
	$(ARM_CC) $(TARGET_CFLAGS) $(TARGET_LDFLAGS) -o $@ src/startup.c src/theta_fixed.c src/max31855.c src/main_tc.c -lgcc
	$(ARM_SIZE) $@

ir-pd-node.elf: src/startup.c src/theta_fixed.c src/max31855.c src/main_irpd.c stm32wle5cc.ld
	$(ARM_CC) $(TARGET_CFLAGS) $(TARGET_LDFLAGS) -o $@ src/startup.c src/theta_fixed.c src/max31855.c src/main_irpd.c -lgcc
	$(ARM_SIZE) $@

gateway.elf: src/startup.c src/theta_fixed.c src/max31855.c src/main_gw.c stm32wle5cc.ld
	$(ARM_CC) $(TARGET_CFLAGS) $(TARGET_LDFLAGS) -o $@ src/startup.c src/theta_fixed.c src/max31855.c src/main_gw.c -lgcc
	$(ARM_SIZE) $@

clean:
	rm -f $(HOST_BIN) $(HOST_BIN).exe *.elf *.map
