# PANO GÖZ · hareketli sunum videosu

`sunum/` altındaki HTML destesinin Remotion ile yapılmış hareketli video hâli.
1920×1080, 30 fps, sessiz (anlatım alttaki altyazı satırlarında).

## Çalıştırma

```console
npm i
npm run dev                                   # Remotion Studio: önizleme ve düzenleme
npx remotion render PanoGoz out/pano-goz.mp4  # tüm videoyu MP4 olarak üret
npx remotion render S05-Theta out/theta.mp4   # tek bir sahne
```

## Yapı

| Dosya | İçerik |
|---|---|
| `src/timeline.ts` | Sahne sırası, süreleri ve giriş geçişleri. Bir sahneyi uzatmak/kısaltmak için yalnız burayı değiştirin; toplam süre buradan hesaplanır. |
| `src/Main.tsx` | Tüm sahneleri `TransitionSeries` ile birleştiren ana kompozisyon (`PanoGoz`). |
| `src/scenes/S01…S24` | Her sahne kendi dosyasında; Studio'da `Sahneler` klasöründe tek tek de açılır. |
| `src/theme.ts` | Renkler (destenin `deck.css` jetonları), yazı tipleri, θ seviye merdiveni, yardımcılar. |
| `src/ui/` | Ortak parçalar: canlı zemin, sahne başlığı, altyazı, kart/çip/simge, geçişler (termal tarama, zoom), sabit çerçeve. |
| `public/` | `sunum/assets/` altındaki logolar, takım fotoğrafları ve arayüz ekran görüntüleri. |

## Notlar

- `S15-Mobil` (saha ekibi mobil uygulaması) bir **konsepttir**; depoda karşılığı olan bir uygulama yoktur
  ve sahnede "KONSEPT" etiketiyle gösterilir.
- Müzik yok. Eklemek için `public/` altına bir ses dosyası koyup `Main.tsx` içine
  `@remotion/media` paketinden `<Audio src={staticFile("muzik.mp3")} />` ekleyin.
