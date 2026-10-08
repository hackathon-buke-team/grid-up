import React, { useMemo } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { evolvePath, getLength, getPointAtLength } from "@remotion/paths";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Em, Icon, IconName } from "../ui/primitives";
import { fadeUp, popIn, prog, pulse } from "../ui/motion";
import { C, CLAMP, EASE_OUT, F } from "../theme";

/* 6 · DONANIM: 9 CİHAZLIK KİT
   Bir modül = bir enstrümante pano = 9 cihaz. Kural: delik yok, tip testli parça değişmez,
   bara bölmesine girilmez. Kelepçeler → termal dizi → PD-01 → ağ geçidi; kırmızı halka Ç7 L2. */

/* ---- pano şeması koordinatları (sunum/src/slides-a.js panelSVG ile aynı) ---- */
const PY = (y: number) => 1500 - y;
const pcx = (k: number) => 72 + k * 105;
const POFF = [-30, -10, 10, 30];
const CAB = [C.l1, "#3a3f47", C.l3, "#7cc4ff"];

const SCH_LEFT = 120;
const SCH_TOP = 324;
const SCH_H = 576;
const S = SCH_H / 1540;
const SCH_W = 1640 * S;
const sx = (x: number) => SCH_LEFT + (x + 20) * S;
const sy = (y: number) => SCH_TOP + (y + 20) * S;

const GX = 1450;
const GY = PY(980) + 10;

/* ---- zamanlama ---- */
const RULE_IN = 22;
const TC_IN = 72;
const IR_IN = 140;
const PD_IN = 196;
const GW_IN = 244;
const RING_IN = 300;

const RF_SRC: [number, number][] = [
  [pcx(5), PY(430)],
  [pcx(6), PY(430)],
  [640, PY(150)],
  [1290, PY(230)],
];

