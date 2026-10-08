import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Card, Em, Icon, Level, Theta } from "../ui/primitives";
import { fadeUp, prog } from "../ui/motion";
import { C, CLAMP, EASE_IN_OUT, EASE_OUT, F, heat, linePath, Pt, sc, severity, tr } from "../theme";

/* 5 · θ: KARDEŞİNE GÖRE FARK
   Canlı model: Çıkış 7'nin üç fazı. Önce sıcak hava, sonra yük artışı — θ kıpırdamaz.
   Sonra yalnız L2 ısınır — θ 6,35 K'e çıkar. Sonra yük oynar — ham fark değişir, θ değişmez. */

const RISE = 30; // anma akımında iletken ısınması, K

const model = (g: number) => {
  const amb = interpolate(g, [95, 150], [28, 34.1], { ...CLAMP, easing: EASE_IN_OUT });
  const f = interpolate(g, [170, 225, 360, 405, 450], [0.55, 0.9, 0.9, 0.5, 0.85], {
    ...CLAMP,
    easing: EASE_IN_OUT,
  });
  const th2 = interpolate(g, [250, 320], [0, 6.35], { ...CLAMP, easing: EASE_IN_OUT });
  const base = amb + RISE * f * f;
  const T1 = base;
  const T2 = base + th2 * f * f;
  const T3 = base;
  const med = (T1 + T3) / 2; // kendisi hariç kardeş medyanı
  const dT = T2 - med;
  return { amb, f, T1, T2, T3, med, dT, theta: dT / (f * f) };
};

/* ---------------- fazlar ---------------- */
const BAR_W = 110;
const BX = [110, 300, 490];
const BY = sc(25, 66, 300, 30); // °C → svg y
const PHASES = [
  { n: "L1", c: C.l1 },
  { n: "L2", c: C.l2 },
  { n: "L3", c: C.l3 },
];

const Bars: React.FC<{ frame: number }> = ({ frame }) => {
  const m = model(frame);
  const Ts = [m.T1, m.T2, m.T3];
  const grow = prog(frame, 70, 30);
  const yMed = BY(m.med);
  const yT2 = BY(m.T2);
  return (
    <svg width={720} height={330} style={{ overflow: "visible" }}>
      <line x1={40} x2={560} y1={300} y2={300} stroke={C.line2} strokeWidth={2} />
      {Ts.map((T, i) => {
        const h = (300 - BY(T)) * grow;
        const t = 0.3 + ((T - 25) / 41) * 0.66;
        const hot = i === 1 && m.dT > 0.4;
        return (
          <g key={i}>
            <rect x={BX[i] - BAR_W / 2} y={30} width={BAR_W} height={270} rx={16} fill={C.panel} stroke={C.line} />
            <rect
              x={BX[i] - BAR_W / 2}
              y={300 - h}
              width={BAR_W}
              height={h}
              rx={16}
              fill={heat(t)}
              style={hot ? { filter: `drop-shadow(0 0 ${8 + m.dT * 3}px ${heat(0.9, 0.8)})` } : undefined}
            />
            <rect x={BX[i] - BAR_W / 2} y={300 - h} width={8} height={h} rx={4} fill={PHASES[i].c} />
            <text
              x={BX[i]}
              y={300 - h - 16}
              textAnchor="middle"
              fontFamily={F.mono}
              fontSize={28}
              fontWeight={700}
              fill={hot ? C.olcum : C.ink}
              opacity={grow}
            >
              {tr(T)}°
            </text>
            <text x={BX[i]} y={286} textAnchor="middle" fontFamily={F.sans} fontSize={28} fontWeight={800} fill={C.bg}>
              {PHASES[i].n}
            </text>
          </g>
        );
      })}
      {/* kardeş medyanı */}
      <g opacity={prog(frame, 100, 20)}>
        <line x1={40} x2={560} y1={yMed} y2={yMed} stroke={C.ink} strokeWidth={2} strokeDasharray="8 8" opacity={0.6} />
        <text x={572} y={yMed - 6} fontFamily={F.sans} fontSize={22} fill={C.muted}>
          kardeş
        </text>
        <text x={572} y={yMed + 20} fontFamily={F.sans} fontSize={22} fill={C.muted}>
          medyanı
        </text>
      </g>
      {/* ham fark parantezi */}
      {m.dT > 0.25 ? (
        <g>
          <path
            d={`M${BX[1] + BAR_W / 2 + 10},${yT2} h10 V${yMed} h-10`}
            fill="none"
            stroke={C.olcum}
            strokeWidth={2.5}
          />
          <text x={BX[1] + BAR_W / 2 + 28} y={(yT2 + yMed) / 2 + 9} fontFamily={F.mono} fontSize={24} fill={C.olcum}>
            ΔT
          </text>
        </g>
      ) : null}
    </svg>
  );
};

