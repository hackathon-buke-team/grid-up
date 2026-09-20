/* PANOGOZ-TC-B1 target port. Real peripheral accesses, never synthetic readings.
 * Design-stage port: cross-compiled, not measured on assembled hardware.
 * OTA writes are deliberately disabled until a signed bootloader is supplied.
 */
#include "node.h"
#include "stm32wlxx_hal.h"
#include "board.h"

static I2C_HandleTypeDef i2c;
static SPI_HandleTypeDef spi;
static ADC_HandleTypeDef adc;
static RTC_HandleTypeDef rtc;
static IWDG_HandleTypeDef wdt;
static SUBGHZ_HandleTypeDef radio;
static uint8_t i2c_ok, spi_ok, adc_ok, rtc_ok, radio_ok, wdt_on;
static uint32_t slept_ms;
static volatile uint8_t wake;
static volatile uint32_t phase_last, phase_period;
static int8_t rssi = -127;

void SysTick_Handler(void) { HAL_IncTick(); }
/* No constructors or heap in this C99 image; ST startup calls this hook. */
void __libc_init_array(void) { }
void *memcpy(void *dst, const void *src, size_t n) {
    uint8_t *d=dst; const uint8_t *s=src;
    while (n--) *d++=*s++;
    return dst;
}
void *memset(void *dst, int v, size_t n) {
    uint8_t *d=dst; while (n--) *d++=(uint8_t)v; return dst;
}

static void gpio(GPIO_TypeDef *port, uint32_t pins, uint32_t mode, uint32_t pull, uint32_t af) {
    GPIO_InitTypeDef g={0};
    g.Pin=pins; g.Mode=mode; g.Pull=pull; g.Speed=GPIO_SPEED_FREQ_LOW; g.Alternate=af;
    HAL_GPIO_Init(port,&g);
}

static int clocks(void) {
    RCC_OscInitTypeDef o={0}; RCC_ClkInitTypeDef c={0};
    HAL_PWR_EnableBkUpAccess();
    (void)HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1);
    o.OscillatorType=RCC_OSCILLATORTYPE_HSE|RCC_OSCILLATORTYPE_LSI;
    o.HSEState=RCC_HSE_ON; o.LSIState=RCC_LSI_ON; o.PLL.PLLState=RCC_PLL_OFF;
    if (HAL_RCC_OscConfig(&o)!=HAL_OK) return -1;
    c.ClockType=RCC_CLOCKTYPE_SYSCLK|RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
    c.SYSCLKSource=RCC_SYSCLKSOURCE_HSE; c.AHBCLKDivider=RCC_SYSCLK_DIV1;
    c.APB1CLKDivider=RCC_HCLK_DIV1; c.APB2CLKDivider=RCC_HCLK_DIV1;
    return HAL_RCC_ClockConfig(&c,FLASH_LATENCY_1)==HAL_OK ? 0 : -1;
}

static int rtc_init(void) {
    RCC_OscInitTypeDef o={0}; RCC_PeriphCLKInitTypeDef p={0};
    o.OscillatorType=RCC_OSCILLATORTYPE_LSE; o.LSEState=RCC_LSE_ON;
    o.PLL.PLLState=RCC_PLL_NONE;
    if (HAL_RCC_OscConfig(&o)!=HAL_OK) return -1;
    p.PeriphClockSelection=RCC_PERIPHCLK_RTC; p.RTCClockSelection=RCC_RTCCLKSOURCE_LSE;
    if (HAL_RCCEx_PeriphCLKConfig(&p)!=HAL_OK) return -1;
    __HAL_RCC_RTC_ENABLE(); __HAL_RCC_RTCAPB_CLK_ENABLE();
    rtc.Instance=RTC; rtc.Init.HourFormat=RTC_HOURFORMAT_24;
    rtc.Init.AsynchPrediv=127; rtc.Init.SynchPrediv=255;
    rtc.Init.OutPut=RTC_OUTPUT_DISABLE; rtc.Init.OutPutRemap=RTC_OUTPUT_REMAP_NONE;
    rtc.Init.OutPutPolarity=RTC_OUTPUT_POLARITY_HIGH; rtc.Init.OutPutType=RTC_OUTPUT_TYPE_OPENDRAIN;
    if (HAL_RTC_Init(&rtc)!=HAL_OK) return -1;
    HAL_NVIC_SetPriority(RTC_WKUP_IRQn,2,0); HAL_NVIC_EnableIRQ(RTC_WKUP_IRQn);
    return 0;
}

