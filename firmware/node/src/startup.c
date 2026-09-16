/* startup.c -- minimal ARMv7-M (Cortex-M4) startup: the 16 CORE exception
 * vectors (standard to every Cortex-M part, not STM32-specific) plus
 * Reset_Handler's .data/.bss init. Device-specific IRQ vectors (index 16+,
 * e.g. USART/SPI/DMA) are intentionally NOT declared here -- this skeleton
 * enables no peripheral interrupts (see main_*.c's TODOs), so there is
 * nothing to route them to yet; see docs/07-FIRMWARE.md Sec.4.
 *
 * STM32WLE5CC memory map (ST datasheet DS13105): 256 KB flash at
 * 0x08000000, 64 KB SRAM at 0x20000000 -- see stm32wle5cc.ld.
 */
#include <stdint.h>

extern uint32_t _sidata; /* end of .data in FLASH (LMA) */
extern uint32_t _sdata;  /* start of .data in RAM (VMA) */
extern uint32_t _edata;
extern uint32_t _sbss;
extern uint32_t _ebss;
extern uint32_t _estack;

void Reset_Handler(void);
static void Default_Handler(void);

int main(void);

void Reset_Handler(void)
{
    uint32_t *src = &_sidata;
    uint32_t *dst = &_sdata;
    while (dst < &_edata) {
        *dst++ = *src++;
    }
    dst = &_sbss;
    while (dst < &_ebss) {
        *dst++ = 0;
    }

    main();

    for (;;) {
        /* main() is not expected to return (bare-metal, no OS to return to) */
    }
}

static void Default_Handler(void)
{
    for (;;) {
    }
}

/* Standard ARMv7-M core vector table, 16 entries (index 0 = initial SP,
 * index 1 = Reset, indices 2-15 = the fixed core exceptions/reserved slots
 * defined by the Armv7-M architecture, same on every Cortex-M4 part). */
__attribute__((section(".isr_vector")))
void (* const g_pfnVectors[16])(void) = {
    (void (*)(void)) & _estack, /* 0  Initial stack pointer */
    Reset_Handler,              /* 1  Reset */
    Default_Handler,            /* 2  NMI */
    Default_Handler,            /* 3  HardFault */
    Default_Handler,            /* 4  MemManage */
    Default_Handler,            /* 5  BusFault */
    Default_Handler,            /* 6  UsageFault */
    0,                          /* 7  Reserved */
    0,                          /* 8  Reserved */
    0,                          /* 9  Reserved */
    0,                          /* 10 Reserved */
    Default_Handler,            /* 11 SVCall */
    Default_Handler,            /* 12 DebugMon */
    0,                          /* 13 Reserved */
    Default_Handler,            /* 14 PendSV */
    Default_Handler,            /* 15 SysTick */
};