/* ---------------- grafik ---------------- */
const G0 = 40;
const G1 = 540;
const CX = sc(G0, G1, 70, 840);
const CY = sc(0, 8, 230, 20);

const Chart: React.FC<{ frame: number }> = ({ frame }) => {
  const thetaPts: Pt[] = [];
  const dtPts: Pt[] = [];
  for (let g = G0; g <= Math.max(G0 + 1, frame); g += 2) {
    const m = model(g);
    thetaPts.push([CX(g), CY(m.theta)]);
    dtPts.push([CX(g), CY(m.dT)]);
  }
  const last = thetaPts[thetaPts.length - 1];
  return (
    <svg width={860} height={260} style={{ overflow: "visible" }}>
      {[0, 2, 4, 6, 8].map((v) => (
        <g key={v}>
          <line x1={70} x2={840} y1={CY(v)} y2={CY(v)} stroke={C.line} strokeWidth={1.5} />
          <text x={56} y={CY(v) + 8} textAnchor="end" fontFamily={F.mono} fontSize={22} fill={C.dim}>
            {v}
          </text>
        </g>
      ))}
      <line x1={70} x2={840} y1={CY(5)} y2={CY(5)} stroke={C.uyari} strokeWidth={2} strokeDasharray="10 8" />
      <text x={836} y={CY(5) - 10} textAnchor="end" fontFamily={F.sans} fontSize={22} fontWeight={700} fill={C.uyari}>
        Uyarı · 5 K
      </text>
      <path d={linePath(dtPts)} fill="none" stroke={C.muted} strokeWidth={3} strokeDasharray="9 7" />
      <path d={linePath(thetaPts)} fill="none" stroke={C.olcum} strokeWidth={5} strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r={8} fill={C.olcum} />
      <circle cx={last[0]} cy={last[1]} r={16} fill={C.olcum} opacity={0.2} />
    </svg>
  );
};

/* ---------------- sadeleşenler ---------------- */
const CANCELS: { t: string; at: number }[] = [
  { t: "Ortam · mevsim · güneş", at: 152 },
  { t: "Yük (I²)", at: 228 },
  { t: "Yayıcılık (IR)", at: 466 },
  { t: "Geçmiş gerekmez", at: 482 },
];

