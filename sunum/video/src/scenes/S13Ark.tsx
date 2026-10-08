import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Card, Chip, Em, Icon } from "../ui/primitives";
import { fadeSide, fadeUp, prog, pulse } from "../ui/motion";
import { C, CLAMP, EASE_OUT, F } from "../theme";

/* 13 · ARK OLAYI: KORUMA BİZDE DEĞİL
   Işık çakar; TVOC-2 ~1 ms'de açar. PANO GÖZ sonra gelir: kim gördü, kim attı, ne zaman.
   Gecikme tek bir sayı değil, 4–13 sn aralığı. Göremediğimiz X1 ekranda yazılı. */

const FLASH = 18;

const KV: { k: string; v: string; at: number; color?: string }[] = [
  { k: "TVOC-2 reg 1300", v: "0x0001 · aktif açma", at: 56, color: C.kritik },
  { k: "Gören dedektör", v: "X2:3", at: 70 },
  { k: "Açan röle", v: "K5", at: 84 },
  { k: "Işık → kontak", v: "~1 ms · SIL-2", at: 98 },
  { k: "Sağlam dedektör", v: "10 / 10", at: 112 },
];

/* en iyi ve en kötü bildirim yolu (sn) — slides-b.js ile aynı */
const SEGS = [
  { n: "TVOC-2 ışık → kontak", v: "~1 ms", note: "bizi beklemez", color: C.acil },
  { n: "Modbus yenileme", v: "0,2–2 s", note: "belgelenmemiş", color: C.uyari },
  { n: "Ağ geçidi taraması", v: "1 s", note: "", color: C.izle },
  { n: "Sunucu işleme", v: "0,3–2 s", note: "", color: C.brand2 },
  { n: "SMS yolu", v: "2,5–8 s", note: "", color: C.ok },
];
const BEST = [0.001, 0.2, 1, 0.3, 2.5];
const WORST = [0.001, 2, 1, 2, 8];
const AX = 14;
const BAR_W = 700;

const LatBar: React.FC<{ frame: number; segs: number[]; start: number; label: string; total: string }> = ({
  frame,
  segs,
  start,
  label,
  total,
}) => {
  let acc = 0;
  const done = prog(frame, start + segs.length * 9 + 4, 14);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 18, height: 52 }}>
      <div style={{ width: 120, fontFamily: F.mono, fontSize: 24, color: C.muted }}>{label}</div>
      <div style={{ position: "relative", width: BAR_W, height: 34, borderRadius: 8, background: C.line }}>
        {segs.map((s, i) => {
          const x = (acc / AX) * BAR_W;
          acc += s;
          const w = Math.max(5, (s / AX) * BAR_W);
          const g = prog(frame, start + i * 9, 16);
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: x,
                top: 0,
                height: 34,
                width: w * g,
                background: SEGS[i].color,
                borderRadius: i === 0 ? "8px 0 0 8px" : i === segs.length - 1 ? "0 8px 8px 0" : 0,
                boxShadow: i === 0 ? `0 0 14px ${C.acil}` : undefined,
              }}
            />
          );
        })}
      </div>
      <div style={{ fontFamily: F.mono, fontSize: 30, fontWeight: 700, color: C.ink, opacity: done }}>{total}</div>
    </div>
  );
};

