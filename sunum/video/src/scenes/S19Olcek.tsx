import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Card, Em, Icon, IconName } from "../ui/primitives";
import { fadeSide, fadeUp, prog } from "../ui/motion";
import { C, CLAMP, F } from "../theme";

/* 19 · ÖLÇEKLENEBİLİRLİK
   100 / 1 000 / 10 000 pano için ölçülen kaynaklar (logaritmik çubuklar); her panonun
   kendi kısa RS-485 hattı ve master'ı → broker; asıl kısıtlar insan ve ekip-günü. */

const COLS = ["100 pano", "1 000 pano", "10 000 pano"];
const ROWS: { n: string; sub: string; lab: string[]; v: number[]; c: string }[] = [
  { n: "Zarf / sn", sub: "gelen telemetri", lab: ["15", "150", "1 500"], v: [15, 150, 1500], c: C.izle },
  { n: "Dedektör CPU", sub: "tek çekirdeğe oranla", lab: ["%2,2", "%21,6", "2,2 çekirdek"], v: [2.16, 21.6, 216], c: C.olcum },
  { n: "Disk", sub: "kararlı hâl", lab: ["18 GB", "180 GB", "1,8 TB"], v: [18, 180, 1800], c: C.brand },
];
const SERVERS = ["2 vCPU · 8 GB", "4 vCPU · 16 GB", "4 düğüm / bölge"];

const TX = 120;
const TY = 330;
const TW = 1060;
const LABEL_W = 260;
const COL_W = (TW - 60 - LABEL_W) / 3;
const BAR_MAX = COL_W - 30;

const glowWin = (frame: number, a: number, b: number) => interpolate(frame, [a, a + 10, b - 10, b], [0, 1, 1, 0], CLAMP);

/* ---------------- topoloji ---------------- */
const PANELS = [0, 1, 2, 3];
const px = (i: number) => 14 + i * 132;
const BROKER = { x: 270, y: 176 };
const pathOf = (i: number) => {
  const x = px(i) + 56;
  return `M${x},92 C${x},140 ${BROKER.x},128 ${BROKER.x},${BROKER.y - 22}`;
};
/* kübik Bézier üzerinde nokta */
const bez = (i: number, t: number) => {
  const x0 = px(i) + 56;
  const P = [
    [x0, 92],
    [x0, 140],
    [BROKER.x, 128],
    [BROKER.x, BROKER.y - 22],
  ];
  const u = 1 - t;
  const x = u * u * u * P[0][0] + 3 * u * u * t * P[1][0] + 3 * u * t * t * P[2][0] + t * t * t * P[3][0];
  const y = u * u * u * P[0][1] + 3 * u * u * t * P[1][1] + 3 * u * t * t * P[2][1] + t * t * t * P[3][1];
  return [x, y];
};

const Topology: React.FC<{ frame: number }> = ({ frame }) => {
  const on = prog(frame, 50, 24);
  return (
    <svg width={540} height={210} viewBox="0 0 540 210" style={{ overflow: "visible" }}>
      {PANELS.map((i) => {
        const x = px(i);
        const a = prog(frame, 44 + i * 6, 18);
        return (
          <g key={i} opacity={a}>
            <rect x={x} y={8} width={112} height={84} rx={12} fill={C.bg2} stroke={C.line2} strokeWidth={1.5} />
            <text x={x + 56} y={32} textAnchor="middle" fontFamily={F.sans} fontSize={18} fill={C.muted}>
              {i === 3 ? "Pano N" : `Pano ${i + 1}`}
            </text>
            {/* panodaki iki cihaz + kısa RS-485 */}
            <rect x={x + 12} y={50} width={22} height={18} rx={4} fill={C.panel2} stroke={C.l1} />
            <rect x={x + 12} y={70} width={22} height={14} rx={4} fill={C.panel2} stroke={C.l1} opacity={0.7} />
            <path d={`M${x + 34},59 H${x + 62} M${x + 34},77 H${x + 50} V64 H${x + 62}`} stroke={C.ok} strokeWidth={2} fill="none" />
            <rect x={x + 62} y={48} width={40} height={30} rx={6} fill={C.brandSoft} stroke={C.brand} strokeWidth={1.5} />
            <text x={x + 82} y={68} textAnchor="middle" fontFamily={F.mono} fontSize={13} fontWeight={700} fill={C.brand}>
              GW
            </text>
            <path d={pathOf(i)} fill="none" stroke={C.line2} strokeWidth={2} />
          </g>
        );
      })}
      <text x={px(0) + 14} y={104} fontFamily={F.mono} fontSize={14} fill={C.ok} opacity={on}>
        RS-485
      </text>
      {/* akan zarflar */}
      {PANELS.map((i) =>
        [0, 1, 2].map((k) => {
          const period = 46 + i * 7;
          const t = (((frame - 56 + k * (period / 3) + i * 9) % period) + period) % period / period;
          const [x, y] = bez(i, t);
          return (
            <circle
              key={`${i}-${k}`}
              cx={x}
              cy={y}
              r={4.5}
              fill={C.izle}
              opacity={on * Math.min(1, t * 6) * Math.min(1, (1 - t) * 6)}
            />
          );
        }),
      )}
      <g opacity={prog(frame, 64, 18)}>
        <rect
          x={BROKER.x - 80}
          y={BROKER.y - 22}
          width={160}
          height={42}
          rx={12}
          fill={C.bg2}
          stroke={C.izle}
          strokeWidth={2}
          style={{ filter: `drop-shadow(0 0 10px ${C.izle}66)` }}
        />
        <text x={BROKER.x} y={BROKER.y + 7} textAnchor="middle" fontFamily={F.sans} fontSize={20} fontWeight={700} fill={C.izle}>
          MQTT broker
        </text>
      </g>
    </svg>
  );
};

