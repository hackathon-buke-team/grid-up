import React, { useMemo } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { evolvePath, getLength, getPointAtLength } from "@remotion/paths";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Em } from "../ui/primitives";
import { prog, pulse } from "../ui/motion";
import { C, CLAMP, EASE_IN_OUT, EASE_OUT, F, Pt, smoothPath } from "../theme";

/* 3 · PROBLEM: ARIZA ÖNCE ISINIR
   Gevşeme → temas direnci → ısınma ↔ oksitlenme (kendini besleyen döngü) → ark, yangın, kesinti.
   Bugün sürecin sonunda fark ediliyor; PANO GÖZ başında görür. Aradaki fark: haftalar. */

const SVG_X = 120;
const SVG_Y = 360;
const W = 1680;
const BASE = 410;

const X = (t: number) => 70 + t * 1540;
const Y = (t: number) => BASE - (12 + 46 * t + 252 * Math.pow(t, 6)) * 1.08;

const STAGES: { t: number; a: string; b: string; c: string }[] = [
  { t: 0.08, a: "Cıvata gevşer", b: "temas direnci artar", c: C.izle },
  { t: 0.37, a: "Bağlantı ısınır", b: "birkaç kelvin, kimse görmez", c: C.uyari },
  { t: 0.65, a: "Oksitlenir", b: "direnç kendini besler", c: C.kritik },
  { t: 0.9, a: "Ark, yangın, kesinti", b: "artık herkes görür", c: C.acil },
];

const T_NOW = 0.93;
const T_PG = 0.24;

const DRAW0 = 26;
const DRAW1 = 130;
const FAIL = 150;
const PG = 206;

