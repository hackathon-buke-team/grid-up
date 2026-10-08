import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Em, Icon, IconName, Theta } from "../ui/primitives";
import { countUp, fadeUp, prog } from "../ui/motion";
import { C, CLAMP, F, tr } from "../theme";

/* 7 · ELEKTRONİK VE FİRMWARE
   Dört kart: 6 ısıl kelepçe, 1 termal dizi, 1 RF/ortam düğümü, 1 ağ geçidi.
   Sensör düğümleri STM32WLE5 (MCU + 868 MHz aynı yongada); ağ geçidi STM32H563.
   Firmware C99: float yok, malloc yok; enerjisiz ve pil zayıf birinci sınıf durum. */

type Board = { code: string; n: number; title: string; icon: IconName; rows: React.ReactNode[] };

const BOARDS: Board[] = [
  {
    code: "PANOGOZ-TC-A1",
    n: 6,
    title: "Isıl kelepçe",
    icon: "therm",
    rows: ["STM32WLE5CC · 868 MHz", "TMP117 ±0,1 °C, ısıl ada", "Split-core CT 3000:1 (400 A)", "ER14250 + HLC1550 pil"],
  },
  {
    code: "PANOGOZ-IR-A1",
    n: 1,
    title: "Termal dizi",
    icon: "camera",
    rows: ["MLX90640 32×24, 110° lens", "SHT41 bölme havası ve nem", "Nişan kilidi: 3 referans vida", "ER14505 Li-SOCl₂"],
  },
  {
    code: "PANOGOZ-PD-A1",
    n: 1,
    title: "RF ve ortam",
    icon: "wave",
    rows: ["HFCT yalnız PE · 1–3 MHz", "TEV plakası + 40 kHz alıcı", "SHT41 · çiy noktası payı", "pC eşdeğeri; IEC 60270 değil"],
  },
  {
    code: "PANOGOZ-GW-A1",
    n: 1,
    title: "Ağ geçidi",
    icon: "antenna",
    rows: ["STM32H563 · SX1262 · LTE", "2 × izole RS-485", "20 000 çerçeve tampon", "2 × 10 F süperkap: 8 sn son nefes"],
  },
];

/* spot ışığı pencereleri */
const SPOT_SENSOR: [number, number] = [56, 138];
const SPOT_GW: [number, number] = [138, 214];
const SPOT_FW: [number, number] = [214, 300];

const win = (frame: number, [a, b]: [number, number]) =>
  interpolate(frame, [a, a + 10, b - 6, b + 4], [0, 1, 1, 0], CLAMP);

const BW = 515;
const BH = 276;