static void rf_switch(int tx) {
    HAL_GPIO_WritePin(GPIOB,PG_RF_CTRL,tx ? GPIO_PIN_SET : GPIO_PIN_RESET);
    HAL_GPIO_WritePin(GPIOB,PG_RF_CTRL_N,tx ? GPIO_PIN_RESET : GPIO_PIN_SET);
}
static int cmd(SUBGHZ_RadioSetCmd_t op, uint8_t *b, uint16_t n) {
    return HAL_SUBGHZ_ExecSetCmd(&radio,op,b,n)==HAL_OK ? 0 : -1;
}
static int radio_init(void) {
    uint8_t standby=0, type=1, cal=0x7f, regulator=0;
    uint8_t image[2]={0xd7,0xdb}; /* 863-870 MHz, RM0461/SX126x band calibration */
    uint8_t base[2]={0,128}, modulation[4]={7,4,1,0}; /* SF7,125 kHz,4/5 */
    uint8_t pa[4]={4,0,1,1}, tx[2]={14,4}; /* low-power PA, 200 us ramp */
    uint8_t irq[8]={0x02,0x63,0,0,0,0,0,0}; /* poll status; no DIO interrupts */
    uint8_t frequency[4];
    uint32_t f=(uint32_t)(((uint64_t)868100000u<<25)/32000000u);
    frequency[0]=(uint8_t)(f>>24); frequency[1]=(uint8_t)(f>>16);
    frequency[2]=(uint8_t)(f>>8); frequency[3]=(uint8_t)f;
    __HAL_RCC_SUBGHZSPI_CLK_ENABLE();
    radio.Init.BaudratePrescaler=SUBGHZSPI_BAUDRATEPRESCALER_8;
    if (HAL_SUBGHZ_Init(&radio)!=HAL_OK) return -1;
    if (cmd(RADIO_SET_STANDBY,&standby,1) || cmd(RADIO_SET_REGULATORMODE,&regulator,1) ||
        cmd(RADIO_CALIBRATE,&cal,1) || cmd(RADIO_CALIBRATEIMAGE,image,2) ||
        cmd(RADIO_SET_PACKETTYPE,&type,1) || cmd(RADIO_SET_RFFREQUENCY,frequency,4) ||
        cmd(RADIO_SET_BUFFERBASEADDRESS,base,2) || cmd(RADIO_SET_MODULATIONPARAMS,modulation,4) ||
        cmd(RADIO_SET_PACONFIG,pa,4) || cmd(RADIO_SET_TXPARAMS,tx,2) ||
        cmd(RADIO_CFG_DIOIRQ,irq,8)) return -1;
    /* Private LoRa sync word, identical on gateway. */
    if (HAL_SUBGHZ_WriteRegister(&radio,0x0740,0x14)!=HAL_OK ||
        HAL_SUBGHZ_WriteRegister(&radio,0x0741,0x24)!=HAL_OK) return -1;
    rf_switch(0);
    return 0;
}

