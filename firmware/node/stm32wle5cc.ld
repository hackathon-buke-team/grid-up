/* stm32wle5cc.ld -- linker script for the real target MCU.
 * Memory sizes from ST datasheet DS13105 (STM32WLE5xx): 256 KB flash,
 * 64 KB SRAM (SRAM1 32K + SRAM2 32K, mapped contiguously here as one RAM
 * region for this skeleton -- see docs/07-FIRMWARE.md Sec.4). */

MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 256K
    RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 64K
}

ENTRY(Reset_Handler)

SECTIONS
{
    .isr_vector :
    {
        . = ALIGN(4);
        KEEP(*(.isr_vector))
        . = ALIGN(4);
    } > FLASH

    .text :
    {
        . = ALIGN(4);
        *(.text)
        *(.text*)
        *(.rodata)
        *(.rodata*)
        . = ALIGN(4);
    } > FLASH

    _sidata = LOADADDR(.data);

    .data :
    {
        . = ALIGN(4);
        _sdata = .;
        *(.data)
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } > RAM AT> FLASH

    .bss :
    {
        . = ALIGN(4);
        _sbss = .;
        *(.bss)
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } > RAM

    ._user_heap_stack :
    {
        . = ALIGN(8);
        . = . + 4096; /* minimum stack reservation, no heap (malloc-free firmware) */
        . = ALIGN(8);
    } > RAM

    _estack = ORIGIN(RAM) + LENGTH(RAM);
}