const Constraint: React.FC<{ icon: IconName; t: string; d: string; style: React.CSSProperties }> = ({
  icon,
  t,
  d,
  style,
}) => (
  <div style={{ display: "flex", gap: 16, alignItems: "flex-start", ...style }}>
    <div
      style={{
        width: 50,
        height: 50,
        borderRadius: 14,
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: C.brandSoft,
        border: `1.5px solid ${C.brand}66`,
      }}
    >
      <Icon name={icon} size={28} color={C.brand2} stroke={2} />
    </div>
    <div>
      <div style={{ fontFamily: F.sans, fontSize: 27, fontWeight: 800, color: C.ink }}>{t}</div>
      <div style={{ fontFamily: F.sans, fontSize: 21, color: C.muted, lineHeight: 1.3 }}>{d}</div>
    </div>
  </div>
);

export const S19Olcek: React.FC = () => {
  const frame = useCurrentFrame();
  const g1 = glowWin(frame, 24, 120);
  const g2 = glowWin(frame, 122, 206);
  const g3 = glowWin(frame, 208, 300);

  return (
    <AbsoluteFill>
      <Backdrop accent={C.izle} second={C.olcum} />
      <SceneHeader
        kicker="10 · Ölçek"
        title="1000 pano, *pahalı* *sunucu* istemez."
        lead="Kaynaklar bu projenin kodu üzerinde ölçüldü; 10 000 pano kestirimdir."
      />

      {/* tablo */}
      <div style={{ position: "absolute", left: TX, top: TY, ...fadeUp(frame, 20, { blur: 8 }) }}>
        <Card style={{ position: "relative", width: TW, height: 560, padding: "18px 30px" }}>
          {/* 100 pano sütunu vurgusu */}
          <div
            style={{
              position: "absolute",
              left: 30 + LABEL_W - 10,
              top: 12,
              width: COL_W,
              height: 410,
              borderRadius: 14,
              background: `${C.izle}12`,
              border: `1.5px solid ${C.izle}`,
              opacity: g1,
            }}
          />
          <div style={{ display: "flex", height: 56, alignItems: "center" }}>
            <div style={{ width: LABEL_W }} />
            {COLS.map((c, j) => (
              <div
                key={c}
                style={{
                  width: COL_W,
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  fontFamily: F.sans,
                  fontSize: 28,
                  fontWeight: 800,
                  color: j === 0 && g1 > 0.5 ? C.izle : C.ink,
                  ...fadeUp(frame, 28 + j * 6, { dist: 16 }),
                }}
              >
                {c}
              </div>
            ))}
          </div>
          {ROWS.map((r, ri) => {
            const max = Math.log10(r.v[2] * 10);
            return (
              <div
                key={r.n}
                style={{ display: "flex", height: 112, alignItems: "center", borderTop: `1px solid ${C.line}` }}
              >
                <div style={{ width: LABEL_W, ...fadeSide(frame, 40 + ri * 14, -30) }}>
                  <div style={{ fontFamily: F.sans, fontSize: 30, fontWeight: 800, color: r.c }}>{r.n}</div>
                  <div style={{ fontFamily: F.sans, fontSize: 21, color: C.dim }}>{r.sub}</div>
                </div>
                {r.v.map((v, j) => {
                  const st = 56 + ri * 18 + j * 12;
                  const p = prog(frame, st, 30);
                  const w = Math.max(10, (Math.log10(v * 10) / max) * BAR_MAX);
                  return (
                    <div key={j} style={{ width: COL_W }}>
                      <div
                        style={{
                          fontFamily: F.mono,
                          fontSize: 28,
                          fontWeight: 700,
                          color: C.ink,
                          opacity: prog(frame, st + 14, 14),
                          marginBottom: 8,
                        }}
                      >
                        {r.lab[j]}
                      </div>
                      <div style={{ width: BAR_MAX, height: 16, borderRadius: 8, background: C.line }}>
                        <div
                          style={{
                            width: w * p,
                            height: "100%",
                            borderRadius: 8,
                            background:
                              j === 2
                                ? `repeating-linear-gradient(135deg, ${r.c} 0 10px, ${r.c}66 10px 18px)`
                                : `linear-gradient(90deg, ${r.c}99, ${r.c})`,
                            boxShadow: `0 0 12px ${r.c}66`,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })}
          <div
            style={{
              display: "flex",
              height: 70,
              alignItems: "center",
              borderTop: `1px solid ${C.line}`,
              ...fadeUp(frame, 128, { dist: 14 }),
            }}
          >
            <div style={{ width: LABEL_W, fontFamily: F.sans, fontSize: 30, fontWeight: 800, color: C.muted }}>
              Sunucu
            </div>
            {SERVERS.map((s) => (
              <div key={s} style={{ width: COL_W, fontFamily: F.mono, fontSize: 23, color: C.ink }}>
                {s}
              </div>
            ))}
          </div>
          <div
            style={{
              fontFamily: F.mono,
              fontSize: 19,
              color: C.dim,
              marginTop: 4,
              ...fadeUp(frame, 146, { dist: 10 }),
            }}
          >
            Logaritmik çubuklar · taralı = kestirim · ölçülen en büyük filo 112 pano
          </div>
        </Card>
      </div>

      {/* topoloji */}
      <div style={{ position: "absolute", left: 1220, top: TY, ...fadeUp(frame, 36) }}>
        <Card glow={g2 > 0.3 ? C.izle : undefined} style={{ width: 580, height: 310, padding: "18px 20px" }}>
          <div style={{ fontFamily: F.mono, fontSize: 20, letterSpacing: "0.14em", color: C.dim }}>
            PAYLAŞILAN SERİ HAT YOK
          </div>
          <div style={{ marginTop: 8 }}>
            <Topology frame={frame} />
          </div>
          <div style={{ fontFamily: F.sans, fontSize: 21, color: C.muted, marginTop: -2, opacity: prog(frame, 90, 16) }}>
            1000. pano, diğer 999'un hattına <span style={{ color: C.ink, fontWeight: 700 }}>sıfır yük</span> ekler.
          </div>
        </Card>
      </div>

      {/* asıl kısıtlar */}
      <div style={{ position: "absolute", left: 1220, top: TY + 330, ...fadeUp(frame, 196) }}>
        <Card glow={g3 > 0.3 ? C.brand : undefined} style={{ width: 580, height: 230, padding: "18px 24px" }}>
          <div style={{ fontFamily: F.mono, fontSize: 20, letterSpacing: "0.14em", color: C.brand }}>
            ASIL ÖLÇEK KISITLARI
          </div>
          <Constraint
            icon="user"
            t="Operatörün dikkati"
            d="100 panoda haftada en fazla 3 telefon çaldıran alarm hedefi"
            style={{ marginTop: 14, ...fadeSide(frame, 206, 30) }}
          />
          <Constraint
            icon="wrench"
            t="Kurulum kapasitesi"
            d="Takvimi yazılım değil ekip-günü belirler"
            style={{ marginTop: 14, ...fadeSide(frame, 222, 30) }}
          />
        </Card>
      </div>

      <Narration
        lines={[
          {
            from: 24,
            to: 118,
            text: (
              <>
                Yüz panoda saniyede <Em color={C.izle}>15 zarf</Em>; dedektör tek çekirdeğin{" "}
                <Em color={C.olcum}>%2,2</Em>'sini kullanıyor.
              </>
            ),
          },
          {
            from: 122,
            to: 204,
            text: (
              <>
                Her panonun kendi kısa hattı ve master'ı var: ölçek seri hatta değil, <Em color={C.izle}>broker'da</Em>.
              </>
            ),
          },
          {
            from: 208,
            to: 298,
            text: (
              <>
                Gerçek kısıtlar <Em>operatörün dikkati</Em> ve <Em>kurulum kapasitesi</Em> — yazılım değil.
              </>
            ),
          },
        ]}
      />
    </AbsoluteFill>
  );
};
