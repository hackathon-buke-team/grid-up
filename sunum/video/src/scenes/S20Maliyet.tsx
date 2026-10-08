import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Card, Em } from "../ui/primitives";
import { countUp, fadeSide, fadeUp, prog, pulse } from "../ui/motion";
import { C, CLAMP, EASE_IN_OUT, F, sc, tr } from "../theme";

/* 20 · MALİYET VE FAYDA
   Önce kötü haber: 100 modül her panoya eşit dağıtılırsa 5 yılda geri ödemez.
   Sonra aynı 100 modül filonun en kötü onda birine: 2,2 yılda geri öder.
   Sayılar sunum/src/slides-c.js costSVG ve docs/07 ile aynıdır. */

const CAPEX = 109.591; // k€
const NET_UNI = 15.885; // k€ / yıl, tekdüze
const NET_DEC = 50.54; // k€ / yıl, en kötü ondalık

const X = sc(0, 5, 110, 950);
const Y = sc(-120, 160, 492, 44);

const RED = { start: 50, dur: 96 };
const GREEN = { start: 166, dur: 90 };

const Line: React.FC<{
  net: number;
  color: string;
  p: number;
  opacity: number;
  frame: number;
  glow: number;
}> = ({ net, color, p, opacity, frame, glow }) => {
  const tEnd = 5 * p;
  const v = (t: number) => -CAPEX + net * t;
  const x0 = X(0);
  const x1 = X(tEnd);
  const area = `M${x0},${Y(0)} L${x0},${Y(v(0))} L${x1},${Y(v(tEnd))} L${x1},${Y(0)} Z`;
  return (
    <g opacity={opacity}>
      <path d={area} fill={color} opacity={0.1} />
      <line
        x1={x0}
        y1={Y(v(0))}
        x2={x1}
        y2={Y(v(tEnd))}
        stroke={color}
        strokeWidth={5}
        strokeLinecap="round"
        style={{ filter: `drop-shadow(0 0 ${6 + glow * 14 * pulse(frame, 30)}px ${color})` }}
      />
      {[0, 1, 2, 3, 4, 5].map((t) =>
        t <= tEnd + 0.001 ? <circle key={t} cx={X(t)} cy={Y(v(t))} r={6} fill={C.bg} stroke={color} strokeWidth={3} /> : null,
      )}
      {p > 0 && p < 1 ? (
        <>
          <circle cx={x1} cy={Y(v(tEnd))} r={9} fill={color} />
          <circle cx={x1} cy={Y(v(tEnd))} r={20} fill={color} opacity={0.22} />
        </>
      ) : null}
    </g>
  );
};

const Chart: React.FC<{ frame: number }> = ({ frame }) => {
  const pr = interpolate(frame, [RED.start, RED.start + RED.dur], [0, 1], { ...CLAMP, easing: EASE_IN_OUT });
  const pg = interpolate(frame, [GREEN.start, GREEN.start + GREEN.dur], [0, 1], { ...CLAMP, easing: EASE_IN_OUT });
  const axes = prog(frame, 26, 24);
  const redDim = interpolate(frame, [GREEN.start, GREEN.start + 30], [1, 0.5], CLAMP);
  const endGlow = interpolate(frame, [344, 364], [0, 1], CLAMP);

  /* geri ödeme noktası (yeşil çizgi sıfırı keser) */
  const tPay = CAPEX / NET_DEC; // ≈ 2,17 yıl
  const payAt = GREEN.start + 42;
  const pay = prog(frame, payAt, 16);

  return (
    <svg width={980} height={540} viewBox="0 0 980 540" style={{ overflow: "visible" }}>
      <g opacity={axes}>
        {[-100, -50, 0, 50, 100, 150].map((v) => (
          <g key={v}>
            <line
              x1={X(0)}
              x2={X(5)}
              y1={Y(v)}
              y2={Y(v)}
              stroke={v === 0 ? C.muted : C.line}
              strokeWidth={v === 0 ? 2.5 : 1.5}
            />
            <text x={X(0) - 16} y={Y(v) + 8} textAnchor="end" fontFamily={F.mono} fontSize={22} fill={C.dim}>
              {v > 0 ? "+" : v < 0 ? "−" : ""}
              {Math.abs(v)}k€
            </text>
          </g>
        ))}
        {[0, 1, 2, 3, 4, 5].map((t) => (
          <text key={t} x={X(t)} y={528} textAnchor="middle" fontFamily={F.mono} fontSize={22} fill={C.dim}>
            {t}. yıl
          </text>
        ))}
        <text x={X(0)} y={16} fontFamily={F.sans} fontSize={22} fill={C.dim}>
          kümülatif net nakit · 100 modül
        </text>
      </g>

      <Line net={NET_UNI} color={C.kritik} p={pr} opacity={redDim} frame={frame} glow={0} />
      <Line net={NET_DEC} color={C.ok} p={pg} opacity={1} frame={frame} glow={endGlow} />

      {/* kırmızı uç etiketi */}
      <g opacity={prog(frame, RED.start + RED.dur - 4, 16) * redDim}>
        <text
          x={X(5) - 14}
          y={Y(-CAPEX + NET_UNI * 5) + 92}
          textAnchor="end"
          fontFamily={F.sans}
          fontSize={26}
          fontWeight={800}
          fill={C.kritik}
        >
          tekdüze dağıtım: −€30 166
        </text>
      </g>

      {/* geri ödeme halkası */}
      <g opacity={pay}>
        <circle cx={X(tPay)} cy={Y(0)} r={12 + 10 * (1 - pay)} fill="none" stroke={C.ok} strokeWidth={3} />
        <circle
          cx={X(tPay)}
          cy={Y(0)}
          r={12 + 26 * ((frame % 36) / 36)}
          fill="none"
          stroke={C.ok}
          strokeWidth={2}
          opacity={(1 - (frame % 36) / 36) * 0.7}
        />
        <text x={X(tPay) + 24} y={Y(0) + 40} fontFamily={F.sans} fontSize={26} fontWeight={800} fill={C.ok}>
          2,2 yılda geri öder
        </text>
      </g>

      {/* yeşil uç etiketi */}
      <g opacity={prog(frame, GREEN.start + GREEN.dur - 4, 16)}>
        <text
          x={X(5) - 18}
          y={Y(-CAPEX + NET_DEC * 5) - 6}
          textAnchor="end"
          fontFamily={F.sans}
          fontSize={26}
          fontWeight={800}
          fill={C.ok}
        >
          en kötü %10: +€143 109
        </text>
      </g>
    </svg>
  );
};

