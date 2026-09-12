# Modbus Haritalama (ICD)

Yarışma brifi gerçek bir RTU/SCADA'ya bağlanmayı istemiyor — "Takımların mevcut
RTU/SCADA yapılarıyla entegrasyon yaklaşımını (Modbus Haritalama) göstermesi
yeterlidir." Bu doküman, `panogoz/scada/` altında kurulan gerçek Modbus TCP
slave'in register haritasını tanımlar; `tools/run_modbus_server.py` ile
127.0.0.1:5020 üzerinde çalıştırılıp herhangi bir Modbus master (modpoll,
QModMaster, vb.) ile canlı doğrulanabilir.

## Genel

- Protokol: Modbus TCP
- Fonksiyon kodu: yalnızca **04 (Read Input Registers)** — salt okunur, master
  hiçbir register'ı yazamaz (Holding Register bloğu kasıtlı olarak boş).
- Ölçek: ondalıklı değerler x10 ile tek register'a sığdırılır (23.4°C → 234).
- İşaret: θ ve sıcaklık register'ları 16 bit two's complement (negatif
  olabilir); akım register'ları işaretsizdir.

## Bağlantı başına register bloğu (8 register)

Taban adres = `bağlantı_indeksi × 8` (bağlantı 0 → 0-7, bağlantı 1 → 8-15, ...).

| Ofset | Ad | Tip | Ölçek | Açıklama |
| --- | --- | --- | --- | --- |
| 0 | SEVERITY_CODE | u16 | 1 | 0=NORMAL, 1=UYARI, 2=ALARM, 3=KRİTİK |
| 1 | THETA_X10 | s16 | x10 | θ metriği (kardeş fazlardan sapma, yüke normalize) |
| 2 | CURRENT_L1_X10 | u16 | x10 | L1 fazı akımı (A) |
| 3 | CURRENT_L2_X10 | u16 | x10 | L2 fazı akımı (A) |
| 4 | CURRENT_L3_X10 | u16 | x10 | L3 fazı akımı (A) |
| 5 | SURFACE_TEMP_L1_X10 | s16 | x10 | L1 bağlantı yüzey sıcaklığı (°C) |
| 6 | SURFACE_TEMP_L2_X10 | s16 | x10 | L2 bağlantı yüzey sıcaklığı (°C) |
| 7 | SURFACE_TEMP_L3_X10 | s16 | x10 | L3 bağlantı yüzey sıcaklığı (°C) |

Kod karşılığı: `panogoz/scada/register_map.py` (`Register` enum, `encode_*`/`decode_*`
fonksiyonları, `ConnectionSnapshot.to_registers()`).

## Doğrulama

`tests/test_modbus.py::test_real_modbus_tcp_client_reads_expected_registers`
gerçek bir `pymodbus.client.ModbusTcpClient` ile sunucuya bağlanıp register'ları
okuyup değerlerin encode edilen değerlerle eşleştiğini doğrular — sahte/mock
istemci değil, gerçek TCP protokol round-trip'i.

Manuel demo:

```bash
python -m tools.run_modbus_server
# başka bir terminalde: modpoll -m tcp -a 1 -r 1 -c 8 -t 4 127.0.0.1
```

## Genişletme

Yeni bir bağlantı eklemek `connection_index`'i bir artırıp aynı 8 register
bloğunu bir sonraki tabana yazmaktan ibarettir — 200 bağlantıya kadar
`register_count` otomatik büyür (`build_context`). Ölçeklenebilirlik notu için
bkz. `docs/olceklenebilirlik.md` (planlanıyor).
