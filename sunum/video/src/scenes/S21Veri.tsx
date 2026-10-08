import React, { useMemo } from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Card, DrawPath, Em, Icon } from "../ui/primitives";
import { countUp, fadeSide, fadeUp, prog } from "../ui/motion";
import { C, CLAMP, EASE_OUT, F, linePath, Pt, rng } from "../theme";

/* 21 · VERİLEN VERİ VE DİJİTAL İKİZ
   Üstte gerçek bir fiderin günlük eğrisi, altta yarışmada verilen "Akım Sensörü" sayfası.
   Altı bağımsız test aynı şeyi söyler: düzgün dağılımlı gürültü. Bu yüzden dijital ikiz. */

const SW = 700;
const SH = 150;

/* sunum/src/slides-c.js seriesSVG ile aynı üretim */
const series = (kind: "real" | "given"): Pt[] => {
  const n = 152;
  const r = rng(kind === "real" ? 5 : 9);
  const pts: Pt[] = [];
  for (let i = 0; i < n; i++) {
    const hr = (i * 0.25) % 24;
    const v =
      kind === "real"
        ? 45 +
          26 * Math.max(0, Math.sin(((hr - 6) / 24) * 2 * Math.PI)) +
          9 * Math.exp(-Math.pow(hr - 20, 2) / 6) +
          (r() - 0.5) * 3
        : 15 + Math.floor(r() * 76);
    pts.push([10 + (i / (n - 1)) * (SW - 20), SH - 8 - ((v - 10) / 85) * (SH - 20)]);
  }
  return pts;
};

const SeriesCard: React.FC<{
  frame: number;
  start: number;
  kind: "real" | "given";
  caption: React.ReactNode;
  foot: React.ReactNode;
  color: string;
}> = ({ frame, start, kind, caption, foot, color }) => {
  const pts = useMemo(() => series(kind), [kind]);
  const d = useMemo(() => linePath(pts), [pts]);
  const p = interpolate(frame, [start + 10, start + 80], [0, 1], { ...CLAMP, easing: Easing.inOut(Easing.cubic) });
  const head = pts[Math.min(pts.length - 1, Math.floor(p * (pts.length - 1)))];
  return (
    <Card style={{ width: 760, height: 272, padding: "22px 30px" }}>
      <div style={{ fontFamily: F.sans, fontSize: 28, fontWeight: 700, color: C.ink }}>{caption}</div>
      <svg width={SW} height={SH + 6} style={{ marginTop: 12, overflow: "visible" }}>
        {[0.25, 0.5, 0.75].map((k) => (
          <line key={k} x1={0} x2={SW} y1={SH * k} y2={SH * k} stroke={C.line} strokeWidth={1.2} />
        ))}
        <DrawPath d={d} progress={p} stroke={color} strokeWidth={kind === "real" ? 3 : 2.2} />
        {p > 0.01 && p < 1 ? <circle cx={head[0]} cy={head[1]} r={6} fill={color} /> : null}
      </svg>
      <div style={{ fontFamily: F.mono, fontSize: 24, color: C.muted, marginTop: 8 }}>{foot}</div>
    </Card>
  );
};

const TESTS: [string, string, string][] = [
  ["Lag-1 otokorelasyon", "+0,0003", "> +0,97"],
  ["var(fark) / var(seri)", "2,0023", "≪ 2"],
  ["Fazlalık basıklık", "−1,2129", "≈ 0"],
  ["KS, U(14,5; 90,5)", "D = 0,0526", "> 0,1101"],
  ["χ², 76 tam sayı", "p = 0,446", "reddedilmeli"],
  ["Gün-üstü şekil korelasyonu", "r = +0,0596", "> 0,85"],
];

const MISSING = ["Sıcaklık · nem sayfası boş", "Etiketli arıza geçmişi yok", "Kardeş fazı yok", "Anomali yok"];

const SWAP = 200;