const Schematic: React.FC<{ frame: number }> = ({ frame }) => {
  const rf = useMemo(
    () =>
      RF_SRC.map(([x, y]) => {
        const d = `M${x},${y} Q${(x + GX) / 2 + 120},${(y + GY) / 2 + 60} ${GX},${GY + 36}`;
        return { d, len: getLength(d) };
      }),
    [],
  );
  const rs1 = `M${GX},${GY - 36} V200`;
  const rs2 = `M${GX - 40},${GY - 36} V335`;

  const tcIn = (i: number) => popIn(frame, TC_IN + i * 4, 18);
  const fov = prog(frame, IR_IN + 6, 26);
  const irIn = prog(frame, IR_IN, 14);
  const pdIn = prog(frame, PD_IN, 16);
  const gwIn = prog(frame, GW_IN, 16);
  const rfDraw = interpolate(frame, [GW_IN + 10, GW_IN + 40], [0.0001, 1], { ...CLAMP, easing: EASE_OUT });
  const rsDraw = interpolate(frame, [GW_IN + 16, GW_IN + 44], [0.0001, 1], { ...CLAMP, easing: EASE_OUT });
  const noEntry = pulse(frame, 40);
  const ring = prog(frame, RING_IN, 14);
  const rp = (frame % 36) / 36;

  return (
    <svg
      viewBox="-20 -20 1640 1540"
      width={SCH_W}
      height={SCH_H}
      style={{ position: "absolute", left: SCH_LEFT, top: SCH_TOP, overflow: "visible" }}
    >
      <defs>
        <pattern id="dn-h" width="26" height="26" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="26" stroke="#1f2933" strokeWidth="9" />
        </pattern>
        <linearGradient id="dn-fov" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor={C.brand} stopOpacity=".42" />
          <stop offset="1" stopColor={C.brand} stopOpacity=".03" />
        </linearGradient>
      </defs>

      <rect x="0" y="0" width="1600" height="1500" rx="14" fill="#090d13" stroke="#55707f" strokeWidth="5" />
      {/* çatı */}
      <rect x="0" y="0" width="1600" height="60" fill="#0f151d" stroke="#2f4149" strokeWidth="3" />
      {[485, 610, 735, 860].map((x, j) => (
        <rect key={x} x={x - 24} y="6" width="48" height="50" rx="5" fill={CAB[j]} opacity=".75" />
      ))}
      {/* bara bölmesi — girilmez */}
      <rect x="0" y="60" width="1300" height="340" fill="url(#dn-h)" stroke="#2f4149" strokeWidth="3" />
      {[0, 1, 2, 3].map((j) => (
        <rect key={j} x="40" y={115 + j * 70} width="1220" height={j === 3 ? 22 : 30} rx="4" fill={CAB[j]} opacity=".55" />
      ))}
      <g opacity={prog(frame, RULE_IN + 10, 16)}>
        <rect
          x="250"
          y="160"
          width="800"
          height="150"
          rx="16"
          fill="rgba(6,8,12,.92)"
          stroke={C.kritik}
          strokeWidth={4 + noEntry * 4}
        />
        <text x="650" y="230" textAnchor="middle" fontFamily={F.sans} fontSize="58" fontWeight="800" fill={C.kritik}>
          Bara bölmesi: girilmez
        </text>
        <text x="650" y="282" textAnchor="middle" fontFamily={F.sans} fontSize="34" fill={C.muted}>
          AG giriş kesicisi yok
        </text>
      </g>

      {/* fider bölmesi */}
      <rect x="0" y="400" width="1300" height="400" fill="#0b1118" stroke="#2f4149" strokeWidth="3" />
      {Array.from({ length: 12 }, (_, k) => {
        const spare = k >= 10;
        return (
          <g key={k}>
            <rect
              x={pcx(k) - 42}
              y="420"
              width="84"
              height="360"
              rx="6"
              fill={spare ? "url(#dn-h)" : "#121a24"}
              stroke="#415a68"
              strokeWidth="3"
            />
            <text x={pcx(k)} y={spare ? 610 : 770} textAnchor="middle" fontFamily={F.sans} fontSize="30" fill={C.dim}>
              {spare ? "Y" + (k - 9) : "Ç" + (k + 1)}
            </text>
            {!spare
              ? [-24, 0, 24].map((o) => (
                  <rect key={o} x={pcx(k) + o - 8} y="470" width="16" height="240" rx="6" fill="#1a2430" stroke="#2f4149" strokeWidth="2" />
                ))
              : null}
          </g>
        );
      })}

      {/* ölçü kolonu */}
      <rect x="1300" y="60" width="300" height="740" fill="#0d131b" stroke="#2f4149" strokeWidth="3" />
      {(
        [
          [80, 200, "TVOC-2 ark rölesi"],
          [215, 335, "MPR-53CS analizör"],
          [350, 440, "Sayaç"],
          [455, 600, "Modem bölmesi"],
          [615, 790, "10 A priz"],
        ] as [number, number, string][]
      ).map(([a, b, t], i) => (
        <g key={t}>
          <rect
            x="1316"
            y={a}
            width="268"
            height={b - a}
            rx="8"
            fill="#121a24"
            stroke={i < 2 && rsDraw > 0.9 ? C.brand2 : "#415a68"}
            strokeWidth="3"
          />
          <text
            x="1450"
            y={i === 3 ? a + 34 : (a + b) / 2 + 11}
            textAnchor="middle"
            fontFamily={F.sans}
            fontSize="28"
            fill={C.muted}
          >
            {t}
          </text>
        </g>
      ))}

      {/* alt kablo bölmesi */}
      <rect x="0" y="800" width="1600" height="700" fill="#080c11" stroke="#2f4149" strokeWidth="3" />
      <text x="24" y="852" fontFamily={F.sans} fontSize="32" fill={C.dim}>
        alt kablo bölmesi
      </text>
      {Array.from({ length: 12 }, (_, k) =>
        POFF.map((o, j) => {
          const x = pcx(k) + o;
          if (k >= 10) {
            return (
              <circle key={`${k}${j}`} cx={x} cy={PY(500)} r="9" fill="none" stroke="#33414f" strokeWidth="3" strokeDasharray="4 4" />
            );
          }
          return (
            <g key={`${k}${j}`}>
              <line x1={x} y1={PY(500) + 10} x2={x} y2="1500" stroke={CAB[j]} strokeWidth="9" />
              <circle cx={x} cy={PY(500)} r="11" fill="#cfd6de" stroke="#0b0f14" strokeWidth="3" />
            </g>
          );
        }),
      )}
      {/* PE barası */}
      <line x1="80" x2="1540" y1={PY(230)} y2={PY(230)} stroke="#35c07a" strokeWidth="16" />
      <line x1="80" x2="1540" y1={PY(230)} y2={PY(230)} stroke="#f4d13a" strokeWidth="16" strokeDasharray="30 30" />

      {/* 1 · altı ısıl kelepçe */}
      {[5, 6].map((k, ki) =>
        [0, 1, 2].map((j) => {
          const st = tcIn(ki * 3 + j);
          return (
            <rect
              key={`${k}${j}`}
              x={pcx(k) + POFF[j] - 13}
              y={PY(430) - 26}
              width="26"
              height="52"
              rx="6"
              fill={C.brand}
              stroke="#fff6"
              strokeWidth="2"
              opacity={st.opacity as number}
              style={{ scale: st.scale, transformBox: "fill-box", transformOrigin: "center" }}
            />
          );
        }),
      )}

      {/* 2 · termal dizi + görüş konisi */}
      <g opacity={irIn}>
        <polygon
          points={`640,${PY(160)} ${640 - 500 * fov},${PY(160) - (PY(160) - PY(500)) * fov} ${640 + 500 * fov},${PY(160) - (PY(160) - PY(500)) * fov}`}
          fill="url(#dn-fov)"
        />
        <rect x="600" y={PY(150) - 18} width="80" height="36" rx="7" fill="#1c2632" stroke={C.brand} strokeWidth="5" />
      </g>

      {/* 3 · PD-01 */}
      <g opacity={pdIn}>
        <circle cx="1290" cy={PY(230)} r={34 * (0.5 + 0.5 * pdIn)} fill="#1c2632" stroke={C.brand} strokeWidth="6" />
        <circle cx="1290" cy={PY(230)} r="10" fill={C.brand} />
        <circle cx="1290" cy={PY(230)} r={40 + rp * 60} fill="none" stroke={C.brand} strokeWidth="3" opacity={(1 - rp) * pdIn} />
      </g>

      {/* 4 · ağ geçidi, radyo ve RS-485 */}
      {rf.map((r, i) => {
        const ev = evolvePath(rfDraw, r.d);
        const t = ((frame * 9 + i * 160) % r.len) / r.len;
        const p = getPointAtLength(r.d, t * r.len) ?? { x: GX, y: GY };
        return (
          <g key={i} opacity={gwIn}>
            <path
              d={r.d}
              fill="none"
              stroke={C.izle}
              strokeWidth="5"
              strokeDasharray={ev.strokeDasharray}
              strokeDashoffset={ev.strokeDashoffset}
              opacity={0.7}
            />
            {rfDraw >= 1 ? <circle cx={p.x} cy={p.y} r="12" fill={C.izle} /> : null}
          </g>
        );
      })}
      {[rs1, rs2].map((d, i) => {
        const ev = evolvePath(rsDraw, d);
        return (
          <path
            key={i}
            d={d}
            fill="none"
            stroke={C.brand2}
            strokeWidth="7"
            strokeDasharray={i === 1 && rsDraw >= 1 ? "16 10" : ev.strokeDasharray}
            strokeDashoffset={i === 1 && rsDraw >= 1 ? -frame * 2 : ev.strokeDashoffset}
            opacity={gwIn}
          />
        );
      })}
      <g opacity={gwIn}>
        <rect x={GX - 74} y={GY - 28} width="148" height="64" rx="9" fill="#1c2632" stroke={C.brand} strokeWidth="6" />
        <text x={GX} y={GY + 14} textAnchor="middle" fontFamily={F.sans} fontSize="32" fontWeight="800" fill={C.brand}>
          GW-01
        </text>
        <path d={`M${GX + 70},${GY - 20} h60 v-60`} stroke={C.brand} strokeWidth="5" fill="none" />
        <circle cx={GX + 130} cy={GY - 86} r="8" fill={C.brand} />
        {[0, 1, 2].map((w) => {
          const q = ((frame + w * 12) % 36) / 36;
          return (
            <circle
              key={w}
              cx={GX + 130}
              cy={GY - 86}
              r={14 + q * 54}
              fill="none"
              stroke={C.izle}
              strokeWidth="4"
              opacity={(1 - q) * prog(frame, GW_IN + 20, 12)}
            />
          );
        })}
      </g>

      {/* Ç7 L2 */}
      <g opacity={ring}>
        <circle cx={pcx(6) - 10} cy={PY(500)} r="26" fill="none" stroke={C.kritik} strokeWidth="6" />
        <circle
          cx={pcx(6) - 10}
          cy={PY(500)}
          r={30 + rp * 50}
          fill="none"
          stroke={C.kritik}
          strokeWidth="5"
          opacity={1 - rp}
        />
      </g>
    </svg>
  );
};

