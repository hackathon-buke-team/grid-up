"""Lay out and render the 3 PANO GOZ schematics using gen_schematics.Sheet.

Every connection is a real drawn wire: each pin gets a short outward stub
(gen_schematics.Sheet._stub) ending in either a same-named label (signal
nets -- two labels with the same text are the same net) or a power symbol
(power nets). Component placement only needs to avoid visual overlap; the
wire geometry itself is generated from each pin's own rotation.
"""
import os
from gen_schematics import Sheet, U

OUT = os.path.dirname(os.path.abspath(__file__))


def connect(sheet, pins, key, net):
    p = pins[key]
    sheet.wire_label(net, p[0], p[1], p.rot)


def power_pin(sheet, pins, key, net):
    p = pins[key]
    sheet.wire_power(net, p[0], p[1], p.rot)


def build_tc_node():
    s = Sheet()

    # --- MCU ---
    _, mcu = s.place("MCU_ST_STM32WL:STM32WLE5CCUx", 0, 0, "U", "STM32WLE5CCUx")

    # Power rails on MCU
    for k in ("VDD", "44", "VDDA", "VBAT", "VDDPA", "VDDRF", "VDDRF1V55", "VDDSMPS"):  # pin 44 shares real name "VDD" with pin 11, addressed by number
        power_pin(s, mcu, k, "+3V3")
    for k in ("VSS", "VSSSMPS"):
        power_pin(s, mcu, k, "GND")
    connect(s, mcu, "VFBSMPS", "+3V3")   # ties SMPS feedback high -> internal LDO mode (simplification, see docs)
    s.no_connect(*mcu["VLXSMPS"])
    s.no_connect(*mcu["RFI_P"])
    s.no_connect(*mcu["RFI_N"])
    s.no_connect(*mcu["RFO_LP"])
    s.no_connect(*mcu["PH3"])

    # VR_PA needs its own decoupling cap to GND (ST reference requirement)
    _, cvrpa = s.place("Device:C", -40, 20, "C", "100nF")
    connect(s, mcu, "VR_PA", "VRPA")
    connect(s, cvrpa, "1", "VRPA")
    power_pin(s, cvrpa, "2", "GND")
    s.pwr_flag(*cvrpa["1"])  # VR_PA is an internal MCU regulator output, no external driver pin type

    # NRST: pull-up + push button
    _, rnrst = s.place("Device:R", -25, 90, "R", "10k")
    power_pin(s, rnrst, "1", "+3V3")
    connect(s, rnrst, "2", "NRST")
    connect(s, mcu, "NRST", "NRST")
    _, swrst = s.place("Switch:SW_Push", 0, 90, "SW", "RESET")
    connect(s, swrst, "1", "NRST")
    power_pin(s, swrst, "2", "GND")

    # ground net has no active "power_out" driver pin anywhere -- flag it
    s.pwr_flag(*mcu["VSS"])

    # deliberately-unused GPIOs on this board (documented, see docs/03)
    for k in ("PC14", "PC15", "PA0", "PA1", "PA2", "PA3", "PA8", "PA9",
              "PA10", "PA11", "PA12", "PB0", "PB5", "PB6", "PB7", "PB8", "PB12"):
        s.no_connect(*mcu[k])

    # SWD header (4-pin tag-connect style: SWDIO, SWCLK, GND, 3V3)
    _, swd = s.place("Connector_Generic:Conn_01x04", 40, 90, "J", "SWD")
    connect(s, swd, "Pin_1", "SWDIO")
    connect(s, swd, "Pin_2", "SWCLK")
    power_pin(s, swd, "Pin_3", "GND")
    power_pin(s, swd, "Pin_4", "+3V3")
    connect(s, mcu, "PA13", "SWDIO")
    connect(s, mcu, "PA14", "SWCLK")

    # HSE crystal 32MHz for the sub-GHz radio timing
    _, y1 = s.place("Device:Crystal", 75, 90, "Y", "32MHz")
    connect(s, y1, "1", "OSC_IN")
    connect(s, y1, "2", "OSC_OUT")
    connect(s, mcu, "OSC_IN", "OSC_IN")
    connect(s, mcu, "OSC_OUT", "OSC_OUT")
    _, cx1 = s.place("Device:C", 65, 75, "C", "12pF")
    _, cx2 = s.place("Device:C", 85, 75, "C", "12pF")
    connect(s, cx1, "1", "OSC_IN"); power_pin(s, cx1, "2", "GND")
    connect(s, cx2, "1", "OSC_OUT"); power_pin(s, cx2, "2", "GND")

    # Power section: LiSOCl2 cell -> reverse-protect diode -> LDO 3V3, supercap buffer
    _, bt = s.place("Device:Battery_Cell", -170, 90, "BT", "LiSOCl2 3.6V")
    _, dp = s.place("Device:D", -170, 60, "D", "reverse-protect")
    connect(s, bt, "+", "VBATT_RAW")
    connect(s, dp, "K", "VBATT_RAW")
    connect(s, dp, "A", "VBATT")
    power_pin(s, bt, "-", "GND")
    _, ldo = s.place("Regulator_Linear:AP2112K-3.3", -130, 90, "U", "AP2112K-3.3")
    connect(s, ldo, "VIN", "VBATT")
    power_pin(s, ldo, "GND", "GND")
    connect(s, ldo, "EN", "VBATT")
    power_pin(s, ldo, "VOUT", "+3V3")
    s.pwr_flag(*ldo["VIN"])  # battery-fed rail: no power_out-typed pin upstream of the LDO
    _, cin = s.place("Device:C", -145, 70, "C", "1uF")
    connect(s, cin, "1", "VBATT"); power_pin(s, cin, "2", "GND")
    _, cout = s.place("Device:C", -110, 70, "C", "1uF")
    power_pin(s, cout, "1", "+3V3"); power_pin(s, cout, "2", "GND")
    _, supercap = s.place("Device:C_Polarized", -90, 90, "C", "1F supercap (TX buffer)")
    power_pin(s, supercap, "1", "+3V3")  # pin 1 = "+" (top) per KiCad's C_Polarized convention
    power_pin(s, supercap, "2", "GND")   # pin 2 = "-" (bottom, filled-rectangle marking)

    # RF matching (simplified single-ended) -> chip antenna
    _, crf = s.place("Device:C", 150, 20, "C", "2.2pF match")
    connect(s, mcu, "RFO_HP", "RF_HP")
    connect(s, crf, "1", "RF_HP")
    connect(s, crf, "2", "ANT")
    _, ant = s.place("Device:Antenna", 175, 20, "AE", "PCB chip antenna")
    connect(s, ant, "A", "ANT")

    # 3x thermocouple channels (MAX31855, shared SPI1 bus, individual CS)
    tc_cs = ["PA4", "PA15", "PC13"]
    for i in range(3):
        bx = -100 + i * 45
        _, m = s.place("Sensor_Temperature:MAX31855KASA", bx, -100, "U", f"MAX31855KASA (TC{i+1})")
        power_pin(s, m, "VCC", "+3V3")
        power_pin(s, m, "GND", "GND")
        connect(s, m, "SCK", "SPI1_SCK")
        connect(s, m, "SO", "SPI1_MISO")
        connect(s, m, f"CS", f"TC{i+1}_CS")
        s.no_connect(*m["NC"])
        connect(s, mcu, tc_cs[i], f"TC{i+1}_CS")
        _, conn = s.place("Connector_Generic:Conn_01x02", bx, -140, "J", f"TC{i+1} probe (K-type)")
        connect(s, conn, "Pin_1", f"TC{i+1}_T+")
        connect(s, conn, "Pin_2", f"TC{i+1}_T-")
        connect(s, m, "T+", f"TC{i+1}_T+")
        connect(s, m, "T-", f"TC{i+1}_T-")
    connect(s, mcu, "PA5", "SPI1_SCK")
    connect(s, mcu, "PA6", "SPI1_MISO")
    connect(s, mcu, "PA7", "SPI1_MOSI")  # unused by MAX31855 (read-only) but bus wired for future use

    # 3x CT (clip-on current) channels via a lumped CT_Interface block
    ct_adc = ["PB3", "PB4", "PB2"]
    for i in range(3):
        bx = 60 + i * 40
        _, ct = s.place("Generic:CT_Interface", bx, -100, "A", f"CT{i+1}_Interface")
        power_pin(s, ct, "VCC", "+3V3")
        power_pin(s, ct, "GND", "GND")
        connect(s, ct, "AOUT", f"CT{i+1}_ADC")
        connect(s, mcu, ct_adc[i], f"CT{i+1}_ADC")
        _, conn = s.place("Connector_Generic:Conn_01x02", bx, -140, "J", f"CT{i+1} clip-on")
        connect(s, conn, "Pin_1", f"CT{i+1}+")
        connect(s, conn, "Pin_2", f"CT{i+1}-")
        connect(s, ct, "CT+", f"CT{i+1}+")
        connect(s, ct, "CT-", f"CT{i+1}-")

    s.text("PANO GOZ - TC dugumu (Termal-Akim)\\nAna giris + 5 besleme cikisi icin\\nortak tasarim (6 adet/pano)", -170, 130)
    s.text("Basitlestirme: CT_Interface kutusu burden R + bias\\nbolucusu + AC-coupling C'yi temsil eder (bkz. docs/03).", 60, -160)

    return s.render("PANO GOZ - TC Dugumu (Termal-Akim)")


