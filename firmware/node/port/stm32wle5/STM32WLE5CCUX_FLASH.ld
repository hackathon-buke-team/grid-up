/* K1 direct-SWD design build. OTA is disabled; no bootloader is implied.
 * STM32WLE5CC: 256 KiB flash, 64 KiB SRAM. Keep 16 KiB config unallocated.
 * An additional ASSERT limits this application's flash to one 88 KiB slot.
 */
ENTRY(Reset_Handler)
MEMORY {
  FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 240K
  RAM (xrw) : ORIGIN = 0x20000000, LENGTH = 64K
}
_estack = ORIGIN(RAM) + LENGTH(RAM);
_Min_Stack_Size = 4096;
SECTIONS {
  .isr_vector : { . = ALIGN(4); KEEP(*(.isr_vector)) . = ALIGN(4); } >FLASH
  .text : { *(.text*) *(.rodata*) KEEP(*(.init)) KEEP(*(.fini)) . = ALIGN(4); } >FLASH
  .ARM.extab : { *(.ARM.extab*) } >FLASH
  .ARM.exidx : { __exidx_start = .; *(.ARM.exidx*) __exidx_end = .; } >FLASH
  .preinit_array : { PROVIDE_HIDDEN(__preinit_array_start = .); KEEP(*(.preinit_array*)) PROVIDE_HIDDEN(__preinit_array_end = .); } >FLASH
  .init_array : { PROVIDE_HIDDEN(__init_array_start = .); KEEP(*(SORT(.init_array.*))) KEEP(*(.init_array*)) PROVIDE_HIDDEN(__init_array_end = .); } >FLASH
  .fini_array : { PROVIDE_HIDDEN(__fini_array_start = .); KEEP(*(SORT(.fini_array.*))) KEEP(*(.fini_array*)) PROVIDE_HIDDEN(__fini_array_end = .); } >FLASH
  _sidata = LOADADDR(.data);
  .data : { . = ALIGN(4); _sdata = .; *(.data*) . = ALIGN(4); _edata = .; } >RAM AT>FLASH
  .bss (NOLOAD) : { . = ALIGN(4); _sbss = .; *(.bss*) *(COMMON) . = ALIGN(4); _ebss = .; } >RAM
  .stack_reserve (NOLOAD) : { . = ALIGN(8); . += _Min_Stack_Size; . = ALIGN(8); } >RAM
  /DISCARD/ : { *(.note.GNU-stack) }
}
ASSERT(SIZEOF(.isr_vector)+SIZEOF(.text)+SIZEOF(.ARM.extab)+SIZEOF(.ARM.exidx)+SIZEOF(.data) <= 88K, "Application exceeds 88 KiB OTA slot budget")
ASSERT(_ebss + _Min_Stack_Size <= _estack, "SRAM and stack overflow")