export const S05Theta: React.FC = () => {
  const frame = useCurrentFrame();
  const m = model(frame);
  const sev = severity(m.theta);

  const hlNum = interpolate(frame, [95, 105, 160, 170], [0, 1, 1, 0], CLAMP);
  const hlDen = Math.max(
    interpolate(frame, [172, 182, 236, 246], [0, 1, 1, 0], CLAMP),
    interpolate(frame, [355, 365, 450, 460], [0, 1, 1, 0], CLAMP),
  );

  return (
    <AbsoluteFill>
      <Backdrop accent={C.olcum} second={C.brand} />
      <SceneHeader kicker="02 · Fikir" title="Kardeşine göre *fark*." />

      {/* formül */}
      <div
        style={{
          position: "absolute",
          left: 120,
          top: 246,
          display: "flex",
          alignItems: "baseline",
          gap: 22,
          fontFamily: F.math,
          fontSize: 58,
          color: C.ink,
          ...fadeUp(frame, 34, { blur: 8 }),
        }}
      >
        <span style={{ fontStyle: "italic", color: C.olcum, fontWeight: 600 }}>
          θ<sub style={{ fontSize: "0.55em" }}>i</sub>
        </span>
        <span>=</span>
        <span
          style={{
            padding: "0 14px",
            borderRadius: 12,
            background: `rgba(247,131,32,${0.22 * hlNum})`,
            boxShadow: `0 0 0 2px rgba(247,131,32,${0.8 * hlNum})`,
          }}
        >
          [ <i>T</i>
          <sub style={{ fontSize: "0.55em" }}>i</sub> − medyan(<i>T</i>
          <sub style={{ fontSize: "0.55em" }}>kardeşler</sub>) ]
        </span>
        <span>/</span>
        <span
          style={{
            padding: "0 14px",
            borderRadius: 12,
            background: `rgba(74,163,255,${0.22 * hlDen})`,
            boxShadow: `0 0 0 2px rgba(74,163,255,${0.8 * hlDen})`,
          }}
        >
          (<i>I</i> / <i>I</i>
          <sub style={{ fontSize: "0.55em" }}>ref</sub>)²
        </span>
        <span style={{ fontFamily: F.mono, fontSize: 24, color: C.dim, marginLeft: 10 }}>[anma akımında kelvin]</span>
      </div>

      {/* sadeleşenler */}
      <div
        style={{
          position: "absolute",
          left: 120,
          top: 336,
          display: "flex",
          alignItems: "center",
          gap: 14,
          ...fadeUp(frame, 50),
        }}
      >
        <span style={{ fontFamily: F.mono, fontSize: 22, color: C.dim, letterSpacing: "0.12em", marginRight: 6 }}>
          SADELEŞENLER
        </span>
        {CANCELS.map((c) => {
          const on = prog(frame, c.at, 14);
          return (
            <span
              key={c.t}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 10,
                padding: "8px 18px",
                borderRadius: 999,
                fontFamily: F.sans,
                fontSize: 24,
                fontWeight: 700,
                color: on > 0.5 ? C.ok : C.dim,
                background: `rgba(53,192,122,${0.14 * on})`,
                border: `1.5px solid ${on > 0.5 ? C.ok : C.line2}`,
                scale: String(1 + 0.12 * Math.sin(on * Math.PI)),
              }}
            >
              <Icon name="check" size={22} color={on > 0.5 ? C.ok : C.line2} stroke={3} />
              {c.t}
            </span>
          );
        })}
      </div>

      {/* sol: üç faz */}
      <div style={{ position: "absolute", left: 120, top: 410, ...fadeUp(frame, 56) }}>
        <Card style={{ width: 760, height: 484, padding: "24px 30px" }}>
          <div style={{ display: "flex", gap: 22 }}>
            <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 14 }}>
              <Icon name="sun" size={40} color={m.amb > 30 ? C.kritik : C.muted} />
              <div>
                <div style={{ fontFamily: F.sans, fontSize: 22, color: C.dim }}>Ortam</div>
                <div style={{ fontFamily: F.mono, fontSize: 32, fontWeight: 700, color: C.ink }}>{tr(m.amb)} °C</div>
              </div>
            </div>
            <div style={{ flex: 1.3, display: "flex", alignItems: "center", gap: 14 }}>
              <Icon name="bolt" size={40} color={C.izle} />
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: F.sans, fontSize: 22, color: C.dim }}>
                  Yük · <i>f</i> = <i>I</i>/<i>I</i>
                  <sub>ref</sub>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                  <span style={{ fontFamily: F.mono, fontSize: 32, fontWeight: 700, color: C.ink }}>{tr(m.f, 2)}</span>
                  <div style={{ flex: 1, height: 12, borderRadius: 6, background: C.line }}>
                    <div
                      style={{
                        width: `${m.f * 100}%`,
                        height: "100%",
                        borderRadius: 6,
                        background: `linear-gradient(90deg, ${C.izle}, #9fd0ff)`,
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div style={{ marginTop: 14 }}>
            <Bars frame={frame} />
          </div>
        </Card>
      </div>

      {/* sağ üst: θ okuması */}
      <div style={{ position: "absolute", left: 920, top: 410, ...fadeUp(frame, 64) }}>
        <Card glow={m.theta > 2 ? sev.color : undefined} style={{ width: 880, height: 186, padding: "22px 34px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ fontFamily: F.sans, fontSize: 24, color: C.muted }}>
                <Theta /> · Çıkış 7 · L2
              </div>
              <div
                style={{
                  fontFamily: F.mono,
                  fontSize: 104,
                  fontWeight: 700,
                  lineHeight: 1.05,
                  color: m.theta > 2 ? C.olcum : C.ink,
                  textShadow: m.theta > 2 ? `0 0 30px ${C.olcum}66` : "none",
                }}
              >
                {tr(Math.abs(m.theta) < 0.005 ? 0 : m.theta, 2)} K
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 14, paddingTop: 6 }}>
              <Level name={sev.name} color={sev.color} size={26} />
              <div style={{ fontFamily: F.mono, fontSize: 26, color: C.muted }}>ham ΔT = {tr(m.dT, 2)} K</div>
            </div>
          </div>
        </Card>
      </div>

      {/* sağ alt: zaman içinde θ ve ham fark */}
      <div style={{ position: "absolute", left: 920, top: 614, ...fadeUp(frame, 72) }}>
        <Card style={{ width: 880, height: 280, padding: "12px 10px 0 0" }}>
          <div
            style={{
              position: "absolute",
              right: 30,
              top: 14,
              display: "flex",
              gap: 26,
              fontFamily: F.sans,
              fontSize: 22,
              color: C.muted,
            }}
          >
            <span>
              <span style={{ color: C.olcum, fontWeight: 800 }}>━</span> <Theta />
            </span>
            <span>
              <span style={{ color: C.muted }}>╍</span> ham fark
            </span>
          </div>
          <Chart frame={frame} />
        </Card>
      </div>

      <Narration
        lines={[
          {
            from: 40,
            to: 92,
            text: (
              <>
                Bir bağlantının sıcaklığı, eksi <Em>kardeşlerinin medyanı</Em>, anma akımına normalize.
              </>
            ),
          },
          {
            from: 96,
            to: 168,
            text: (
              <>
                Sıcak hava dalgası: üç faz birden <Em>+6,1 K</Em>. Sabit eşik alarm verirdi — <Theta /> kıpırdamıyor.
              </>
            ),
          },
          {
            from: 172,
            to: 246,
            text: (
              <>
                Yük artıyor: Joule ısısı üç fazda da <Em color={C.izle}>I²</Em> ile artar. Paydadaki I² bunu sadeleştirir.
              </>
            ),
          },
          {
            from: 250,
            to: 346,
            text: (
              <>
                Şimdi yalnız L2 ısınıyor — gevşek bağlantı budur. <Theta /> = <Em color={C.olcum}>6,35 K</Em> →{" "}
                <Em color={C.uyari}>UYARI</Em>
              </>
            ),
          },
          {
            from: 350,
            to: 456,
            text: (
              <>
                Yük düşse de artsa da: <Em color={C.muted}>ham fark değişir</Em>, <Theta />{" "}
                <Em color={C.olcum}>değişmez</Em>. Ölçtüğümüz şey bağlantının kendisi.
              </>
            ),
          },
          {
            from: 460,
            to: 538,
            text: (
              <>
                Geçmiş gerekmez: montaj günü üç kardeş zaten birbirinin referansı.
              </>
            ),
          },
        ]}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          background: `radial-gradient(600px 400px at 40% 75%, ${C.olcum}10, transparent 70%)`,
          opacity: interpolate(frame, [250, 320], [0, 1], { ...CLAMP, easing: EASE_OUT }),
        }}
      />
    </AbsoluteFill>
  );
};