const Kpi: React.FC<{
  value: string;
  unit?: string;
  color: string;
  label: React.ReactNode;
  at: number;
  frame: number;
  hot: number;
}> = ({ value, unit, color, label, at, frame, hot }) => (
  <div style={{ ...fadeSide(frame, at, 50, 22) }}>
    <Card
      glow={hot > 0.3 ? color : undefined}
      style={{ height: 124, padding: "0 26px", display: "flex", alignItems: "center", gap: 24 }}
    >
      <div
        style={{
          width: 200,
          flexShrink: 0,
          fontFamily: F.mono,
          fontSize: 58,
          fontWeight: 700,
          color,
          textShadow: `0 0 ${20 * hot}px ${color}`,
          whiteSpace: "nowrap",
        }}
      >
        {value}
        {unit ? <span style={{ fontSize: 28, marginLeft: 8 }}>{unit}</span> : null}
      </div>
      <div style={{ fontFamily: F.sans, fontSize: 22, lineHeight: 1.3, color: C.muted }}>{label}</div>
    </Card>
  </div>
);

const win = (frame: number, a: number, b: number) => interpolate(frame, [a, a + 10, b - 10, b], [0, 1, 1, 0], CLAMP);

export const S20Maliyet: React.FC = () => {
  const frame = useCurrentFrame();

  const k1 = countUp(frame, 112, 30, 0, 6.9);
  const k2 = countUp(frame, 214, 30, 0, 2.2);
  const k3 = countUp(frame, 268, 30, 0, 3.3);
  const k4 = countUp(frame, 290, 34, 0, 43.5);

  return (
    <AbsoluteFill>
      <Backdrop accent={C.kritik} second={C.ok} />
      <SceneHeader kicker="11 · Maliyet" title="Önce *kötü* *haber.*" accent={C.kritik} />

      <div style={{ position: "absolute", left: 120, top: 290, ...fadeUp(frame, 18, { blur: 8 }) }}>
        <Card style={{ position: "relative", width: 1020, height: 600, padding: "26px 20px 20px 10px" }}>
          <Chart frame={frame} />
          {/* kapanış cümlesi */}
          <div
            style={{
              position: "absolute",
              left: 140,
              top: 74,
              fontFamily: F.sans,
              fontSize: 44,
              fontWeight: 800,
              lineHeight: 1.12,
              color: C.ink,
              maxWidth: 520,
              ...fadeUp(frame, 346, { dist: 24, blur: 8 }),
            }}
          >
            Soru kaç pano değil,
            <br />
            <span style={{ color: C.ok }}>hangi panolar.</span>
          </div>
        </Card>
      </div>

      <div
        style={{
          position: "absolute",
          left: 1180,
          top: 290,
          width: 620,
          display: "flex",
          flexDirection: "column",
          gap: 18,
        }}
      >
        <Kpi
          frame={frame}
          at={104}
          value={tr(k1)}
          unit="yıl"
          color={C.kritik}
          hot={win(frame, 112, 160)}
          label={<>100 pano, her panoya eşit: 5 yılda geri ödemez · başa baş 175 pano</>}
        />
        <Kpi
          frame={frame}
          at={206}
          value={tr(k2)}
          unit="yıl"
          color={C.ok}
          hot={win(frame, 214, 266)}
          label={<>Aynı 100 modül, filonun en kötü %10'una konursa</>}
        />
        <Kpi
          frame={frame}
          at={260}
          value={tr(k3)}
          unit="yıl"
          color={C.izle}
          hot={win(frame, 268, 300)}
          label={<>1000 pano tekdüze: öğrenme eğrisi donanımı %28,8 ucuzlatır</>}
        />
        <Kpi
          frame={frame}
          at={282}
          value={`%${tr(k4)}`}
          color={C.brand}
          hot={win(frame, 292, 344)}
          label={<>fayda tespit oranından bağımsız · termografi €130 → €21,7 / pano / yıl</>}
        />
      </div>

      <Narration
        lines={[
          {
            from: 22,
            to: 152,
            text: (
              <>
                Her panoya eşit dağıtılmış 100 modül, 5 yılda parasını geri ödemez:{" "}
                <Em color={C.kritik}>−€30 166</Em>.
              </>
            ),
          },
          {
            from: 158,
            to: 262,
            text: (
              <>
                Aynı 100 modül filonun <Em color={C.ok}>en kötü %10'una</Em>: 2,2 yılda geri öder, beş yılda +€143 109.
              </>
            ),
          },
          {
            from: 266,
            to: 340,
            text: (
              <>
                Faydanın <Em>%43,5</Em>'i hiçbir kusur bulunmasa bile gerçekleşir: termografi ziyaretleri seyrelir.
              </>
            ),
          },
          {
            from: 344,
            to: 418,
            text: <>O panoları dağıtım şirketi zaten biliyor: arıza kaydı, yaş, yük faktörü, son termografi.</>,
          },
        ]}
      />
    </AbsoluteFill>
  );
};
