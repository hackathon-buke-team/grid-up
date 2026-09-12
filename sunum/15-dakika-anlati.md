# 15 Dakikalık Sunum Anlatısı (K4 §4.5)

> Bu bir taslak iskelettir; K1/K2/K3 ekranları/donanımı hazırlandıkça
> doldurulacak ve takım önünde en az bir kez süre tutularak prova edilecek
> (bkz. görev dağılımı §5 Kilometre Taşları, G+7). Bugün itibarıyla yalnız
> K4'ün parçaları (dedektör omurgası, kural motoru, bildirim, doğruluk
> raporu) çalışır durumda.

## Zaman planı

| Dakika | Bölüm | Sahibi | Durum |
|---|---|---|---|
| 0:00–1:30 | Problem: 1600 kVA panoda haftalar önce haber verme ihtiyacı | Hepsi | Metin hazır |
| 1:30–3:30 | θ metriği — sabit eşik neden yetmiyor (canlı sayı ile) | K4 | **Hazır** — `reports/duyarlilik-egrisi.png` |
| 3:30–6:00 | Uçtan uca mimari: sensör → dedektör → kural → SCADA/bildirim | K2 | K2'yi bekliyor |
| 6:00–9:00 | Canlı demo: normal senaryo → alarm senaryosu → Telegram'a düşen mesaj | K3 + K4 | K4 bildirim tarafı hazır, demo paneli K3'ü bekliyor |
| 9:00–11:00 | Doğruluk sunumu: 17 senaryo matrisi, haber verme süresi, yanlış alarm bütçesi | K4 | **Hazır** — `reports/dogruluk-raporu.md` |
| 11:00–13:00 | Donanım tasarımı: şematik, PCB, mekanik yerleşim | K1 | K1'i bekliyor |
| 13:00–14:00 | Maliyet, ölçeklenebilirlik, açık maddeler (dürüstçe) | K1 + K2 | Kısmen |
| 14:00–15:00 | Kapanış: üç cümle + soru-cevaba geçiş | Hepsi | Metin hazır |

## Öne çıkarılacak üç cümle

1. Sabit eşik ağustosu atlatacak kadar yüksek kurulur, dolayısıyla şubatta
   kördür; biz kardeşler arasındaki farkı ölçüyoruz ve yük ile mevsim
   sadeleşiyor.
2. Bastırma katmanı, alarm üretmediğimiz durumların gerekçesini de kaydeder;
   "78 derece okudun, neden söylemedin?" sorusunun cevabı ekranda hazır
   duruyor.
3. Sistem koruma yapmaz ve bunu açıkça söyler: ark açması SIL-2 donanımda
   yaklaşık bir milisaniyede gerçekleşir, biz gözler, konumlandırır, zaman
   damgalar ve haber veririz.

## K4'ün canlı gösterebileceği somut kanıtlar (bugün)

- `python -m pytest -q` → 45/45 yeşil, canlı ekranda çalıştırılabilir.
- `python -m tools.run_accuracy_report` → 17 senaryo matrisi + duyarlılık
  eğrisi 10 saniyeden kısa sürede yeniden üretilir.
- Gerçek Telegram mesajı: kritik bir senaryo tetiklenip telefona bildirim
  düşürülebilir (bkz. `docs/04-ANOMALI-TESPIT.md` §8).
