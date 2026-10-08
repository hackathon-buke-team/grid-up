import React, { useMemo } from "react";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Card, Em, Level, Theta } from "../ui/primitives";
import { prog } from "../ui/motion";
import { C, CLAMP, EASE_OUT, F, heat, rng, tr } from "../theme";

/* 1 · KAPAK
   Sağda EK-II/14 alt kablo bölmesi: 10 fider + 2 yedek, 48 pabuç. Termal göz soldan sağa
   geçer; pabuçların hepsi birbirine benzer — biri hariç: Çıkış 7, L2. */

const cx = (k: number) => 52 + k * 41;
const LY = 232;
const OFF = [-11, -4, 4, 11];
const CAB = [C.l1, "#3a3f47", C.l3, "#7cc4ff"];
const HOT_X = cx(6) - 4;

/* svg (560×520) → ekran */
const SVG_LEFT = 1040;
const SVG_TOP = 150;
const SVG_W = 760;
const K = SVG_W / 560;

const Cabinet: React.FC<{ scan: number; found: number; frame: number }> = ({ scan, found, frame }) => {
  const lugs = useMemo(() => {
    const r = rng(7);
    const out: { x: number; j: number; k: number; t: number; hot: boolean }[] = [];
    for (let k = 0; k < 10; k++) {
      OFF.forEach((o, j) => {
        const hot = k === 6 && j === 1;
        const t = hot ? 1 : (j === 3 ? 0.4 : 0.5) + r() * 0.1 + (k === 5 || k === 6 ? 0.06 : 0);
        out.push({ x: cx(k) + o, j, k, t, hot });
      });
    }
    return out;
  }, []);
  const bodyHeat = useMemo(() => {
    const r = rng(11);
    return Array.from({ length: 10 }, () => 0.24 + r() * 0.05);
  }, []);

  const scanX = scan * 560;
  const ring = (frame % 40) / 40;

  return (
    <svg viewBox="0 0 560 520" width={SVG_W} height={520 * K} style={{ overflow: "visible" }}>
      <defs>
        <pattern id="cv-h" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="7" stroke="#26313d" strokeWidth="2" />
        </pattern>
        <filter id="cv-b" x="-2" y="-2" width="5" height="5">
          <feGaussianBlur stdDeviation="3.6" />
        </filter>
        <linearGradient id="cv-fov" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor={C.brand} stopOpacity=".22" />
          <stop offset="1" stopColor={C.brand} stopOpacity="0" />
        </linearGradient>
        <radialGradient id="cv-bg" cx={HOT_X / 560} cy={LY / 520} r=".9">
          <stop offset="0" stopColor="#3b0d5e" />
          <stop offset=".5" stopColor="#1a0838" />
          <stop offset="1" stopColor="#0a0418" />
        </radialGradient>
        <clipPath id="cv-clip">
          <rect x="0" y="0" width={scanX} height="520" />
        </clipPath>
      </defs>

      <rect x="14" y="20" width="532" height="486" rx="12" fill="#080b10" stroke={C.line2} />

      {/* fiderler ve kablolar */}
      {Array.from({ length: 12 }, (_, k) => {
        const x = cx(k);
        const spare = k >= 10;
        const a = interpolate(frame, [8 + k * 2.5, 26 + k * 2.5], [0, 1], CLAMP);
        return (
          <g key={k} opacity={a}>
            <text x={x} y="62" textAnchor="middle" fontFamily={F.mono} fontSize="10" fill={C.dim}>
              {spare ? "Y" + (k - 9) : "Ç" + (k + 1)}
            </text>
            {spare ? (
              <rect x={x - 15} y="70" width="30" height="126" rx="3" fill="url(#cv-h)" stroke={C.line2} />
            ) : (
              <>
                <rect x={x - 15} y="70" width="30" height="126" rx="3" fill="#0d131b" stroke="#33414f" />
                <rect x={x - 11} y="76" width="22" height="10" rx="2" fill="#1a2330" />
                {[-9, -2, 5].map((o) => (
                  <rect key={o} x={x + o} y="98" width="5" height="72" rx="2" fill="#18212c" stroke="#2c3a48" />
                ))}
                {OFF.map((o, j) => (
                  <g key={j}>
                    <line x1={x + o} y1={LY + 4} x2={x + o} y2="470" stroke={CAB[j]} strokeWidth="3.2" />
                    <circle cx={x + o} cy={LY} r="3.4" fill="#cfd6de" stroke="#0b0f14" />
                  </g>
                ))}
              </>
            )}
          </g>
        );
      })}

      {/* Ç6 ve Ç7 üç fazındaki ısıl kelepçeler */}
      {[5, 6].map((k) =>
        [0, 1, 2].map((j) => (
          <rect
            key={`${k}${j}`}
            x={cx(k) + OFF[j] - 3.5}
            y="268"
            width="7"
            height="15"
            rx="2"
            fill={C.brand}
            opacity={interpolate(frame, [40, 56], [0, 1], CLAMP)}
          />
        )),
      )}

      {/* termal dizinin görüş konisi */}
      <polygon points={`270,486 44,${LY} 500,${LY}`} fill="url(#cv-fov)" opacity={interpolate(frame, [44, 70], [0, 1], CLAMP)} />
      <rect x="252" y="484" width="36" height="14" rx="3" fill="#1c2632" stroke={C.brand} />
      <text x="296" y="495" fontFamily={F.mono} fontSize="9.5" fill={C.muted}>
        TN-IR 32×24
      </text>

      {/* termal katman — tarama çizgisiyle açılır */}
      <g clipPath="url(#cv-clip)">
        <rect x="15" y="21" width="530" height="484" rx="12" fill="url(#cv-bg)" />
        {Array.from({ length: 10 }, (_, k) => (
          <g key={k}>
            <rect x={cx(k) - 15} y="70" width="30" height="126" rx="3" fill={heat(bodyHeat[k])} />
            {[-9, -2, 5].map((o) => (
              <rect key={o} x={cx(k) + o} y="98" width="5" height="72" rx="2" fill={heat(bodyHeat[k] + 0.1)} />
            ))}
          </g>
        ))}
        {lugs.map((l, i) => (
          <g key={i}>
            <line
              x1={l.x}
              y1={LY}
              x2={l.x}
              y2="470"
              stroke={heat(l.t * (l.hot ? 0.8 : 0.62))}
              strokeWidth={l.hot ? 7 : 5}
              strokeOpacity=".75"
              filter="url(#cv-b)"
            />
            <line
              x1={l.x}
              y1={LY}
              x2={l.x}
              y2={LY + (l.hot ? 110 : 40)}
              stroke={heat(l.t * 0.9)}
              strokeWidth={l.hot ? 5 : 3}
              strokeLinecap="round"
            />
            <circle cx={l.x} cy={LY} r={l.hot ? 24 : 10} fill={heat(l.t)} filter="url(#cv-b)" />
            <circle cx={l.x} cy={LY} r={l.hot ? 6 : 3.8} fill={l.hot ? "#fffbd0" : heat(Math.min(1, l.t + 0.14))} />
          </g>
        ))}
      </g>

      {/* tarama çizgisi */}
      {scan > 0 && scan < 1 ? (
        <g>
          <rect x={scanX - 40} y="21" width="40" height="484" fill={heat(0.85, 0.12)} />
          <line x1={scanX} y1="21" x2={scanX} y2="505" stroke={heat(0.95)} strokeWidth="2.5" />
          <line x1={scanX} y1="21" x2={scanX} y2="505" stroke={heat(0.85, 0.6)} strokeWidth="9" filter="url(#cv-b)" />
        </g>
      ) : null}

      {/* bulunan pabuç */}
      {found > 0 ? (
        <g opacity={found}>
          <circle cx={HOT_X} cy={LY} r={14 + ring * 30} fill="none" stroke={C.olcum} strokeWidth="2" opacity={1 - ring} />
          <circle cx={HOT_X} cy={LY} r="13" fill="none" stroke={C.olcum} strokeWidth="2.4" />
        </g>
      ) : null}
    </svg>
  );
};

