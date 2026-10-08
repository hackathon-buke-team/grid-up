import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Em } from "../ui/primitives";
import { fadeUp, prog } from "../ui/motion";
import { C, CLAMP, EASE_OUT, F } from "../theme";

/* 2 · TAKIM
   Takım Büke: dört kişi, dördü de Bilgisayar Mühendisliği. İş dört paralel pakete bölündü. */

const MEMBERS = [
  {
    name: "Melih Ekizce",
    uni: "İzmir Yüksek Teknoloji Enstitüsü",
    degree: "Yüksek Lisans · devam ediyor",
    on: true,
    photo: "foto_melih.jpg",
  },
  {
    name: "Mustafa Eren Işıktaşlı",
    uni: "Yıldız Teknik Üniversitesi",
    degree: "Yüksek Lisans · devam ediyor",
    on: true,
    photo: "foto_eren.jpg",
  },
  {
    name: "Serhat Özdemir",
    uni: "Dokuz Eylül Üniversitesi",
    degree: "Lisans",
    on: false,
    photo: "foto_serhat.jpg",
  },
  {
    name: "Mert Arı",
    uni: "Bursa Uludağ Üniversitesi",
    degree: "Lisans",
    on: false,
    photo: "foto_mert.jpg",
  },
];

const PACKAGES = [
  "Donanım ve uç düğüm",
  "Sunucu · entegrasyon · ölçek",
  "İzleme ekranları · operasyon",
  "Bildirim · doğrulama · sunum",
];

const CARD_W = 400;
const GAP = 24;
const ROW_LEFT = (1920 - (CARD_W * 4 + GAP * 3)) / 2;
const PHOTO = 176;
const RING_R = PHOTO / 2 + 10;
const RING_LEN = 2 * Math.PI * RING_R;

const Member: React.FC<{ m: (typeof MEMBERS)[number]; i: number; frame: number }> = ({ m, i, frame }) => {
  const s = 22 + i * 8;
  const ring = prog(frame, s + 8, 30);
  const photoIn = prog(frame, s + 4, 22);
  const float = Math.sin((frame + i * 23) / 34) * 4 * prog(frame, s + 30, 20);
  return (
    <div
      style={{
        position: "absolute",
        left: ROW_LEFT + i * (CARD_W + GAP),
        top: 322,
        width: CARD_W,
        ...fadeUp(frame, s, { dist: 60, dur: 24, blur: 8 }),
        translate: `0px ${(1 - prog(frame, s, 24)) * 60 + float}px`,
      }}
    >
      <div
        style={{
          height: 494,
          borderRadius: 26,
          background: `linear-gradient(180deg, ${C.panel2} 0%, ${C.panel} 100%)`,
          border: `1.5px solid ${C.line2}`,
          boxShadow: "0 24px 60px -24px rgba(0,0,0,.8), inset 0 1px 0 rgba(255,255,255,.04)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          padding: "28px 20px 0",
          textAlign: "center",
        }}
      >
        <div style={{ position: "relative", width: PHOTO + 28, height: PHOTO + 28, flexShrink: 0 }}>
          <svg width={PHOTO + 28} height={PHOTO + 28} style={{ position: "absolute", inset: 0 }}>
            <circle cx={(PHOTO + 28) / 2} cy={(PHOTO + 28) / 2} r={RING_R} fill="none" stroke={C.line2} strokeWidth={3} />
            <circle
              cx={(PHOTO + 28) / 2}
              cy={(PHOTO + 28) / 2}
              r={RING_R}
              fill="none"
              stroke={m.on ? C.brand : C.izle}
              strokeWidth={4}
              strokeLinecap="round"
              strokeDasharray={RING_LEN}
              strokeDashoffset={RING_LEN * (1 - ring)}
              transform={`rotate(-90 ${(PHOTO + 28) / 2} ${(PHOTO + 28) / 2})`}
            />
          </svg>
          <Img
            src={staticFile(m.photo)}
            style={{
              position: "absolute",
              left: 14,
              top: 14,
              width: PHOTO,
              height: PHOTO,
              borderRadius: "50%",
              objectFit: "cover",
              opacity: photoIn,
              scale: String(0.85 + 0.15 * photoIn),
            }}
          />
        </div>
        <div
          style={{
            marginTop: 22,
            fontFamily: F.sans,
            fontWeight: 800,
            fontSize: 32,
            lineHeight: 1.15,
            color: C.ink,
            minHeight: 74,
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
          }}
        >
          {m.name}
        </div>
        <div style={{ marginTop: 6, fontFamily: F.sans, fontSize: 25, lineHeight: 1.25, color: C.muted, minHeight: 62 }}>
          {m.uni}
        </div>
        <div style={{ marginTop: 4, fontFamily: F.sans, fontSize: 23, color: C.dim }}>Bilgisayar Mühendisliği</div>
        <div
          style={{
            marginTop: 16,
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            padding: "7px 18px",
            borderRadius: 999,
            fontFamily: F.sans,
            fontWeight: 700,
            fontSize: 20,
            whiteSpace: "nowrap",
            flexShrink: 0,
            color: m.on ? C.brand2 : C.muted,
            background: m.on ? C.brandSoft : "rgba(147,160,178,.08)",
            border: `1.5px solid ${m.on ? C.brand + "88" : C.line2}`,
            opacity: prog(frame, s + 26, 16),
          }}
        >
          <span style={{ width: 10, height: 10, borderRadius: 99, background: m.on ? C.brand : C.muted }} />
          {m.degree}
        </div>
      </div>
    </div>
  );
};

export const S02Takim: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill>
      <Backdrop accent={C.brand} second={C.izle} />
      <SceneHeader kicker="Takım" title="Takım *Büke*" align="center" />

      {MEMBERS.map((m, i) => (
        <Member key={m.name} m={m} i={i} frame={frame} />
      ))}

      {/* iş paketleri */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 838,
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          gap: 14,
        }}
      >
        <span
          style={{
            fontFamily: F.mono,
            fontSize: 22,
            letterSpacing: "0.14em",
            color: C.dim,
            marginRight: 8,
            opacity: interpolate(frame, [70, 86], [0, 1], CLAMP),
          }}
        >
          4 PARALEL PAKET
        </span>
        {PACKAGES.map((p, i) => {
          const a = prog(frame, 76 + i * 6, 16);
          return (
            <span
              key={p}
              style={{
                padding: "8px 18px",
                borderRadius: 999,
                fontFamily: F.sans,
                fontSize: 23,
                fontWeight: 700,
                color: C.ink,
                background: "rgba(74,163,255,.08)",
                border: `1.5px solid ${C.izle}55`,
                opacity: a,
                translate: `0px ${(1 - a) * 18}px`,
              }}
            >
              {p}
            </span>
          );
        })}
      </div>

      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 246,
          textAlign: "center",
          fontFamily: F.sans,
          fontSize: 30,
          color: C.muted,
          opacity: interpolate(frame, [34, 52], [0, 1], CLAMP),
          translate: `0px ${interpolate(frame, [34, 56], [14, 0], { ...CLAMP, easing: EASE_OUT })}px`,
        }}
      >
        ADM & GDZ Elektrik · Grid Up Hackathon · Pano/Hücre İçi Anomali Erken Uyarı Sistemi
      </div>

      <Narration
        lines={[
          {
            from: 40,
            to: 176,
            text: (
              <>
                Dört kişiyiz, dördümüz de <Em>Bilgisayar Mühendisliği</Em> — işi dört paralel pakete böldük.
              </>
            ),
          },
        ]}
      />
    </AbsoluteFill>
  );
};