/* ---- şema üzerindeki etiketler ---- */
const Tag: React.FC<{ x: number; y: number; at: number; frame: number; color?: string; children: React.ReactNode }> = ({
  x,
  y,
  at,
  frame,
  color = C.brand,
  children,
}) => (
  <div
    style={{
      position: "absolute",
      left: sx(x),
      top: sy(y),
      padding: "5px 14px",
      borderRadius: 10,
      background: "rgba(6,8,12,.92)",
      border: `2px solid ${color}`,
      fontFamily: F.sans,
      fontSize: 22,
      fontWeight: 800,
      color,
      whiteSpace: "nowrap",
      ...fadeUp(frame, at, { dist: 14, dur: 14 }),
    }}
  >
    {children}
  </div>
);

/* ---- sağ sütun ---- */
const RULES: { t: string; icon: IconName }[] = [
  { t: "Delik delinmez", icon: "x" },
  { t: "Tip testli parça değişmez", icon: "lock" },
  { t: "Bara bölmesine girilmez", icon: "shield" },
];

const DEVICES: { n: number; at: number; t: string; s: string; icon: IconName }[] = [
  {
    n: 6,
    at: TC_IN,
    t: "TC ısıl kelepçe · Ç6 ve Ç7",
    s: "TMP117 ±0,1 °C + kendi split-core CT'si · iki üçlü = iki kardeş kümesi",
    icon: "therm",
  },
  {
    n: 1,
    at: IR_IN,
    t: "TN-IR termal dizi",
    s: "32×24, 110° lens, mıknatıs kaide · kalan 34 pabucu yukarıdan görür",
    icon: "camera",
  },
  {
    n: 1,
    at: PD_IN,
    t: "PD-01 RF ve ortam düğümü",
    s: "M12 topraklama saplaması · HFCT yalnız PE'ye · nem",
    icon: "wave",
  },
  {
    n: 1,
    at: GW_IN,
    t: "GW-01 ağ geçidi",
    s: "Ölçü kolonu, DIN ray, 10 A priz · TVOC-2 ve MPR-53CS'i RS-485 ile okur",
    icon: "antenna",
  },
];