export const S01Kapak: React.FC = () => {
  const frame = useCurrentFrame();

  const scan = interpolate(frame, [70, 165], [0, 1], { ...CLAMP, easing: Easing.inOut(Easing.cubic) });
  const found = prog(frame, 150, 14);
  const theta = interpolate(frame, [176, 226], [0, 17.6], { ...CLAMP, easing: EASE_OUT });

  return (
    <AbsoluteFill>
      <Backdrop accent={C.brand} second="#6a1fb0" />

      {/* kabin + kamera itmesi */}
      <div
        style={{
          position: "absolute",
          left: SVG_LEFT,
          top: SVG_TOP,
          transformOrigin: `${HOT_X * K}px ${LY * K}px`,
          opacity: interpolate(frame, [4, 30], [0, 1], CLAMP),
          scale: interpolate(frame, [0, 60, 170, 300], [0.94, 1, 1, 1.07], {
            ...CLAMP,
            easing: [EASE_OUT, Easing.linear, Easing.inOut(Easing.quad)],
          }),
        }}
      >
        <Cabinet scan={scan} found={found} frame={frame} />
      </div>
      <div
        style={{
          position: "absolute",
          left: SVG_LEFT + 14 * K,
          top: SVG_TOP - 34,
          fontFamily: F.mono,
          fontSize: 22,
          color: C.dim,
          opacity: interpolate(frame, [20, 40], [0, 1], CLAMP),
        }}
      >
        EK-II/14 · alt kablo bölmesi · 48 pabuç
      </div>

      {/* bulgu kartı */}
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
        <line
          x1={SVG_LEFT + HOT_X * K}
          y1={SVG_TOP + LY * K + 22}
          x2={SVG_LEFT + HOT_X * K}
          y2={SVG_TOP + LY * K + 22 + interpolate(frame, [160, 180], [0, 110], { ...CLAMP, easing: EASE_OUT })}
          stroke={C.olcum}
          strokeWidth={2}
          opacity={found}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          left: SVG_LEFT + HOT_X * K - 200,
          top: SVG_TOP + LY * K + 136,
          opacity: interpolate(frame, [172, 190], [0, 1], CLAMP),
          translate: `0px ${interpolate(frame, [172, 194], [24, 0], { ...CLAMP, easing: EASE_OUT })}px`,
        }}
      >
        <Card glow={C.kritik} style={{ padding: "24px 30px", width: 470 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontFamily: F.mono, fontSize: 28, color: C.muted }}>Çıkış 7 · L2</div>
            <Level name="Kritik" color={C.kritik} size={20} />
          </div>
          <div style={{ fontFamily: F.mono, fontSize: 66, fontWeight: 700, color: C.olcum, marginTop: 8 }}>
            <Theta /> = {tr(theta)} K
          </div>
          <div style={{ fontFamily: F.sans, fontSize: 26, color: C.muted, marginTop: 4 }}>
            ACİL'e <Em color={C.acil}>~15 gün</Em> (13–19)
          </div>
        </Card>
      </div>

      {/* sol sütun */}
      <div style={{ position: "absolute", left: 120, top: 110, display: "flex", alignItems: "center", gap: 28 }}>
        <Img
          src={staticFile("logo-gridup-dark.png")}
          style={{
            height: 128,
            opacity: interpolate(frame, [6, 24], [0, 1], CLAMP),
            scale: interpolate(frame, [6, 30], [0.85, 1], { ...CLAMP, easing: EASE_OUT }),
          }}
        />
        <div
          style={{
            opacity: interpolate(frame, [14, 32], [0, 1], CLAMP),
            translate: `${interpolate(frame, [14, 34], [-24, 0], { ...CLAMP, easing: EASE_OUT })}px 0px`,
          }}
        >
          <div style={{ fontFamily: F.mono, fontSize: 26, letterSpacing: "0.2em", color: C.brand }}>
            GRID UP HACKATHON · FİNAL
          </div>
          <div style={{ fontFamily: F.sans, fontSize: 28, color: C.muted, marginTop: 8 }}>ADM & GDZ Elektrik</div>
        </div>
      </div>

      <div style={{ position: "absolute", left: 112, top: 360 }}>
        <div
          style={{
            fontFamily: F.sans,
            fontWeight: 900,
            fontSize: 160,
            letterSpacing: "-0.035em",
            lineHeight: 0.95,
            color: C.ink,
            whiteSpace: "nowrap",
          }}
        >
          {"PANO GÖZ".split("").map((ch, i) => {
            const s = 22 + i * 3;
            const p = interpolate(frame, [s, s + 22], [0, 1], { ...CLAMP, easing: EASE_OUT });
            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  width: ch === " " ? "0.28em" : undefined,
                  opacity: p,
                  translate: `0px ${(1 - p) * 90}px`,
                  filter: `blur(${(1 - p) * 14}px)`,
                  color: i >= 5 ? C.brand : undefined,
                }}
              >
                {ch}
              </span>
            );
          })}
        </div>
        <div
          style={{
            marginTop: 26,
            fontFamily: F.sans,
            fontSize: 44,
            fontWeight: 500,
            color: C.ink,
            maxWidth: 780,
            lineHeight: 1.2,
            opacity: interpolate(frame, [52, 72], [0, 1], CLAMP),
            translate: `0px ${interpolate(frame, [52, 76], [20, 0], { ...CLAMP, easing: EASE_OUT })}px`,
          }}
        >
          Pano / hücre içi anomali <span style={{ color: C.brand2 }}>erken uyarı</span> sistemi
        </div>
        <div
          style={{
            marginTop: 18,
            fontFamily: F.mono,
            fontSize: 26,
            color: C.dim,
            opacity: interpolate(frame, [64, 84], [0, 1], CLAMP),
          }}
        >
          1600 kVA TEDAŞ AG dağıtım panosu · Takım Büke
        </div>
      </div>

      {/* imza cümlesi */}
      <div
        style={{
          position: "absolute",
          left: 120,
          bottom: 120,
          fontFamily: F.sans,
          fontSize: 46,
          fontWeight: 700,
          color: C.ink,
          maxWidth: 820,
          lineHeight: 1.2,
          opacity: interpolate(frame, [215, 240], [0, 1], CLAMP),
          translate: `0px ${interpolate(frame, [215, 244], [26, 0], { ...CLAMP, easing: EASE_OUT })}px`,
        }}
      >
        Sıcaklığa değil, <span style={{ color: C.olcum }}>kardeşine göre farka</span> bakıyoruz.
      </div>
      <div
        style={{
          position: "absolute",
          left: 120,
          bottom: 92,
          height: 4,
          borderRadius: 2,
          background: `linear-gradient(90deg, ${C.olcum}, transparent)`,
          width: interpolate(frame, [230, 270], [0, 560], { ...CLAMP, easing: EASE_OUT }),
        }}
      />
    </AbsoluteFill>
  );
};