def build_ir_pd_node():
    s = Sheet()
    _, mcu = s.place("MCU_ST_STM32WL:STM32WLE5CCUx", 0, 0, "U", "STM32WLE5CCUx")

    for k in ("VDD", "44", "VDDA", "VBAT", "VDDPA", "VDDRF", "VDDRF1V55", "VDDSMPS"):  # pin 44 shares real name "VDD" with pin 11, addressed by number
        power_pin(s, mcu, k, "+3V3")
    for k in ("VSS", "VSSSMPS"):
        power_pin(s, mcu, k, "GND")
    connect(s, mcu, "VFBSMPS", "+3V3")
    s.no_connect(*mcu["VLXSMPS"])
    s.no_connect(*mcu["RFI_P"])
    s.no_connect(*mcu["RFI_N"])
    s.no_connect(*mcu["RFO_LP"])
    s.no_connect(*mcu["PH3"])

    _, cvrpa = s.place("Device:C", -40, 20, "C", "100nF")
    connect(s, mcu, "VR_PA", "VRPA")
    connect(s, cvrpa, "1", "VRPA"); power_pin(s, cvrpa, "2", "GND")
    s.pwr_flag(*cvrpa["1"])

    _, rnrst = s.place("Device:R", -25, 90, "R", "10k")
    power_pin(s, rnrst, "1", "+3V3"); connect(s, rnrst, "2", "NRST")
    connect(s, mcu, "NRST", "NRST")
    _, swrst = s.place("Switch:SW_Push", 0, 90, "SW", "RESET")
    connect(s, swrst, "1", "NRST"); power_pin(s, swrst, "2", "GND")

    s.pwr_flag(*mcu["VSS"])
    for k in ("PC13", "PC14", "PC15", "PA1", "PA2", "PA3", "PA4", "PA5", "PA6", "PA7",
              "PA8", "PA9", "PA10", "PA11", "PA12", "PA15", "PB0", "PB2", "PB4",
              "PB5", "PB6", "PB7", "PB8", "PB12"):
        s.no_connect(*mcu[k])

    _, swd = s.place("Connector_Generic:Conn_01x04", 40, 90, "J", "SWD")
    connect(s, swd, "Pin_1", "SWDIO"); connect(s, swd, "Pin_2", "SWCLK")
    power_pin(s, swd, "Pin_3", "GND"); power_pin(s, swd, "Pin_4", "+3V3")
    connect(s, mcu, "PA13", "SWDIO"); connect(s, mcu, "PA14", "SWCLK")

    _, y1 = s.place("Device:Crystal", 75, 90, "Y", "32MHz")
    connect(s, y1, "1", "OSC_IN"); connect(s, y1, "2", "OSC_OUT")
    connect(s, mcu, "OSC_IN", "OSC_IN"); connect(s, mcu, "OSC_OUT", "OSC_OUT")
    _, cx1 = s.place("Device:C", 65, 75, "C", "12pF")
    _, cx2 = s.place("Device:C", 85, 75, "C", "12pF")
    connect(s, cx1, "1", "OSC_IN"); power_pin(s, cx1, "2", "GND")
    connect(s, cx2, "1", "OSC_OUT"); power_pin(s, cx2, "2", "GND")

    _, bt = s.place("Device:Battery_Cell", -170, 90, "BT", "LiSOCl2 3.6V")
    _, dp = s.place("Device:D", -170, 60, "D", "reverse-protect")
    connect(s, bt, "+", "VBATT_RAW"); connect(s, dp, "K", "VBATT_RAW"); connect(s, dp, "A", "VBATT")
    power_pin(s, bt, "-", "GND")
    _, ldo = s.place("Regulator_Linear:AP2112K-3.3", -130, 90, "U", "AP2112K-3.3")
    connect(s, ldo, "VIN", "VBATT"); power_pin(s, ldo, "GND", "GND")
    connect(s, ldo, "EN", "VBATT"); power_pin(s, ldo, "VOUT", "+3V3")
    s.pwr_flag(*ldo["VIN"])
    _, cin = s.place("Device:C", -145, 70, "C", "1uF")
    connect(s, cin, "1", "VBATT"); power_pin(s, cin, "2", "GND")
    _, cout = s.place("Device:C", -110, 70, "C", "1uF")
    power_pin(s, cout, "1", "+3V3"); power_pin(s, cout, "2", "GND")
    _, supercap = s.place("Device:C_Polarized", -90, 90, "C", "1F supercap (TX buffer)")
    power_pin(s, supercap, "1", "+3V3"); power_pin(s, supercap, "2", "GND")

    _, crf = s.place("Device:C", 150, 20, "C", "2.2pF match")
    connect(s, mcu, "RFO_HP", "RF_HP"); connect(s, crf, "1", "RF_HP"); connect(s, crf, "2", "ANT")
    _, ant = s.place("Device:Antenna", 175, 20, "AE", "PCB chip antenna")
    connect(s, ant, "A", "ANT")

    # HFCT input: BNC -> DC block -> RF_Frontend (BPF+LNA+LogDet, lumped) -> ADC
    _, bnc = s.place("Connector:Conn_Coaxial_Small", -100, -80, "J", "BNC (HFCT30/50)")
    _, tvs = s.place("Diode:PTVS5V0Z1USK", -100, -110, "D", "TVS 5V")
    connect(s, bnc, "In", "HFCT_IN"); connect(s, tvs, "K", "HFCT_IN")
    power_pin(s, bnc, "Ext", "GND"); power_pin(s, tvs, "A", "GND")
    _, cdc = s.place("Device:C", -60, -80, "C", "1nF DC-block")
    connect(s, cdc, "1", "HFCT_IN"); connect(s, cdc, "2", "RF_IN")
    _, rfe = s.place("Generic:RF_Frontend", -20, -80, "A", "HFCT front-end (BPF+LNA+LogDet)")
    connect(s, rfe, "RFIN", "RF_IN")
    power_pin(s, rfe, "VCC", "+3V3"); power_pin(s, rfe, "GND", "GND")
    connect(s, rfe, "ENVOUT", "PD_ENV")
    connect(s, mcu, "PB3", "PD_ENV")

    # Zero-cross phase reference via optocoupler, tapped from panel olcu devresi
    _, refconn = s.place("Connector_Generic:Conn_01x02", 60, -80, "J", "Olcu devresi referansi (LV)")
    _, rlim = s.place("Device:R", 90, -80, "R", "10k (akim sinirlama)")
    _, opto = s.place("Isolator:4N25", 120, -80, "U", "4N25")
    # 4N25 real pinout (verified against Isolator.kicad_sym): 1=A 2=K 3=NC 4=E 5=B 6=C
    connect(s, refconn, "Pin_1", "ACREF_A")
    connect(s, refconn, "Pin_2", "ACREF_B")
    connect(s, rlim, "1", "ACREF_A"); connect(s, rlim, "2", "OPTO_A")
    connect(s, opto, "1", "OPTO_A")
    connect(s, opto, "2", "ACREF_B")
    s.no_connect(*opto["3"])
    power_pin(s, opto, "4", "GND")
    _, rpu = s.place("Device:R", 145, -60, "R", "10k pull-up")
    power_pin(s, rpu, "1", "+3V3"); connect(s, rpu, "2", "ZC_SIG")
    connect(s, opto, "6", "ZC_SIG")
    s.no_connect(*opto["5"])
    connect(s, mcu, "PA0", "ZC_SIG")

    s.text("PANO GOZ - IR/PD dugumu (Kismi Desarj / Ark)\\nAna giris kablo riseri icin (1 adet/pano)", -170, 130)
    s.text("Basitlestirme: RF_Frontend kutusu bandpass filtre +\\nLNA + log-amp zarf dedektoru zincirini temsil eder\\n(gercek IC secimi PCB asamasinda, bkz. docs/03).", -20, -140)
    s.text("Faz referansi panonun Olcu Devresi (gG, >=2A) ucundan\\nizoleli (4N25) sekilde alinir - sifir gecis zaman damgasi icin.", 60, -140)

    return s.render("PANO GOZ - IR-PD Dugumu (Kismi Desarj/Ark)")


