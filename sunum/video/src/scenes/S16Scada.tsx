import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Card, Em, Icon } from "../ui/primitives";
import { countUp, fadeSide, fadeUp, prog, pulse } from "../ui/motion";
import { C, CLAMP, EASE_OUT, F } from "../theme";

/* 16 · SCADA: MODBUS HARİTALAMA
   Taban adres formülü hesaplanır (1624), 48 register'lık blok dolar, register tablosu kayar.
   Kaynak cihazların üretemediği iki register parlar. Yazma denemesi: exception 0x01. */

type Reg = { o: string; n: string; raw: string; eng: string; color?: string; star?: boolean };

const REGS: Reg[] = [
  { o: "+0", n: "PANEL_ID", raw: "14", eng: "14" },
  { o: "+2", n: "HEALTH_INDEX", raw: "67", eng: "67" },
  { o: "+4", n: "STATUS_WORD", raw: "0x0000", eng: "bit 8 · ark rölesi bağı", star: true },
  { o: "+6", n: "THETA_MAX", raw: "176", eng: "× 0,1 = 17,6 K", color: C.olcum },
  { o: "+7", n: "THETA_MAX_JOINT", raw: "25", eng: "Ç7-L2" },
  { o: "+8", n: "THETA_SLOPE", raw: "3013", eng: "3,01 K/hf" },
  { o: "+45", n: "DATA_AGE_S", raw: "2", eng: "2 sn · veri yaşı", star: true },
];
const KEY_CELLS = [0, 2, 6, 7, 8, 9, 45];
const STAR_CELLS = [4, 45];

const CMD = "$ modpoll -m tcp -0 -r 1624 -p 5020 127.0.0.1 1";
const ROW_START = 100;
const STAR_AT = 202;
const CMD_START = 232;
const ERR_AT = 266;