export const S13Ark: React.FC = () => {
  const frame = useCurrentFrame();

  const flash = interpolate(frame, [FLASH, FLASH + 3, FLASH + 16], [0, 1, 0], { ...CLAMP, easing: Easing.out(Easing.quad) });
  const after = interpolate(frame, [FLASH + 3, FLASH + 70], [1, 0], CLAMP);
  const range = prog(frame, 222, 20);
  const x1 = prog(frame, 250, 16);

  return (
    <AbsoluteFill>
      <Backdrop accent={C.kritik} second={C.izle} />
      <SceneHeader kicker="06 · Alarm" title="Biz açmadık; *TVOC-2* açtı." delay={34} accent={C.kritik} />

      {/* sol: olay kartı */}
      <div style={{ position: "absolute", left: 120, top: 330, ...fadeUp(frame, 46) }}>
        <Card glow={C.kritik} style={{ width: 600, height: 566, padding: "26px 32px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
            <div
              style={{
                width: 76,
                height: 76,
                borderRadius: 20,
                background: `radial-gradient(circle, ${C.kritik}66, ${C.kritik}11 70%)`,
                border: `2px solid ${C.kritik}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: `0 0 ${20 + 30 * pulse(frame, 30) * after + 10}px ${C.kritik}88`,
              }}
            >
              <Icon name="flash" size={48} color="#fff3e8" stroke={2} />
            </div>
            <div>
              <div style={{ fontFamily: F.sans, fontSize: 34, fontWeight: 800, color: C.ink }}>Ark olayı</div>
              <div style={{ fontFamily: F.mono, fontSize: 24, color: C.muted }}>SOKE-14 · zaman damgalı</div>
            </div>
          </div>

          <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 2 }}>
            {KV.map((r) => {
              const p = prog(frame, r.at, 14);
              const chars = Math.round(interpolate(frame, [r.at + 4, r.at + 16], [0, r.v.length], CLAMP));
              return (
                <div
                  key={r.k}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "baseline",
                    padding: "9px 0",
                    whiteSpace: "nowrap",
                    borderBottom: `1px solid ${C.line}`,
                    opacity: p,
                    translate: `${(1 - p) * -24}px 0px`,
                  }}
                >
                  <span style={{ fontFamily: F.sans, fontSize: 26, color: C.muted }}>{r.k}</span>
                  <span style={{ fontFamily: F.mono, fontSize: 27, fontWeight: 700, color: r.color ?? C.ink }}>
                    {r.v.slice(0, chars)}
                  </span>
                </div>
              );
            })}
          </div>

          <div
            style={{
              marginTop: 16,
              display: "flex",
              gap: 14,
              alignItems: "flex-start",
              padding: "14px 18px",
              borderRadius: 14,
              background: `rgba(244,177,58,${0.06 + 0.1 * x1 * pulse(frame, 36)})`,
              border: `1.5px solid ${C.uyari}${x1 > 0.5 ? "cc" : "44"}`,
              ...fadeUp(frame, 132),
            }}
          >
            <Icon name="eye" size={30} color={C.uyari} stroke={2} />
            <div style={{ fontFamily: F.sans, fontSize: 22, lineHeight: 1.35, color: C.ink }}>
              Register 222/223 yalnız <b>X2 ve X3</b>'ü kapsar.{" "}
              <span style={{ color: C.uyari, fontWeight: 700 }}>X1'i göremiyoruz — ekranda da öyle yazar.</span>
            </div>
          </div>
        </Card>
      </div>

      {/* sağ üst: koruma bizde değil */}
      <div style={{ position: "absolute", left: 760, top: 330, ...fadeSide(frame, 58, 50) }}>
        <Card style={{ width: 1040, height: 150, padding: "24px 34px", display: "flex", alignItems: "center", gap: 28 }}>
          <div
            style={{
              width: 92,
              height: 92,
              borderRadius: 999,
              border: `3px solid ${C.izle}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Icon name="shield" size={50} color={C.izle} stroke={2} />
          </div>
          <div>
            <div style={{ fontFamily: F.sans, fontSize: 44, fontWeight: 800, color: C.ink }}>
              PANO GÖZ <span style={{ color: C.izle }}>koruma değildir.</span>
            </div>
            <div style={{ fontFamily: F.sans, fontSize: 28, color: C.muted, marginTop: 4 }}>
              Koruma bizi beklemez. Biz gözlemler, konumlandırır, zaman damgalar ve haber veririz.
            </div>
          </div>
        </Card>
      </div>

      {/* sağ alt: gecikme aralığı */}
      <div style={{ position: "absolute", left: 760, top: 504, ...fadeUp(frame, 96) }}>
        <Card style={{ width: 1040, height: 392, padding: "22px 34px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <div style={{ fontFamily: F.sans, fontSize: 28, fontWeight: 700, color: C.ink }}>
              Bildirim gecikmesi · <span style={{ color: C.muted, fontWeight: 500 }}>tek temiz sayı değil, bir aralık</span>
            </div>
          </div>

          <div style={{ marginTop: 14, position: "relative" }}>
            <LatBar frame={frame} segs={BEST} start={112} label="en iyi" total="≈ 4 sn" />
            <LatBar frame={frame} segs={WORST} start={160} label="en kötü" total="13 sn" />
            {/* eksen */}
            <div style={{ position: "relative", marginLeft: 138, width: BAR_W, height: 30 }}>
              {[0, 2, 4, 6, 8, 10, 12, 14].map((v) => (
                <span
                  key={v}
                  style={{
                    position: "absolute",
                    left: (v / AX) * BAR_W,
                    translate: "-50% 0px",
                    fontFamily: F.mono,
                    fontSize: 20,
                    color: C.dim,
                  }}
                >
                  {v}
                </span>
              ))}
            </div>
            {/* 4–13 sn aralık parantezi */}
            <div
              style={{
                position: "absolute",
                left: 138 + (4 / AX) * BAR_W,
                top: -6,
                height: 116,
                width: ((13 - 4) / AX) * BAR_W * range,
                borderRadius: 10,
                border: `2.5px solid ${C.kritik}`,
                background: `${C.kritik}14`,
                opacity: range,
              }}
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 28px", marginTop: 10 }}>
            {SEGS.map((s, i) => (
              <div
                key={s.n}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  fontFamily: F.sans,
                  fontSize: 22,
                  color: C.muted,
                  whiteSpace: "nowrap",
                  ...fadeUp(frame, 120 + i * 8, { dist: 12 }),
                }}
              >
                <span style={{ width: 14, height: 14, borderRadius: 4, background: s.color, flexShrink: 0 }} />
                <span style={{ color: C.ink }}>{s.n}</span>
                <span style={{ fontFamily: F.mono, color: C.ink, fontWeight: 700 }}>{s.v}</span>
                {s.note ? <span style={{ color: C.dim, fontSize: 20 }}>{s.note}</span> : null}
              </div>
            ))}
            <div style={{ display: "flex", alignItems: "center", ...fadeUp(frame, 226, { dist: 12 }) }}>
              <Chip color={C.kritik} solid style={{ fontSize: 24 }}>
                Toplam 4–13 sn
              </Chip>
            </div>
          </div>
        </Card>
      </div>

      {/* ark çakması */}
      <AbsoluteFill
        style={{
          pointerEvents: "none",
          background: `radial-gradient(circle at 50% 46%, rgba(255,255,255,${flash}), rgba(170,210,255,${0.85 * flash}) 30%, rgba(74,163,255,${0.5 * flash}) 60%, rgba(6,8,12,${0.3 * flash}))`,
        }}
      />
      <AbsoluteFill
        style={{
          pointerEvents: "none",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          opacity: interpolate(frame, [FLASH - 2, FLASH + 2, FLASH + 22, FLASH + 34], [0, 1, 1, 0], CLAMP),
        }}
      >
        <svg width={600} height={600} viewBox="-300 -300 600 600">
          {Array.from({ length: 14 }, (_, i) => {
            const a = (i / 14) * Math.PI * 2 + 0.2;
            const len = 120 + ((i * 37) % 90) + interpolate(frame, [FLASH, FLASH + 20], [0, 80], { ...CLAMP, easing: EASE_OUT });
            return (
              <line
                key={i}
                x1={Math.cos(a) * 30}
                y1={Math.sin(a) * 30}
                x2={Math.cos(a) * len}
                y2={Math.sin(a) * len}
                stroke="#e8f4ff"
                strokeWidth={4}
                strokeLinecap="round"
              />
            );
          })}
          <circle r={46} fill="#ffffff" />
          <circle r={90} fill="#bfe0ff" opacity={0.4} />
        </svg>
      </AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 760,
          textAlign: "center",
          fontFamily: F.mono,
          fontSize: 34,
          fontWeight: 700,
          color: C.bg,
          letterSpacing: "0.14em",
          opacity: interpolate(frame, [FLASH + 2, FLASH + 6, FLASH + 22, FLASH + 32], [0, 1, 1, 0], CLAMP),
        }}
      >
        ~1 ms · TVOC-2 AÇTI
      </div>

      <Narration
        lines={[
          {
            from: 40,
            to: 108,
            text: (
              <>
                Ark oluştu. Panodaki ABB TVOC-2 açtı: ışıktan kontağa <Em color={C.kritik}>~1 ms</Em>, SIL-2 donanımda.
              </>
            ),
          },
          {
            from: 112,
            to: 186,
            text: (
              <>
                İşimiz açmadan sonra başlar: <Em>hangi dedektör</Em>, <Em>hangi röle</Em>, ne zaman — ve haber.
              </>
            ),
          },
          {
            from: 190,
            to: 250,
            text: (
              <>
                Gecikme tek bir sayı değil: <Em color={C.kritik}>4–13 sn</Em>. TVOC-2'nin Modbus yenilemesini ABB
                belgelemiyor.
              </>
            ),
          },
          {
            from: 254,
            to: 298,
            text: (
              <>
                Görmediğimizi gördü gibi göstermek <Em color={C.uyari}>en tehlikeli hatadır</Em>.
              </>
            ),
          },
        ]}
      />
    </AbsoluteFill>
  );
};