def build_gateway():
    s = Sheet()
    _, mcu = s.place("MCU_ST_STM32WL:STM32WLE5CCUx", 0, 0, "U", "STM32WLE5CCUx")

    for k in ("VDD", "44", "VDDA", "VBAT", "VDDPA", "VDDRF", "VDDRF1V55", "VDDSMPS"):  # pin 44 shares real name "VDD" with pin 11, addressed by number
        power_pin(s, mcu, k, "+3V3")
    for k in ("VSS", "VSSSMPS"):
        power_pin(s, mcu, k, "GND")
    connect(s, mcu, "VFBSMPS", "+3V3")
    s.no_connect(*mcu["VLXSMPS"])
    s.no_connect(*mcu["RFI_P"])
    s.no_connect(*mcu["RFI_N"])
    s.no_connect(*mcu["RFO_LP"])
    s.no_connect(*mcu["PH3"])

    _, cvrpa = s.place("Device:C", -40, 20, "C", "100nF")
    connect(s, mcu, "VR_PA", "VRPA")
    connect(s, cvrpa, "1", "VRPA"); power_pin(s, cvrpa, "2", "GND")
    s.pwr_flag(*cvrpa["1"])

    _, rnrst = s.place("Device:R", -25, 90, "R", "10k")
    power_pin(s, rnrst, "1", "+3V3"); connect(s, rnrst, "2", "NRST")
    connect(s, mcu, "NRST", "NRST")
    _, swrst = s.place("Switch:SW_Push", 0, 90, "SW", "RESET")
    connect(s, swrst, "1", "NRST"); power_pin(s, swrst, "2", "GND")

    s.pwr_flag(*mcu["VSS"])
    for k in ("PC13", "PC14", "PC15", "PA0", "PA1", "PA2", "PA3", "PA4", "PA6", "PA7",
              "PA15", "PB0", "PB2", "PB3", "PB4", "PB5", "PB6", "PB7", "PB8", "PB12"):
        s.no_connect(*mcu[k])

    _, swd = s.place("Connector_Generic:Conn_01x04", 40, 90, "J", "SWD")
    connect(s, swd, "Pin_1", "SWDIO"); connect(s, swd, "Pin_2", "SWCLK")
    power_pin(s, swd, "Pin_3", "GND"); power_pin(s, swd, "Pin_4", "+3V3")
    connect(s, mcu, "PA13", "SWDIO"); connect(s, mcu, "PA14", "SWCLK")

    _, y1 = s.place("Device:Crystal", 75, 90, "Y", "32MHz (MCU/radio)")
    connect(s, y1, "1", "OSC_IN"); connect(s, y1, "2", "OSC_OUT")
    connect(s, mcu, "OSC_IN", "OSC_IN"); connect(s, mcu, "OSC_OUT", "OSC_OUT")
    _, cx1 = s.place("Device:C", 65, 75, "C", "12pF")
    _, cx2 = s.place("Device:C", 85, 75, "C", "12pF")
    connect(s, cx1, "1", "OSC_IN"); power_pin(s, cx1, "2", "GND")
    connect(s, cx2, "1", "OSC_OUT"); power_pin(s, cx2, "2", "GND")

    # Mains-tap power: fuse -> HLK-PM01 (220VAC->5V) -> LDO 3V3
    _, fuse = s.place("Device:Fuse", -170, 90, "F", "0.5A (modul dali)")
    _, acdc = s.place("Converter_ACDC:HLK-PM01", -140, 90, "U", "HLK-PM01 (220VAC->5V)")
    connect(s, fuse, "1", "AC_L_PANEL"); connect(s, fuse, "2", "AC_L")
    connect(s, acdc, "AC/L", "AC_L")
    s.pwr_flag(*acdc["AC/L"])  # mains input, externally supplied
    connect(s, acdc, "AC/N", "AC_N")
    s.pwr_flag(*acdc["AC/N"])
    connect(s, acdc, "-Vout", "GND5V")
    connect(s, acdc, "+Vout", "V5")
    _, ldo = s.place("Regulator_Linear:AP2112K-3.3", -110, 90, "U", "AP2112K-3.3")
    connect(s, ldo, "VIN", "V5")
    connect(s, ldo, "GND", "GND5V")  # 5V-side return, isolated per HLK-PM01 datasheet, bonded to logic GND at one point
    power_pin(s, ldo, "VOUT", "+3V3")
    connect(s, ldo, "EN", "V5")
    _, cin = s.place("Device:C", -125, 70, "C", "10uF")
    connect(s, cin, "1", "V5"); connect(s, cin, "2", "GND5V")
    _, cout = s.place("Device:C", -95, 70, "C", "1uF")
    power_pin(s, cout, "1", "+3V3"); power_pin(s, cout, "2", "GND")
    s.text("GND5V, sistem GND'sine tek noktadan\\nbaglanir (HLK-PM01 izole cikis).", -170, 55)

    _, crf = s.place("Device:C", 150, 20, "C", "2.2pF match")
    connect(s, mcu, "RFO_HP", "RF_HP"); connect(s, crf, "1", "RF_HP"); connect(s, crf, "2", "ANT")
    _, sma = s.place("Connector:Conn_Coaxial_Small", 175, 20, "J", "SMA (harici anten)")
    connect(s, sma, "In", "ANT"); power_pin(s, sma, "Ext", "GND")

    # W5500 SPI ethernet controller
    _, w5 = s.place("Interface_Ethernet:W5500", 0, -140, "U", "W5500")
    power_pin(s, w5, "VDD", "+3V3"); power_pin(s, w5, "GND", "GND")
    power_pin(s, w5, "4", "+3V3")   # AVDD (pin 4, the power_in-typed analog supply pin)
    power_pin(s, w5, "3", "GND")    # AGND (pin 3, the power_in-typed analog return pin)
    connect(s, mcu, "PA8", "ETH_SCLK"); connect(s, w5, "SCLK", "ETH_SCLK")
    connect(s, mcu, "PA5", "ETH_MISO"); connect(s, w5, "MISO", "ETH_MISO")
    connect(s, mcu, "PA10", "ETH_MOSI"); connect(s, w5, "MOSI", "ETH_MOSI")
    connect(s, mcu, "PA9", "ETH_CS"); connect(s, w5, "SCS", "ETH_CS")
    connect(s, mcu, "PA11", "ETH_INT"); connect(s, w5, "INT", "ETH_INT")
    connect(s, mcu, "PA12", "ETH_RST"); connect(s, w5, "RST", "ETH_RST")
    # PMODE0-2 = 000 (auto-negotiation, per WIZnet datasheet)
    power_pin(s, w5, "PMODE0", "GND")
    power_pin(s, w5, "PMODE1", "GND")
    power_pin(s, w5, "PMODE2", "GND")
    # RSVD1-6 in the WIZnet datasheet = pins 23,38,39,40,41,42 (real library
    # gives all six the same bare name "RSVD", so they're addressed by number)
    for k in ("23", "38", "39", "40", "41", "42"):
        s.no_connect(*w5[k])
    for k in ("SPDLED", "LINKLED", "DUPLED", "ACTLED"):
        s.no_connect(*w5[k])  # status LEDs not populated in this pass, see docs/03
    # required support network per WIZnet reference design
    _, rexres = s.place("Device:R", -50, -170, "R", "12k 1% (EXRES1 bias)")
    connect(s, rexres, "1", "EXRES1"); power_pin(s, rexres, "2", "GND")
    connect(s, w5, "EXRES1", "EXRES1")
    _, ctocap = s.place("Device:C", -20, -170, "C", "2.2uF (TOCAP)")
    connect(s, ctocap, "1", "TOCAP"); power_pin(s, ctocap, "2", "GND")
    connect(s, w5, "TOCAP", "TOCAP")
    _, cvbg = s.place("Device:C", 10, -170, "C", "0.1uF (VBG)")
    connect(s, cvbg, "1", "VBG"); power_pin(s, cvbg, "2", "GND")
    connect(s, w5, "VBG", "VBG")
    _, c1v2 = s.place("Device:C", 40, -170, "C", "1uF (1V2O)")
    connect(s, c1v2, "1", "1V2O"); power_pin(s, c1v2, "2", "GND")
    connect(s, w5, "1V2O", "1V2O")
    # 25MHz crystal for W5500
    _, yw = s.place("Device:Crystal", 70, -170, "Y", "25MHz (W5500)")
    connect(s, yw, "1", "ETH_XI"); connect(s, yw, "2", "ETH_XO")
    connect(s, w5, "XI_CLKIN", "ETH_XI"); connect(s, w5, "XO", "ETH_XO")
    _, cw1 = s.place("Device:C", 60, -190, "C", "18pF")
    _, cw2 = s.place("Device:C", 80, -190, "C", "18pF")
    connect(s, cw1, "1", "ETH_XI"); power_pin(s, cw1, "2", "GND")
    connect(s, cw2, "1", "ETH_XO"); power_pin(s, cw2, "2", "GND")

    # RJ45 (no magnetics on this simplified schematic - see docs/03)
    _, rj = s.place("Connector:RJ45", 130, -140, "J", "RJ45 (magnetics harici, bkz. docs)")
    connect(s, w5, "TXP", "ETH_TXP"); connect(s, rj, "1", "ETH_TXP")
    connect(s, w5, "TXN", "ETH_TXN"); connect(s, rj, "2", "ETH_TXN")
    connect(s, w5, "RXP", "ETH_RXP"); connect(s, rj, "3", "ETH_RXP")
    connect(s, w5, "RXN", "ETH_RXN"); connect(s, rj, "4", "ETH_RXN")
    for k in ("5", "6", "7", "8"):
        s.no_connect(*rj[k])

    s.text("PANO GOZ - Gateway karti (1 adet/pano)\\nTC/PD dugumlerinden sub-GHz toplar, W5500 uzerinden\\non-prem MQTT broker'a kablolu (Ethernet) baglanir.", -170, 130)
    s.text("Basitlestirme: W5500-RJ45 arasi izolasyon magnetics\\nmodulu (entegre MagJack) bu semada gosterilmedi,\\nPCB'de eklenmelidir (bkz. docs/03).", 130, -190)

    return s.render("PANO GOZ - Gateway Karti")


BOARDS = {
    "tc-node": build_tc_node,
    "ir-pd-node": build_ir_pd_node,
    "gateway": build_gateway,
}

if __name__ == "__main__":
    for name, fn in BOARDS.items():
        d = os.path.join(OUT, name)
        os.makedirs(d, exist_ok=True)
        content = fn()
        sch_path = os.path.join(d, f"{name}.kicad_sch")
        with open(sch_path, "w", encoding="utf-8") as f:
            f.write(content)
        pro_path = os.path.join(d, f"{name}.kicad_pro")
        if not os.path.exists(pro_path):
            with open(pro_path, "w", encoding="utf-8") as f:
                f.write('{\n  "meta": { "filename": "%s.kicad_pro", "version": 1 },\n  "sheets": [ [ "%s", "Root" ] ]\n}\n' % (name, name))
        print("wrote", sch_path)
