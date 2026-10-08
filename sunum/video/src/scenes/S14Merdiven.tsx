import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Card, Chip, Em, Icon } from "../ui/primitives";
import { fadeSide, fadeUp, prog, pulse } from "../ui/motion";
import { C, CLAMP, EASE_IN_OUT, EASE_OUT, F } from "../theme";

/* 14 · SEVİYE MERDİVENİ VE BİLDİRİM
   Solda beş basamak; yalnız Kritik ve Acil telefonu çaldırır. Ortada nöbetçinin telefonu:
   SMS kendini yazar, "TAMAM 1 0541" ile onaylanır. Sağda onay gelmezse yükselen merdiven.
   Son ~40 karede kamera telefona iter: sıradaki sahne (saha uygulaması) telefonun içinden açılır. */

const SMS =
  "PANO GÖZ KRİTİK · SOKE-14 · Ç7·L2·pabuç θ=17.6K · bağlantıyı torkla · ACİL'e 15 g (13-19) · onay: TAMAM 1 0541";

const LADDER = [
  { n: "ACİL", c: C.acil, t: "≥ 25 K", a: "derhal ekip · SMS + sesli", phone: true },
  { n: "KRİTİK", c: C.kritik, t: "≥ 12 K", a: "7 gün içinde ziyaret · SMS", phone: true },
  { n: "UYARI", c: C.uyari, t: "≥ 5 K", a: "iş emri · planlı ziyaret", phone: false },
  { n: "İZLE", c: C.izle, t: "≥ 2 K", a: "haftalık özet", phone: false },
  { n: "BİLGİ", c: C.bilgi, t: "< 2 K", a: "kayıt", phone: false },
];

const ESC = [
  { t: "0 dk", h: "1. kademe · nöbetçi", d: "SMS · kişiye ve olaya bağlı onay kodu", at: 160, icon: "phone" as const },
  { t: "15 / 45 dk", h: "2. kademe · şef + sesli arama", d: "Onay yoksa: Acil 15 dk, Kritik 45 dk", at: 178, icon: "bell" as const },
  { t: "sonra", h: "3. kademe · işletme müdürü", d: "Merdiven her adımı kayda yazar", at: 196, icon: "user" as const },
];

const ROW_H = 84;
const ROW_GAP = 12;
const LADDER_TOP = 352;
const LADDER_W = 580;

const PHONE_W = 380;
const PHONE_H = 570;
const PHONE_X = 960 - PHONE_W / 2;
const PHONE_Y = 334;
const PHONE_CY = PHONE_Y + PHONE_H / 2;

const TYPE_START = 136;
const PUSH_START = 380;

