import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Card, Em, Icon, IconName } from "../ui/primitives";
import { fadeSide, fadeUp, prog, pulse } from "../ui/motion";
import { C, CLAMP, EASE_OUT, F } from "../theme";

/* 18 · SAHA UYGULAMASI
   Kurulum prosedürü bir zaman çizelgesi olarak akar; soldaki saat her adımın
   dakikasıyla dolar. Güvenlik kapısı ve RS-485 adımı ayrıca vurgulanır. */

type Step = { icon: IconName; t: string; d: string; m: number; c?: string };

const STEPS: Step[] = [
  {
    icon: "camera",
    t: "Güvenlik kapısı",
    d: "Dokunmadan termal kamerayla tara. Pabuç > 110 °C ise dur, montaj yok.",
    m: 10,
    c: C.kritik,
  },
  { icon: "therm", t: "6 kelepçe · Ç6 ve Ç7", d: "Kablo kılıfına, pabuçtan 50–100 mm aşağı; emniyet teli askıya.", m: 30 },
  { icon: "eye", t: "Termal dizi nişanı", d: "Mıknatıs kaide, yukarı bakış; üç referans vida kilitlenene kadar.", m: 20 },
  { icon: "wave", t: "RF düğümü · M12 saplama", d: "HFCT yalnız PE iletkenine; faza takılırsa doğrulama yakalar.", m: 15 },
  {
    icon: "plug",
    t: "Ağ geçidi · DIN ray + 10 A priz",
    d: "İki RS-485 hattı. Enerjili indirmeye izin yoksa planlı kesintiye ertelenir.",
    m: 30,
    c: C.uyari,
  },
  {
    icon: "phone",
    t: "Dizüstüsüz devreye alma",
    d: "Telefonla etiket okuma → NFC dokunuş → çizimde konum → test SMS.",
    m: 35,
    c: C.ok,
  },
];

const STEP_AT = (i: number) => 40 + i * 28;
const ROW_H = 86;
const ROW_GAP = 12;
const RAIL_X = 560;

/* vurgu pencereleri (anlatımla eşleşir) */
const FOCUS: [number, number, number][] = [
  [0, 112, 200],
  [4, 204, 262],
  [5, 266, 330],
];

const Clock: React.FC<{ frame: number }> = ({ frame }) => {
  let done = 0;
  STEPS.forEach((s, i) => {
    done += s.m * interpolate(frame, [STEP_AT(i), STEP_AT(i) + 26], [0, 1], { ...CLAMP, easing: EASE_OUT });
  });
  const target = 150;
  const shown = interpolate(frame, [STEP_AT(5) + 26, STEP_AT(5) + 46], [done, target], { ...CLAMP, easing: EASE_OUT });
  const frac = shown / target;
  const r = 118;
  const L = 2 * Math.PI * r;
  const mins = Math.round(shown);
  const label = `${Math.floor(mins / 60)}:${String(mins % 60).padStart(2, "0")}`;
  return (
    <svg width={250} height={250} viewBox="0 0 300 300">
      <defs>
        <linearGradient id="saha-clk" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor={C.brand} />
          <stop offset="1" stopColor={C.brand2} />
        </linearGradient>
      </defs>
      <circle cx={150} cy={150} r={r} fill="none" stroke={C.line} strokeWidth={20} />
      {Array.from({ length: 12 }, (_, k) => {
        const a = (k / 12) * Math.PI * 2 - Math.PI / 2;
        return (
          <line
            key={k}
            x1={150 + Math.cos(a) * (r - 22)}
            y1={150 + Math.sin(a) * (r - 22)}
            x2={150 + Math.cos(a) * (r - 32)}
            y2={150 + Math.sin(a) * (r - 32)}
            stroke={C.line2}
            strokeWidth={3}
          />
        );
      })}
      <circle
        cx={150}
        cy={150}
        r={r}
        fill="none"
        stroke="url(#saha-clk)"
        strokeWidth={20}
        strokeLinecap="round"
        strokeDasharray={`${L * frac} ${L}`}
        transform="rotate(-90 150 150)"
        style={{ filter: `drop-shadow(0 0 10px ${C.brand}88)` }}
      />
      <text x={150} y={156} textAnchor="middle" fontFamily={F.mono} fontWeight={700} fontSize={66} fill={C.ink}>
        {label}
      </text>
      <text x={150} y={198} textAnchor="middle" fontFamily={F.sans} fontSize={24} fill={C.muted}>
        saat · 2 kişi
      </text>
    </svg>
  );
};

