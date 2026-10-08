import React, { useMemo } from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Card, Em, Icon, IconName, Theta } from "../ui/primitives";
import { fadeSide, fadeUp, prog } from "../ui/motion";
import { C, CLAMP, EASE_IN_OUT, EASE_OUT, F, heat, rng, tr } from "../theme";

/* 12 · BASTIRILMIŞ ALARMLAR
   Solda sıcak hava dalgası: 40 bağlantı birlikte +6,1 K. Sabit eşik 40 alarm sayar,
   θ değişimi 0,0000 K kalır → BASTIRILDI. Sağda gerekçeli bastırma listesi dolar. */

const COLS = 8;
const ROWS = 5;
const CELL_W = 80;
const CELL_H = 46;
const GAP = 10;
const THR = 60; // sabit eşik, °C
const RISE_START = 64;
const RISE_END = 150;

const rise = (f: number) =>
  interpolate(f, [RISE_START, RISE_END], [0, 6.1], { ...CLAMP, easing: EASE_IN_OUT });

type Rule = { icon: IconName; title: string; desc: React.ReactNode; code: string; color: string; at: number };

const RULES: Rule[] = [
  {
    icon: "sun",
    title: "Sıcak hava dalgası",
    desc: (
      <>
        40 bağlantı birlikte +6,1 K · Δ<Theta /> = 0,0000 K
      </>
    ),
    code: "pano değil, hava",
    color: C.ok,
    at: 178,
  },
  {
    icon: "wave",
    title: "Üç fazda THD birlikte yükseldi",
    desc: "Şebeke olayı adayı. Isıl bulgu silinmez, bir kademe geriler.",
    code: "GRID_THD_3PH",
    color: C.izle,
    at: 206,
  },
  {
    icon: "wrench",
    title: "Sensör kaydı · kelepçe düştü",
    desc: "Cihaz iş emri açılır — tork iş emri değil.",
    code: "DEVICE_MOUNT_LOST · DRIFT",
    color: C.uyari,
    at: 230,
  },
  {
    icon: "pin",
    title: "Bölgesel olay penceresi",
    desc: "Frekans penceresi dışında: yüz panoya yüz ekip çıkmaz.",
    code: "GRID_WINDOW",
    color: C.kritik,
    at: 254,
  },
  {
    icon: "clock",
    title: "Yük sıçraması · inrush",
    desc: "θ kararlı hâl içindir; 3τ boyunca askıya alınır.",
    code: "LOAD_STEP · INRUSH",
    color: C.bilgi,
    at: 278,
  },
];

const HeatGrid: React.FC<{ frame: number }> = ({ frame }) => {
  const base = useMemo(() => {
    const r = rng(3);
    return Array.from({ length: COLS * ROWS }, () => 54.4 + r() * 3.6);
  }, []);
  const rs = rise(frame);
  return (
    <svg width={COLS * CELL_W + (COLS - 1) * GAP} height={ROWS * CELL_H + (ROWS - 1) * GAP} style={{ overflow: "visible" }}>
      {base.map((b, i) => {
        const col = i % COLS;
        const row = Math.floor(i / COLS);
        const x = col * (CELL_W + GAP);
        const y = row * (CELL_H + GAP);
        const T = b + rs;
        const over = T >= THR;
        const appear = prog(frame, 30 + (col + row) * 2, 14);
        return (
          <g key={i} opacity={appear} transform={`translate(${x} ${y + (1 - appear) * 14})`}>
            <rect width={CELL_W} height={CELL_H} rx={10} fill={heat(0.42 + (T - 52) / 22)} />
            <rect
              width={CELL_W}
              height={CELL_H}
              rx={10}
              fill="none"
              stroke={over ? C.kritik : "rgba(255,255,255,.08)"}
              strokeWidth={over ? 3 : 1}
            />
            {over ? <circle cx={CELL_W - 12} cy={12} r={5} fill={C.kritik} /> : null}
          </g>
        );
      })}
    </svg>
  );
};