void hal_init(void) {
    int clock_ok;
    HAL_Init(); clock_ok=clocks()==0;
    __HAL_RCC_GPIOA_CLK_ENABLE(); __HAL_RCC_GPIOB_CLK_ENABLE(); __HAL_RCC_GPIOC_CLK_ENABLE();
    __HAL_RCC_TIM2_CLK_ENABLE(); __HAL_RCC_I2C1_CLK_ENABLE(); __HAL_RCC_SPI1_CLK_ENABLE();
    __HAL_RCC_ADC_CLK_ENABLE();
    /* Start in quiet states before connecting output drivers. */
    HAL_GPIO_WritePin(GPIOA,PG_FRAM_CS,GPIO_PIN_SET);
    HAL_GPIO_WritePin(GPIOB,PG_DIV_EN,GPIO_PIN_RESET);
    HAL_GPIO_WritePin(GPIOB,PG_LOAD_EN|PG_RF_CTRL,GPIO_PIN_RESET);
    HAL_GPIO_WritePin(GPIOB,PG_RF_CTRL_N,GPIO_PIN_SET);
    gpio(GPIOA,PG_FRAM_CS,GPIO_MODE_OUTPUT_PP,GPIO_NOPULL,0);
    gpio(GPIOB,PG_DIV_EN|PG_LOAD_EN|PG_RF_CTRL|PG_RF_CTRL_N,GPIO_MODE_OUTPUT_PP,GPIO_NOPULL,0);
    gpio(GPIOB,PG_MOUNT,GPIO_MODE_INPUT,GPIO_PULLUP,0);
    gpio(GPIOB,PG_I2C_SCL|PG_I2C_SDA,GPIO_MODE_AF_OD,GPIO_NOPULL,GPIO_AF4_I2C1);
    gpio(GPIOA,GPIO_PIN_5|GPIO_PIN_6|GPIO_PIN_7,GPIO_MODE_AF_PP,GPIO_NOPULL,GPIO_AF5_SPI1);
    gpio(GPIOA,GPIO_PIN_0|GPIO_PIN_2,GPIO_MODE_ANALOG,GPIO_NOPULL,0);
    gpio(GPIOA,PG_PHASE_PIN,GPIO_MODE_IT_RISING,GPIO_NOPULL,0);
    HAL_NVIC_SetPriority(EXTI9_5_IRQn,1,0); HAL_NVIC_EnableIRQ(EXTI9_5_IRQn);
    TIM2->PSC=(HAL_RCC_GetPCLK1Freq()/1000000u)-1u; TIM2->ARR=0xffffffffu;
    TIM2->EGR=TIM_EGR_UG; TIM2->CR1=TIM_CR1_CEN;
    i2c.Instance=I2C1; i2c.Init.Timing=0x00707cbb; /* 100 kHz,32 MHz,100ns rise; verify on board */
    i2c.Init.AddressingMode=I2C_ADDRESSINGMODE_7BIT;
    i2c_ok=(uint8_t)(clock_ok && HAL_I2C_Init(&i2c)==HAL_OK);
    spi.Instance=SPI1; spi.Init.Mode=SPI_MODE_MASTER; spi.Init.Direction=SPI_DIRECTION_2LINES;
    spi.Init.DataSize=SPI_DATASIZE_8BIT; spi.Init.CLKPolarity=SPI_POLARITY_LOW;
    spi.Init.CLKPhase=SPI_PHASE_1EDGE; spi.Init.NSS=SPI_NSS_SOFT;
    spi.Init.BaudRatePrescaler=SPI_BAUDRATEPRESCALER_32; spi.Init.FirstBit=SPI_FIRSTBIT_MSB;
    spi.Init.CRCCalculation=SPI_CRCCALCULATION_DISABLE; spi.Init.NSSPMode=SPI_NSS_PULSE_DISABLE;
    spi_ok=(uint8_t)(HAL_SPI_Init(&spi)==HAL_OK);
    adc.Instance=ADC; adc.Init.ClockPrescaler=ADC_CLOCK_SYNC_PCLK_DIV4;
    adc.Init.Resolution=ADC_RESOLUTION_12B; adc.Init.DataAlign=ADC_DATAALIGN_RIGHT;
    adc.Init.ScanConvMode=ADC_SCAN_DISABLE; adc.Init.EOCSelection=ADC_EOC_SINGLE_CONV;
    adc.Init.NbrOfConversion=1; adc.Init.ExternalTrigConv=ADC_SOFTWARE_START;
    adc.Init.ExternalTrigConvEdge=ADC_EXTERNALTRIGCONVEDGE_NONE;
    adc.Init.Overrun=ADC_OVR_DATA_OVERWRITTEN;
    adc.Init.SamplingTimeCommon1=ADC_SAMPLETIME_79CYCLES_5;
    adc_ok=(uint8_t)(HAL_ADC_Init(&adc)==HAL_OK && HAL_ADCEx_Calibration_Start(&adc)==HAL_OK);
    rtc_ok=(uint8_t)(rtc_init()==0);
    radio_ok=(uint8_t)(clock_ok && radio_init()==0);
    __HAL_RCC_CLEAR_RESET_FLAGS();
}

