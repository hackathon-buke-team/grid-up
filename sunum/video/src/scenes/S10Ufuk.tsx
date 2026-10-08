import React, { useMemo } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Chip, Em, Icon, Theta } from "../ui/primitives";
import { fadeUp, popIn, prog, pulse } from "../ui/motion";
import { C, CLAMP, EASE_OUT, F, Pt, rng, sc, smoothPath, tr } from "../theme";

/* 10 · HAFTALAR ÖNCE: TARİH VE UFUK
   Ç7-L2'nin günlük θ medyanı çizilir. Geriye bakan yol (CUSUM, 3/5 gün → Uyarı, iki aile → Kritik),
   başlangıç tarihi (değişim noktası, aralıkla) ve ileriye bakan yol (ACİL'e 15 gün, 13–19).
   Eğri şematiktir; işaretlerdeki sayılar 3 Ekim demo koşusundandır. */

const CARD = { x: 120, y: 262, w: 1680, h: 544 };
const X = sc(-45, 20, 110, 1620);
const Y = sc(0, 28, 372, 56);
const CU_TOP = 408;
const CU_BOT = 488;

const thetaAt = (d: number) => (d < -22 ? 2 + (d + 45) * 0.2 : 6.6 + (d + 22) * 0.5);

const DAYS: [number, string][] = [
  [-45, "19 Ağu"],
  [-30, "3 Eyl"],
  [-22, "11 Eyl"],
  [-11, "22 Eyl"],
  [0, "bugün"],
  [15, "18 Eki"],
];
const TH: [number, string, string][] = [
  [2, "İzle", C.izle],
  [5, "Uyarı", C.uyari],
  [12, "Kritik", C.kritik],
  [25, "Acil", C.acil],
];

/* zamanlama */
const DRAW0 = 56;
const DRAW1 = 176;
const dayToFrame = (d: number) => DRAW0 + ((d + 45) / 45) * (DRAW1 - DRAW0);
const T_CP = 206;
const T_PROJ = 276;
const T_RULE = 350;

const SLOPE_HI = 0.563; // K/gün, %90 GA üst ucu (3,9 K/hf)
const SLOPE_LO = 0.397; // K/gün, alt ucu (2,8 K/hf)

