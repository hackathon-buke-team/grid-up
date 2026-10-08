import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Card, Em, Icon } from "../ui/primitives";
import { countUp, fadeSide, fadeUp, pulse } from "../ui/motion";
import { C, CLAMP, F, tr } from "../theme";

/* 23 · ŞARTNAME KARŞILIĞI
   Beklenen teknik çıktılar satır satır, renkle değil kelimeyle: Tamam ya da Kısmen.
   Sağda arkasındaki iş, sayarak. */

const REQ: [string, boolean, string][] = [
  ["Kabin içi modül tasarımı", false, "9 cihaz, yerleşim, BOM · KiCad çizilmedi"],
  ["Elektronik dokümantasyon", false, "Blok şema, I/O, pin dizilimi, katman yığını, güç ağacı"],
  ["Yazılım mimarisi", true, "C99 firmware · Python sunucu · saf JS arayüz"],
  ["Monitoring", true, "Filo, dijital ikiz, kanıt, bastırılanlar, PRPD, SCADA"],
  ["SCADA · Modbus haritalama", true, "Çalışan TCP slave · ICD v2.0 · salt okunur"],
  ["On-premise, kamu bulutu yok", true, "Tek komut · internet yok · dış servis çağrısı yok"],
  ["SMS / anlık bildirim", false, "Merdiven, onay kodu, fırtına tavanı · gönderim simüle"],
  ["Ölçek · ≥ 100 modül", true, "112 pano ile ölçüldü · kaynak profili raporlandı"],
];

const KPIS: { v: (f: number) => string; l: string; s: number }[] = [
  { v: (f) => `${Math.round(countUp(f, 66, 40, 0, 33))} bin`, l: "satır Python · sunucu, dedektör", s: 60 },
  { v: (f) => `${tr(countUp(f, 76, 40, 0, 4.5))} bin`, l: "satır C99 · uç düğüm firmware", s: 70 },
  { v: (f) => `${tr(countUp(f, 86, 40, 0, 7.9))} bin`, l: "satır arayüz · bağımlılıksız JS", s: 80 },
  { v: (f) => `${Math.round(countUp(f, 96, 40, 0, 172))}`, l: "otomatik test · gerileme takımı", s: 90 },
  { v: (f) => `${Math.round(countUp(f, 106, 34, 0, 11))} + ICD`, l: "teknik belge · ≈ 5 800 satır", s: 100 },
];

const ROW_H = 68;

export const S23Sartname: React.FC = () => {
  const frame = useCurrentFrame();
  const partialGlow = interpolate(frame, [128, 140, 196, 206], [0, 1, 1, 0], CLAMP) * (0.55 + 0.45 * pulse(frame, 30));

  return (
    <AbsoluteFill>
      <Backdrop accent={C.ok} second={C.brand} />
      <SceneHeader kicker="13 · Özet" title="Şartname karşılığı: *bugünkü* durum." size={80} />

      {/* tablo */}
      <div style={{ position: "absolute", left: 120, top: 282, ...fadeUp(frame, 16) }}>
        <Card style={{ width: 1250, padding: "18px 26px 14px" }}>
          <div
            style={{
              display: "flex",
              fontFamily: F.mono,
              fontSize: 22,
              letterSpacing: "0.12em",
              color: C.dim,
              paddingBottom: 10,
              borderBottom: `1px solid ${C.line2}`,
            }}
          >
            <span style={{ width: 186 }}>DURUM</span>
            <span style={{ width: 448 }}>BEKLENEN ÇIKTI</span>
            <span style={{ flex: 1 }}>KARŞILIĞI</span>
            <span style={{ letterSpacing: 0, fontFamily: F.sans, fontSize: 24, fontWeight: 700, ...fadeUp(frame, 118, { dist: 10 }) }}>
              <span style={{ color: C.ok }}>5 Tamam</span>
              <span style={{ color: C.dim }}> · </span>
              <span style={{ color: C.uyari }}>3 Kısmen</span>
            </span>
          </div>
          {REQ.map(([t, ok, d], i) => {
            const s = 26 + i * 11;
            const chip = interpolate(frame, [s + 6, s + 20], [0, 1], {
              ...CLAMP,
              easing: Easing.spring({ damping: 11, stiffness: 160 }),
            });
            const color = ok ? C.ok : C.uyari;
            const glow = ok ? 0 : partialGlow;
            return (
              <div
                key={t}
                style={{
                  display: "flex",
                  alignItems: "center",
                  height: ROW_H,
                  borderBottom: i < REQ.length - 1 ? `1px solid ${C.line}` : "none",
                  background: `rgba(244,177,58,${0.08 * glow})`,
                  ...fadeSide(frame, s, -40, 18),
                }}
              >
                <div style={{ width: 186 }}>
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "6px 16px",
                      borderRadius: 999,
                      fontFamily: F.sans,
                      fontWeight: 800,
                      fontSize: 24,
                      color,
                      background: color + "1f",
                      border: `2px solid ${color}`,
                      boxShadow: glow ? `0 0 ${24 * glow}px ${C.uyari}` : "none",
                      scale: String(chip),
                      opacity: Math.min(1, chip * 1.5),
                    }}
                  >
                    {ok ? (
                      <Icon name="check" size={22} color={color} stroke={3.2} />
                    ) : (
                      <svg width={22} height={22} viewBox="0 0 24 24">
                        <circle cx="12" cy="12" r="9" fill="none" stroke={color} strokeWidth="2.6" />
                        <path d="M12 3a9 9 0 010 18z" fill={color} />
                      </svg>
                    )}
                    {ok ? "Tamam" : "Kısmen"}
                  </span>
                </div>
                <div style={{ width: 448, fontFamily: F.sans, fontSize: 29, fontWeight: 700, color: C.ink }}>{t}</div>
                <div style={{ flex: 1, fontFamily: F.sans, fontSize: 24, lineHeight: 1.22, color: C.muted }}>{d}</div>
              </div>
            );
          })}
        </Card>
      </div>

      {/* sağ: arkasındaki iş */}
      <div style={{ position: "absolute", left: 1400, top: 282, width: 400 }}>
        {KPIS.map((k, i) => (
          <div key={k.l} style={{ marginBottom: 12, ...fadeSide(frame, k.s, 40, 18) }}>
            <Card style={{ padding: "14px 24px" }}>
              <div style={{ fontFamily: F.mono, fontSize: 46, fontWeight: 700, color: i === 3 ? C.ok : C.brand2, lineHeight: 1.1 }}>
                {k.v(frame)}
              </div>
              <div style={{ fontFamily: F.sans, fontSize: 23, color: C.muted, marginTop: 2 }}>{k.l}</div>
            </Card>
          </div>
        ))}
      </div>

      <Narration
        lines={[
          {
            from: 22,
            to: 124,
            text: (
              <>
                Şartnamenin beklenen çıktıları, renkle değil kelimeyle: <Em color={C.ok}>Tamam</Em> ya da{" "}
                <Em color={C.uyari}>Kısmen</Em>.
              </>
            ),
          },
          {
            from: 128,
            to: 204,
            text: <>"Kısmen"leri biz söylüyoruz: KiCad çizilmedi, SMS gönderimi simüle.</>,
          },
          {
            from: 208,
            to: 268,
            text: <>Gerileme testleri, gerçekten yaşadığımız hataları yeniden üretip kilitliyor.</>,
          },
        ]}
      />
    </AbsoluteFill>
  );
};