uint32_t hal_uptime_ms(void) { return HAL_GetTick(); }
uint32_t hal_uptime_us(void) { return TIM2->CNT+slept_ms*1000u; }
void RTC_WKUP_IRQHandler(void) { HAL_RTCEx_WakeUpTimerIRQHandler(&rtc); }
void HAL_RTCEx_WakeUpTimerEventCallback(RTC_HandleTypeDef *h) { (void)h; wake=1; }
void EXTI9_5_IRQHandler(void) { HAL_GPIO_EXTI_IRQHandler(PG_PHASE_PIN); }
void HAL_GPIO_EXTI_Callback(uint16_t pin) {
    if (pin==PG_PHASE_PIN) {
        uint32_t t=hal_uptime_us(), d=t-phase_last;
        phase_last=t; phase_period=(d>=16000u && d<=24000u) ? d : 0;
    }
}

void hal_sleep_ms(uint32_t ms, int deep) {
    uint8_t sleep_cmd=4;
    if (radio_ok) (void)cmd(RADIO_SET_SLEEP,&sleep_cmd,1);
    HAL_GPIO_WritePin(GPIOB,PG_DIV_EN,GPIO_PIN_RESET);
    HAL_GPIO_WritePin(GPIOB,PG_LOAD_EN,GPIO_PIN_RESET);
    while (ms) {
        /* Two-second RTC chunks keep IWDG alive even with factory option bytes.
         * Actual battery consumption must be measured; no 13-year claim here. */
        if (deep && rtc_ok && ms>=10u) {
            uint32_t step=ms>2000u?2000u:ms;
            uint32_t ticks=(step*2048u+999u)/1000u;
            wake=0; hal_wdt_kick();
            if (HAL_RTCEx_SetWakeUpTimer_IT(&rtc,ticks-1u,RTC_WAKEUPCLOCK_RTCCLK_DIV16,0)!=HAL_OK) break;
            HAL_SuspendTick();
            while (!wake) HAL_PWREx_EnterSTOP2Mode(PWR_STOPENTRY_WFI);
            HAL_ResumeTick();
            extern __IO uint32_t uwTick;
            uwTick+=step; slept_ms+=step;
            (void)HAL_RTCEx_DeactivateWakeUpTimer(&rtc);
            if (clocks()!=0) { i2c_ok=0; radio_ok=0; }
            ms-=step;
        } else {
            uint32_t step=ms>1000u?1000u:ms;
            hal_wdt_kick(); HAL_Delay(step); ms-=step;
        }
    }
}