export const S16Scada: React.FC = () => {
  const frame = useCurrentFrame();

  const addr = Math.round(countUp(frame, 74, 34, 1000, 1624));
  const cmdChars = Math.round(interpolate(frame, [CMD_START, CMD_START + 28], [0, CMD.length], CLAMP));
  const err = prog(frame, ERR_AT, 10);
  const star = prog(frame, STAR_AT, 14);
  const shake = frame >= ERR_AT && frame < ERR_AT + 12 ? Math.sin(frame * 2.6) * 6 * (1 - (frame - ERR_AT) / 12) : 0;

  return (
    <AbsoluteFill>
      <Backdrop accent={C.izle} second={C.brand} />
      <SceneHeader kicker="07 · Entegrasyon" title="Tek blok tanımla, *yüz* *kez* kopyala." accent={C.izle} />

      {/* sol üst: taban adres */}
      <div style={{ position: "absolute", left: 120, top: 330, ...fadeUp(frame, 28) }}>
        <Card style={{ width: 640, height: 176, padding: "20px 30px" }}>
          <div style={{ fontFamily: F.sans, fontSize: 24, color: C.muted }}>Pano n'in taban adresi</div>
          <div style={{ fontFamily: F.mono, fontSize: 38, color: C.ink, marginTop: 8 }}>1000 + 48 × (n − 1)</div>
          <div
            style={{
              fontFamily: F.mono,
              fontSize: 38,
              fontWeight: 700,
              color: C.brand,
              marginTop: 4,
              ...fadeSide(frame, 52, -30),
            }}
          >
            1000 + 48 × 13 ={" "}
            <span
              style={{
                color: frame >= 108 ? C.olcum : C.brand,
                textShadow: frame >= 108 ? `0 0 ${18 * (1 - prog(frame, 108, 30))}px ${C.olcum}` : "none",
              }}
            >
              {addr}
            </span>
          </div>
        </Card>
      </div>

      {/* sol orta: 48 register'lık blok */}
      <div style={{ position: "absolute", left: 120, top: 524, ...fadeUp(frame, 56) }}>
        <Card style={{ width: 640, height: 256, padding: "18px 30px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <span style={{ fontFamily: F.sans, fontSize: 24, fontWeight: 700, color: C.ink }}>SOKE-14 · 48 register</span>
            <span style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: F.mono, fontSize: 20, color: C.ok }}>
              <Icon name="lock" size={22} color={C.ok} stroke={2} /> salt okunur
            </span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(12, 1fr)", gap: 6, marginTop: 14 }}>
            {Array.from({ length: 48 }, (_, i) => {
              const p = prog(frame, 66 + i * 1.1, 10);
              const key = KEY_CELLS.includes(i);
              const st = STAR_CELLS.includes(i);
              const lit = st ? star : 0;
              return (
                <div
                  key={i}
                  style={{
                    height: 38,
                    borderRadius: 7,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontFamily: F.mono,
                    fontSize: 18,
                    fontWeight: 700,
                    color: st && lit > 0.5 ? C.bg : key ? C.olcum : C.dim,
                    background:
                      st && lit > 0.5
                        ? C.brand
                        : key
                          ? "rgba(255,234,70,.14)"
                          : "rgba(74,163,255,.08)",
                    border: `1.5px solid ${st && lit > 0.5 ? C.brand : key ? C.olcum + "88" : C.line2}`,
                    boxShadow: st && lit > 0.5 ? `0 0 ${10 + 10 * pulse(frame, 30)}px ${C.brand}` : "none",
                    opacity: p,
                    scale: String(0.6 + 0.4 * p),
                  }}
                >
                  {key || st ? i : ""}
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* sol alt: tam tarama */}
      <div style={{ position: "absolute", left: 120, top: 798, ...fadeUp(frame, 124) }}>
        <Card style={{ width: 640, height: 104, padding: "14px 26px", display: "flex", justifyContent: "space-between" }}>
          {[
            { v: Math.round(countUp(frame, 130, 30, 0, 4800)).toLocaleString("tr-TR"), l: "register · 100 pano" },
            { v: "≥ " + Math.round(countUp(frame, 140, 26, 0, 39)), l: "istek · FC03 ≤ 125" },
            { v: Math.round(countUp(frame, 150, 26, 0, 19)) + " ms", l: "ölçülen" },
          ].map((s) => (
            <div key={s.l}>
              <div style={{ fontFamily: F.mono, fontSize: 40, fontWeight: 700, color: C.ok, lineHeight: 1.1 }}>{s.v}</div>
              <div style={{ fontFamily: F.sans, fontSize: 20, color: C.muted }}>{s.l}</div>
            </div>
          ))}
        </Card>
      </div>

      {/* sağ: register tablosu */}
      <div style={{ position: "absolute", left: 800, top: 330, ...fadeUp(frame, 84) }}>
        <Card style={{ width: 1000, height: 416, padding: "16px 30px" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "90px 300px 140px 1fr",
              fontFamily: F.mono,
              fontSize: 20,
              color: C.dim,
              letterSpacing: "0.08em",
              paddingBottom: 8,
              borderBottom: `1.5px solid ${C.line2}`,
            }}
          >
            <span>OFSET</span>
            <span>REGISTER</span>
            <span>HAM</span>
            <span>MÜHENDİSLİK</span>
          </div>
          {REGS.map((r, i) => {
            const p = prog(frame, ROW_START + i * 12, 16);
            const hl = r.star ? star : 0;
            const th = r.n === "THETA_MAX" ? prog(frame, 150, 16) : 0;
            return (
              <div
                key={r.n}
                style={{
                  display: "grid",
                  gridTemplateColumns: "90px 300px 140px 1fr",
                  alignItems: "center",
                  height: 40,
                  marginTop: 3,
                  padding: "0 0 0 0",
                  borderRadius: 10,
                  fontFamily: F.mono,
                  fontSize: 25,
                  color: C.ink,
                  background: hl
                    ? `rgba(247,131,32,${0.16 * hl})`
                    : th
                      ? `rgba(255,234,70,${0.1 * th})`
                      : "transparent",
                  boxShadow: hl ? `inset 0 0 0 2px rgba(247,131,32,${0.85 * hl})` : "none",
                  opacity: p,
                  translate: `${(1 - p) * 60}px 0px`,
                }}
              >
                <span style={{ color: C.dim, paddingLeft: 8 }}>{r.o}</span>
                <span style={{ fontWeight: 700 }}>{r.n}</span>
                <span style={{ color: C.muted }}>{r.raw}</span>
                <span style={{ color: r.star && hl > 0.5 ? C.brand2 : r.color ?? C.ink, fontWeight: 700 }}>{r.eng}</span>
              </div>
            );
          })}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              marginTop: 10,
              fontFamily: F.sans,
              fontSize: 22,
              color: C.ink,
              ...fadeUp(frame, STAR_AT + 8, { dist: 10 }),
            }}
          >
            <span
              style={{
                width: 14,
                height: 14,
                borderRadius: 4,
                background: C.brand,
                boxShadow: `0 0 10px ${C.brand}`,
                flexShrink: 0,
              }}
            />
            Kaynak cihazların <b style={{ color: C.brand2 }}>üretemediği</b> iki register: ark rölesiyle bağ koptu · veri
            ne kadar bayat
          </div>
        </Card>
      </div>

      {/* sağ alt: yazma denemesi */}
      <div style={{ position: "absolute", left: 800, top: 764, ...fadeUp(frame, 150) }}>
        <div
          style={{
            translate: `${shake}px 0px`,
            width: 1000,
            height: 138,
            borderRadius: 18,
            background: "#04060a",
            border: `1.5px solid ${err > 0.5 ? C.kritik + "aa" : C.line2}`,
            boxShadow: err > 0.5 ? `0 0 40px -10px ${C.kritik}` : "none",
            padding: "16px 26px",
            fontFamily: F.mono,
            position: "relative",
          }}
        >
          <div style={{ fontSize: 24, color: C.ink }}>
            <span style={{ color: C.ok }}>$</span>
            {CMD.slice(1, Math.max(1, cmdChars))}
            {cmdChars < CMD.length && Math.floor(frame / 8) % 2 === 0 ? <span style={{ color: C.izle }}> ▍</span> : null}
          </div>
          <div style={{ fontSize: 24, fontWeight: 700, color: C.kritik, marginTop: 8, opacity: err }}>
            Illegal Function exception response! (0x01)
          </div>
          <div style={{ fontSize: 20, color: C.dim, marginTop: 6, opacity: prog(frame, ERR_AT + 10, 12) }}>
            FC 05/06/15/16 istisnasız reddedilir · Modbus'ta kimlik doğrulama yok
          </div>
          <div
            style={{
              position: "absolute",
              right: 26,
              top: 26,
              width: 88,
              height: 88,
              borderRadius: 22,
              background: `${C.kritik}1f`,
              border: `2px solid ${C.kritik}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              opacity: err,
              scale: String(interpolate(frame, [ERR_AT, ERR_AT + 14], [0.4, 1], { ...CLAMP, easing: Easing.out(Easing.back(2.2)) })),
            }}
          >
            <Icon name="lock" size={50} color={C.kritik} stroke={2} />
          </div>
        </div>
      </div>

      <Narration
        lines={[
          {
            from: 22,
            to: 108,
            text: (
              <>
                Her pano sabit adımlı, deliksiz bir blok. 14 numaralı panonun adresi kafadan atılmadı:{" "}
                <Em color={C.olcum}>1624</Em>.
              </>
            ),
          },
          {
            from: 112,
            to: 198,
            text: (
              <>
                THETA_MAX ham 176 × 0,1 = <Em color={C.olcum}>17,6 K</Em> — arayüzdeki sayıyla aynı nesneden gelir,
                çelişemez.
              </>
            ),
          },
          {
            from: 202,
            to: 262,
            text: (
              <>
                Klasik ağ geçidi son iyi değeri sessizce yayınlar; bizimki <Em>kendi sağlığını</Em> da söyler.
              </>
            ),
          },
          {
            from: 266,
            to: 328,
            text: (
              <>
                Yazma denemesi: <Em color={C.kritik}>exception 0x01</Em>. Kimliksiz bir protokolde yazma yolu istisnasız
                kapalı.
              </>
            ),
          },
        ]}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          background: `radial-gradient(800px 300px at 68% 80%, ${C.kritik}1c, transparent 70%)`,
          opacity: interpolate(frame, [ERR_AT, ERR_AT + 6, ERR_AT + 50], [0, 1, 0.4], { ...CLAMP, easing: EASE_OUT }),
        }}
      />
    </AbsoluteFill>
  );
};
