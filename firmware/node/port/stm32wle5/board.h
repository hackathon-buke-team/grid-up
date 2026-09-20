#ifndef PG_BOARD_H
#define PG_BOARD_H
/* PANOGOZ-TC-B1, UFQFPN48. Shared with hardware/B1/pinmap.csv. */
#define PG_BOARD_NAME "PANOGOZ-TC-B1"
#define PG_BOARD_VDD_MV 3000u
#define PG_CT_RATIO 3000u
#define PG_CT_BURDEN_MOHM 5100u
#define PG_FRAM_BYTES 8192u
#define PG_TMP117_ADDR (0x48u << 1)
#define PG_SHT41_ADDR (0x44u << 1)
#define PG_I2C_SCL GPIO_PIN_6 /* PB6, pin 4 */
#define PG_I2C_SDA GPIO_PIN_7 /* PB7, pin 5 */
#define PG_FRAM_CS GPIO_PIN_4 /* PA4, pin 12 */
#define PG_BATTERY_ADC ADC_CHANNEL_7 /* PA2, pin 9: 1:2 switched divider */
#define PG_CT_ADC ADC_CHANNEL_5 /* PA0, pin 7 */
#define PG_MOUNT GPIO_PIN_3 /* PB3, pin 1; switch to GND */
#define PG_DIV_EN GPIO_PIN_4 /* PB4, pin 2; N-MOS drives P-MOS gate, high=on */
#define PG_LOAD_EN GPIO_PIN_5 /* PB5, pin 3; 68R load via N-MOS */
#define PG_RF_CTRL GPIO_PIN_0 /* PB0, pin 30; PE4259, low=RX high=LP TX */
#define PG_RF_CTRL_N GPIO_PIN_12 /* PB12, pin 32; complementary */
/* No PC3/4/5 or PB9 on the selected UFQFPN48 package. */
#define PG_PHASE_PIN GPIO_PIN_8 /* PA8, pin 16: external comparator */
#define PG_PD_PIN GPIO_PIN_9 /* PA9, pin 17: PD pulse comparator */
#endif
