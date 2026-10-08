import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { SceneHeader } from "../ui/SceneHeader";
import { Card, Chip, DrawPath, Icon, IconName, Level, Mark, Theta } from "../ui/primitives";
import { fadeSide, fadeUp, prog, pulse } from "../ui/motion";
import { C, CLAMP, EASE_IN_OUT, F, heat, Pt, smoothPath, tr } from "../theme";

/* 15 · SAHA EKİBİ UYGULAMASI (konsept)
   Merdivendeki SMS'in telefonundan "içeri" girilir. Kritik alarm ekip telefonuna düşer,
   ekip üstlenir, sahada güvenlik kapısı + NFC ile doğru panoyu doğrular, torklar;
   θ tabana döner ve iş emri kapanır. Merkez konsolu her adımı aynı anda görür. */

/* ---------------- zaman çizelgesi ---------------- */
const T = {
  notif: 34, // bildirim düşer
  tapNotif: 78,
  detail: 92, // alarm ayrıntısı
  tapAccept: 168,
  site: 206, // sahada: güvenlik kapısı
  nfc: 284,
  work: 334, // müdahale
  torque: 352,
  thetaDrop: 384,
  closed: 456,
};

/* ---------------- telefon ölçüleri ---------------- */
const PW = 440;
const PH = 900;
const PX = 960 - PW / 2;
const PY = 92;
const SW = PW - 28;
const SH = PH - 28;

/* Ekran geçişi: sağdan kayarak gelir, sola itilip kararır */
const screenStyle = (frame: number, enter: number, exit: number | null, from: "right" | "zoom" = "right") => {
  const i = prog(frame, enter, 18, EASE_IN_OUT);
  const o = exit === null ? 0 : prog(frame, exit, 18, EASE_IN_OUT);
  if (frame < enter - 1 || (exit !== null && frame > exit + 19)) return { display: "none" } as React.CSSProperties;
  const enterT = from === "zoom" ? `0px ${(1 - i) * 40}px` : `${(1 - i) * SW}px 0px`;
  return {
    position: "absolute",
    inset: 0,
    opacity: from === "zoom" ? i * (1 - o * 0.6) : 1 - o * 0.6,
    translate: o > 0 ? `${-o * SW * 0.3}px 0px` : enterT,
    scale: from === "zoom" ? String(0.92 + 0.08 * i) : "1",
    filter: o > 0 ? `brightness(${1 - o * 0.5})` : undefined,
  } as React.CSSProperties;
};

/* Dokunma izi */
const Tap: React.FC<{ frame: number; at: number; x: number; y: number }> = ({ frame, at, x, y }) => {
  if (frame < at - 8 || frame > at + 22) return null;
  const p = interpolate(frame, [at - 8, at, at + 22], [0, 1, 2], CLAMP);
  const r = p < 1 ? 26 : 26 + (p - 1) * 40;
  const o = p < 1 ? p * 0.9 : 0.9 * (2 - p);
  return (
    <div
      style={{
        position: "absolute",
        left: x - r,
        top: y - r,
        width: r * 2,
        height: r * 2,
        borderRadius: 999,
        background: "rgba(255,255,255,.22)",
        border: "2px solid rgba(255,255,255,.7)",
        opacity: o,
        zIndex: 20,
      }}
    />
  );
};

const AppBar: React.FC<{ title: string }> = ({ title }) => (
  <div
    style={{
      display: "flex",
      alignItems: "center",
      gap: 12,
      padding: "62px 22px 14px",
      borderBottom: `1px solid ${C.line}`,
    }}
  >
    <Mark size={34} />
    <div style={{ flex: 1 }}>
      <div style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 21, color: C.ink }}>PANO GÖZ · Saha</div>
      <div style={{ fontFamily: F.mono, fontSize: 15, color: C.dim }}>{title}</div>
    </div>
    <div
      style={{
        width: 36,
        height: 36,
        borderRadius: 99,
        background: C.panel2,
        border: `1.5px solid ${C.line2}`,
        display: "grid",
        placeItems: "center",
      }}
    >
      <Icon name="user" size={20} color={C.muted} />
    </div>
  </div>
);