export const S21Veri: React.FC = () => {
  const frame = useCurrentFrame();

  const testsOut = interpolate(frame, [SWAP - 6, SWAP + 12], [1, 0], { ...CLAMP, easing: EASE_OUT });
  const stamp = interpolate(frame, [SWAP + 4, SWAP + 20], [0, 1], {
    ...CLAMP,
    easing: Easing.spring({ damping: 11, stiffness: 160 }),
  });

  return (
    <AbsoluteFill>
      <Backdrop accent={C.kritik} second={C.ok} />
      <SceneHeader kicker="12 · Dürüstlük" title="Verilen veri *sentetik* — ölçtük." accent={C.brand} />

      {/* sol: iki seri */}
      <div style={{ position: "absolute", left: 120, top: 290, ...fadeUp(frame, 22) }}>
        <SeriesCard
          frame={frame}
          start={20}
          kind="real"
          color={C.ok}
          caption={
            <>
              Gerçek bir fider böyle görünür <span style={{ color: C.dim, fontWeight: 500 }}>· dijital ikiz</span>
            </>
          }
          foot={
            <>
              lag-1 &gt; <span style={{ color: C.ok }}>0,97</span> · günün saati akımı belirler
            </>
          }
        />
      </div>
      <div style={{ position: "absolute", left: 120, top: 588, ...fadeUp(frame, 34) }}>
        <SeriesCard
          frame={frame}
          start={44}
          kind="given"
          color={C.kritik}
          caption={
            <>
              "Akım Sensörü" sayfası <span style={{ color: C.dim, fontWeight: 500 }}>· 152 satır, 15 dk</span>
            </>
          }
          foot={
            <>
              lag-1 = <span style={{ color: C.kritik }}>+0,0003</span> · komşu ölçümler ilişkisiz
            </>
          }
        />
        {/* damga */}
        <div
          style={{
            position: "absolute",
            right: 34,
            top: 96,
            padding: "10px 22px",
            border: `4px solid ${C.kritik}`,
            borderRadius: 12,
            fontFamily: F.sans,
            fontWeight: 900,
            fontSize: 30,
            letterSpacing: "0.08em",
            color: C.kritik,
            background: "rgba(6,8,12,.82)",
            rotate: "-6deg",
            opacity: Math.min(1, stamp * 1.4),
            scale: String(1.6 - 0.6 * stamp),
          }}
        >
          EĞİTİMDE KULLANILMADI
        </div>
      </div>

      {/* sağ, 1. evre: altı test */}
      <div
        style={{
          position: "absolute",
          left: 920,
          top: 290,
          width: 880,
          opacity: testsOut,
          translate: `0px ${(1 - testsOut) * -30}px`,
        }}
      >
        <div style={{ fontFamily: F.mono, fontSize: 22, color: C.dim, letterSpacing: "0.14em", marginBottom: 12, ...fadeUp(frame, 50) }}>
          ALTI BAĞIMSIZ TEST · ÖLÇÜLEN / BEKLENEN
        </div>
        {TESTS.map(([t, m, e], i) => {
          const s = 64 + i * 12;
          const x = prog(frame, s + 6, 14);
          return (
            <div
              key={t}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 18,
                height: 58,
                marginBottom: 8,
                padding: "0 22px",
                borderRadius: 14,
                background: C.panel,
                border: `1.5px solid ${C.line2}`,
                ...fadeSide(frame, s, 50),
              }}
            >
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 99,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: C.kritik + "22",
                  border: `2px solid ${C.kritik}`,
                  scale: String(0.3 + 0.7 * x),
                  opacity: x,
                }}
              >
                <Icon name="x" size={20} color={C.kritik} stroke={3} />
              </div>
              <div style={{ flex: 1, fontFamily: F.sans, fontSize: 27, fontWeight: 600, color: C.ink }}>{t}</div>
              <div style={{ width: 200, fontFamily: F.mono, fontSize: 28, fontWeight: 700, color: C.kritik, textAlign: "right" }}>
                {m}
              </div>
              <div style={{ width: 200, fontFamily: F.mono, fontSize: 22, color: C.dim, textAlign: "right" }}>{e}</div>
            </div>
          );
        })}
        <div
          style={{
            marginTop: 14,
            display: "flex",
            alignItems: "center",
            gap: 16,
            padding: "14px 24px",
            borderRadius: 14,
            background: C.kritik + "18",
            border: `2px solid ${C.kritik}`,
            boxShadow: `0 0 40px -10px ${C.kritik}`,
            opacity: prog(frame, 146, 10),
            scale: String(
              interpolate(frame, [146, 162], [1.15, 1], { ...CLAMP, easing: Easing.spring({ damping: 12, stiffness: 150 }) }),
            ),
          }}
        >
          <span style={{ fontFamily: F.mono, fontSize: 30, fontWeight: 700, color: C.ink }}>=RASTGELEARADA(15;90)</span>
          <span style={{ fontFamily: F.sans, fontSize: 28, color: C.muted }}>ile uyumlu düzgün gürültü</span>
        </div>
      </div>

      {/* sağ, 2. evre: kümede olmayanlar + dijital ikiz */}
      <div style={{ position: "absolute", left: 920, top: 290, width: 880 }}>
        <div style={{ fontFamily: F.mono, fontSize: 22, color: C.dim, letterSpacing: "0.14em", ...fadeUp(frame, SWAP + 6) }}>
          KÜMEDE OLMAYANLAR
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 14 }}>
          {MISSING.map((m, i) => (
            <div
              key={m}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                height: 58,
                padding: "0 20px",
                borderRadius: 14,
                background: C.panel,
                border: `1.5px solid ${C.line2}`,
                fontFamily: F.sans,
                fontSize: 26,
                fontWeight: 600,
                color: C.ink,
                ...fadeUp(frame, SWAP + 10 + i * 6, { dist: 24 }),
              }}
            >
              <Icon name="x" size={24} color={C.kritik} stroke={2.6} />
              {m}
            </div>
          ))}
        </div>

        <div style={{ marginTop: 26, ...fadeUp(frame, SWAP + 30, { blur: 6 }) }}>
          <Card glow={C.ok} style={{ padding: "26px 32px" }}>
            <div style={{ fontFamily: F.mono, fontSize: 22, color: C.ok, letterSpacing: "0.14em" }}>BU YÜZDEN</div>
            <div style={{ display: "flex", gap: 46, marginTop: 10, alignItems: "flex-end" }}>
              <div>
                <div style={{ fontFamily: F.mono, fontSize: 88, fontWeight: 700, color: C.olcum, lineHeight: 1 }}>
                  {Math.round(countUp(frame, SWAP + 38, 30, 0, 17))}
                </div>
                <div style={{ fontFamily: F.sans, fontSize: 26, color: C.muted, marginTop: 6 }}>senaryo</div>
              </div>
              <div>
                <div style={{ fontFamily: F.mono, fontSize: 88, fontWeight: 700, color: C.ok, lineHeight: 1 }}>
                  {Math.round(countUp(frame, SWAP + 46, 26, 0, 7))}
                </div>
                <div style={{ fontFamily: F.sans, fontSize: 26, color: C.muted, marginTop: 6 }}>negatif kontrol</div>
              </div>
              <div style={{ flex: 1, fontFamily: F.sans, fontSize: 30, lineHeight: 1.3, color: C.ink, paddingBottom: 4 }}>
                Fizikten türetilmiş <Em color={C.ok}>dijital ikiz</Em>; verilen küme de aynı testlerden geçti.
              </div>
            </div>
            <div
              style={{
                marginTop: 20,
                padding: "14px 20px",
                borderRadius: 12,
                border: `1.5px solid ${C.uyari}88`,
                background: C.uyari + "14",
                fontFamily: F.sans,
                fontSize: 28,
                lineHeight: 1.3,
                color: C.ink,
                opacity: prog(frame, SWAP + 70, 16),
              }}
            >
              Hiçbir başarım sayısı saha verisiyle doğrulanmış değil —{" "}
              <Em color={C.uyari}>pilotun ölçeceği ilk şey</Em>.
            </div>
          </Card>
        </div>
      </div>

      <Narration
        lines={[
          {
            from: 22,
            to: 112,
            text: <>Verilen akım verisini önce analiz ettik: gerçek bir fider böyle görünmez.</>,
          },
          {
            from: 116,
            to: SWAP - 2,
            text: (
              <>
                Altı bağımsız test aynı şeyi söylüyor: Excel'in <Em color={C.kritik}>RASTGELEARADA</Em>'sıyla üretilmiş
                gürültü.
              </>
            ),
          },
          {
            from: SWAP + 2,
            to: 270,
            text: (
              <>
                Bu yüzden modeli bu veriye uydurmadık — <Em color={C.ok}>fizikten türetilmiş</Em> bir ikiz kurduk.
              </>
            ),
          },
          {
            from: 274,
            to: 328,
            text: (
              <>
                Gerçek yanlış alarm oranı ancak <Em>etiketli bir pilot sahada</Em> ölçülür.
              </>
            ),
          },
        ]}
      />
    </AbsoluteFill>
  );
};