int16_t hal_tmp117_oneshot(void) {
    uint8_t config[2]={0x0c,0x00}, b[2]; uint32_t start;
    if (!i2c_ok || HAL_I2C_Mem_Write(&i2c,PG_TMP117_ADDR,1,I2C_MEMADD_SIZE_8BIT,config,2,20)!=HAL_OK)
        return PG_T_FAULT;
    start=HAL_GetTick();
    do {
        HAL_Delay(2);
        if (HAL_I2C_Mem_Read(&i2c,PG_TMP117_ADDR,1,I2C_MEMADD_SIZE_8BIT,b,2,20)!=HAL_OK) return PG_T_FAULT;
        if (b[0]&0x20u) {
            if (HAL_I2C_Mem_Read(&i2c,PG_TMP117_ADDR,0,I2C_MEMADD_SIZE_8BIT,b,2,20)!=HAL_OK) return PG_T_FAULT;
            return (int16_t)(((uint16_t)b[0]<<8)|b[1]);
        }
    } while ((uint32_t)(HAL_GetTick()-start)<100u);
    return PG_T_FAULT;
}
int16_t hal_air_temp_lsb(void) { return PG_T_FAULT; } /* TC has no air sensor */

static int read_adc(uint32_t channel) {
    ADC_ChannelConfTypeDef c={0}; int v;
    if (!adc_ok) return -1;
    c.Channel=channel; c.Rank=ADC_REGULAR_RANK_1; c.SamplingTime=ADC_SAMPLINGTIME_COMMON_1;
    if (HAL_ADC_ConfigChannel(&adc,&c)!=HAL_OK || HAL_ADC_Start(&adc)!=HAL_OK) return -1;
    if (HAL_ADC_PollForConversion(&adc,10)!=HAL_OK) { (void)HAL_ADC_Stop(&adc); return -1; }
    v=(int)HAL_ADC_GetValue(&adc); (void)HAL_ADC_Stop(&adc); return v;
}
static uint32_t vdda_mv(void) {
    int v=read_adc(ADC_CHANNEL_VREFINT);
    return v>0 ? __LL_ADC_CALC_VREFANALOG_VOLTAGE((uint32_t)v,LL_ADC_RESOLUTION_12B) : 0;
}
int32_t hal_ct_rms_ma(void) {
    uint32_t supply=vdda_mv(), start=hal_uptime_us();
    uint64_t sq=0; uint32_t sum=0; unsigned n;
    if (!supply) return -1;
    for (n=0;n<64;n++) {
        int x;
        while ((uint32_t)(hal_uptime_us()-start)<(n*20000u)/64u) { }
        x=read_adc(PG_CT_ADC);
        if (x<8 || x>4087) return -1; /* open bias / saturation is unavailable */
        sum+=(uint32_t)x; sq+=(uint64_t)(uint32_t)x*(uint32_t)x;
    }
    /* Remove actual sampled bias, then RMS. All arithmetic is integer. */
    sq=(sq*64u-(uint64_t)sum*sum)/4096u;
    return (int32_t)((uint64_t)pg_isqrt64(sq)*supply*PG_CT_RATIO*1000u/(4095u*PG_CT_BURDEN_MOHM));
}
int8_t hal_mcu_temp_c(void) {
    uint32_t supply=vdda_mv(); int raw=read_adc(ADC_CHANNEL_TEMPSENSOR);
    int32_t t;
    if (!supply || raw<0) return -128;
    t=__LL_ADC_CALC_TEMPERATURE(supply,(uint32_t)raw,LL_ADC_RESOLUTION_12B);
    return (int8_t)(t < -127 ? -127 : t > 127 ? 127 : t);
}
uint16_t hal_vbat_mv(void) {
    int raw; uint32_t supply=vdda_mv();
    HAL_GPIO_WritePin(GPIOB,PG_DIV_EN,GPIO_PIN_SET); HAL_Delay(3);
    raw=read_adc(PG_BATTERY_ADC);
    HAL_GPIO_WritePin(GPIOB,PG_DIV_EN,GPIO_PIN_RESET);
    return raw>=0 && supply ? (uint16_t)((uint32_t)raw*supply*2u/4095u) : 0;
}
uint16_t hal_vbat_loaded_mv(void) {
    uint16_t v;
    HAL_GPIO_WritePin(GPIOB,PG_LOAD_EN,GPIO_PIN_SET); HAL_Delay(10);
    v=hal_vbat_mv(); HAL_GPIO_WritePin(GPIOB,PG_LOAD_EN,GPIO_PIN_RESET); return v;
}
int hal_mount_ok(void) { return HAL_GPIO_ReadPin(GPIOB,PG_MOUNT)==GPIO_PIN_RESET; }
uint32_t hal_mains_period_us(void) {
    return (uint32_t)(hal_uptime_us()-phase_last)<100000u ? phase_period : 0;
}
int hal_pd_pop(uint32_t *dt, uint16_t *a) { (void)dt; (void)a; return 0; } /* TC variant */