const Row: React.FC<{ k: string; v: React.ReactNode; color?: string }> = ({ k, v, color = C.ink }) => (
  <div
    style={{
      display: "flex",
      justifyContent: "space-between",
      gap: 12,
      padding: "11px 0",
      borderBottom: `1px solid ${C.line}`,
      fontFamily: F.sans,
      fontSize: 19,
    }}
  >
    <span style={{ color: C.dim }}>{k}</span>
    <span style={{ color, fontWeight: 700, textAlign: "right" }}>{v}</span>
  </div>
);

/* Ekranın altına sabit eylem düğmesi */
const ActionButton: React.FC<{ frame: number; enabled: boolean; tapAt: number; label: string; hint: string }> = ({
  frame,
  enabled,
  tapAt,
  label,
  hint,
}) => (
  <div style={{ position: "absolute", left: 22, right: 22, bottom: 34 }}>
    <div
      style={{
        height: 62,
        borderRadius: 18,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: F.sans,
        fontWeight: 800,
        fontSize: 21,
        color: enabled ? C.bg : C.dim,
        background: enabled ? C.ok : C.panel2,
        border: `1.5px solid ${enabled ? C.ok : C.line2}`,
        boxShadow: enabled ? `0 10px 30px -8px ${C.ok}` : "none",
        scale: String(1 - 0.05 * Math.sin(prog(frame, tapAt - 4, 10) * Math.PI)),
      }}
    >
      {label}
    </div>
    <div style={{ fontFamily: F.sans, fontSize: 15, color: C.dim, textAlign: "center", marginTop: 8 }}>{hint}</div>
  </div>
);

/* Termal küçük resim: 4 pabuç, biri sıcak (önce) ya da hepsi eş (sonra) */
const ThermalThumb: React.FC<{ hot: boolean; label: string }> = ({ hot, label }) => (
  <div style={{ flex: 1 }}>
    <svg viewBox="0 0 160 100" width="100%" style={{ borderRadius: 12, display: "block" }}>
      <defs>
        <filter id={`tb${hot ? 1 : 0}`} x="-1" y="-1" width="3" height="3">
          <feGaussianBlur stdDeviation="5" />
        </filter>
      </defs>
      <rect width="160" height="100" fill="#160636" />
      {[28, 62, 96, 130].map((x, i) => {
        const t = hot && i === 1 ? 1 : 0.55 + (i === 3 ? -0.08 : 0);
        return (
          <g key={x}>
            <rect x={x - 5} y={42} width={10} height={58} fill={heat(t * 0.7)} />
            <circle cx={x} cy={42} r={hot && i === 1 ? 20 : 12} fill={heat(t)} filter={`url(#tb${hot ? 1 : 0})`} />
            <circle cx={x} cy={42} r={hot && i === 1 ? 6 : 4} fill={heat(Math.min(1, t + 0.1))} />
          </g>
        );
      })}
    </svg>
    <div style={{ fontFamily: F.mono, fontSize: 15, color: C.dim, marginTop: 6, textAlign: "center" }}>{label}</div>
  </div>
);

/* Telefon saati merkez günlüğüyle aynı ilerler */
const clock = (frame: number) => {
  let t = "09:41";
  LOG.forEach((l) => {
    if (frame >= l.at) t = l.t;
  });
  return t;
};