export const S18Saha: React.FC = () => {
  const frame = useCurrentFrame();

  const focusOf = (i: number) =>
    FOCUS.filter(([k]) => k === i).reduce(
      (acc, [, a, b]) => Math.max(acc, interpolate(frame, [a, a + 10, b - 8, b], [0, 1, 1, 0], CLAMP)),
      0,
    );
  const anyFocus = FOCUS.reduce(
    (acc, [, a, b]) => Math.max(acc, interpolate(frame, [a, a + 10, b - 8, b], [0, 1, 1, 0], CLAMP)),
    0,
  );

  const railP = interpolate(frame, [STEP_AT(0), STEP_AT(5) + 20], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const railH = (STEPS.length - 1) * (ROW_H + ROW_GAP);

  return (
    <AbsoluteFill>
      <Backdrop accent={C.brand} second={C.ok} />
      <SceneHeader kicker="09 · Saha" title="İki kişi, iki buçuk saat, *kesinti* *yok.*" />

      {/* sol: saat + kalıcı kurallar */}
      <div style={{ position: "absolute", left: 120, top: 300, width: 390, ...fadeUp(frame, 18, { blur: 8 }) }}>
        <Card style={{ padding: "16px 20px 18px", display: "flex", flexDirection: "column", alignItems: "center" }}>
          <Clock frame={frame} />
          <div style={{ fontFamily: F.sans, fontSize: 22, color: C.dim, marginTop: 4 }}>ilk 5 kurulum 3,5–4 saat</div>
          <div
            style={{
              marginTop: 12,
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "8px 16px",
              borderRadius: 999,
              border: `1.5px solid ${C.ok}66`,
              background: `${C.ok}18`,
              fontFamily: F.sans,
              fontSize: 22,
              fontWeight: 700,
              color: C.ok,
            }}
          >
            <Icon name="shield" size={22} color={C.ok} stroke={2.4} />
            Kesinti gerekmez
          </div>
        </Card>
      </div>
      <div style={{ position: "absolute", left: 120, top: 688, width: 390, display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ ...fadeUp(frame, 214) }}>
          <Card glow={C.brand} style={{ padding: "16px 20px" }}>
            <div style={{ fontFamily: F.sans, fontSize: 26, fontWeight: 800, color: C.brand2 }}>7 gün öğrenme</div>
            <div style={{ fontFamily: F.sans, fontSize: 21, color: C.muted, marginTop: 2 }}>
              Taban toplanır · mutlak limitler açık
            </div>
          </Card>
        </div>
        <div style={{ ...fadeUp(frame, 234) }}>
          <Card style={{ padding: "16px 20px" }}>
            <div style={{ fontFamily: F.sans, fontSize: 26, fontWeight: 800, color: C.ink }}>
              Pano ≠ cihaz iş emri
            </div>
            <div style={{ fontFamily: F.sans, fontSize: 21, color: C.muted, marginTop: 2 }}>
              Elektrik işi ayrı · sensör düzeltme ayrı
            </div>
          </Card>
        </div>
      </div>

      {/* sağ: adımlar */}
      <div style={{ position: "absolute", left: RAIL_X, top: 300, width: 1800 - RAIL_X }}>
        {/* ray */}
        <div
          style={{
            position: "absolute",
            left: 31,
            top: ROW_H / 2,
            width: 4,
            height: railH,
            borderRadius: 2,
            background: C.line,
          }}
        />
        <div
          style={{
            position: "absolute",
            left: 31,
            top: ROW_H / 2,
            width: 4,
            height: railH * railP,
            borderRadius: 2,
            background: `linear-gradient(180deg, ${C.kritik}, ${C.brand} 40%, ${C.ok})`,
            boxShadow: `0 0 12px ${C.brand}`,
          }}
        />
        {STEPS.map((s, i) => {
          const at = STEP_AT(i);
          const f = focusOf(i);
          const dim = 1 - 0.45 * anyFocus * (1 - f);
          const col = s.c ?? C.brand;
          const dot = prog(frame, at, 14);
          return (
            <div
              key={s.t}
              style={{
                position: "absolute",
                left: 0,
                top: i * (ROW_H + ROW_GAP),
                width: 1800 - RAIL_X,
                height: ROW_H,
                display: "flex",
                alignItems: "center",
                gap: 22,
                opacity: dim,
              }}
            >
              <div
                style={{
                  width: 66,
                  height: 66,
                  borderRadius: 99,
                  flexShrink: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: C.panel2,
                  border: `2.5px solid ${dot > 0.5 ? col : C.line2}`,
                  boxShadow: f > 0 ? `0 0 ${10 + 20 * f * pulse(frame, 24)}px ${col}` : "none",
                  scale: String(0.6 + 0.4 * dot),
                  opacity: Math.max(0.3, dot),
                }}
              >
                <Icon name={s.icon} size={32} color={dot > 0.5 ? col : C.dim} stroke={2} />
              </div>
              <div
                style={{
                  flex: 1,
                  height: ROW_H,
                  borderRadius: 16,
                  padding: "0 24px",
                  display: "flex",
                  alignItems: "center",
                  gap: 20,
                  background: f > 0 ? `${col}14` : C.panel,
                  border: `1.5px solid ${f > 0.3 ? col : C.line}`,
                  scale: String(1 + 0.015 * f),
                  ...fadeSide(frame, at, 50, 20),
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontFamily: F.sans, fontSize: 29, fontWeight: 800, color: C.ink }}>{s.t}</div>
                  <div
                    style={{
                      fontFamily: F.sans,
                      fontSize: 22,
                      color: s.c && f > 0 ? s.c : C.muted,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {s.d}
                  </div>
                </div>
                <div
                  style={{
                    fontFamily: F.mono,
                    fontSize: 24,
                    fontWeight: 700,
                    color: s.c ?? C.brand2,
                    padding: "6px 14px",
                    borderRadius: 10,
                    background: C.bg2,
                    border: `1px solid ${C.line2}`,
                  }}
                >
                  {s.m} dk
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <Narration
        lines={[
          {
            from: 22,
            to: 108,
            text: (
              <>
                Kesinti yok: yalnız <Em>alt kablo bölmesine</Em>, ölçü kolonuna ve mevcut prize dokunuyoruz.
              </>
            ),
          },
          {
            from: 112,
            to: 200,
            text: (
              <>
                İlk adım bir güvenlik kapısı: <Em color={C.kritik}>110 °C</Em> üstünde bir pabuç varsa ekip montaj yapmaz.
              </>
            ),
          },
          {
            from: 204,
            to: 262,
            text: (
              <>
                RS-485: izin yoksa <Em color={C.uyari}>planlı kesintiye</Em> ertelenir — sistem onsuz da çalışır.
              </>
            ),
          },
          {
            from: 266,
            to: 328,
            text: (
              <>
                Devreye alma telefonla: <Em color={C.ok}>elle yazılan pano numarası</Em> hatası ortadan kalkar.
              </>
            ),
          },
        ]}
      />
    </AbsoluteFill>
  );
};
