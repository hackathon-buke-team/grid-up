import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Card, Chip, DrawPath, Em, Icon, Theta } from "../ui/primitives";
import { fadeUp, popIn, prog } from "../ui/motion";
import { C, CLAMP, EASE_IN_OUT, F, Pt, sc, smoothPath, tr } from "../theme";

/* 11 · KÖR OLDUĞUMUZ YERİ SÖYLERİZ
   θ_min = 3σ / f². Günün saati ilerledikçe yük düşer, görülebilen en küçük kusur büyür:
   15:00'te (f ≈ 0,92) 1 K'nin altı, 03:00'te (f = 0,18) 18,5 K. Bunu saklamıyoruz, ekranda yazıyoruz. */

const SIG_CLAMP = 0.2; // kelepçe σ, K
const SIG_IR = 0.8; // IR dizi σ, K
const loadAt = (hr: number) => 0.55 - 0.37 * Math.cos((2 * Math.PI * (hr - 3)) / 24);
const thMin = (sigma: number, f: number) => (3 * sigma) / (f * f);

/* grafik koordinatları (kart içi) */
const X = sc(0.1, 1, 100, 820);
const Y = sc(0, 30, 470, 70);

const curve = (sigma: number) => {
  const p: Pt[] = [];
  for (let f = 0.1; f <= 1.0001; f += 0.01) {
    const v = thMin(sigma, f);
    if (v <= 31) p.push([X(f), Y(v)]);
  }
  return smoothPath(p);
};
const D_CLAMP = curve(SIG_CLAMP);
const D_IR = curve(SIG_IR);

/* 24 saatlik yük profili (mini) */
const SPX = sc(0, 24, 0, 300);
const SPY = sc(0, 1, 70, 4);
const SPARK = (() => {
  const p: Pt[] = [];
  for (let h = 0; h <= 24.001; h += 0.5) p.push([SPX(h), SPY(loadAt(h))]);
  return smoothPath(p);
})();

