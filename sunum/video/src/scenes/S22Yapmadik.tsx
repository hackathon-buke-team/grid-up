import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Em, Icon } from "../ui/primitives";
import { fadeUp, prog } from "../ui/motion";
import { C, CLAMP, EASE_OUT, F } from "../theme";

/* 22 · YAPMADIKLARIMIZ
   Altı kart sırayla açılır, başlığın üstünden kırmızı bir çizgi geçer, gerekçe belirir.
   Ardından "belgelendi, kodlanmadı" listesi. */

const ITEMS: [string, string][] = [
  ["Bara bölmesine sensör", "AG giriş kesicisi yok: enerjisiz yapmak dağıtım merkezini OG'den karartır. Profili sildik."],
  ["Enerji hasadı iddiası", "Teorik olarak mümkün, ölçmedik. Ölçmediğimizi teklif etmeyiz."],
  ["Derin öğrenme · LSTM", "Otokodlayıcı yavaş sürüklenmeyi öğrenir: 0,2 K/hafta sinyaline kör."],
  ["SCADA'ya yazma yolu", "Modbus'ta kimlik doğrulama yok. FC 05/06/15/16 istisnasız reddedilir."],
  ["Sparkplug B rozeti", "DDATA için QoS 0 zorunlu; store-and-forward'ımız PUBACK ister."],
  ["Tek başına PD ile ekip", "400 V'ta klasik KD oluşmaz. RF kanalı ısıl bulguyu yalnız destekler."],
];

const DOCS = ["KiCad şematik / PCB", "IEC 104 / OPC UA", "Gerçek SMS gönderimi", "TimescaleDB sürücüsü", "OG hücre donanımı"];

const CARD_W = 544;
const CARD_H = 222;
const GAP = 24;

export const S22Yapmadik: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill>
      <Backdrop accent={C.kritik} second={C.uyari} />
      <SceneHeader
        kicker="12 · Dürüstlük"
        title="Bilerek *yapmadıklarımız*."
        lead="Bir hackathon teslimi için en değerli bölüm."
      />

      {ITEMS.map(([t, d], i) => {
        const s = 40 + i * 20;
        const col = i % 3;
        const row = Math.floor(i / 3);
        const strike = interpolate(frame, [s + 12, s + 26], [0, 1], { ...CLAMP, easing: EASE_OUT });
        const x = interpolate(frame, [s + 8, s + 24], [0, 1], {
          ...CLAMP,
          easing: Easing.spring({ damping: 10, stiffness: 170 }),
        });
        const appear = prog(frame, s, 18);
        const flash = interpolate(frame, [s + 12, s + 20, s + 40], [0, 1, 0], CLAMP);
        return (
          <div
            key={t}
            style={{
              position: "absolute",
              left: 120 + col * (CARD_W + GAP),
              top: 336 + row * (CARD_H + GAP),
              width: CARD_W,
              height: CARD_H,
              padding: "24px 28px",
              borderRadius: 22,
              background: `linear-gradient(180deg, ${C.panel2} 0%, ${C.panel} 100%)`,
              border: `1.5px solid ${flash > 0.05 ? C.kritik : C.line2}`,
              boxShadow: `0 0 ${50 * flash}px -6px ${C.kritik}, 0 24px 60px -24px rgba(0,0,0,.8)`,
              opacity: appear,
              translate: `0px ${(1 - appear) * 40}px`,
              scale: String(0.94 + 0.06 * appear),
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div
                style={{
                  width: 46,
                  height: 46,
                  borderRadius: 99,
                  flexShrink: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: C.kritik + "22",
                  border: `2px solid ${C.kritik}`,
                  scale: String(x),
                }}
              >
                <Icon name="x" size={26} color={C.kritik} stroke={3} />
              </div>
              <div style={{ position: "relative" }}>
                <div
                  style={{
                    fontFamily: F.sans,
                    fontSize: 34,
                    fontWeight: 800,
                    letterSpacing: "-0.01em",
                    color: strike > 0.3 ? "#c3ccd6" : C.ink,
                    whiteSpace: "nowrap",
                  }}
                >
                  {t}
                </div>
                <div
                  style={{
                    position: "absolute",
                    left: -4,
                    top: "52%",
                    height: 3,
                    borderRadius: 2,
                    background: C.kritik,
                    boxShadow: `0 0 10px ${C.kritik}`,
                    width: `calc(${strike * 100}% + ${strike * 8}px)`,
                  }}
                />
              </div>
            </div>
            <div
              style={{
                marginTop: 18,
                fontFamily: F.sans,
                fontSize: 30,
                lineHeight: 1.28,
                color: C.ink,
                opacity: prog(frame, s + 22, 16) * 0.92,
              }}
            >
              {d}
            </div>
          </div>
        );
      })}

      {/* belgelendi, kodlanmadı */}
      <div style={{ position: "absolute", left: 120, top: 830, right: 120 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            fontFamily: F.mono,
            fontSize: 22,
            letterSpacing: "0.14em",
            color: C.uyari,
            ...fadeUp(frame, 200, { dist: 16 }),
          }}
        >
          <Icon name="book" size={26} color={C.uyari} />
          BELGELENDİ, KODLANMADI
          <span style={{ letterSpacing: 0, color: C.dim, fontFamily: F.sans, fontSize: 22 }}>
            · her belgenin sonunda aynı başlıkla bir liste
          </span>
        </div>
        <div style={{ display: "flex", gap: 14, marginTop: 14 }}>
          {DOCS.map((d, i) => (
            <span
              key={d}
              style={{
                display: "inline-flex",
                alignItems: "center",
                padding: "8px 22px",
                borderRadius: 999,
                fontFamily: F.sans,
                fontWeight: 700,
                fontSize: 26,
                color: C.uyari,
                background: C.uyari + "1c",
                border: `1.5px solid ${C.uyari}66`,
                whiteSpace: "nowrap",
                ...fadeUp(frame, 210 + i * 7, { dist: 18 }),
              }}
            >
              {d}
            </span>
          ))}
        </div>
      </div>

      <Narration
        bottom={40}
        lines={[
          {
            from: 40,
            to: 128,
            text: (
              <>
                Bara bölmesine girmedik: <Em color={C.kritik}>AG giriş kesicisi yok</Em>. Erken taslakta vardı — sildik.
              </>
            ),
          },
          {
            from: 132,
            to: 200,
            text: <>Ölçmediğimiz bir şeyi teklif etmiyoruz; rozeti takıp kuralı çiğnemiyoruz.</>,
          },
          {
            from: 204,
            to: 328,
            text: (
              <>
                Jüri ne teslim edildiğini ve <Em color={C.uyari}>ne edilmediğini</Em> tek bakışta görsün.
              </>
            ),
          },
        ]}
      />
    </AbsoluteFill>
  );
};