/* ---------------- telefon içeriği ---------------- */
const Phone: React.FC<{ frame: number }> = ({ frame }) => {
  /* θ: 30 günlük yükseliş (ayrıntı ekranı) */
  const trend: Pt[] = Array.from({ length: 30 }, (_, i) => {
    const v = i < 9 ? 1 + i * 0.12 : 2.1 + Math.pow((i - 9) / 20, 1.25) * 15.5;
    return [16 + i * 12.4, 92 - v * 4.4];
  });
  const theta = interpolate(frame, [T.thetaDrop, T.thetaDrop + 60], [17.6, 1.0], {
    ...CLAMP,
    easing: Easing.inOut(Easing.cubic),
  });
  const after = theta < 2;
  const accepted = frame >= T.tapAccept;
  const nfcOk = frame >= T.nfc + 34;

  return (
    <div
      style={{
        position: "absolute",
        left: PX,
        top: PY,
        width: PW,
        height: PH,
        borderRadius: 70,
        background: "linear-gradient(160deg, #1b2430, #0b0f14 40%, #151c26)",
        border: `2px solid ${C.line2}`,
        boxShadow: `0 60px 120px -30px rgba(0,0,0,.9), 0 0 0 10px #0a0d12, 0 0 80px -10px ${C.brand}33`,
        translate: `0px ${Math.sin(frame / 38) * 5}px`,
      }}
    >
      <div
        style={{
          position: "absolute",
          left: 14,
          top: 14,
          width: SW,
          height: SH,
          borderRadius: 58,
          overflow: "hidden",
          background: C.bg2,
        }}
      >
        {/* durum çubuğu */}
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 0,
            height: 48,
            zIndex: 10,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "8px 34px 0",
            fontFamily: F.sans,
            fontWeight: 700,
            fontSize: 17,
            color: C.ink,
          }}
        >
          <span>{clock(frame)}</span>
          <span style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <Icon name="wifi" size={18} color={C.ink} stroke={2.2} />
            <Icon name="battery" size={20} color={C.ink} stroke={2} />
          </span>
        </div>
        <div
          style={{
            position: "absolute",
            left: SW / 2 - 62,
            top: 12,
            width: 124,
            height: 34,
            borderRadius: 20,
            background: "#000",
            zIndex: 11,
          }}
        />

        {/* 0 · kilit ekranı + bildirim */}
        <div style={screenStyle(frame, -20, T.detail, "zoom")}>
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: "radial-gradient(120% 80% at 30% 10%, #2a1650, #0a0e14 60%), #0a0e14",
            }}
          />
          <div style={{ position: "absolute", top: 110, width: "100%", textAlign: "center" }}>
            <div style={{ fontFamily: F.sans, fontSize: 22, color: C.muted }}>Pazartesi, 5 Ekim</div>
            <div style={{ fontFamily: F.sans, fontWeight: 700, fontSize: 96, color: C.ink, letterSpacing: "-0.02em" }}>
              09:41
            </div>
          </div>
          <div
            style={{
              position: "absolute",
              left: 14,
              right: 14,
              top: 300,
              opacity: prog(frame, T.notif, 14),
              translate: `0px ${interpolate(frame, [T.notif, T.notif + 20], [-120, 0], {
                ...CLAMP,
                easing: Easing.out(Easing.back(1.4)),
              })}px`,
              scale: String(1 + 0.03 * Math.sin(prog(frame, T.tapNotif - 6, 12) * Math.PI)),
            }}
          >
            <div
              style={{
                borderRadius: 26,
                padding: "16px 18px",
                background: "rgba(30,36,48,.92)",
                border: `1.5px solid ${C.kritik}88`,
                boxShadow: `0 0 40px ${C.kritik}44`,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <Mark size={26} />
                <span style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 17, color: C.ink, flex: 1 }}>
                  PANO GÖZ
                </span>
                <span style={{ fontFamily: F.sans, fontSize: 15, color: C.dim }}>şimdi</span>
              </div>
              <div style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 21, color: C.kritik, marginTop: 10 }}>
                KRİTİK · SOKE-14
              </div>
              <div style={{ fontFamily: F.sans, fontSize: 19, color: C.ink, marginTop: 4, lineHeight: 1.35 }}>
                Ç7 · L2 pabuç · <Theta /> = 17,6 K
                <br />
                Bağlantıyı torkla · ACİL'e 15 g (13–19)
              </div>
            </div>
          </div>
          <div
            style={{
              position: "absolute",
              bottom: 40,
              width: "100%",
              textAlign: "center",
              fontFamily: F.sans,
              fontSize: 17,
              color: C.dim,
              opacity: prog(frame, T.notif + 20, 14),
            }}
          >
            Açmak için dokunun
          </div>
          <Tap frame={frame} at={T.tapNotif} x={SW / 2} y={380} />
        </div>

        {/* 1 · alarm ayrıntısı + üstlen */}
        <div style={screenStyle(frame, T.detail, T.site, "zoom")}>
          <AppBar title="Olay #2417 · Ekip 3" />
          <div style={{ padding: "16px 22px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <Level name="Kritik" color={C.kritik} size={17} />
              <span style={{ fontFamily: F.mono, fontSize: 15, color: C.dim }}>pano iş emri</span>
            </div>
            <div style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 25, color: C.ink, marginTop: 12 }}>
              SOKE-14 · Çıkış 7 · L2
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginTop: 4 }}>
              <span style={{ fontFamily: F.mono, fontWeight: 700, fontSize: 52, color: C.olcum }}>
                <Theta /> 17,6 K
              </span>
            </div>
            <svg width={SW - 44} height={100} style={{ display: "block", marginTop: 4 }}>
              <line x1={16} x2={SW - 60} y1={92 - 12 * 4.4} y2={92 - 12 * 4.4} stroke={C.kritik} strokeDasharray="5 5" />
              <line x1={16} x2={SW - 60} y1={92 - 5 * 4.4} y2={92 - 5 * 4.4} stroke={C.uyari} strokeDasharray="5 5" />
              <DrawPath d={smoothPath(trend)} progress={prog(frame, T.detail + 10, 34)} stroke={C.olcum} strokeWidth={3.5} />
            </svg>
            <Row k="Eğim" v="+3,01 K/hafta" />
            <Row k="ACİL'e kalan" v="15 gün (13–19)" color={C.acil} />
            <Row k="Yapılacak" v="Tork anahtarıyla yeniden sık" color={C.brand2} />
            {/* rota */}
            <div
              style={{
                marginTop: 14,
                height: 112,
                borderRadius: 18,
                background: "#0d1520",
                border: `1px solid ${C.line2}`,
                overflow: "hidden",
                position: "relative",
              }}
            >
              <svg width={SW - 44} height={112}>
                {[18, 52, 86].map((y) => (
                  <line key={y} x1={0} x2={SW} y1={y} y2={y + 10} stroke="#1a2738" strokeWidth={8} />
                ))}
                {[60, 170, 280].map((x) => (
                  <line key={x} x1={x} x2={x - 16} y1={0} y2={112} stroke="#1a2738" strokeWidth={8} />
                ))}
                <DrawPath
                  d="M38,96 L52,58 L166,62 L158,28 L300,30"
                  progress={prog(frame, T.tapAccept + 4, 36)}
                  stroke={C.izle}
                  strokeWidth={4}
                />
                <circle cx={38} cy={96} r={7} fill={C.izle} />
                <circle cx={300} cy={30} r={9} fill={C.kritik} />
                <circle cx={300} cy={30} r={9 + pulse(frame, 30) * 10} fill={C.kritik} opacity={0.25} />
              </svg>
              <div
                style={{
                  position: "absolute",
                  right: 12,
                  bottom: 8,
                  fontFamily: F.mono,
                  fontSize: 14,
                  color: C.muted,
                }}
              >
                Rota · SOKE-14
              </div>
            </div>
            {/* üstlen düğmesi */}
            <div
              style={{
                marginTop: 16,
                height: 62,
                borderRadius: 18,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 10,
                fontFamily: F.sans,
                fontWeight: 800,
                fontSize: 22,
                color: accepted ? C.bg : C.bg,
                background: accepted ? C.ok : C.brand,
                boxShadow: `0 10px 30px -8px ${accepted ? C.ok : C.brand}`,
                scale: String(1 - 0.05 * Math.sin(prog(frame, T.tapAccept - 4, 10) * Math.PI)),
              }}
            >
              {accepted ? (
                <>
                  <Icon name="check" size={24} color={C.bg} stroke={3} /> Üstlenildi · Ekip 3 yolda
                </>
              ) : (
                <>Üstlen</>
              )}
            </div>
          </div>
          <Tap frame={frame} at={T.tapAccept} x={SW / 2} y={SH - 72} />
        </div>

        {/* 2 · sahada: güvenlik kapısı + NFC */}
        <div style={screenStyle(frame, T.site, T.work)}>
          <AppBar title="Sahada · güvenlik kapısı" />
          <div style={{ padding: "18px 22px" }}>
            {[
              { t: "Termal ön tarama", d: "110 °C kapısı geçildi", at: T.site + 22 },
              { t: "KKD ve çalışma izni", d: "onaylandı", at: T.site + 40 },
              { t: "Yalnız alt kablo bölmesi", d: "bara bölmesine girilmez", at: T.site + 58 },
            ].map((c) => {
              const on = prog(frame, c.at, 10);
              return (
                <div
                  key={c.t}
                  style={{
                    display: "flex",
                    gap: 14,
                    alignItems: "center",
                    padding: "13px 14px",
                    marginBottom: 10,
                    borderRadius: 16,
                    background: C.panel,
                    border: `1.5px solid ${on > 0.5 ? C.ok + "88" : C.line2}`,
                    ...fadeSide(frame, c.at - 12, 30, 14),
                  }}
                >
                  <div
                    style={{
                      width: 34,
                      height: 34,
                      borderRadius: 99,
                      display: "grid",
                      placeItems: "center",
                      background: on > 0.5 ? C.ok : "transparent",
                      border: `2px solid ${on > 0.5 ? C.ok : C.line2}`,
                      scale: String(0.6 + 0.4 * on),
                    }}
                  >
                    {on > 0.5 ? <Icon name="check" size={20} color={C.bg} stroke={3.2} /> : null}
                  </div>
                  <div>
                    <div style={{ fontFamily: F.sans, fontWeight: 700, fontSize: 19, color: C.ink }}>{c.t}</div>
                    <div style={{ fontFamily: F.sans, fontSize: 16, color: C.dim }}>{c.d}</div>
                  </div>
                </div>
              );
            })}
            {/* NFC */}
            <div
              style={{
                marginTop: 14,
                borderRadius: 22,
                padding: "22px 16px",
                textAlign: "center",
                background: nfcOk ? `${C.ok}1a` : C.panel,
                border: `1.5px solid ${nfcOk ? C.ok : C.izle}88`,
                ...fadeUp(frame, T.nfc - 10, { dist: 24 }),
              }}
            >
              <svg width={150} height={120} viewBox="0 0 150 120">
                {[0, 1, 2].map((i) => {
                  const w = ((((frame - T.nfc + i * 10) % 30) + 30) % 30) / 30;
                  return nfcOk || frame <= T.nfc ? null : (
                    <circle
                      key={i}
                      cx={75}
                      cy={60}
                      r={18 + w * 46}
                      fill="none"
                      stroke={C.izle}
                      strokeWidth={3}
                      opacity={1 - w}
                    />
                  );
                })}
                <circle cx={75} cy={60} r={26} fill={nfcOk ? C.ok : C.izle} />
                {nfcOk ? (
                  <path d="M63 61l8 8 16-17" stroke={C.bg} strokeWidth={5} fill="none" strokeLinecap="round" />
                ) : (
                  <path
                    d="M66 50a14 14 0 010 20M72 46a20 20 0 010 28M78 42a26 26 0 010 36"
                    stroke={C.bg}
                    strokeWidth={3}
                    fill="none"
                    strokeLinecap="round"
                  />
                )}
              </svg>
              <div style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 21, color: nfcOk ? C.ok : C.ink }}>
                {nfcOk ? "SOKE-14 · Ç7-L2 doğrulandı" : "Pano etiketine dokunun"}
              </div>
              <div style={{ fontFamily: F.sans, fontSize: 16, color: C.dim, marginTop: 4 }}>
                {nfcOk ? "doğru pano, doğru bağlantı" : "NFC · konum doğrulama"}
              </div>
            </div>
          </div>
          <ActionButton
            frame={frame}
            enabled={nfcOk}
            tapAt={T.work - 6}
            label="Müdahaleye başla"
            hint={nfcOk ? "konum doğrulandı" : "önce pano etiketine dokunun"}
          />
          <Tap frame={frame} at={T.work - 6} x={SW / 2} y={SH - 84} />
        </div>

        {/* 3 · müdahale + canlı θ + kapanış */}
        <div style={screenStyle(frame, T.work, null)}>
          <AppBar title={frame >= T.closed ? "Olay #2417 · kapandı" : "Müdahale"} />
          <div style={{ padding: "18px 22px" }}>
            <div
              style={{
                display: "flex",
                gap: 14,
                alignItems: "center",
                padding: "13px 14px",
                borderRadius: 16,
                background: C.panel,
                border: `1.5px solid ${frame >= T.torque ? C.ok + "88" : C.line2}`,
              }}
            >
              <Icon name="wrench" size={30} color={frame >= T.torque ? C.ok : C.muted} />
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: F.sans, fontWeight: 700, fontSize: 19, color: C.ink }}>
                  Tork anahtarıyla yeniden sıkıldı
                </div>
                <div style={{ fontFamily: F.sans, fontSize: 16, color: C.dim }}>temas yüzeyi kontrol edildi</div>
              </div>
              {frame >= T.torque ? <Icon name="check" size={26} color={C.ok} stroke={3} /> : null}
            </div>
            <div style={{ display: "flex", gap: 12, marginTop: 14, ...fadeUp(frame, T.torque + 6, { dist: 20 }) }}>
              <ThermalThumb hot label="önce" />
              <div style={{ opacity: prog(frame, T.thetaDrop + 30, 16), flex: 1 }}>
                <ThermalThumb hot={false} label="sonra" />
              </div>
            </div>
            {/* canlı θ */}
            <div
              style={{
                marginTop: 16,
                padding: "16px 18px",
                borderRadius: 20,
                background: C.panel,
                border: `1.5px solid ${(after ? C.ok : C.kritik) + "88"}`,
                ...fadeUp(frame, T.thetaDrop - 14, { dist: 20 }),
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontFamily: F.sans, fontSize: 17, color: C.muted }}>
                  Canlı <Theta /> · Ç7-L2
                </span>
                <Level name={after ? "Bilgi" : theta >= 12 ? "Kritik" : "Uyarı"} color={after ? C.bilgi : theta >= 12 ? C.kritik : C.uyari} size={15} />
              </div>
              <div
                style={{
                  fontFamily: F.mono,
                  fontWeight: 700,
                  fontSize: 58,
                  color: after ? C.ok : C.olcum,
                  marginTop: 2,
                }}
              >
                {tr(theta)} K
              </div>
              <div style={{ height: 8, borderRadius: 4, background: C.line, marginTop: 6 }}>
                <div
                  style={{
                    width: `${(theta / 17.6) * 100}%`,
                    height: "100%",
                    borderRadius: 4,
                    background: after ? C.ok : `linear-gradient(90deg, ${C.uyari}, ${C.kritik})`,
                  }}
                />
              </div>
              <div style={{ fontFamily: F.sans, fontSize: 16, color: C.dim, marginTop: 8 }}>
                {after ? "tabana döndü · 24 sa doğrulama izlemesi" : "tork sonrası kardeşlerine yaklaşıyor…"}
              </div>
            </div>
          </div>

          <ActionButton
            frame={frame}
            enabled={after}
            tapAt={T.closed - 6}
            label="İş emrini kapat"
            hint={after ? "θ tabana döndü" : "θ tabana dönünce açılır"}
          />
          <Tap frame={frame} at={T.closed - 6} x={SW / 2} y={SH - 84} />

          {/* kapanış örtüsü */}
          {frame >= T.closed - 2 ? (
            <div
              style={{
                position: "absolute",
                inset: 0,
                background: `rgba(10,14,20,${0.92 * prog(frame, T.closed, 14)})`,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 14,
              }}
            >
              <svg width={150} height={150} viewBox="0 0 150 150" style={{ ...popInStyle(frame, T.closed + 4) }}>
                <circle cx={75} cy={75} r={64} fill={`${C.ok}22`} stroke={C.ok} strokeWidth={5} />
                <DrawPath d="M46 77l20 20 40-44" progress={prog(frame, T.closed + 14, 16)} stroke={C.ok} strokeWidth={10} />
              </svg>
              <div style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 30, color: C.ink, ...fadeUp(frame, T.closed + 16) }}>
                İş emri kapandı
              </div>
              <div
                style={{
                  fontFamily: F.mono,
                  fontSize: 18,
                  color: C.muted,
                  textAlign: "center",
                  lineHeight: 1.5,
                  ...fadeUp(frame, T.closed + 24),
                }}
              >
                <Theta /> 17,6 K → 1,0 K
                <br />
                merkez · SCADA güncellendi
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};

