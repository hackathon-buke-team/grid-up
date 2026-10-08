import React, { useMemo } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { evolvePath } from "@remotion/paths";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Card, Em, Level } from "../ui/primitives";
import { fadeUp, popIn, prog, pulse } from "../ui/motion";
import { C, CLAMP, EASE_IN_OUT, EASE_OUT, F, Pt, sc, smoothPath } from "../theme";

/* 4 · SABİT EŞİK NEDEN ÇALIŞMAZ
   Şubat 09:00 %35 yükte 62 °C kusurludur; ağustos 15:00 %95 yükte aynı 62 °C normaldir.
   Eşik ağustosa göre kurulur → kasımdan nisana kusurlu pabuç eşiğin altında: kör bölge.
   Grafik şematiktir (fiziği anlatan çizim), ölçüm değildir. */

/* ---------------- termometre ---------------- */
const Thermo: React.FC<{ level: number; color: string }> = ({ level, color }) => {
  const top = 18;
  const bot = 222;
  const lvl = bot - (level / 100) * (bot - top);
  return (
    <svg width={112} height={270} viewBox="0 0 112 270">
      <rect x={30} y={8} width={28} height={232} rx={14} fill="#0b1018" stroke={C.line2} strokeWidth={2} />
      {[0, 20, 40, 60, 80, 100].map((t) => {
        const y = bot - (t / 100) * (bot - top);
        return (
          <g key={t}>
            <line x1={62} x2={72} y1={y} y2={y} stroke={C.dim} strokeWidth={1.5} />
            <text x={75} y={y + 5} fontFamily={F.mono} fontSize={13} fill={C.dim}>
              {t}
            </text>
          </g>
        );
      })}
      <rect x={37} y={lvl} width={14} height={bot - lvl + 20} rx={7} fill={color} />
      <circle cx={44} cy={244} r={21} fill={color} />
      <circle cx={44} cy={244} r={30} fill={color} opacity={0.15} />
    </svg>
  );
};

const ThermoCard: React.FC<{
  frame: number;
  start: number;
  when: string;
  load: string;
  color: string;
  verdict: string;
  top: number;
}> = ({ frame, start, when, load, color, verdict, top }) => {
  const fill = interpolate(frame, [start + 10, start + 50], [0, 62], { ...CLAMP, easing: EASE_OUT });
  return (
    <div style={{ position: "absolute", left: 120, top, ...fadeUp(frame, start, { dist: 40, blur: 6 }) }}>
      <Card glow={fill > 61 ? color : undefined} style={{ width: 520, height: 262, padding: "4px 28px", display: "flex", alignItems: "center", gap: 26 }}>
        <Thermo level={fill} color={color} />
        <div>
          <div style={{ fontFamily: F.sans, fontSize: 28, fontWeight: 700, color: C.ink }}>{when}</div>
          <div style={{ fontFamily: F.sans, fontSize: 26, color: C.muted, marginTop: 2 }}>{load}</div>
          <div style={{ fontFamily: F.mono, fontSize: 76, fontWeight: 700, color: C.ink, lineHeight: 1.1, marginTop: 6 }}>
            {Math.round(fill)}
            <span style={{ fontFamily: F.sans, fontSize: 52, fontWeight: 700, color: C.muted, marginLeft: 10 }}>°C</span>
          </div>
          <div style={{ marginTop: 8, ...popIn(frame, start + 54) }}>
            <Level name={verdict} color={color} size={24} />
          </div>
        </div>
      </Card>
    </div>
  );
};

/* ---------------- yıl grafiği ---------------- */
const CW = 1080;
const XM = sc(0, 11, 90, 1050);
const YT = sc(20, 100, 440, 40);
const healthy = (m: number) => 49 + 13 * Math.cos((2 * Math.PI * (m - 7)) / 12);
const faulty = (m: number) => healthy(m) + 26;
const THRESH = 72;
const MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

const CHART_IN = 112;
const HEALTHY_DRAW = [126, 190] as const;
const FAULTY_DRAW = [142, 206] as const;
const THRESH_IN = 206;
const DOTS_IN = 222;
const BLIND_IN = 248;