export const S10Ufuk: React.FC = () => {
  const frame = useCurrentFrame();

  const data = useMemo(() => {
    const r = rng(11);
    const out: { d: number; th: number; cu: number }[] = [];
    let cu = 0;
    for (let d = -45; d <= 0; d++) {
      const noise = d === 0 ? 0 : (r() - 0.5) * 0.9;
      const th = d === 0 ? 17.6 : Math.max(0.4, thetaAt(d) + noise);
      cu = Math.max(0, cu + th - 1.5);
      out.push({ d, th, cu });
    }
    return out;
  }, []);
  const cuMax = data[data.length - 1].cu;
  const CY = (v: number) => CU_BOT - (CU_BOT - CU_TOP) * Math.sqrt(v / cuMax);

  const dDraw = interpolate(frame, [DRAW0, DRAW1], [-45, 0], CLAMP);
  const shown = data.filter((p) => p.d <= dDraw);
  const pts: Pt[] = shown.map((p) => [X(p.d), Y(p.th)]);
  const cuPts: Pt[] = shown.map((p) => [X(p.d), CY(p.cu)]);
  const nextIdx = Math.min(data.length - 1, shown.length);
  if (shown.length > 0 && shown.length < data.length) {
    const a = data[shown.length - 1];
    const b = data[nextIdx];
    const k = dDraw - a.d;
    pts.push([X(dDraw), Y(a.th + (b.th - a.th) * k)]);
    cuPts.push([X(dDraw), CY(a.cu + (b.cu - a.cu) * k)]);
  }
  const head = pts[pts.length - 1] ?? [X(-45), Y(2)];
  const headTheta = ((372 - head[1]) * 28) / (372 - 56);
  const cuCross = data.find((p) => p.cu > 8)?.d ?? -40;

  const cpIn = prog(frame, T_CP, 22);
  const proj = prog(frame, T_PROJ, 44);
  const days = interpolate(frame, [T_PROJ + 14, T_PROJ + 54], [0, 15], { ...CLAMP, easing: EASE_OUT });

  /* koni */
  const projDays = 20 * proj;
  const cone = [
    [X(0), Y(17.6)],
    [X(projDays), Y(Math.min(28, 17.6 + projDays * SLOPE_HI))],
    [X(projDays), Y(17.6 + projDays * SLOPE_LO)],
  ]
    .map((p) => p.join(","))
    .join(" ");
  const mid = Math.min(14.8, projDays);

  const card = (frameIn: number, x: number, y: number, w: number, color: string, children: React.ReactNode) => (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: w,
        boxSizing: "border-box",
        padding: "10px 16px",
        borderRadius: 12,
        background: "rgba(6,8,12,.94)",
        border: `2px solid ${color}`,
        boxShadow: `0 10px 40px -10px ${color}88`,
        ...fadeUp(frame, frameIn, { dist: 16, dur: 16 }),
      }}
    >
      {children}
    </div>
  );

  return (
    <AbsoluteFill>
      <Backdrop accent={C.olcum} second={C.acil} />
      <SceneHeader kicker="05 · Yöntem" title="Haftalar önce: *tarih* ve *ufuk.*" />

      <div
        style={{
          position: "absolute",
          left: CARD.x,
          top: CARD.y,
          width: CARD.w,
          height: CARD.h,
          borderRadius: 22,
          background: `linear-gradient(180deg, ${C.panel2}, ${C.panel})`,
          border: `1.5px solid ${C.line2}`,
          ...fadeUp(frame, 30, { blur: 6 }),
        }}
      >
        <svg width={CARD.w} height={CARD.h} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
          <text x={24} y={34} fontFamily={F.mono} fontSize={22} fill={C.dim}>
            θ günlük medyan · K · SOKE-14 / Ç7-L2
          </text>

          {/* gelecek bölgesi */}
          <rect x={X(0)} y={50} width={X(20) - X(0)} height={CU_BOT - 50} fill="rgba(255,47,121,.035)" />

          {/* eşikler */}
          {TH.map(([v, l, c], i) => (
            <g key={v} opacity={prog(frame, 40 + i * 5, 14)}>
              <line x1={110} x2={1620} y1={Y(v)} y2={Y(v)} stroke={c} strokeOpacity={0.55} strokeWidth={2} strokeDasharray="8 8" />
              <text x={100} y={Y(v) + 7} textAnchor="end" fontFamily={F.mono} fontSize={21} fill={c}>
                {l} {v}
              </text>
            </g>
          ))}
          <line x1={110} x2={1620} y1={Y(0)} y2={Y(0)} stroke={C.line2} strokeWidth={2} />

          {/* bugün */}
          <line x1={X(0)} x2={X(0)} y1={50} y2={CU_BOT} stroke={C.line2} strokeWidth={2} />

          {/* değişim noktası bandı */}
          <g opacity={cpIn}>
            <rect
              x={X(-29)}
              y={50}
              width={(X(-15) - X(-29)) * cpIn}
              height={CU_BOT - 50}
              fill="rgba(255,47,121,.09)"
            />
            <line x1={X(-22)} x2={X(-22)} y1={50} y2={CU_BOT} stroke={C.acil} strokeWidth={2.5} strokeDasharray="6 5" />
          </g>

          {/* CUSUM şeridi */}
          <g opacity={prog(frame, 46, 14)}>
            <text x={100} y={CU_TOP + 18} textAnchor="end" fontFamily={F.mono} fontSize={20} fill={C.kritik}>
              CUSUM
            </text>
            <line x1={110} x2={1620} y1={CU_BOT} y2={CU_BOT} stroke={C.line2} strokeWidth={1.5} />
            <line x1={110} x2={X(0)} y1={CY(8)} y2={CY(8)} stroke={C.uyari} strokeWidth={1.5} strokeDasharray="5 5" />
            <text x={X(0) + 10} y={CY(8) + 6} fontFamily={F.mono} fontSize={19} fill={C.uyari}>
              h = 8
            </text>
          </g>
          {cuPts.length > 1 ? (
            <path
              d={`M${cuPts[0][0]},${CU_BOT} ${cuPts.map((p) => `L${p[0]},${p[1]}`).join(" ")} L${cuPts[cuPts.length - 1][0]},${CU_BOT} Z`}
              fill="rgba(255,107,61,.18)"
              stroke={C.kritik}
              strokeWidth={2.5}
            />
          ) : null}
          {dDraw >= cuCross ? (
            <circle cx={X(cuCross)} cy={CY(8)} r={6} fill={C.uyari} opacity={prog(frame, dayToFrame(cuCross), 8)} />
          ) : null}

          {/* tarih etiketleri */}
          {DAYS.map(([d, t], i) => (
            <text
              key={d}
              x={X(d)}
              y={524}
              textAnchor="middle"
              fontFamily={F.mono}
              fontSize={21}
              fill={d === 0 ? C.ink : d === -22 ? C.acil : C.dim}
              opacity={prog(frame, 44 + i * 4, 14)}
            >
              {t}
            </text>
          ))}

          {/* koni */}
          {proj > 0 ? (
            <g>
              <polygon points={cone} fill="rgba(255,47,121,.2)" />
              <line
                x1={X(0)}
                y1={Y(17.6)}
                x2={X(mid)}
                y2={Y(17.6 + (mid * 7.4) / 14.8)}
                stroke={C.acil}
                strokeWidth={3}
                strokeDasharray="9 6"
              />
              <rect
                x={X(13.1)}
                y={Y(25) - 5}
                width={(X(18.6) - X(13.1)) * prog(frame, T_PROJ + 34, 16)}
                height={10}
                rx={5}
                fill={C.acil}
              />
              {proj > 0.72 ? <circle cx={X(14.8)} cy={Y(25)} r={8} fill={C.acil} stroke={C.bg} strokeWidth={2} /> : null}
            </g>
          ) : null}

          {/* θ çizgisi */}
          {pts.length > 1 ? (
            <>
              <path d={smoothPath(pts)} fill="none" stroke={C.olcum} strokeWidth={9} opacity={0.15} />
              <path d={smoothPath(pts)} fill="none" stroke={C.olcum} strokeWidth={4} strokeLinejoin="round" />
            </>
          ) : null}
          {frame >= DRAW0 ? (
            <g>
              <circle cx={head[0]} cy={head[1]} r={9} fill={C.olcum} />
              <circle cx={head[0]} cy={head[1]} r={14 + 10 * pulse(frame, 30)} fill={C.olcum} opacity={0.18} />
            </g>
          ) : null}

          {/* alarm işaretleri */}
          {[
            { d: -27, th: 5.6, c: C.uyari, lx: 500, ly: 284 },
            { d: -11, th: 12.1, c: C.kritik, lx: X(-11) + 20, ly: 268 },
          ].map((m) =>
            dDraw >= m.d ? (
              <g key={m.d} opacity={prog(frame, dayToFrame(m.d), 10)}>
                <circle cx={X(m.d)} cy={Y(m.th)} r={10} fill="none" stroke={m.c} strokeWidth={3} />
                <line
                  x1={X(m.d) + (m.lx - X(m.d)) * 0.4}
                  y1={Y(m.th) + (m.ly - Y(m.th)) * 0.4}
                  x2={m.lx}
                  y2={m.ly}
                  stroke={m.c}
                  strokeWidth={2}
                />
              </g>
            ) : null,
          )}
        </svg>

        {/* canlı θ etiketi */}
        {frame >= DRAW0 && frame < DRAW1 + 30 ? (
          <div
            style={{
              position: "absolute",
              left: head[0] + 16,
              top: head[1] - 46,
              fontFamily: F.mono,
              fontSize: 26,
              fontWeight: 700,
              color: C.olcum,
              opacity: interpolate(frame, [DRAW0, DRAW0 + 8, DRAW1 + 14, DRAW1 + 30], [0, 1, 1, 0], CLAMP),
            }}
          >
            {tr(Math.max(0, headTheta))} K
          </div>
        ) : null}
        <div
          style={{
            position: "absolute",
            left: X(0) - 140,
            top: Y(17.6) - 52,
            fontFamily: F.mono,
            fontSize: 30,
            fontWeight: 700,
            color: C.olcum,
            ...popIn(frame, DRAW1 + 20),
          }}
        >
          17,6 K
        </div>

        {/* kartlar */}
        {dDraw >= -27
          ? card(
              dayToFrame(-27) + 2,
              130,
              186,
              370,
              C.uyari,
              <>
                <div style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 24, color: C.uyari }}>Uyarı · iş emri açıldı</div>
                <div style={{ fontFamily: F.mono, fontSize: 19, color: C.muted, marginTop: 2 }}>
                  CUSUM &gt; 8 · θ ≥ 5 K · 3/5 gün
                </div>
                <div style={{ fontFamily: F.sans, fontSize: 20, color: C.dim, marginTop: 2 }}>telefon çalmaz</div>
              </>,
            )
          : null}
        {dDraw >= -11
          ? card(
              dayToFrame(-11) + 2,
              X(-11) - 4,
              268,
              270,
              C.kritik,
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Icon name="phone" size={24} color={C.kritik} stroke={2.2} />
                  <span style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 24, color: C.kritik }}>Kritik · SMS</span>
                </div>
                <div style={{ fontFamily: F.sans, fontSize: 20, color: C.muted, marginTop: 4 }}>
                  iki bağımsız sensör ailesi hemfikir
                </div>
              </>,
            )
          : null}
        {card(
          T_CP + 10,
          X(-22) + 12,
          62,
          360,
          C.acil,
          <>
            <div style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 24, color: C.acil, whiteSpace: "nowrap" }}>Değişim noktası ≈ 11 Eylül</div>
            <div style={{ fontFamily: F.sans, fontSize: 20, color: C.muted, marginTop: 2 }}>bir aralık: rampa, basamak değil</div>
          </>,
        )}
        {card(
          T_PROJ + 12,
          X(0) + 26,
          Y(17.6) + 30,
          430,
          C.acil,
          <>
            <div style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 30, color: C.acil }}>
              ACİL'e ~{Math.round(days)} gün <span style={{ fontWeight: 600, fontSize: 26 }}>(13–19)</span>
            </div>
            <div style={{ fontFamily: F.mono, fontSize: 19, color: C.muted, marginTop: 4 }}>
              +3,5 K/hf · %90 GA 2,8–3,9 K/hf
            </div>
          </>,
        )}
        {card(
          T_RULE + 8,
          X(0) + 26,
          Y(17.6) + 140,
          430,
          C.line2,
          <>
            <div style={{ fontFamily: F.sans, fontSize: 20, color: C.muted }}>21 günde &lt; 14 geçerli gün olsaydı:</div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 4 }}>
              <span style={{ fontFamily: F.mono, fontWeight: 700, fontSize: 24, color: C.ink }}>YETERSIZ_GECMIS</span>
              <span style={{ fontFamily: F.sans, fontSize: 20, color: C.dim }}>· gün sayısı yok</span>
            </div>
          </>,
        )}
      </div>

      {/* yöntem çipleri */}
      <div style={{ position: "absolute", left: 120, top: 828, display: "flex", gap: 14 }}>
        {[
          { t: "CUSUM + 3/5 gün", c: C.izle, at: 100, icon: "chart" as const },
          { t: "Değişim noktası · aralık", c: C.acil, at: T_CP + 4, icon: "flag" as const },
          { t: "Theil-Sen + güven aralığı", c: C.brand, at: T_PROJ + 4, icon: "clock" as const },
          { t: "21 günde < 14 gün → sayı yok", c: C.ink, at: T_RULE, icon: "x" as const },
        ].map((c) => {
          const on = prog(frame, c.at, 14);
          return (
            <div key={c.t} style={{ opacity: 0.35 + 0.65 * on, scale: String(1 + 0.08 * Math.sin(on * Math.PI)) }}>
              <Chip color={on > 0.5 ? c.c : C.dim} style={{ fontSize: 22, padding: "6px 18px" }}>
                <Icon name={c.icon} size={22} color={on > 0.5 ? c.c : C.dim} stroke={2.2} />
                {c.t}
              </Chip>
            </div>
          );
        })}
      </div>

      <Narration
        lines={[
          {
            from: 50,
            to: 140,
            text: (
              <>
                Sarı çizgi: Ç7-L2'nin günlük <Theta /> medyanı. <Em color={C.uyari}>Uyarı</Em> iş emri açar — telefon
                çalmaz.
              </>
            ),
          },
          {
            from: 144,
            to: 202,
            text: (
              <>
                <Em color={C.kritik}>Kritik</Em>'te iki bağımsız sensör ailesi hemfikirdir: nöbetçiye SMS gider.
              </>
            ),
          },
          {
            from: 206,
            to: 270,
            text: (
              <>
                Bozulma <Em color={C.acil}>≈ 11 Eylül</Em>'de hızlandı. Tarih bir aralık — bozulma bir rampa.
              </>
            ),
          },
          {
            from: 274,
            to: 346,
            text: (
              <>
                Bu gidişle ACİL'e <Em color={C.acil}>15 gün (13–19)</Em> — aralık, eğimin kendi güven aralığından.
              </>
            ),
          },
          {
            from: 350,
            to: 418,
            text: (
              <>
                Geçmiş yetersizse sayı <Em>üretilmez</Em>. Sayı üretmemek ürünün kendisi.
              </>
            ),
          },
        ]}
      />
    </AbsoluteFill>
  );
};