export const S11Korluk: React.FC = () => {
  const frame = useCurrentFrame();

  const hr = interpolate(frame, [40, 110, 168], [15, 15, 27], { ...CLAMP, easing: EASE_IN_OUT });
  const f = loadAt(hr);
  const m = thMin(SIG_CLAMP, f);
  const low = f < 0.35;
  const hh = Math.floor(hr) % 24;
  const mm = Math.floor(((hr % 1) * 60) / 10) * 10;
  const clock = `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
  const stateCol = low ? C.izle : C.ok;
  const cursorIn = prog(frame, 70, 14);

  return (
    <AbsoluteFill>
      <Backdrop accent={C.izle} second={C.olcum} />
      <SceneHeader kicker="05 · Yöntem" title="Kör olduğumuz yeri *söyleriz.*" accent={C.brand} />

      {/* sol: görülebilirlik tabanı */}
      <div style={{ position: "absolute", left: 120, top: 270, ...fadeUp(frame, 30, { blur: 6 }) }}>
        <Card style={{ width: 860, height: 620, padding: 0, position: "relative" }}>
          <svg width={860} height={620} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
            <text x={30} y={44} fontFamily={F.sans} fontSize={23} fill={C.muted}>
              görülebilen en küçük kusur · K
            </text>

            {/* düşük görünürlük bandı */}
            <rect x={X(0.1)} y={Y(30)} width={X(0.35) - X(0.1)} height={Y(0) - Y(30)} fill="rgba(74,163,255,.09)" />
            <line x1={X(0.35)} x2={X(0.35)} y1={Y(30)} y2={Y(0)} stroke={C.izle} strokeWidth={2} strokeDasharray="6 5" />
            <text x={X(0.36) + 4} y={Y(28.5)} fontFamily={F.mono} fontSize={21} fill={C.izle}>
              f = 0,35
            </text>
            <text
              x={(X(0.1) + X(0.35)) / 2}
              y={Y(1.6)}
              textAnchor="middle"
              fontFamily={F.sans}
              fontSize={21}
              fontWeight={700}
              fill={C.izle}
            >
              görünürlük düşük
            </text>

            {[0, 5, 10, 15, 20, 25, 30].map((v) => (
              <g key={v}>
                <line x1={X(0.1)} x2={X(1)} y1={Y(v)} y2={Y(v)} stroke={C.line} strokeWidth={1.5} />
                <text x={X(0.1) - 14} y={Y(v) + 7} textAnchor="end" fontFamily={F.mono} fontSize={21} fill={C.dim}>
                  {v}
                </text>
              </g>
            ))}
            {[0.2, 0.4, 0.6, 0.8, 1].map((v) => (
              <text key={v} x={X(v)} y={506} textAnchor="middle" fontFamily={F.mono} fontSize={21} fill={C.dim}>
                {tr(v, 1)}
              </text>
            ))}
            <text x={X(1)} y={540} textAnchor="end" fontFamily={F.sans} fontSize={21} fill={C.dim}>
              yük faktörü f = I / I_ref
            </text>

            <DrawPath d={D_IR} progress={prog(frame, 50, 40)} stroke={C.muted} strokeWidth={3} strokeDasharray="8 7" />
            <DrawPath d={D_CLAMP} progress={prog(frame, 40, 40)} stroke={C.olcum} strokeWidth={5} />
            <g opacity={prog(frame, 74, 14)}>
              <line x1={560} x2={600} y1={104} y2={104} stroke={C.olcum} strokeWidth={5} strokeLinecap="round" />
              <text x={612} y={111} fontFamily={F.sans} fontSize={21} fontWeight={700} fill={C.olcum}>
                kelepçe · σ = 0,2 K
              </text>
              <line x1={560} x2={600} y1={140} y2={140} stroke={C.muted} strokeWidth={3} strokeDasharray="8 7" />
              <text x={612} y={147} fontFamily={F.sans} fontSize={21} fill={C.muted}>
                IR dizi · σ = 0,8 K
              </text>
            </g>

            {/* imleç */}
            <g opacity={cursorIn}>
              <line x1={X(f)} x2={X(f)} y1={Y(30)} y2={Y(0)} stroke={C.ink} strokeOpacity={0.35} strokeWidth={2} />
              <line x1={X(0.1)} x2={X(f)} y1={Y(m)} y2={Y(m)} stroke={stateCol} strokeOpacity={0.6} strokeWidth={2} strokeDasharray="4 6" />
              <circle cx={X(f)} cy={Y(Math.min(30, m))} r={22} fill={stateCol} opacity={0.2} />
              <circle cx={X(f)} cy={Y(Math.min(30, m))} r={10} fill={C.olcum} stroke={C.bg} strokeWidth={3} />
            </g>
          </svg>

          {/* alt çipler */}
          <div
            style={{
              position: "absolute",
              left: 30,
              right: 30,
              top: 562,
              display: "flex",
              gap: 12,
              flexWrap: "nowrap",
            }}
          >
            <div style={{ ...popIn(frame, 248) }}>
              <Chip color={C.izle} style={{ fontSize: 21, padding: "5px 14px" }}>
                <Icon name="eye" size={22} color={C.izle} stroke={2.2} />
                ayrı durum · SCADA'da ayrı bit
              </Chip>
            </div>
            <div style={{ ...popIn(frame, 256) }}>
              <Chip color={C.kritik} style={{ fontSize: 21, padding: "5px 14px" }}>
                <Icon name="therm" size={22} color={C.kritik} stroke={2.2} />
                mutlak limitler açık · 90 · 110 · 130 °C
              </Chip>
            </div>
          </div>
        </Card>
      </div>

      {/* sağ üst: formül */}
      <div style={{ position: "absolute", left: 1020, top: 270, ...fadeUp(frame, 38) }}>
        <Card style={{ width: 780, height: 112, padding: "14px 30px", display: "flex", alignItems: "center", gap: 30 }}>
          <div style={{ fontFamily: F.math, fontSize: 58, color: C.ink, whiteSpace: "nowrap" }}>
            <span style={{ fontStyle: "italic", color: C.olcum }}>
              θ<sub style={{ fontSize: "0.5em" }}>min</sub>
            </span>{" "}
            = 3<i>σ</i> / <i>f</i>²
          </div>
          <div style={{ fontFamily: F.sans, fontSize: 22, color: C.muted, lineHeight: 1.3 }}>
            Kusur, gözlenen farkı yalnız <Theta />·f² kadar büyütür.
          </div>
        </Card>
      </div>

      {/* sağ orta: canlı okuma */}
      <div style={{ position: "absolute", left: 1020, top: 400, ...fadeUp(frame, 48) }}>
        <Card glow={stateCol} style={{ width: 780, height: 300, padding: "22px 30px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 30 }}>
            <div>
              <div style={{ fontFamily: F.sans, fontSize: 21, color: C.dim }}>Saat</div>
              <div style={{ fontFamily: F.mono, fontSize: 44, fontWeight: 700, color: C.ink, lineHeight: 1.1 }}>
                {clock}
              </div>
            </div>
            <div>
              <div style={{ fontFamily: F.sans, fontSize: 21, color: C.dim }}>Yük f</div>
              <div style={{ fontFamily: F.mono, fontSize: 44, fontWeight: 700, color: C.izle, lineHeight: 1.1 }}>
                {tr(f, 2)}
              </div>
            </div>
            <svg width={300} height={74} style={{ overflow: "visible", marginLeft: "auto" }}>
              <path d={SPARK} fill="none" stroke={C.izle} strokeWidth={3} opacity={0.75} />
              <line x1={0} x2={300} y1={SPY(0.35)} y2={SPY(0.35)} stroke={C.izle} strokeWidth={1.5} strokeDasharray="4 5" opacity={0.6} />
              <circle cx={SPX(hr % 24)} cy={SPY(f)} r={8} fill={C.olcum} stroke={C.bg} strokeWidth={2.5} />
              <text x={0} y={96} fontFamily={F.mono} fontSize={18} fill={C.dim}>
                00
              </text>
              <text x={150} y={96} textAnchor="middle" fontFamily={F.mono} fontSize={18} fill={C.dim}>
                12
              </text>
              <text x={300} y={96} textAnchor="end" fontFamily={F.mono} fontSize={18} fill={C.dim}>
                24
              </text>
            </svg>
          </div>
          <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginTop: 20 }}>
            <div>
              <div style={{ fontFamily: F.sans, fontSize: 22, color: C.muted }}>
                Şu an görülebilen en küçük <Theta />
              </div>
              <div
                style={{
                  fontFamily: F.mono,
                  fontSize: 88,
                  fontWeight: 700,
                  lineHeight: 1,
                  color: low ? C.izle : C.ok,
                  textShadow: `0 0 30px ${stateCol}55`,
                }}
              >
                {tr(m)} K
              </div>
            </div>
            <Chip color={stateCol} solid style={{ fontSize: 24, marginBottom: 10 }}>
              <Icon name={low ? "eye" : "check"} size={24} color={C.bg} stroke={2.4} />
              {low ? "Görünürlük düşük" : "Tam görüş"}
            </Chip>
          </div>
          <div
            style={{
              marginTop: 14,
              fontFamily: F.sans,
              fontSize: 25,
              fontStyle: "italic",
              color: C.ink,
            }}
          >
            {low
              ? `“Şu anda ${tr(m)} K'nin altındaki bir kusuru göremiyorum.”`
              : `“${tr(m)} K ve üstündeki kusuru görüyorum.”`}
          </div>
        </Card>
      </div>

      {/* sağ alt: karşılaştırma */}
      <div style={{ position: "absolute", left: 1020, top: 720, display: "flex", gap: 20 }}>
        <div style={{ ...fadeUp(frame, 182, { dist: 24 }) }}>
          <Card style={{ width: 380, height: 170, padding: "18px 24px", opacity: 0.85 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, fontFamily: F.mono, fontSize: 21, color: C.dim }}>
              <Icon name="x" size={24} color={C.kritik} stroke={2.6} />
              RAKİP ÜRÜN · 03:00
            </div>
            <div style={{ position: "relative", marginTop: 16, fontFamily: F.sans, fontSize: 34, fontWeight: 700, color: C.muted }}>
              “Her şey normal.”
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  top: "52%",
                  height: 4,
                  borderRadius: 2,
                  background: C.kritik,
                  width: `${prog(frame, 214, 14) * 270}px`,
                }}
              />
            </div>
            <div style={{ marginTop: 8, fontFamily: F.sans, fontSize: 21, color: C.dim }}>kör olduğunu bilmiyor</div>
          </Card>
        </div>
        <div style={{ ...fadeUp(frame, 192, { dist: 24 }) }}>
          <Card glow={C.ok} style={{ width: 380, height: 170, padding: "18px 24px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, fontFamily: F.mono, fontSize: 21, color: C.ok }}>
              <Icon name="check" size={24} color={C.ok} stroke={2.6} />
              PANO GÖZ · 03:00
            </div>
            <div style={{ marginTop: 16, fontFamily: F.sans, fontSize: 30, fontWeight: 700, color: C.ink, lineHeight: 1.2 }}>
              “18,5 K altını göremiyorum.”
            </div>
            <div style={{ marginTop: 8, fontFamily: F.sans, fontSize: 21, color: C.dim }}>kullanılabilir bir bilgi</div>
          </Card>
        </div>
      </div>

      <Narration
        lines={[
          {
            from: 36,
            to: 104,
            text: (
              <>
                Yük düştükçe aynı kusuru görmek <Em color={C.izle}>zorlaşır</Em>. Bunu saklamıyoruz, hesaplıyoruz.
              </>
            ),
          },
          {
            from: 108,
            to: 176,
            text: (
              <>
                Öğleden sonra 1 K'nin altı bile görünür. Gece 03:00, <Em color={C.izle}>%18 yük</Em>:{" "}
                <Em color={C.izle}>18,5 K</Em>.
              </>
            ),
          },
          {
            from: 180,
            to: 242,
            text: (
              <>
                Rakip “her şey normal” der. Biz kör olduğumuz <Em color={C.ok}>eşiği</Em> söyleriz.
              </>
            ),
          },
          {
            from: 246,
            to: 298,
            text: (
              <>
                Bu bir arıza değil, görünürlük durumu. <Em color={C.kritik}>Mutlak limitler</Em> her zaman açık.
              </>
            ),
          },
        ]}
      />
    </AbsoluteFill>
  );
};