export const S03Problem: React.FC = () => {
  const frame = useCurrentFrame();

  const d = useMemo(() => {
    const pts: Pt[] = [];
    for (let t = 0; t <= 1.0001; t += 0.02) pts.push([X(t), Y(t)]);
    return smoothPath(pts);
  }, []);
  const len = useMemo(() => getLength(d), [d]);

  const draw = interpolate(frame, [DRAW0, DRAW1], [0, 1], { ...CLAMP, easing: EASE_IN_OUT });
  const { strokeDasharray, strokeDashoffset } = evolvePath(Math.max(0.0001, draw), d);
  const head = getPointAtLength(d, Math.max(0.001, draw * len)) ?? { x: X(0), y: Y(0) };
  // eğrinin ucu hangi t'de? (x doğrusal)
  const tHead = (head.x - 70) / 1540;

  const failIn = prog(frame, FAIL, 18);
  const pgIn = prog(frame, PG, 18);
  const arrow = interpolate(frame, [PG + 14, PG + 50], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const band = prog(frame, PG + 30, 30);

  const loopSpin = frame * 4;
  const loopIn = prog(frame, 96, 18);

  return (
    <AbsoluteFill>
      <Backdrop accent={C.kritik} second={C.izle} />
      <SceneHeader
        kicker="01 · Problem"
        title="Arıza önce *ısınır*, sonra yanar."
        lead="Gevşek bir cıvata, nemli bir kablo kanalı, yıpranan bir yalıtım: hepsi kritik andan haftalar önce sinyal verir."
      />

      <svg
        width={W}
        height={560}
        style={{ position: "absolute", left: SVG_X, top: SVG_Y, overflow: "visible" }}
      >
        <defs>
          <linearGradient id="pb-fill" x1="0" x2="1">
            <stop offset="0" stopColor={C.izle} stopOpacity=".16" />
            <stop offset=".55" stopColor={C.uyari} stopOpacity=".18" />
            <stop offset="1" stopColor={C.acil} stopOpacity=".4" />
          </linearGradient>
          <linearGradient id="pb-stroke" x1="0" x2="1">
            <stop offset="0" stopColor={C.izle} />
            <stop offset=".55" stopColor={C.uyari} />
            <stop offset=".85" stopColor={C.kritik} />
            <stop offset="1" stopColor={C.acil} />
          </linearGradient>
          <marker id="pb-ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" fill={C.brand2} />
          </marker>
          <clipPath id="pb-clip">
            <rect x={0} y={0} width={head.x + 2} height={560} />
          </clipPath>
        </defs>

        {/* eksenler */}
        <line x1={70} y1={BASE} x2={1620} y2={BASE} stroke={C.line2} strokeWidth={2} opacity={prog(frame, 16, 16)} />
        <text x={1600} y={BASE - 14} textAnchor="end" fontFamily={F.mono} fontSize={22} fill={C.muted} opacity={prog(frame, 20, 16)}>
          zaman →
        </text>
        <text x={70} y={22} fontFamily={F.mono} fontSize={22} fill={C.dim} opacity={prog(frame, 20, 16)}>
          bağlantı sıcaklığı
        </text>

        {/* PANO GÖZ ile bugün arasındaki pencere */}
        <rect
          x={X(T_PG)}
          y={40}
          width={(X(T_NOW) - X(T_PG)) * band}
          height={BASE - 40}
          fill={C.brand}
          opacity={0.06}
        />

        {/* eğri altı dolgu */}
        <path d={`${d} L${X(1)},${BASE} L${X(0)},${BASE} Z`} fill="url(#pb-fill)" clipPath="url(#pb-clip)" />
        <path
          d={d}
          fill="none"
          stroke="url(#pb-stroke)"
          strokeWidth={6}
          strokeLinecap="round"
          strokeDasharray={strokeDasharray}
          strokeDashoffset={strokeDashoffset}
        />
        {draw > 0 && draw < 1 ? (
          <g>
            <circle cx={head.x} cy={head.y} r={16} fill={C.olcum} opacity={0.25} />
            <circle cx={head.x} cy={head.y} r={7} fill={C.olcum} />
          </g>
        ) : null}

        {/* aşamalar */}
        {STAGES.map((s) => {
          const reached = tHead >= s.t - 0.005 || draw >= 1;
          const at = DRAW0 + (DRAW1 - DRAW0) * s.t * 0.9;
          const a = reached ? prog(frame, at, 14) : 0;
          return (
            <g key={s.a} opacity={a}>
              <line x1={X(s.t)} x2={X(s.t)} y1={Y(s.t) + 10} y2={BASE} stroke={s.c} strokeWidth={1.5} strokeDasharray="3 6" opacity={0.6} />
              <circle cx={X(s.t)} cy={Y(s.t)} r={10 + 4 * a} fill={C.bg} stroke={s.c} strokeWidth={4} />
              <text
                x={X(s.t)}
                y={BASE + 52 - (1 - a) * 12}
                textAnchor="middle"
                fontFamily={F.sans}
                fontSize={30}
                fontWeight={700}
                fill={C.ink}
              >
                {s.a}
              </text>
              <text x={X(s.t)} y={BASE + 88} textAnchor="middle" fontFamily={F.sans} fontSize={24} fill={C.muted}>
                {s.b}
              </text>
            </g>
          );
        })}

        {/* kendini besleyen döngü: ısınma ↔ oksitlenme */}
        <g opacity={loopIn} transform={`translate(${X(0.65) - 150} ${Y(0.65) - 50})`}>
          <g transform={`rotate(${loopSpin} 0 0)`}>
            <circle r={34} fill="none" stroke={C.kritik} strokeWidth={3} strokeDasharray="40 14" />
            <path d="M34,0 l-8,-10 l16,0 z" fill={C.kritik} />
            <path d="M-34,0 l-8,10 l16,0 z" fill={C.kritik} />
          </g>
          <text x={0} y={-50} textAnchor="middle" fontFamily={F.sans} fontSize={22} fontWeight={700} fill={C.kritik}>
            ısınma ↔ oksitlenme
          </text>
        </g>

        {/* bugün fark edilen an */}
        <g opacity={failIn}>
          <line
            x1={X(T_NOW)}
            x2={X(T_NOW)}
            y1={40}
            y2={40 + (BASE - 40) * failIn}
            stroke={C.kritik}
            strokeWidth={3}
            strokeDasharray="8 8"
          />
          <g transform={`translate(${X(T_NOW) - 400} ${40 + (1 - failIn) * -16})`}>
            <rect width={384} height={86} rx={14} fill="rgba(255,107,61,.12)" stroke={C.kritik} strokeWidth={2} />
            <text x={22} y={38} fontFamily={F.sans} fontSize={28} fontWeight={800} fill={C.kritik}>
              Bugün fark edilen an
            </text>
            <text x={22} y={70} fontFamily={F.sans} fontSize={22} fill={C.muted}>
              ekipman arızası, kesinti, yangın
            </text>
          </g>
          <circle
            cx={X(T_NOW)}
            cy={Y(T_NOW)}
            r={14 + pulse(frame, 30) * 16}
            fill="none"
            stroke={C.acil}
            strokeWidth={3}
            opacity={1 - pulse(frame, 30) * 0.8}
          />
        </g>

        {/* PANO GÖZ'ün gördüğü an */}
        <g opacity={pgIn}>
          <line
            x1={X(T_PG)}
            x2={X(T_PG)}
            y1={40}
            y2={40 + (BASE - 40) * pgIn}
            stroke={C.brand}
            strokeWidth={3}
            strokeDasharray="8 8"
          />
          <g transform={`translate(${X(T_PG) + 16} ${40 + (1 - pgIn) * -16})`}>
            <rect width={404} height={86} rx={14} fill={C.brandSoft} stroke={C.brand} strokeWidth={2} />
            <text x={22} y={38} fontFamily={F.sans} fontSize={28} fontWeight={800} fill={C.brand}>
              PANO GÖZ'ün gördüğü an
            </text>
            <text x={22} y={70} fontFamily={F.sans} fontSize={22} fill={C.muted}>
              θ yükselir, CUSUM birikir
            </text>
          </g>
          <circle cx={X(T_PG)} cy={Y(T_PG)} r={12} fill={C.brand} />
          <circle cx={X(T_PG)} cy={Y(T_PG)} r={22 + pulse(frame, 36) * 10} fill={C.brand} opacity={0.18} />
        </g>

        {/* haftalar önce */}
        {arrow > 0 ? (
          <g>
            <line
              x1={X(T_NOW) - 8}
              x2={X(T_NOW) - 8 - (X(T_NOW) - X(T_PG) - 16) * arrow}
              y1={190}
              y2={190}
              stroke={C.brand2}
              strokeWidth={3}
              markerEnd="url(#pb-ar)"
            />
            <g opacity={prog(frame, PG + 40, 16)}>
              <rect x={(X(T_PG) + X(T_NOW)) / 2 - 120} y={168} width={240} height={46} rx={23} fill={C.bg} stroke={C.brand2} strokeWidth={2} />
              <text
                x={(X(T_PG) + X(T_NOW)) / 2}
                y={200}
                textAnchor="middle"
                fontFamily={F.sans}
                fontSize={28}
                fontWeight={800}
                fill={C.brand2}
              >
                haftalar önce
              </text>
            </g>
          </g>
        ) : null}
      </svg>

      <Narration
        lines={[
          {
            from: 30,
            to: 144,
            text: (
              <>
                Bağlantı gevşer, ısınır, oksitlenir — <Em color={C.kritik}>süreç kendini besler</Em>.
              </>
            ),
          },
          {
            from: 148,
            to: 202,
            text: <>Bugün bu süreç sonunda fark ediliyor: müşteri karanlıkta kaldığında.</>,
          },
          {
            from: 206,
            to: 326,
            text: (
              <>
                PANO GÖZ eğrinin başına bakar: <Em>haftalar</Em> — arıza ekibi yerine planlı bir tork iş emri.
              </>
            ),
          },
        ]}
      />
    </AbsoluteFill>
  );
};