static void select_fram(int on) { HAL_GPIO_WritePin(GPIOA,PG_FRAM_CS,on ? GPIO_PIN_RESET : GPIO_PIN_SET); }
int hal_fram_read(uint16_t addr, void *dst, uint16_t n) {
    uint8_t head[3]={3,(uint8_t)(addr>>8),(uint8_t)addr}; HAL_StatusTypeDef rc;
    if (!spi_ok || (uint32_t)addr+n>PG_FRAM_BYTES) return -1;
    select_fram(1); rc=HAL_SPI_Transmit(&spi,head,3,20);
    if (rc==HAL_OK) rc=HAL_SPI_Receive(&spi,dst,n,50);
    select_fram(0); return rc==HAL_OK ? 0 : -1;
}
int hal_fram_write(uint16_t addr, const void *src, uint16_t n) {
    uint8_t wen=6, head[3]={2,(uint8_t)(addr>>8),(uint8_t)addr}, check[32];
    const uint8_t *b=src; uint16_t off; HAL_StatusTypeDef rc;
    if (!spi_ok || (uint32_t)addr+n>PG_FRAM_BYTES) return -1;
    select_fram(1); rc=HAL_SPI_Transmit(&spi,&wen,1,20); select_fram(0);
    if (rc!=HAL_OK) return -1;
    select_fram(1); rc=HAL_SPI_Transmit(&spi,head,3,20);
    if (rc==HAL_OK) rc=HAL_SPI_Transmit(&spi,(uint8_t *)src,n,50);
    select_fram(0); if (rc!=HAL_OK) return -1;
    for (off=0;off<n;) {
        uint16_t i, count=(uint16_t)(n-off); if (count>sizeof check) count=sizeof check;
        if (hal_fram_read((uint16_t)(addr+off),check,count)!=0) return -1;
        for (i=0;i<count;i++) if (check[i]!=b[off+i]) return -1;
        off=(uint16_t)(off+count);
    }
    return 0;
}