const popInStyle = (frame: number, at: number): React.CSSProperties => {
  const p = interpolate(frame, [at, at + 20], [0, 1], { ...CLAMP, easing: Easing.out(Easing.back(1.8)) });
  return { opacity: Math.min(1, p * 1.5), scale: String(0.3 + 0.7 * p) };
};

/* ---------------- sol: adımlar ---------------- */
const STEPS: { t: string; d: string; icon: IconName; from: number; to: number }[] = [
  {
    t: "Bildirim",
    d: "Kritik alarm ekip telefonuna anında düşer. SMS yedek kanal olarak kalır.",
    icon: "bell",
    from: T.notif,
    to: T.detail,
  },
  {
    t: "Üstlen",
    d: "Tek dokunuş: olay ekibe atanır, ne yapılacağı ve kalan süre ekranda.",
    icon: "user",
    from: T.detail,
    to: T.site,
  },
  {
    t: "Güvenlik kapısı + NFC",
    d: "Termal ön tarama, sonra panoya dokunuş: doğru pano, doğru bağlantı.",
    icon: "nfc",
    from: T.site,
    to: T.work,
  },
  {
    t: "Müdahale ve doğrulama",
    d: "Tork sonrası θ canlı izlenir; tabana dönünce iş emri kapanır.",
    icon: "wrench",
    from: T.work,
    to: 9999,
  },
];