export const S12Bastirma: React.FC = () => {
  const frame = useCurrentFrame();

  const base = useMemo(() => {
    const r = rng(3);
    return Array.from({ length: COLS * ROWS }, () => 54.4 + r() * 3.6);
  }, []);
  const rs = rise(frame);
  const alarms = base.filter((b) => b + rs >= THR).length;
  const amb = 35.1 + rs;

  const stamp = interpolate(frame, [152, 166], [0, 1], { ...CLAMP, easing: Easing.out(Easing.back(1.8)) });

  return (
    <AbsoluteFill>
      <Backdrop accent={C.ok} second={C.kritik} />
      <SceneHeader
        kicker="06 · Alarm"
        title="*Üretmediğimiz* alarmlar."
        lead={<>“78 °C okudun, neden bana söylemedin?” — cevabı ekranda, gerekçesiyle durur.</>}
      />

      {/* sol: sıcak hava dalgası */}
      <div style={{ position: "absolute", left: 120, top: 340, ...fadeUp(frame, 22) }}>
        <Card style={{ width: 780, height: 556, padding: "24px 30px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontFamily: F.sans, fontSize: 28, fontWeight: 700, color: C.ink }}>
              Sıcak hava dalgası · <span style={{ color: C.muted, fontWeight: 500 }}>40 bağlantı</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <Icon name="sun" size={36} color={amb > 40 ? C.kritik : C.uyari} />
              <div style={{ textAlign: "right" }}>
                <div style={{ fontFamily: F.mono, fontSize: 30, fontWeight: 700, color: amb > 40 ? C.kritik : C.ink }}>
                  {tr(amb)} °C
                </div>
                <div
                  style={{
                    fontFamily: F.sans,
                    fontSize: 20,
                    color: C.uyari,
                    opacity: interpolate(frame, [130, 145], [0, 1], CLAMP),
                  }}
                >
                  şartname dahili maks 40 °C
                </div>
              </div>
            </div>
          </div>

          <div style={{ marginTop: 18, position: "relative" }}>
            <HeatGrid frame={frame} />
            <div
              style={{
                position: "absolute",
                left: 0,
                right: 0,
                top: 0,
                height: ROWS * CELL_H + (ROWS - 1) * GAP,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                pointerEvents: "none",
              }}
            >
              <div
                style={{
                  opacity: stamp,
                  scale: String(1.5 - 0.5 * stamp),
                  rotate: "-5deg",
                  padding: "14px 30px",
                  borderRadius: 16,
                  border: `4px solid ${C.ok}`,
                  background: "rgba(6,8,12,.86)",
                  textAlign: "center",
                  boxShadow: `0 0 40px ${C.ok}55`,
                }}
              >
                <div style={{ fontFamily: F.sans, fontWeight: 900, fontSize: 48, letterSpacing: "0.06em", color: C.ok }}>
                  BASTIRILDI
                </div>
                <div style={{ fontFamily: F.sans, fontSize: 26, color: C.ink }}>hava hakkında bir okuma</div>
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 18, marginTop: 22 }}>
            <div
              style={{
                flex: 1,
                padding: "14px 22px",
                borderRadius: 16,
                border: `1.5px solid ${alarms > 0 ? C.kritik + "88" : C.line2}`,
                background: alarms > 0 ? "rgba(255,107,61,.08)" : "transparent",
              }}
            >
              <div style={{ fontFamily: F.sans, fontSize: 22, color: C.muted }}>Sabit eşikli sistem</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
                <span style={{ fontFamily: F.mono, fontSize: 64, fontWeight: 700, color: C.kritik }}>{alarms}</span>
                <span style={{ fontFamily: F.sans, fontSize: 28, color: C.kritik }}>alarm</span>
              </div>
            </div>
            <div
              style={{
                flex: 1,
                padding: "14px 22px",
                borderRadius: 16,
                border: `1.5px solid ${C.ok}88`,
                background: "rgba(53,192,122,.08)",
              }}
            >
              <div style={{ fontFamily: F.sans, fontSize: 22, color: C.muted }}>PANO GÖZ</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
                <span style={{ fontFamily: F.mono, fontSize: 64, fontWeight: 700, color: C.ok }}>0</span>
                <span style={{ fontFamily: F.mono, fontSize: 26, color: C.ok }}>
                  Δ<Theta /> = 0,0000 K
                </span>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* sağ: gerekçeli bastırma listesi */}
      <div style={{ position: "absolute", left: 940, top: 340, width: 860 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 16,
            ...fadeUp(frame, 40),
          }}
        >
          <div style={{ fontFamily: F.mono, fontSize: 24, letterSpacing: "0.14em", color: C.muted }}>
            BASTIRILANLAR · GEREKÇELİ
          </div>
          <div style={{ fontFamily: F.mono, fontSize: 22, color: C.dim }}>
            {RULES.filter((r) => frame >= r.at).length} / {RULES.length}
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {RULES.map((r, i) => {
            const on = prog(frame, r.at, 18);
            const flash = interpolate(frame, [r.at, r.at + 8, r.at + 40], [0, 1, 0], CLAMP);
            return (
              <div key={i} style={{ position: "relative", height: 92 }}>
                {/* boş iskelet satır — parıltı taraması: liste dolmayı bekliyor */}
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    borderRadius: 16,
                    overflow: "hidden",
                    border: `1.5px dashed ${C.line2}`,
                    background: C.panel + "aa",
                    opacity: interpolate(frame, [44 + i * 4, 58 + i * 4], [0, 1], CLAMP) * (1 - on),
                  }}
                >
                  <div style={{ position: "absolute", left: 22, top: 22, width: 54, height: 48, borderRadius: 14, background: C.line }} />
                  <div style={{ position: "absolute", left: 96, top: 26, width: 300 - i * 30, height: 16, borderRadius: 8, background: C.line }} />
                  <div style={{ position: "absolute", left: 96, top: 54, width: 440 - i * 20, height: 12, borderRadius: 6, background: C.line }} />
                  <div
                    style={{
                      position: "absolute",
                      top: 0,
                      bottom: 0,
                      width: 220,
                      left: ((frame * 9 + i * 60) % 1300) - 260,
                      background: "linear-gradient(90deg, transparent, rgba(255,255,255,.06), transparent)",
                    }}
                  />
                </div>
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    display: "flex",
                    alignItems: "center",
                    gap: 18,
                    padding: "0 22px",
                    borderRadius: 16,
                    background: `linear-gradient(90deg, ${r.color}${Math.round(18 + flash * 40).toString(16)}, ${C.panel} 60%)`,
                    border: `1.5px solid ${r.color}${flash > 0.05 ? "cc" : "55"}`,
                    boxShadow: flash > 0.05 ? `0 0 ${30 * flash}px ${r.color}66` : "none",
                    ...fadeSide(frame, r.at, -60, 18),
                  }}
                >
                  <div
                    style={{
                      width: 54,
                      height: 54,
                      borderRadius: 14,
                      background: r.color + "22",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <Icon name={r.icon} size={32} color={r.color} stroke={2} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontFamily: F.sans, fontSize: 28, fontWeight: 700, color: C.ink }}>{r.title}</div>
                    <div style={{ fontFamily: F.sans, fontSize: 22, color: C.muted, marginTop: 2 }}>{r.desc}</div>
                  </div>
                  <div
                    style={{
                      fontFamily: F.mono,
                      fontSize: 18,
                      color: r.color,
                      textAlign: "right",
                      maxWidth: 190,
                      lineHeight: 1.25,
                    }}
                  >
                    {r.code}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          background: `radial-gradient(700px 500px at 27% 62%, ${C.kritik}14, transparent 70%)`,
          opacity: interpolate(frame, [RISE_START, RISE_END, 160, 190], [0, 1, 1, 0], { ...CLAMP, easing: EASE_OUT }),
        }}
      />

      <Narration
        lines={[
          {
            from: 22,
            to: 140,
            text: (
              <>
                Sıcak hava dalgası: ortam <Em color={C.kritik}>41,2 °C</Em>. Kırk bağlantının hepsi birden{" "}
                <Em>+6,1 K</Em>.
              </>
            ),
          },
          {
            from: 144,
            to: 214,
            text: (
              <>
                Sabit eşik burada <Em color={C.kritik}>40 alarm</Em> üretirdi. <Theta /> değişimi{" "}
                <Em color={C.ok}>0,0000 K</Em> — kardeşler aynı havayı soluyor.
              </>
            ),
          },
          {
            from: 218,
            to: 296,
            text: (
              <>
                Her kural tek soruya cevap verir: bu okuma <Em>pano</Em> hakkında mı — şebeke, hava, yük ya da
                kendi cihazımız mı?
              </>
            ),
          },
          {
            from: 300,
            to: 358,
            text: (
              <>
                Bu liste bir hata ayıklama günlüğü değil; <Em color={C.ok}>kendi ekranı olan bir ürün</Em>.
              </>
            ),
          },
        ]}
      />
    </AbsoluteFill>
  );
};
