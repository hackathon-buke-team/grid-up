import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Card, DrawPath, Em, Theta } from "../ui/primitives";
import { fadeUp, popIn, prog } from "../ui/motion";
import { C, CLAMP, F, linePath, Pt, rng, sc, tr } from "../theme";

/* 9 · TESPİT ZİNCİRİ
   Yedi kutu soldan sağa: ölçüm → kardeş farkı → θ → günlük medyan (CUSUM · değişim noktası ·
   Theil-Sen) → bastırma → füzyon → alarm. Anlatım ilerledikçe ilgili kutular öne çıkar.
   Altta: yedi arıza modu ve "Yapay zekâ nerede?" — otokodlayıcı yavaş sürüklenmeye kördür. */

type Node = { t: string; a?: string; b?: string; chips?: string[]; tag: string; c: string };

const NODES: Node[] = [
  { t: "Ölçüm", a: "T · TMP117 / IR", b: "I · kelepçe CT", tag: "dakikada bir", c: C.line2 },
  { t: "Kardeş farkı", a: "T − medyan", b: "kendisi hariç", tag: "fider içinde", c: C.line2 },
  { t: "θ kestirimi", a: "RLS, ileri model", b: "dekonvolüsyon yok", tag: "K, anma akımında", c: C.olcum },
  { t: "Günlük medyan", chips: ["CUSUM · h = 8", "Değişim noktası", "Theil-Sen eğim"], tag: "gün ölçeği", c: C.olcum },
  { t: "Bastırma", a: "şebeke · hava · yük", b: "cihaz · öğrenme", tag: "Türkçe gerekçe", c: C.izle },
  { t: "Füzyon", a: "7 arıza modu", b: "sağlık endeksi", tag: "tavanlı LLR", c: C.line2 },
  { t: "Alarm", a: "3/5 gün debounce", b: "2 aile = ekip", tag: "SMS · SCADA", c: C.kritik },
];

const NW = 216;
const NG = 28;
const NY = 366;
const NH = 210;
const nx = (i: number) => 120 + i * (NW + NG);

const MODES: [string, number][] = [
  ["Gevşek bağlantı", 0.3],
  ["Aşırı yük", 0.15],
  ["Ark koruma bütünlüğü", 0.15],
  ["Isıl kaçış / soğutma", 0.1],
  ["Harmonik nötr", 0.1],
  ["Nem / yoğuşma", 0.1],
  ["Yalıtım zayıflaması", 0.1],
];

/* Anlatıma göre odak pencereleri: [başlangıç, bitiş, kutular] */
const FOCUS: [number, number, number[]][] = [
  [40, 124, [0, 1]],
  [128, 206, [2, 3]],
  [210, 272, [4, 5, 6]],
];

const env = (frame: number, a: number, b: number) =>
  interpolate(frame, [a, a + 10, b - 10, b], [0, 1, 1, 0], CLAMP);

/* ---------------- "Yapay zekâ nerede?" mini grafiği ---------------- */
const AX = sc(0, 10, 40, 700);
const AY = sc(0, 2.4, 128, 14);

const AiChart: React.FC<{ frame: number }> = ({ frame }) => {
  const r = rng(5);
  const truth: Pt[] = [];
  const recon: Pt[] = [];
  for (let w = 0; w <= 10.0001; w += 0.25) {
    const th = 0.2 * w + (r() - 0.5) * 0.08;
    truth.push([AX(w), AY(th)]);
    recon.push([AX(w), AY(0.2 * w - 0.05 + (r() - 0.5) * 0.04)]);
  }
  const p = prog(frame, 272, 44);
  const lbl = prog(frame, 314, 14);
  return (
    <svg width={740} height={150} style={{ overflow: "visible" }}>
      {[0, 1, 2].map((v) => (
        <g key={v}>
          <line x1={40} x2={700} y1={AY(v)} y2={AY(v)} stroke={C.line} strokeWidth={1.5} />
          <text x={28} y={AY(v) + 7} textAnchor="end" fontFamily={F.mono} fontSize={20} fill={C.dim}>
            {v}
          </text>
        </g>
      ))}
      <text x={700} y={148} textAnchor="end" fontFamily={F.mono} fontSize={20} fill={C.dim}>
        10 hafta
      </text>
      <DrawPath d={linePath(truth)} progress={p} stroke={C.olcum} strokeWidth={4} />
      <DrawPath d={linePath(recon)} progress={p} stroke={C.muted} strokeWidth={3} strokeDasharray="8 7" />
      <g opacity={lbl}>
        <rect x={420} y={AY(1.85) - 24} width={270} height={36} rx={8} fill={C.bg} stroke={C.kritik} strokeWidth={1.5} />
        <text x={555} y={AY(1.85) + 1} textAnchor="middle" fontFamily={F.sans} fontSize={21} fontWeight={700} fill={C.kritik}>
          artık ≈ 0 → alarm yok
        </text>
      </g>
    </svg>
  );
};