const BoardCard: React.FC<{ b: Board; i: number; frame: number; spot: number; dim: number }> = ({
  b,
  i,
  frame,
  spot,
  dim,
}) => {
  const col = i % 2;
  const row = Math.floor(i / 2);
  const isGw = i === 3;
  const buf = Math.round(countUp(frame, SPOT_GW[0] + 6, 40, 0, 20000));
  const breath = isGw ? interpolate(frame, [SPOT_GW[0] + 30, SPOT_GW[0] + 70], [1, 0], CLAMP) : 1;
  return (
    <div
      style={{
        position: "absolute",
        left: 120 + col * (BW + 20),
        top: 324 + row * (BH + 20),
        width: BW,
        height: BH,
        padding: "20px 26px",
        borderRadius: 22,
        background: `linear-gradient(180deg, ${C.panel2} 0%, ${C.panel} 100%)`,
        border: `1.5px solid ${spot > 0.5 ? C.brand : C.line2}`,
        boxShadow:
          spot > 0.5
            ? `0 0 0 1px ${C.brand}33, 0 24px 60px -20px ${C.brand}77`
            : "0 24px 60px -24px rgba(0,0,0,.8)",
        ...fadeUp(frame, 18 + i * 8, { dist: 40, blur: 6 }),
        opacity: prog(frame, 18 + i * 8, 20) * (1 - 0.45 * dim),
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontFamily: F.mono, fontSize: 21, color: C.dim, letterSpacing: "0.04em" }}>{b.code}</span>
        <span
          style={{
            fontFamily: F.mono,
            fontSize: 22,
            fontWeight: 700,
            color: C.brand,
            padding: "3px 14px",
            borderRadius: 999,
            background: C.brandSoft,
            border: `1.5px solid ${C.brand}66`,
          }}
        >
          ×{b.n}
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 6 }}>
        <Icon name={b.icon} size={32} color={C.brand2} />
        <span style={{ fontFamily: F.sans, fontSize: 34, fontWeight: 800, color: C.ink }}>{b.title}</span>
      </div>
      <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
        {b.rows.map((r, k) => {
          const isBuf = isGw && k === 2;
          const isBreath = isGw && k === 3;
          return (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 12, fontFamily: F.sans, fontSize: 24, color: C.muted }}>
              <span style={{ width: 7, height: 7, borderRadius: 2, background: C.brand, flexShrink: 0 }} />
              {isBuf && frame >= SPOT_GW[0] ? (
                <span>
                  <span style={{ fontFamily: F.mono, fontWeight: 700, color: C.ink }}>{String(buf).replace(/\B(?=(\d{3})+(?!\d))/g, " ")}</span> çerçeve
                  tampon
                </span>
              ) : (
                <span>{r}</span>
              )}
              {isBreath && frame >= SPOT_GW[0] + 24 ? (
                <span style={{ marginLeft: "auto", width: 70, height: 12, borderRadius: 6, background: C.line, flexShrink: 0 }}>
                  <span
                    style={{
                      display: "block",
                      width: `${breath * 100}%`,
                      height: "100%",
                      borderRadius: 6,
                      background: breath > 0.3 ? C.ok : C.kritik,
                    }}
                  />
                </span>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

/* firmware döngüsü */
const LOOP = ["SAMPLE", "AGGREGATE", "TX", "SLEEP"];
const FwRing: React.FC<{ frame: number }> = ({ frame }) => {
  const cx = 150;
  const cy = 132;
  const r = 90;
  const a = ((frame * 2.4) % 360) - 90;
  const rad = (a * Math.PI) / 180;
  const active = Math.floor(((((a + 90 + 45) % 360) + 360) % 360) / 90);
  return (
    <svg width={310} height={250} style={{ overflow: "visible" }}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={C.line2} strokeWidth={2.5} strokeDasharray="5 8" />
      <circle cx={cx + r * Math.cos(rad)} cy={cy + r * Math.sin(rad)} r={9} fill={C.brand} />
      <circle cx={cx + r * Math.cos(rad)} cy={cy + r * Math.sin(rad)} r={18} fill={C.brand} opacity={0.2} />
      {LOOP.map((n, i) => {
        const ang = -Math.PI / 2 + (i * Math.PI) / 2;
        const x = cx + r * Math.cos(ang);
        const y = cy + r * Math.sin(ang);
        const on = i === active;
        const w = n.length * 11 + 26;
        return (
          <g key={n}>
            <rect x={x - w / 2} y={y - 17} width={w} height={34} rx={17} fill={on ? C.brand : C.panel} stroke={on ? C.brand : C.line2} strokeWidth={2} />
            <text x={x} y={y + 6} textAnchor="middle" fontFamily={F.mono} fontSize={17} fontWeight={700} fill={on ? C.bg : C.ink}>
              {n}
            </text>
          </g>
        );
      })}
      <g transform={`translate(${cx - 28} ${cy - 28})`}>
        <svg width={56} height={56} viewBox="0 0 24 24" fill="none" stroke={C.brand2} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
          <rect x="6" y="6" width="12" height="12" rx="1.5" />
          <path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4" />
        </svg>
      </g>
    </svg>
  );
};

export const S07Elektronik: React.FC = () => {
  const frame = useCurrentFrame();

  const sSensor = win(frame, SPOT_SENSOR);
  const sGw = win(frame, SPOT_GW);
  const sFw = win(frame, SPOT_FW);
  const spots = [sSensor, sSensor, sSensor, sGw];
  const anySpot = Math.max(sSensor, sGw, sFw);

  const e1 = countUp(frame, 70, 50, 0, 470.59);
  const e2 = countUp(frame, 80, 50, 0, 660.91);

  return (
    <AbsoluteFill>
      <Backdrop accent={C.brand} second={C.izle} />
      <SceneHeader kicker="03 · Donanım" title="Dört kart, *tek* firmware." />

      {BOARDS.map((b, i) => (
        <BoardCard key={b.code} b={b} i={i} frame={frame} spot={spots[i]} dim={Math.max(0, anySpot - spots[i])} />
      ))}

      {/* firmware */}
      <div
        style={{
          position: "absolute",
          left: 1210,
          top: 324,
          width: 590,
          height: 330,
          padding: "16px 10px 0 14px",
          borderRadius: 22,
          background: `linear-gradient(180deg, ${C.panel2} 0%, ${C.panel} 100%)`,
          border: `1.5px solid ${sFw > 0.5 ? C.brand : C.line2}`,
          boxShadow: sFw > 0.5 ? `0 24px 60px -20px ${C.brand}77` : "0 24px 60px -24px rgba(0,0,0,.8)",
          ...fadeUp(frame, 50, { dist: 40, blur: 6 }),
          opacity: prog(frame, 50, 20) * (1 - 0.45 * Math.max(0, anySpot - sFw)),
        }}
      >
        <FwRing frame={frame} />
        <div style={{ position: "absolute", left: 336, top: 34, width: 240, display: "flex", flexDirection: "column", gap: 10 }}>
          <span style={{ fontFamily: F.mono, fontSize: 22, fontWeight: 700, color: C.brand2 }}>C99 · STM32WLE5</span>
          <span style={{ fontFamily: F.sans, fontSize: 26, fontWeight: 800, color: C.ink }}>float yok</span>
          <span style={{ fontFamily: F.sans, fontSize: 26, fontWeight: 800, color: C.ink }}>malloc yok</span>
          <span style={{ fontFamily: F.sans, fontSize: 22, color: C.muted, lineHeight: 1.25 }}>
            <Theta /> uçta, sabit noktada
          </span>
        </div>
        <div
          style={{
            position: "absolute",
            left: 22,
            bottom: 16,
            display: "flex",
            gap: 10,
            alignItems: "center",
            fontFamily: F.mono,
            fontSize: 18,
            color: C.uyari,
            opacity: prog(frame, SPOT_FW[0] + 20, 16),
          }}
        >
          <span style={{ padding: "4px 10px", borderRadius: 8, border: `1.5px solid ${C.uyari}88` }}>DE_ENERGISED</span>
          <span style={{ padding: "4px 10px", borderRadius: 8, border: `1.5px solid ${C.uyari}88` }}>LOW_BATTERY</span>
          <span style={{ fontFamily: F.sans, color: C.muted, fontSize: 19 }}>birinci sınıf durum</span>
        </div>
      </div>

      {/* modül maliyeti */}
      <div
        style={{
          position: "absolute",
          left: 1210,
          top: 674,
          width: 590,
          height: 222,
          padding: "20px 28px",
          borderRadius: 22,
          background: `linear-gradient(180deg, ${C.panel2} 0%, ${C.panel} 100%)`,
          border: `1.5px solid ${C.line2}`,
          ...fadeUp(frame, 62, { dist: 40, blur: 6 }),
          opacity: prog(frame, 62, 20),
        }}
      >
        <div style={{ fontFamily: F.mono, fontSize: 20, letterSpacing: "0.12em", color: C.dim }}>MODÜL DONANIMI</div>
        <div style={{ display: "flex", gap: 34, marginTop: 6 }}>
          <div>
            <div style={{ fontFamily: F.mono, fontSize: 48, fontWeight: 700, color: C.brand }}>€{tr(e1, 2)}</div>
            <div style={{ fontFamily: F.sans, fontSize: 22, color: C.muted }}>1000 adet</div>
          </div>
          <div>
            <div style={{ fontFamily: F.mono, fontSize: 48, fontWeight: 700, color: C.ink }}>€{tr(e2, 2)}</div>
            <div style={{ fontFamily: F.sans, fontSize: 22, color: C.muted }}>100 adet</div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
          {["−25…+70 °C", "IP65", "14,5 mT hesaplandı"].map((t, i) => (
            <span
              key={t}
              style={{
                fontFamily: F.sans,
                fontSize: 21,
                fontWeight: 700,
                color: C.ink,
                padding: "5px 14px",
                borderRadius: 999,
                border: `1.5px solid ${C.line2}`,
                background: "rgba(255,255,255,.03)",
                ...fadeUp(frame, 96 + i * 6, { dist: 10 }),
              }}
            >
              {t}
            </span>
          ))}
        </div>
      </div>

      <Narration
        lines={[
          {
            from: 24,
            to: 134,
            text: (
              <>
                Sensör düğümleri <Em>STM32WLE5</Em>: mikrodenetleyici ve 868 MHz radyo aynı yongada, pille çalışır.
              </>
            ),
          },
          {
            from: 138,
            to: 212,
            text: (
              <>
                Bağlantı koparsa <Em>20 000 çerçeve</Em> tamponda; elektrik giderse <Em>8 sn</Em> "son nefes".
              </>
            ),
          },
          {
            from: 216,
            to: 296,
            text: (
              <>
                Firmware C99: float yok, malloc yok. <Em color={C.uyari}>"Pano enerjisiz"</Em> bir hata değil, bir durum.
              </>
            ),
          },
        ]}
      />
    </AbsoluteFill>
  );
};