const YearChart: React.FC<{ frame: number }> = ({ frame }) => {
  const paths = useMemo(() => {
    const p = (fn: (m: number) => number) => {
      const pts: Pt[] = [];
      for (let m = 0; m <= 11.001; m += 0.25) pts.push([XM(m), YT(fn(m))]);
      return smoothPath(pts);
    };
    return { h: p(healthy), f: p(faulty) };
  }, []);

  const hp = interpolate(frame, [...HEALTHY_DRAW], [0.0001, 1], { ...CLAMP, easing: EASE_IN_OUT });
  const fp = interpolate(frame, [...FAULTY_DRAW], [0.0001, 1], { ...CLAMP, easing: EASE_IN_OUT });
  const hEv = evolvePath(hp, paths.h);
  const fEv = evolvePath(fp, paths.f);
  const th = prog(frame, THRESH_IN, 22);
  const blind = prog(frame, BLIND_IN, 30);
  const dots = prog(frame, DOTS_IN, 16);
  const pz = pulse(frame, 34);

  /* kusurlu eğri eşiğin altında: m ≤ 3.45 ve m ≥ 10.55 */
  const B1 = 3.45;
  const B2 = 10.55;

  return (
    <svg width={CW} height={500} style={{ overflow: "visible" }}>
      <defs>
        <clipPath id="se-blind">
          <rect x={XM(0)} y={0} width={XM(B1) - XM(0)} height={500} />
          <rect x={XM(B2)} y={0} width={XM(11) - XM(B2) + 1} height={500} />
        </clipPath>
      </defs>
      {[20, 40, 60, 80, 100].map((t) => (
        <g key={t}>
          <line x1={XM(0)} x2={XM(11)} y1={YT(t)} y2={YT(t)} stroke={C.line} strokeWidth={1.5} />
          <text x={XM(0) - 14} y={YT(t) + 8} textAnchor="end" fontFamily={F.mono} fontSize={22} fill={C.dim}>
            {t}
          </text>
        </g>
      ))}
      {MONTHS.map((a, m) => (
        <text
          key={a}
          x={XM(m)}
          y={478}
          textAnchor="middle"
          fontFamily={F.sans}
          fontSize={22}
          fontWeight={m === 1 || m === 7 ? 800 : 400}
          fill={m === 1 || m === 7 ? C.ink : C.dim}
        >
          {a}
        </text>
      ))}

      {/* kör bölge */}
      <g opacity={blind}>
        <rect x={XM(0)} y={YT(100)} width={(XM(B1) - XM(0)) * blind} height={YT(20) - YT(100)} fill={C.kritik} opacity={0.13} />
        <rect
          x={XM(B2)}
          y={YT(100)}
          width={(XM(11) - XM(B2) + 1) * blind}
          height={YT(20) - YT(100)}
          fill={C.kritik}
          opacity={0.13}
        />
        <text x={XM(1.72)} y={YT(100) + 34} textAnchor="middle" fontFamily={F.sans} fontSize={28} fontWeight={800} fill={C.kritik}>
          kör bölge
        </text>
        <text x={XM(10.78)} y={YT(100) + 34} textAnchor="middle" fontFamily={F.sans} fontSize={24} fontWeight={800} fill={C.kritik}>
          kör
        </text>
      </g>

      <path
        d={paths.h}
        fill="none"
        stroke={C.ok}
        strokeWidth={5}
        strokeLinecap="round"
        strokeDasharray={hEv.strokeDasharray}
        strokeDashoffset={hEv.strokeDashoffset}
      />
      <path
        d={paths.f}
        fill="none"
        stroke={C.kritik}
        strokeWidth={5}
        strokeLinecap="round"
        strokeDasharray={fEv.strokeDasharray}
        strokeDashoffset={fEv.strokeDashoffset}
      />
      {/* kör bölgedeki kusurlu eğri vurgusu */}
      <path d={paths.f} fill="none" stroke={C.kritik} strokeWidth={14} opacity={0.35 * blind * (0.6 + 0.4 * pz)} clipPath="url(#se-blind)" />

      <text x={XM(9.2)} y={YT(healthy(9.2)) + 60} textAnchor="middle" fontFamily={F.sans} fontSize={24} fontWeight={700} fill={C.ok} opacity={prog(frame, 180, 16)}>
        sağlam pabuç
      </text>
      <text x={XM(7)} y={YT(faulty(7)) - 18} textAnchor="middle" fontFamily={F.sans} fontSize={24} fontWeight={700} fill={C.kritik} opacity={prog(frame, 196, 16)}>
        kusurlu pabuç
      </text>

      {/* sabit eşik */}
      <line
        x1={XM(0)}
        x2={XM(0) + (XM(11) - XM(0)) * th}
        y1={YT(THRESH)}
        y2={YT(THRESH)}
        stroke={C.uyari}
        strokeWidth={3}
        strokeDasharray="12 9"
      />
      <g opacity={prog(frame, THRESH_IN + 14, 14)}>
        <rect x={XM(0.15)} y={YT(THRESH) - 46} width={248} height={36} rx={18} fill={C.bg} />
        <text x={XM(0.15) + 124} y={YT(THRESH) - 19} textAnchor="middle" fontFamily={F.sans} fontSize={24} fontWeight={800} fill={C.uyari}>
          sabit eşik 72 °C
        </text>
      </g>

      {/* aynı 62 °C, iki hüküm */}
      <g opacity={dots}>
        <circle cx={XM(1)} cy={YT(62)} r={9 + 3 * dots} fill={C.kritik} />
        <circle cx={XM(1)} cy={YT(62)} r={20 + pz * 12} fill="none" stroke={C.kritik} strokeWidth={2} opacity={1 - pz} />
        <text x={XM(1) + 22} y={YT(62) - 12} fontFamily={F.mono} fontSize={24} fontWeight={700} fill={C.ink}>
          62 °C
        </text>
        <circle cx={XM(7)} cy={YT(62)} r={9 + 3 * dots} fill={C.ok} />
        <text x={XM(7)} y={YT(62) + 40} textAnchor="middle" fontFamily={F.mono} fontSize={24} fontWeight={700} fill={C.ink}>
          62 °C
        </text>
      </g>
    </svg>
  );
};