export const S14Merdiven: React.FC = () => {
  const frame = useCurrentFrame();

  const chars = Math.round(interpolate(frame, [TYPE_START, TYPE_START + SMS.length / 2], [0, SMS.length], CLAMP));
  const typing = chars < SMS.length;
  const ring = frame >= 108 && frame <= 140;
  const wiggle = ring ? Math.sin(frame * 1.9) * 3 * interpolate(frame, [108, 114, 132, 140], [0, 1, 1, 0], CLAMP) : 0;
  const crit = prog(frame, 100, 12);
  const sig = interpolate(frame, [100, 118], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const escFill = interpolate(frame, [200, 270], [0, 1], { ...CLAMP, easing: EASE_IN_OUT });
  const push = interpolate(frame, [PUSH_START, 420], [0, 1], { ...CLAMP, easing: Easing.in(Easing.quad) });
  const sideFade = 1 - 0.65 * push;

  const kritikRowY = LADDER_TOP + 1 * (ROW_H + ROW_GAP) + ROW_H / 2;
  const kritikRowX = 120 + LADDER_W * 0.9;

  return (
    <AbsoluteFill>
      <Backdrop accent={C.kritik} second={C.izle} />

      <AbsoluteFill
        style={{
          transformOrigin: `960px ${PHONE_CY}px`,
          scale: String(1 + 0.12 * push),
        }}
      >
        <div style={{ opacity: sideFade }}>
          <SceneHeader kicker="06 · Alarm" title="Yalnız *Kritik* ve *Acil* telefonu çaldırır." size={76} />
        </div>

        {/* sol: seviye merdiveni */}
        <div style={{ position: "absolute", left: 120, top: LADDER_TOP, width: LADDER_W, opacity: sideFade }}>
          {LADDER.map((l, i) => {
            const at = 30 + (LADDER.length - 1 - i) * 10;
            const p = prog(frame, at, 18);
            const hot = l.phone ? crit : 0;
            const glow = l.n === "KRİTİK" ? hot * (0.6 + 0.4 * pulse(frame, 30)) : hot * 0.35;
            return (
              <div
                key={l.n}
                style={{
                  position: "absolute",
                  top: i * (ROW_H + ROW_GAP),
                  left: 0,
                  width: `${100 - i * 11}%`,
                  height: ROW_H,
                  borderRadius: 14,
                  background: `linear-gradient(90deg, ${l.c}${l.phone ? "30" : "1c"}, ${C.panel} 85%)`,
                  border: `1.5px solid ${l.c}${glow > 0.3 ? "ee" : "55"}`,
                  boxShadow: glow > 0 ? `0 0 ${36 * glow}px ${l.c}77` : "none",
                  display: "flex",
                  alignItems: "center",
                  gap: 16,
                  padding: "0 18px 0 0",
                  overflow: "hidden",
                  opacity: p,
                  translate: `${(1 - p) * -50}px 0px`,
                }}
              >
                <div style={{ width: 8, alignSelf: "stretch", background: l.c }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
                    <span
                      style={{
                        fontFamily: F.sans,
                        fontWeight: 800,
                        fontSize: 30,
                        color: l.c,
                        letterSpacing: "0.04em",
                      }}
                    >
                      {l.n}
                    </span>
                    <span style={{ fontFamily: F.mono, fontSize: 24, color: C.ink }}>θ {l.t}</span>
                  </div>
                  <div style={{ fontFamily: F.sans, fontSize: 22, color: C.muted, whiteSpace: "nowrap" }}>{l.a}</div>
                </div>
                {l.phone ? <Icon name="phone" size={34} color={l.c} stroke={2} /> : null}
              </div>
            );
          })}
          <div
            style={{
              position: "absolute",
              top: 5 * (ROW_H + ROW_GAP) + 6,
              fontFamily: F.sans,
              fontSize: 24,
              color: C.muted,
              ...fadeUp(frame, 86, { dist: 12 }),
            }}
          >
            Bir ayar değil — <span style={{ color: C.ink, fontWeight: 700 }}>kodda bir sözleşme.</span>
          </div>
        </div>

        {/* Kritik → telefon sinyali */}
        <svg width={1920} height={1080} style={{ position: "absolute", inset: 0, opacity: sideFade }}>
          <line
            x1={kritikRowX + 8}
            y1={kritikRowY}
            x2={kritikRowX + 8 + (PHONE_X - kritikRowX - 20) * sig}
            y2={kritikRowY}
            stroke={C.kritik}
            strokeWidth={3}
            strokeDasharray="8 8"
            strokeDashoffset={-frame * 1.5}
            opacity={sig > 0 ? 0.9 : 0}
          />
          {sig > 0 && sig < 1 ? (
            <circle cx={kritikRowX + 8 + (PHONE_X - kritikRowX - 20) * sig} cy={kritikRowY} r={8} fill={C.kritik} />
          ) : null}
        </svg>

        {/* orta: telefon */}
        <div
          style={{
            position: "absolute",
            left: PHONE_X,
            top: PHONE_Y,
            width: PHONE_W,
            height: PHONE_H,
            rotate: `${wiggle}deg`,
            ...fadeUp(frame, 44, { dist: 50 }),
          }}
        >
          {/* çalma halkaları */}
          {ring
            ? [0, 1].map((k) => {
                const r = ((frame - 108 + k * 8) % 16) / 16;
                return (
                  <div
                    key={k}
                    style={{
                      position: "absolute",
                      inset: -20 - r * 40,
                      borderRadius: 60 + r * 30,
                      border: `3px solid ${C.kritik}`,
                      opacity: (1 - r) * 0.7,
                    }}
                  />
                );
              })
            : null}
          <div
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: 52,
              background: "#0b0f15",
              border: `3px solid ${C.line2}`,
              boxShadow: `0 40px 80px -30px rgba(0,0,0,.9), 0 0 0 1px rgba(255,255,255,.05), 0 0 ${40 * crit}px ${C.kritik}33`,
              padding: 14,
            }}
          >
            <div
              style={{
                position: "relative",
                width: "100%",
                height: "100%",
                borderRadius: 40,
                overflow: "hidden",
                background: `linear-gradient(180deg, ${C.panel2}, ${C.bg2})`,
              }}
            >
              <div
                style={{
                  position: "absolute",
                  top: 10,
                  left: "50%",
                  translate: "-50% 0px",
                  width: 110,
                  height: 26,
                  borderRadius: 14,
                  background: "#05070a",
                }}
              />
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "50px 18px 12px",
                  borderBottom: `1px solid ${C.line}`,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div
                    style={{
                      width: 34,
                      height: 34,
                      borderRadius: 99,
                      background: C.line2,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <Icon name="user" size={22} color={C.muted} />
                  </div>
                  <span style={{ fontFamily: F.sans, fontSize: 20, fontWeight: 700, color: C.ink, whiteSpace: "nowrap" }}>
                    Nöbetçi tekniker
                  </span>
                </div>
                <span style={{ fontFamily: F.mono, fontSize: 15, color: C.dim, whiteSpace: "nowrap" }}>UCS-2</span>
              </div>

              <div style={{ padding: "18px 16px", display: "flex", flexDirection: "column", gap: 14 }}>
                {frame >= TYPE_START - 4 ? (
                  <div
                    style={{
                      alignSelf: "flex-start",
                      maxWidth: 300,
                      padding: "14px 16px",
                      borderRadius: "20px 20px 20px 6px",
                      background: C.line2,
                      fontFamily: F.sans,
                      fontSize: 21,
                      lineHeight: 1.38,
                      color: C.ink,
                      ...fadeUp(frame, TYPE_START - 4, { dist: 14, dur: 10 }),
                    }}
                  >
                    {SMS.slice(0, chars)}
                    {typing && Math.floor(frame / 6) % 2 === 0 ? <span style={{ color: C.kritik }}>▍</span> : null}
                  </div>
                ) : (
                  <div
                    style={{
                      marginTop: 60,
                      alignSelf: "center",
                      textAlign: "center",
                      opacity: interpolate(frame, [70, 90, 104, 112], [0, 1, 1, 0], CLAMP),
                    }}
                  >
                    <Icon name="bell" size={44} color={C.dim} />
                    <div style={{ fontFamily: F.sans, fontSize: 22, color: C.dim, marginTop: 8 }}>Nöbet · sessiz</div>
                  </div>
                )}
                {frame >= 236 ? (
                  <div
                    style={{
                      alignSelf: "flex-end",
                      padding: "12px 20px",
                      borderRadius: "20px 20px 6px 20px",
                      background: C.izle,
                      fontFamily: F.mono,
                      fontSize: 24,
                      fontWeight: 700,
                      color: "#04111f",
                      ...fadeSide(frame, 238, 50, 14),
                    }}
                  >
                    TAMAM 1 0541
                  </div>
                ) : null}
                {frame >= 262 ? (
                  <div
                    style={{
                      alignSelf: "center",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "8px 16px",
                      borderRadius: 999,
                      border: `1.5px solid ${C.ok}`,
                      background: `${C.ok}1f`,
                      fontFamily: F.sans,
                      fontSize: 20,
                      fontWeight: 700,
                      color: C.ok,
                      ...fadeUp(frame, 264, { dist: 12, dur: 14 }),
                      scale: String(
                        interpolate(frame, [264, 278], [0.6, 1], { ...CLAMP, easing: Easing.out(Easing.back(2)) }),
                      ),
                    }}
                  >
                    <Icon name="check" size={20} color={C.ok} stroke={3} />
                    Olay ONAYLANDI
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>

        {/* sağ: onay gelmezse yükselen merdiven */}
        <div style={{ position: "absolute", left: 1220, top: 352, width: 580, opacity: sideFade }}>
          <div
            style={{
              fontFamily: F.mono,
              fontSize: 22,
              letterSpacing: "0.14em",
              color: C.muted,
              marginBottom: 14,
              ...fadeUp(frame, 150, { dist: 12 }),
            }}
          >
            ONAY GELMEZSE
          </div>
          <div style={{ position: "relative" }}>
            <div style={{ position: "absolute", left: 27, top: 30, width: 4, height: 2 * 118, background: C.line2 }} />
            <div
              style={{
                position: "absolute",
                left: 27,
                top: 30,
                width: 4,
                height: 2 * 118 * escFill,
                background: `linear-gradient(180deg, ${C.kritik}, ${C.acil})`,
                boxShadow: `0 0 12px ${C.acil}`,
              }}
            />
            {ESC.map((e, i) => (
              <div
                key={e.h}
                style={{
                  display: "flex",
                  gap: 18,
                  alignItems: "flex-start",
                  height: 106,
                  marginBottom: 12,
                  ...fadeSide(frame, e.at, 50),
                }}
              >
                <div
                  style={{
                    width: 58,
                    height: 58,
                    borderRadius: 99,
                    flexShrink: 0,
                    background: C.panel2,
                    border: `2.5px solid ${escFill >= i / 2 - 0.01 ? C.kritik : C.line2}`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    position: "relative",
                    zIndex: 1,
                  }}
                >
                  <Icon name={e.icon} size={28} color={escFill >= i / 2 - 0.01 ? C.kritik : C.muted} stroke={2} />
                </div>
                <Card style={{ flex: 1, height: 106, padding: "10px 20px", borderRadius: 16 }}>
                  <div style={{ fontFamily: F.mono, fontSize: 20, fontWeight: 700, color: C.kritik }}>{e.t}</div>
                  <div style={{ fontFamily: F.sans, fontSize: 25, fontWeight: 700, color: C.ink, whiteSpace: "nowrap" }}>
                    {e.h}
                  </div>
                  <div style={{ fontFamily: F.sans, fontSize: 21, color: C.muted, whiteSpace: "nowrap" }}>{e.d}</div>
                </Card>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 6 }}>
            {["2 bağımsız sensör ailesi", "24 sa bekleme · Acil muaf", "saatte 8 Kritik tavanı · Acil muaf"].map((t, i) => (
              <div key={t} style={fadeUp(frame, 290 + i * 10, { dist: 14 })}>
                <Chip color={i === 0 ? C.izle : C.uyari} style={{ fontSize: 21, padding: "6px 16px" }}>
                  {t}
                </Chip>
              </div>
            ))}
          </div>
        </div>
      </AbsoluteFill>

      <Narration
        lines={[
          {
            from: 22,
            to: 104,
            text: (
              <>
                Beş basamak: Bilgi kayda geçer, İzle haftalık özete, <Em color={C.uyari}>Uyarı</Em> bir iş emri açar.
              </>
            ),
          },
          {
            from: 108,
            to: 230,
            text: (
              <>
                Telefonu yalnız <Em color={C.kritik}>Kritik</Em> ve <Em color={C.acil}>Acil</Em> çaldırır — iki bağımsız
                sensör ailesi hemfikirse.
              </>
            ),
          },
          {
            from: 234,
            to: 318,
            text: (
              <>
                Nöbetçi <Em color={C.izle}>“TAMAM 1 0541”</Em> yazar: kod kişiye ve olaya bağlı, başkası onaylayamaz.
              </>
            ),
          },
          {
            from: 322,
            to: 418,
            text: (
              <>
                Onay gelmezse merdiven yükselir: Acil'de <Em color={C.acil}>15</Em>, Kritik'te{" "}
                <Em color={C.kritik}>45 dakika</Em> sonra şef ve sesli arama.
              </>
            ),
          },
        ]}
      />
    </AbsoluteFill>
  );
};