const Steps: React.FC<{ frame: number }> = ({ frame }) => (
  <div style={{ position: "absolute", left: 120, top: 470, width: 560, display: "flex", flexDirection: "column", gap: 14 }}>
    {STEPS.map((s, i) => {
      const active = frame >= s.from && frame < s.to;
      const done = frame >= s.to || (i === STEPS.length - 1 && frame >= T.closed + 10);
      const a = interpolate(frame, [s.from, s.from + 14, s.to, s.to + 14], [0, 1, 1, 0], CLAMP);
      const color = done ? C.ok : active ? C.brand : C.dim;
      return (
        <div
          key={s.t}
          style={{
            borderRadius: 20,
            padding: "16px 22px",
            background: `rgba(18,26,37,${0.35 + 0.65 * a})`,
            border: `1.5px solid ${active ? C.brand + "aa" : done ? C.ok + "55" : C.line}`,
            boxShadow: active ? `0 18px 50px -20px ${C.brand}88` : "none",
            ...fadeSide(frame, 30 + i * 6, -40, 18),
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div
              style={{
                width: 46,
                height: 46,
                borderRadius: 14,
                display: "grid",
                placeItems: "center",
                background: color + "22",
                border: `1.5px solid ${color}`,
              }}
            >
              <Icon name={done ? "check" : s.icon} size={26} color={color} stroke={done ? 3 : 2} />
            </div>
            <div style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 32, color: active || done ? C.ink : C.muted }}>
              {s.t}
            </div>
          </div>
          <div
            style={{
              overflow: "hidden",
              height: 84 * a,
              opacity: a,
              fontFamily: F.sans,
              fontSize: 27,
              lineHeight: 1.35,
              color: C.muted,
              paddingTop: 10 * a,
            }}
          >
            {s.d}
          </div>
        </div>
      );
    })}
  </div>
);