export const S04SabitEsik: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Backdrop accent={C.uyari} second={C.kritik} />
      <SceneHeader kicker="01 · Problem" title="Aynı *62°C*, iki ayrı hüküm." />

      <ThermoCard
        frame={frame}
        start={22}
        when="Şubat · 09:00"
        load="yük %35"
        color={C.kritik}
        verdict="Kusurlu"
        top={330}
      />
      <ThermoCard
        frame={frame}
        start={34}
        when="Ağustos · 15:00"
        load="yük %95"
        color={C.ok}
        verdict="Normal"
        top={622}
      />

      <div style={{ position: "absolute", left: 680, top: 330, ...fadeUp(frame, CHART_IN, { dist: 30, blur: 8 }) }}>
        <Card style={{ width: 1120, height: 554, padding: "22px 20px 0 10px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "0 14px 0 24px" }}>
            <div style={{ fontFamily: F.sans, fontSize: 26, fontWeight: 700, color: C.ink }}>
              Bir yıl · aynı pano · aynı pabuç sırası
            </div>
            <div style={{ fontFamily: F.mono, fontSize: 20, color: C.dim }}>°C · şematik çizim</div>
          </div>
          <YearChart frame={frame} />
        </Card>
      </div>

      <Narration
        lines={[
          {
            from: 24,
            to: 112,
            text: (
              <>
                Şubat sabahı %35 yükte 62 °C: <Em color={C.kritik}>kusurlu</Em>. Ağustos, tam yükte aynı 62 °C:{" "}
                <Em color={C.ok}>normal</Em>.
              </>
            ),
          },
          {
            from: 116,
            to: 240,
            text: <>Sıcaklığı durum değil, yük ve mevsim belirler: eşik ağustosa göre kurulmak zorunda.</>,
          },
          {
            from: 246,
            to: 386,
            text: (
              <>
                Kasımdan nisana kusurlu pabuç eşiğin altında: yılın yarısında sistem <Em color={C.kritik}>kör</Em>.
              </>
            ),
          },
        ]}
      />
    </AbsoluteFill>
  );
};