const COL_X = 800;
const COL_W = 1000;

export const S06Donanim: React.FC = () => {
  const frame = useCurrentFrame();

  const count = frame < TC_IN ? 0 : frame < IR_IN ? 6 : frame < PD_IN ? 7 : frame < GW_IN ? 8 : 9;
  const filled = (i: number) => {
    if (i < 6) return prog(frame, TC_IN + i * 4, 10);
    if (i === 6) return prog(frame, IR_IN, 10);
    if (i === 7) return prog(frame, PD_IN, 10);
    return prog(frame, GW_IN, 10);
  };
  const lastChange = count === 6 ? TC_IN : count === 7 ? IR_IN : count === 8 ? PD_IN : count === 9 ? GW_IN : -100;
  const bump = interpolate(frame, [lastChange, lastChange + 6, lastChange + 16], [1, 1.25, 1], CLAMP);

  return (
    <AbsoluteFill>
      <Backdrop accent={C.brand} second={C.izle} />
      <SceneHeader kicker="03 · Donanım" title="Bir modül = bir pano = *9* cihaz." />

      <div style={{ ...fadeUp(frame, 14, { dist: 20, blur: 6 }), position: "absolute", inset: 0 }}>
        <Schematic frame={frame} />
      </div>

      <Tag x={790} y={PY(430) - 30} at={TC_IN + 16} frame={frame}>
        6 × TC
      </Tag>
      <Tag x={720} y={PY(150) - 20} at={IR_IN + 12} frame={frame}>
        TN-IR
      </Tag>
      <Tag x={1070} y={PY(230) + 50} at={PD_IN + 12} frame={frame}>
        PD-01
      </Tag>
      <Tag x={740} y={850} at={RING_IN + 8} frame={frame} color={C.kritik}>
        Ç7 · L2
      </Tag>

      {/* kurallar */}
      <div style={{ position: "absolute", left: COL_X, top: 326, display: "flex", gap: 12 }}>
        {RULES.map((r, i) => (
          <div
            key={r.t}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "9px 18px",
              borderRadius: 999,
              fontFamily: F.sans,
              fontSize: 24,
              fontWeight: 700,
              color: C.ink,
              background: "rgba(255,107,61,.10)",
              border: `1.5px solid ${C.kritik}88`,
              ...fadeUp(frame, RULE_IN + i * 6, { dist: 16 }),
            }}
          >
            <Icon name={r.icon} size={24} color={C.kritik} stroke={2.4} />
            {r.t}
          </div>
        ))}
      </div>

      {/* kit sayacı */}
      <div
        style={{
          position: "absolute",
          left: COL_X,
          top: 398,
          width: COL_W,
          display: "flex",
          alignItems: "center",
          gap: 18,
          ...fadeUp(frame, 40, { dist: 16 }),
        }}
      >
        <span style={{ fontFamily: F.mono, fontSize: 22, letterSpacing: "0.14em", color: C.dim }}>KİT</span>
        <div style={{ display: "flex", gap: 8 }}>
          {Array.from({ length: 9 }, (_, i) => {
            const f = filled(i);
            return (
              <div
                key={i}
                style={{
                  width: 54,
                  height: 22,
                  borderRadius: 6,
                  border: `1.5px solid ${f > 0.5 ? C.brand : C.line2}`,
                  background: `rgba(247,131,32,${0.85 * f})`,
                  boxShadow: f > 0.5 ? `0 0 14px ${C.brand}66` : "none",
                }}
              />
            );
          })}
        </div>
        <span
          style={{
            fontFamily: F.mono,
            fontSize: 40,
            fontWeight: 700,
            color: count === 9 ? C.brand : C.ink,
            scale: String(bump),
            minWidth: 110,
          }}
        >
          {count}/9
        </span>
      </div>

      {/* cihaz satırları */}
      {DEVICES.map((d, i) => {
        const a = prog(frame, d.at, 18);
        const next = DEVICES[i + 1]?.at ?? RING_IN;
        const active = frame >= d.at && frame < next + 10 ? interpolate(frame, [d.at, d.at + 10, next, next + 10], [0, 1, 1, 0], CLAMP) : 0;
        return (
          <div
            key={d.t}
            style={{
              position: "absolute",
              left: COL_X,
              top: 456 + i * 112,
              width: COL_W,
              height: 100,
              display: "flex",
              alignItems: "center",
              gap: 22,
              padding: "0 24px",
              borderRadius: 18,
              background: `linear-gradient(180deg, ${C.panel2} 0%, ${C.panel} 100%)`,
              border: `1.5px solid ${active > 0.5 ? C.brand : C.line2}`,
              boxShadow: active > 0.5 ? `0 18px 50px -24px ${C.brand}aa` : "none",
              opacity: a,
              translate: `${(1 - a) * 40}px 0px`,
            }}
          >
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: 99,
                flexShrink: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: F.mono,
                fontSize: 34,
                fontWeight: 700,
                color: active > 0.5 ? C.bg : C.brand,
                background: active > 0.5 ? C.brand : C.brandSoft,
                border: `2px solid ${C.brand}`,
              }}
            >
              {d.n}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <Icon name={d.icon} size={28} color={C.brand2} />
                <span style={{ fontFamily: F.sans, fontSize: 30, fontWeight: 800, color: C.ink }}>{d.t}</span>
              </div>
              <div style={{ fontFamily: F.sans, fontSize: 22, lineHeight: 1.25, color: C.muted, marginTop: 4 }}>{d.s}</div>
            </div>
          </div>
        );
      })}

      <Narration
        lines={[
          {
            from: 22,
            to: 132,
            text: (
              <>
                Tek kural: delik yok, tip testli parça değişmez, <Em color={C.kritik}>bara bölmesine girilmez</Em>.
              </>
            ),
          },
          {
            from: 136,
            to: 240,
            text: (
              <>
                θ için kardeş gerekir: <Em>Ç6 ve Ç7'nin üç fazına</Em> kelepçe — kalan 34 pabucu termal dizi görür.
              </>
            ),
          },
          {
            from: 244,
            to: 356,
            text: (
              <>
                Ağ geçidi sensörleri <Em color={C.izle}>868 MHz</Em> ile, ark rölesi ve analizörü{" "}
                <Em>RS-485</Em> ile okur.
              </>
            ),
          },
        ]}
      />
    </AbsoluteFill>
  );
};