static int packet_params(uint8_t length) {
    uint8_t standby=0, clear[2]={0xff,0xff};
    uint8_t params[6]={0,8,0,length,1,0}; /* explicit header, CRC on, normal IQ */
    if (cmd(RADIO_SET_STANDBY,&standby,1) || cmd(RADIO_CLR_IRQSTATUS,clear,2)) return -1;
    return cmd(RADIO_SET_PACKETPARAMS,params,6);
}
int hal_radio_tx(const uint8_t *buf, int len) {
    uint8_t timeout[3]={0,0xfa,0}, status[2]; uint32_t start;
    if (!radio_ok || len<=0 || len>127 || packet_params((uint8_t)len)) return -1;
    if (HAL_SUBGHZ_WriteBuffer(&radio,0,(uint8_t *)buf,(uint16_t)len)!=HAL_OK) return -1;
    rf_switch(1); start=HAL_GetTick();
    if (cmd(RADIO_SET_TX,timeout,3)) { rf_switch(0); return -1; }
    while ((uint32_t)(HAL_GetTick()-start)<1100u) {
        if (HAL_SUBGHZ_ExecGetCmd(&radio,RADIO_GET_IRQSTATUS,status,2)!=HAL_OK) break;
        if (status[1]&1u) { rf_switch(0); return (int)(HAL_GetTick()-start); }
        if (status[0]&2u) break;
        hal_wdt_kick();
    }
    rf_switch(0); return -1;
}
int hal_radio_rx(uint8_t *buf, int cap, uint32_t win_ms) {
    uint8_t timeout[3], status[2], info[2], ps[3], standby=0;
    uint32_t ticks=win_ms*64u, start; int len=0;
    if (!radio_ok || cap<=0 || win_ms>1000u || packet_params(127)) return -1;
    timeout[0]=(uint8_t)(ticks>>16); timeout[1]=(uint8_t)(ticks>>8); timeout[2]=(uint8_t)ticks;
    rf_switch(0); start=HAL_GetTick();
    if (cmd(RADIO_SET_RX,timeout,3)) return -1;
    while ((uint32_t)(HAL_GetTick()-start)<win_ms+10u) {
        if (HAL_SUBGHZ_ExecGetCmd(&radio,RADIO_GET_IRQSTATUS,status,2)!=HAL_OK) { len=-1; break; }
        if (status[1]&0x60u) { len=-1; break; } /* header or CRC error */
        if (status[1]&2u) {
            if (HAL_SUBGHZ_ExecGetCmd(&radio,RADIO_GET_RXBUFFERSTATUS,info,2)!=HAL_OK || info[0]>cap) { len=-1; break; }
            len=info[0];
            if (HAL_SUBGHZ_ReadBuffer(&radio,info[1],buf,(uint16_t)len)!=HAL_OK) len=-1;
            if (HAL_SUBGHZ_ExecGetCmd(&radio,RADIO_GET_PACKETSTATUS,ps,3)==HAL_OK) rssi=(int8_t)(-(int)ps[0]/2);
            break;
        }
        if (status[0]&2u) break;
    }
    (void)cmd(RADIO_SET_STANDBY,&standby,1); return len;
}
int8_t hal_radio_rssi(void) { return rssi; }

void hal_wdt_start(uint32_t ms) {
    if (wdt_on) { hal_wdt_kick(); return; }
    if (ms>30000u) ms=30000u;
    if (ms<1000u) ms=1000u;
    wdt.Instance=IWDG; wdt.Init.Prescaler=IWDG_PRESCALER_256;
    wdt.Init.Reload=(ms*125u)/1000u; wdt.Init.Window=IWDG_WINDOW_DISABLE;
    wdt_on=(uint8_t)(HAL_IWDG_Init(&wdt)==HAL_OK);
}
void hal_wdt_kick(void) { if (wdt_on) (void)HAL_IWDG_Refresh(&wdt); }
void hal_wdt_stop(void) { hal_wdt_kick(); } /* IWDG cannot be stopped in software */
uint32_t hal_reset_cause(void) {
    uint32_t r=RCC->CSR, out=0;
    if (r&RCC_CSR_BORRSTF) out|=PG_RST_BOR|PG_RST_POR;
    if (r&RCC_CSR_PINRSTF) out|=PG_RST_PIN;
    if (r&RCC_CSR_IWDGRSTF) out|=PG_RST_IWDG;
    if (r&RCC_CSR_SFTRSTF) out|=PG_RST_SW;
    if (r&RCC_CSR_LPWRRSTF) out|=PG_RST_LPWR;
    return out;
}
void hal_reboot(void) { NVIC_SystemReset(); }
int hal_flash_erase_slot(uint8_t s) { (void)s; return -1; }
int hal_flash_write(uint8_t s, uint32_t o, const uint8_t *p, uint32_t n) {
    (void)s; (void)o; (void)p; (void)n; return -1;
}
uint32_t hal_flash_crc32(uint8_t s, uint32_t n) { (void)s; (void)n; return 0; }
void hal_flash_mark_trial(uint8_t s, uint8_t n) { (void)s; (void)n; }
void hal_log(const char *s) { (void)s; }
void hal_logf(const char *fmt, ...) { (void)fmt; }