/* ---------------- sağ: merkez konsolu ---------------- */
const STATES = [
  { at: T.notif, label: "KRİTİK · açık", color: C.kritik },
  { at: T.tapAccept, label: "ÜSTLENİLDİ · Ekip 3", color: C.izle },
  { at: T.nfc + 34, label: "SAHADA · NFC doğrulandı", color: C.uyari },
  { at: T.thetaDrop, label: "DOĞRULANIYOR", color: C.olcum },
  { at: T.closed, label: "KAPANDI", color: C.ok },
];

const LOG = [
  { at: T.notif, t: "09:41", m: "Alarm açıldı · θ 17,6 K" },
  { at: T.tapAccept, t: "09:42", m: "Ekip 3 üstlendi" },
  { at: T.nfc + 34, t: "10:05", m: "NFC: SOKE-14 · Ç7-L2" },
  { at: T.torque, t: "10:21", m: "Tork tamam · foto eklendi" },
  { at: T.closed, t: "10:32", m: "θ 1,0 K · iş emri kapandı" },
];

const Console: React.FC<{ frame: number }> = ({ frame }) => {
  let st = STATES[0];
  let stIdx = 0;
  STATES.forEach((s, i) => {
    if (frame >= s.at) {
      st = s;
      stIdx = i;
    }
  });
  const flash = 1 - prog(frame, STATES[stIdx].at, 20);
  return (
    <div style={{ position: "absolute", left: 1280, top: 160, width: 520, ...fadeSide(frame, 40, 50, 20) }}>
      <Card style={{ padding: "22px 26px" }} glow={flash > 0.05 ? st.color : undefined}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Icon name="grid" size={28} color={C.muted} />
          <span style={{ fontFamily: F.sans, fontWeight: 700, fontSize: 26, color: C.ink }}>Merkez · izleme konsolu</span>
        </div>
        <div
          style={{
            marginTop: 18,
            padding: "16px 18px",
            borderRadius: 16,
            background: C.bg2,
            border: `1.5px solid ${st.color}88`,
          }}
        >
          <div style={{ fontFamily: F.mono, fontSize: 24, color: C.muted }}>SOKE-14 · Ç7-L2</div>
          <div
            style={{
              marginTop: 10,
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "8px 16px",
              borderRadius: 10,
              fontFamily: F.sans,
              fontWeight: 800,
              fontSize: 24,
              letterSpacing: "0.04em",
              color: st.color,
              background: st.color + "22",
              border: `2px solid ${st.color}`,
              scale: String(1 + 0.08 * flash),
            }}
          >
            <span style={{ width: 11, height: 11, borderRadius: 99, background: st.color }} />
            {st.label}
          </div>
        </div>
        <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 4 }}>
          {LOG.map((l) => {
            if (frame < l.at) return null;
            return (
              <div
                key={l.m}
                style={{
                  display: "flex",
                  gap: 16,
                  fontFamily: F.mono,
                  fontSize: 22,
                  padding: "6px 0",
                  borderBottom: `1px solid ${C.line}`,
                  ...fadeSide(frame, l.at, 30, 14),
                }}
              >
                <span style={{ color: C.dim }}>{l.t}</span>
                <span style={{ color: C.ink }}>{l.m}</span>
              </div>
            );
          })}
        </div>
      </Card>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 22, ...fadeUp(frame, 64) }}>
        <Chip color={C.izle}>Onay kişiye ve olaya bağlı</Chip>
        <Chip color={C.izle}>Pano iş emri ≠ cihaz iş emri</Chip>
        <Chip color={C.izle}>Her adım kayda geçer</Chip>
      </div>
      <div style={{ marginTop: 22, ...fadeUp(frame, T.closed + 18, { dist: 30 }) }}>
        <Card glow={C.ok} style={{ padding: "20px 26px" }}>
          <div style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 32, color: C.ok }}>Arıza olmadan kapandı</div>
          <div style={{ fontFamily: F.sans, fontSize: 26, color: C.muted, marginTop: 6, lineHeight: 1.35 }}>
            ACİL'e 15 gün kala, planlı bir iş emriyle. Müşteri karanlıkta kalmadı.
          </div>
        </Card>
      </div>
    </div>
  );
};