export const S09Tespit: React.FC = () => {
  const frame = useCurrentFrame();

  /* dalga: veri zincirde soldan sağa ilerler */
  const wave = ((frame - 118) / 14) % 9;
  const anyFocus = Math.max(...FOCUS.map(([a, b]) => env(frame, a, b)));

  return (
    <AbsoluteFill>
      <Backdrop accent={C.olcum} second={C.izle} />
      <SceneHeader kicker="05 · Yöntem" title="Her kutunun bir *birimi* var." lead="Hiçbiri eğitim verisi istemez." />

      {/* zaman ölçeği parantezleri */}
      {[
        { x0: nx(0), x1: nx(2) + NW, t: "dakika ölçeği", c: C.izle, at: 52 },
        { x0: nx(3), x1: nx(6) + NW, t: "gün ölçeği · avlanan sinyal 0,2 K/hafta", c: C.olcum, at: 150 },
      ].map((b) => (
        <div
          key={b.t}
          style={{
            position: "absolute",
            left: b.x0,
            width: b.x1 - b.x0,
            top: 314,
            opacity: prog(frame, b.at, 16),
          }}
        >
          <div style={{ textAlign: "center", fontFamily: F.mono, fontSize: 21, color: b.c, letterSpacing: "0.04em" }}>
            {b.t}
          </div>
          <div
            style={{
              marginTop: 6,
              height: 10,
              borderTop: `2px solid ${b.c}`,
              borderLeft: `2px solid ${b.c}`,
              borderRight: `2px solid ${b.c}`,
              borderRadius: "6px 6px 0 0",
              opacity: 0.7,
              width: `${prog(frame, b.at, 24) * 100}%`,
              marginLeft: `${(1 - prog(frame, b.at, 24)) * 50}%`,
            }}
          />
        </div>
      ))}

      {/* oklar */}
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        {NODES.slice(0, -1).map((_, i) => {
          const x = nx(i) + NW + NG / 2;
          const lit = Math.max(0, 1 - Math.abs(wave - (i + 0.5)) * 1.5);
          return (
            <path
              key={i}
              d={`M${x - 6},${NY + NH / 2 - 12} L${x + 6},${NY + NH / 2} L${x - 6},${NY + NH / 2 + 12}`}
              fill="none"
              stroke={lit > 0.1 ? C.brand : C.line2}
              strokeWidth={3.5}
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity={prog(frame, 44 + i * 12, 10)}
            />
          );
        })}
      </svg>

      {/* kutular */}
      {NODES.map((n, i) => {
        const appear = prog(frame, 40 + i * 12, 18);
        const focus = Math.max(0, ...FOCUS.filter(([, , ids]) => ids.includes(i)).map(([a, b]) => env(frame, a, b)));
        const dim = 1 - 0.55 * anyFocus * (1 - focus);
        const lit = frame > 118 ? Math.max(0, 1 - Math.abs(wave - i) * 1.4) : 0;
        const border = n.c === C.line2 ? (focus > 0.5 ? C.brand : C.line2) : n.c;
        return (
          <div key={i}>
            <div
              style={{
                position: "absolute",
                left: nx(i),
                top: NY,
                width: NW,
                height: NH,
                boxSizing: "border-box",
                padding: "18px 18px",
                borderRadius: 16,
                background: `linear-gradient(180deg, ${C.panel2}, ${C.panel})`,
                border: `2px solid ${border}`,
                boxShadow: `0 0 ${10 + 34 * Math.max(lit * 0.7, focus)}px -4px ${n.c === C.line2 ? C.brand : n.c}${
                  Math.max(lit * 0.7, focus) > 0.05 ? "aa" : "00"
                }`,
                opacity: appear * dim,
                translate: `0px ${(1 - appear) * 30 - focus * 8}px`,
              }}
            >
              <div style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 28, color: C.ink, lineHeight: 1.1 }}>
                {i === 2 ? (
                  <>
                    <Theta /> kestirimi
                  </>
                ) : (
                  n.t
                )}
              </div>
              {n.chips ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 5, marginTop: 10 }}>
                  {n.chips.map((c, j) => (
                    <div
                      key={c}
                      style={{
                        padding: "2px 8px",
                        borderRadius: 999,
                        background: "rgba(255,234,70,.08)",
                        border: "1.5px solid rgba(255,234,70,.35)",
                        fontFamily: F.mono,
                        fontSize: 17,
                        color: C.olcum,
                        whiteSpace: "nowrap",
                        opacity: prog(frame, 150 + j * 8, 12),
                      }}
                    >
                      {c}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ marginTop: 14, fontFamily: F.sans, fontSize: 22, lineHeight: 1.35, color: C.muted }}>
                  <div>{n.a}</div>
                  <div>{n.b}</div>
                </div>
              )}
            </div>
            <div
              style={{
                position: "absolute",
                left: nx(i),
                width: NW,
                top: NY + NH + 12,
                textAlign: "center",
                fontFamily: F.mono,
                fontSize: 20,
                color: focus > 0.5 ? C.ink : C.dim,
                opacity: appear * dim,
              }}
            >
              {n.tag}
            </div>
          </div>
        );
      })}

      {/* yedi arıza modu */}
      <div style={{ position: "absolute", left: 120, top: 632, ...fadeUp(frame, 212) }}>
        <Card style={{ width: 880, height: 270, padding: "16px 28px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <div style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 26, color: C.ink }}>
              7 arıza modu · sağlık endeksi tam ayrışır
            </div>
            <div style={{ fontFamily: F.mono, fontSize: 20, color: C.muted }}>
              HI = 100 · Π (1 − r)<sup>w</sup>
            </div>
          </div>
          <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 3 }}>
            {MODES.map(([n, w], i) => {
              const g = prog(frame, 224 + i * 5, 20);
              return (
                <div key={n} style={{ display: "flex", alignItems: "center", gap: 18, height: 26 }}>
                  <span style={{ width: 290, fontFamily: F.sans, fontSize: 22, color: C.muted }}>{n}</span>
                  <span style={{ flex: 1, height: 12, borderRadius: 6, background: C.line }}>
                    <span
                      style={{
                        display: "block",
                        height: "100%",
                        borderRadius: 6,
                        width: `${(w / 0.3) * 100 * g}%`,
                        background: i === 0 ? `linear-gradient(90deg, ${C.brand}, ${C.olcum})` : C.brand2,
                        opacity: i === 0 ? 1 : 0.7,
                      }}
                    />
                  </span>
                  <span style={{ width: 70, textAlign: "right", fontFamily: F.mono, fontSize: 22, color: C.ink, opacity: g }}>
                    {tr(w, 2)}
                  </span>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* yapay zekâ nerede? */}
      <div style={{ position: "absolute", left: 1040, top: 632, ...fadeUp(frame, 262) }}>
        <Card glow={frame > 312 ? C.kritik : undefined} style={{ width: 760, height: 270, padding: "16px 10px 0 18px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingRight: 18 }}>
            <div style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 28, color: C.ink }}>“Yapay zekâ nerede?”</div>
            <div style={{ display: "flex", gap: 18, fontFamily: F.sans, fontSize: 20, color: C.muted }}>
              <span>
                <span style={{ color: C.olcum, fontWeight: 800 }}>━</span> gerçek sürüklenme
              </span>
              <span>╍ otokodlayıcı</span>
            </div>
          </div>
          <div style={{ marginTop: 4 }}>
            <AiChart frame={frame} />
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 0 }}>
            <span style={{ fontFamily: F.sans, fontSize: 22, color: C.muted }}>Her çıktımızın birimi var:</span>
            {["kelvin", "mikroohm", "gün"].map((u, i) => (
              <span
                key={u}
                style={{
                  padding: "3px 14px",
                  borderRadius: 999,
                  fontFamily: F.mono,
                  fontSize: 21,
                  fontWeight: 700,
                  color: C.ok,
                  border: `1.5px solid ${C.ok}`,
                  background: "rgba(53,192,122,.12)",
                  ...popIn(frame, 326 + i * 6),
                }}
              >
                {u}
              </span>
            ))}
          </div>
        </Card>
      </div>

      <Narration
        lines={[
          {
            from: 40,
            to: 124,
            text: (
              <>
                Ölçüm dakikada bir gelir; kardeş medyanı bağlantının <Em>kendisi hariç</Em> alınır.
              </>
            ),
          },
          {
            from: 128,
            to: 206,
            text: (
              <>
                <Theta /> ileri modelle, RLS ile kestirilir. Sonra ölçek <Em color={C.olcum}>gün</Em> olur: CUSUM,
                değişim noktası, eğim.
              </>
            ),
          },
          {
            from: 210,
            to: 272,
            text: (
              <>
                Sıra sabit: bastırma → füzyon → alarm. Açıklanabilen kanıt <Em color={C.izle}>olasılığa girmez</Em>.
              </>
            ),
          },
          {
            from: 276,
            to: 358,
            text: (
              <>
                Otokodlayıcı <Em color={C.olcum}>0,2 K/hafta</Em> sürüklenmeyi normal diye öğrenir — avladığımız sinyale{" "}
                <Em color={C.kritik}>kör</Em>.
              </>
            ),
          },
        ]}
      />
    </AbsoluteFill>
  );
};