/* Telefon ↔ merkez senkron akışı */
const SyncLine: React.FC<{ frame: number }> = ({ frame }) => {
  const x0 = PX + PW + 6;
  const x1 = 1280;
  const y = 330;
  const events = STATES.map((s) => s.at);
  return (
    <svg width={1920} height={1080} style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
      <line
        x1={x0}
        x2={x1}
        y1={y}
        y2={y}
        stroke={C.line2}
        strokeWidth={2}
        strokeDasharray="6 8"
        opacity={prog(frame, 50, 20)}
      />
      {events.map((at, i) => {
        const p = interpolate(frame, [at, at + 22], [0, 1], { ...CLAMP, easing: EASE_IN_OUT });
        if (p <= 0 || p >= 1) return null;
        const dir = i === 0 ? -1 : 1; // ilk olay merkezden telefona, diğerleri telefondan merkeze
        const x = dir === 1 ? x0 + (x1 - x0) * p : x1 - (x1 - x0) * p;
        return (
          <g key={at}>
            <circle cx={x} cy={y} r={9} fill={STATES[i].color} />
            <circle cx={x} cy={y} r={20} fill={STATES[i].color} opacity={0.25} />
          </g>
        );
      })}
    </svg>
  );
};

export const S15Mobil: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Backdrop accent={C.izle} second={C.brand} />
      {/* telefonun arkasındaki ışık */}
      <div
        style={{
          position: "absolute",
          left: 960 - 400,
          top: 140,
          width: 800,
          height: 800,
          borderRadius: 999,
          background: `radial-gradient(circle, ${frame >= T.closed ? C.ok : C.kritik}22, transparent 65%)`,
          opacity: 0.6 + 0.4 * pulse(frame, 60),
          pointerEvents: "none",
        }}
      />
      <div style={{ position: "absolute", left: 0, top: 0, width: 820, height: 460 }}>
        <SceneHeader
          kicker="06 · Alarm → Saha"
          title="Alarm sahaya iner, ekip *doğrudan* müdahale eder."
          size={60}
          delay={18}
        />
      </div>
      <div style={{ position: "absolute", left: 120, top: 396, ...fadeUp(frame, 44) }}>
        <Chip color={C.dim} style={{ fontSize: 22, padding: "6px 16px" }}>
          KONSEPT · saha ekibi mobil uygulaması
        </Chip>
      </div>
      <Steps frame={frame} />
      <Console frame={frame} />
      <Phone frame={frame} />
      <SyncLine frame={frame} />
    </AbsoluteFill>
  );
};
