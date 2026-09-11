"""PANO GOZ northbound SCADA interface - Modbus TCP, read-only.

This module is the ONE definition of the register map.  The live Modbus slave,
the generated ICD document, the point-list CSV and the UI's "SCADA" screen are
all produced from the tables below, so the map a judge polls with ``modpoll``
and the map printed in the PDF cannot drift apart.

Design decisions, and why
-------------------------

**Read-only, with no exceptions.**  Function codes 3 and 4 are served; 5, 6, 15
and 16 return exception 0x01 ILLEGAL_FUNCTION.  Modbus has no authentication.
An unauthenticated write path into a system that can command an ABB TVOC-2
self-test is the worst possible thing to ship, particularly since ABB does not
document whether arc protection is inhibited while diagnostics run.  The two
actuator paths that exist in PANO GOZ live behind operator authentication and a
physical key switch at the gateway, never on this bus.

**Addressing is 0-based PDU throughout.**  ``modpoll -0`` and the SCADA
configuration must both use raw addressing.  Modicon 4x notation is given in
the generated document for convenience only.

**Fixed stride, no holes, no version branches.**  Every panel occupies exactly
``REGS_PER_PANEL`` registers at ``PANEL_BASE + REGS_PER_PANEL * (n-1)``.  A
SCADA engineer configures one block and copies it 100 times.  Unpopulated
panels read as zero with ``DATA_VALID`` clear rather than raising an exception,
because a polling failure and an empty panel must look different.

**The two most valuable registers are ones the source devices cannot provide.**
``STATUS_WORD`` bit 8 says our link to the arc relay is down, and ``DATA_AGE_S``
says how stale this block is.  A conventional gateway silently republishes its
last good value forever; this one tells the truth about its own health.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

ICD_VERSION = "2.0.0"
ICD_VERSION_ENCODED = 20000  # major*10000 + minor*100 + patch

RegType = Literal["u16", "i16", "u32", "bits"]


@dataclass(frozen=True)
class Reg:
    """One register (or register pair) in the map."""

    offset: int
    name: str
    rtype: RegType
    scale: float
    unit: str
    label_tr: str
    note: str = ""

    @property
    def words(self) -> int:
        return 2 if self.rtype == "u32" else 1

    @property
    def raw_range(self) -> tuple[int, int]:
        if self.rtype == "u16" or self.rtype == "bits":
            return (0, 65535)
        if self.rtype == "i16":
            return (-32768, 32767)
        return (0, 4294967295)

    @property
    def eng_range(self) -> tuple[float, float]:
        lo, hi = self.raw_range
        return (lo * self.scale, hi * self.scale)


# --------------------------------------------------------------------------
# Bit definitions
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Bit:
    bit: int
    name: str
    label_tr: str
    note: str = ""


STATUS_BITS: tuple[Bit, ...] = (
    Bit(0, "DATA_VALID", "Veri geçerli", "0 ise bu blok doldurulmadı, alarm olarak yorumlamayın"),
    Bit(1, "STALE", "Veri bayat", f"DATA_AGE_S eşiği aşıldı"),
    Bit(2, "SENSITIVITY_LOW", "Görünürlük düşük", "Yük çok düşük, θ güvenilir değil"),
    Bit(3, "DE_ENERGISED", "Pano enerjisiz", "Akım yok, hiçbir ısıl gösterge anlamlı değil"),
    Bit(4, "LEARN_MODE", "Öğrenme modu", "Devreye alma sonrası 7 gün; mutlak limitler yine de aktif"),
    Bit(5, "SUPPRESSED", "Bastırılmış alarm var", "Gerekçesi alarm konsolunda kayıtlı"),
    Bit(6, "MAINTENANCE", "Bakım modu", "Operatör tarafından elle bastırıldı"),
    Bit(7, "ANALYSER_COMMS_LOST", "Analizör haberleşmesi yok", "Entes MPR-53CS RS-485"),
    Bit(8, "ARC_RELAY_COMMS_LOST", "Ark rölesi haberleşmesi yok", "ABB TVOC-2 RS-485 · cihazın kendisi bunu bildiremez"),
    Bit(9, "GATEWAY_COMMS_LOST", "Ağ geçidi çevrimdışı", ""),
    Bit(10, "MOUNT_LOST", "Sensör düştü/kaydı", "Mıknatıs kaide teması kayboldu"),
    Bit(11, "AIM_SHIFTED", "Termal dizi nişanı kaydı", "Referans noktaları eşleşmiyor"),
    Bit(12, "CELL_LOW", "Pil zayıf", ""),
    Bit(13, "CLOCK_UNSYNCED", "Saat senkron değil", ""),
    Bit(14, "CONFIG_MISMATCH", "Yapılandırma uyuşmazlığı", ""),
    Bit(15, "SELFTEST_DUE", "Ark otokontrolü gecikti", ""),
)

ARC_BITS: tuple[Bit, ...] = (
    Bit(0, "ACTIVE_TRIP", "Aktif açma", "TVOC-2 reg 1300 bit0"),
    Bit(1, "ACTIVE_ERROR", "Aktif hata", "TVOC-2 reg 1300 bit1"),
    Bit(2, "START_SEQUENCE", "Başlatma dizisi", "TVOC-2 reg 1300 bit2"),
    Bit(3, "DIAGNOSTICS_RUNNING", "Otokontrol çalışıyor", "TVOC-2 reg 1300 bit3"),
    Bit(4, "DETECTOR_FAULT", "Dedektör arızası", "reg 222/223 · yalnız FW >= 03.00.00"),
    Bit(5, "AMBIENT_WARNING", "Ortam ışığı uyarısı", "reg 224/225 · dedektör kör olabilir"),
    Bit(6, "COMMS_LOST", "Haberleşme yok", "PANO GÖZ tarafından üretilir"),
    Bit(7, "SELFTEST_DISABLED", "Otokontrol devre dışı", "ABB yazılı teyidi alınana kadar varsayılan"),
    Bit(8, "NOT_FITTED", "Ark rölesi takılı değil", "Bu panoda TVOC-2 yok"),
)

DEVICE_FAULT_BITS: tuple[Bit, ...] = tuple(
    Bit(i, f"DEV_{k}", f"{k} arızalı", "")
    for i, k in enumerate(
        ("TC01", "TC02", "TC03", "TC04", "TC05", "TC06", "TNIR", "PD01", "GW01")
    )
)

ENGINE_BITS: tuple[Bit, ...] = (
    Bit(0, "INGEST_OK", "Toplama servisi çalışıyor", ""),
    Bit(1, "DETECTOR_OK", "Dedektör çalışıyor", ""),
    Bit(2, "STORE_OK", "Veri tabanı erişilebilir", ""),
    Bit(3, "NOTIFY_OK", "Bildirim servisi çalışıyor", ""),
    Bit(4, "SMS_PATH_OK", "SMS yolu doğrulandı", ""),
    Bit(5, "STORM_ACTIVE", "Alarm fırtınası bastırma etkin", ""),
    Bit(6, "DEGRADED", "Sistem düşük kapasitede", ""),
)


# --------------------------------------------------------------------------
# Global block - unit id 1, PDU 0..GLOBAL_SIZE-1
# --------------------------------------------------------------------------

GLOBAL_BASE = 0
GLOBAL_SIZE = 32

GLOBAL_REGS: tuple[Reg, ...] = (
    Reg(0, "ICD_VERSION", "u32", 1, "-", "ICD sürümü", "majör*10000 + minör*100 + yama"),
    Reg(2, "PANEL_COUNT", "u16", 1, "adet", "Tanımlı pano sayısı", ""),
    Reg(3, "PANELS_ONLINE", "u16", 1, "adet", "Çevrimiçi pano sayısı", ""),
    Reg(4, "FLEET_WORST_SEVERITY", "u16", 1, "-", "Filodaki en yüksek seviye", "0 BILGI · 1 IZLE · 2 UYARI · 3 KRITIK · 4 ACIL"),
    Reg(5, "FLEET_ALARMS_ACTIVE", "u16", 1, "adet", "Aktif alarm", ""),
    Reg(6, "FLEET_ALARMS_CRITICAL", "u16", 1, "adet", "Kritik ve üzeri alarm", ""),
    Reg(7, "WATCHDOG_HEARTBEAT", "u16", 1, "-", "Canlılık sayacı", "Her saniye artar, 65535'te sarar. Durursa PANO GÖZ ölmüştür."),
    Reg(8, "SERVER_TIME", "u32", 1, "s", "Sunucu zamanı", "Unix epoch, UTC"),
    Reg(10, "ENGINE_STATE", "bits", 1, "-", "Motor durumu", "ENGINE_BITS"),
    Reg(11, "DETECTOR_LAG_S", "u16", 1, "s", "Dedektör gecikmesi", "Son tamamlanan çevrimden beri geçen süre"),
    Reg(12, "REGS_PER_PANEL", "u16", 1, "-", "Pano blok boyu", "Sabit"),
    Reg(13, "PANEL_BLOCK_BASE", "u32", 1, "-", "İlk pano blok adresi", ""),
    Reg(15, "FLEET_HEALTH_MIN", "u16", 1, "-", "En düşük sağlık endeksi", ""),
    Reg(16, "FLEET_HEALTH_MEAN", "u16", 1, "-", "Ortalama sağlık endeksi", ""),
    Reg(17, "DISPATCH_QUEUE", "u16", 1, "adet", "Ekip yönlendirme kuyruğu", ""),
    Reg(18, "SUPPRESSED_24H", "u16", 1, "adet", "Son 24 saatte bastırılan alarm", "Gerekçeleriyle birlikte kayıtlı"),
    Reg(19, "PANELS_SENSITIVITY_LOW", "u16", 1, "adet", "Görünürlüğü düşük pano", "Bu panolarda θ geçici olarak güvenilir değil"),
)


# --------------------------------------------------------------------------
# Per-panel block
# --------------------------------------------------------------------------

PANEL_BASE = 1000
REGS_PER_PANEL = 48
MAX_PANELS = 200  # 1000 + 48*200 = 10600, still comfortably inside 5-digit 4x

PANEL_REGS: tuple[Reg, ...] = (
    Reg(0, "PANEL_ID", "u32", 1, "-", "Pano kimliği", "Sayısal varlık numarası"),
    Reg(2, "HEALTH_INDEX", "u16", 1, "-", "Sağlık endeksi", "100 sağlıklı, 0 en kötü"),
    Reg(3, "SEVERITY", "u16", 1, "-", "Seviye", "0 BILGI · 1 IZLE · 2 UYARI · 3 KRITIK · 4 ACIL"),
    Reg(4, "STATUS_WORD", "bits", 1, "-", "Durum bitleri", "STATUS_BITS"),
    Reg(5, "ACTIVE_ALARMS", "u16", 1, "adet", "Aktif alarm sayısı", ""),
    Reg(6, "THETA_MAX", "i16", 0.1, "K", "En kötü θ", "Anma akımında sıcaklık fazlası"),
    Reg(7, "THETA_MAX_JOINT", "u16", 1, "-", "En kötü bağlantı indeksi", "JOINTS dizisindeki sıra"),
    Reg(8, "THETA_SLOPE", "i16", 0.001, "K/hafta", "θ eğimi", "Pozitif ise bozulma sürüyor"),
    Reg(9, "SENSITIVITY_PCT", "u16", 1, "%", "Görünürlük", "Yüke bağlı tespit yeteneği"),
    Reg(10, "RISK_LOOSE", "u16", 0.1, "%", "Gevşek bağlantı riski", ""),
    Reg(11, "RISK_OVERLOAD", "u16", 0.1, "%", "Aşırı yük riski", ""),
    Reg(12, "RISK_ARC_INTEGRITY", "u16", 0.1, "%", "Ark koruma bütünlüğü riski", ""),
    Reg(13, "RISK_THERMAL", "u16", 0.1, "%", "Isıl kaçış riski", ""),
    Reg(14, "RISK_HARMONIC", "u16", 0.1, "%", "Harmonik nötr riski", ""),
    Reg(15, "RISK_MOISTURE", "u16", 0.1, "%", "Nem / yoğuşma riski", ""),
    Reg(16, "RISK_INSULATION", "u16", 0.1, "%", "Yalıtım riski", ""),
    Reg(17, "T_JOINT_MAX", "i16", 0.1, "°C", "En yüksek bağlantı sıcaklığı", ""),
    Reg(18, "T_AIR", "i16", 0.1, "°C", "Kabin içi hava", ""),
    Reg(19, "RH", "u16", 0.1, "%", "Bağıl nem", ""),
    Reg(20, "DEWPOINT_MARGIN", "i16", 0.1, "K", "Yoğuşma payı", "Negatif ise yüzeyde yoğuşma var"),
    Reg(21, "I_L1", "u16", 0.1, "A", "L1 akımı", ""),
    Reg(22, "I_L2", "u16", 0.1, "A", "L2 akımı", ""),
    Reg(23, "I_L3", "u16", 0.1, "A", "L3 akımı", ""),
    Reg(24, "I_N", "u16", 0.1, "A", "Nötr akımı", ""),
    Reg(25, "V_L1", "u16", 0.1, "V", "L1 gerilimi", ""),
    Reg(26, "V_L2", "u16", 0.1, "V", "L2 gerilimi", ""),
    Reg(27, "V_L3", "u16", 0.1, "V", "L3 gerilimi", ""),
    Reg(28, "FREQ", "u16", 0.01, "Hz", "Frekans", ""),
    Reg(29, "THD_V_MAX", "u16", 0.1, "%", "En yüksek gerilim THD", ""),
    Reg(30, "THD_I_MAX", "u16", 0.1, "%", "En yüksek akım THD", "I > CT anmasının %10'u değilse 0"),
    Reg(31, "LOAD_FACTOR", "u16", 0.1, "%", "Yük faktörü", "Anma akımına göre"),
    Reg(32, "PD_RATE", "u16", 1, "1/s", "RF darbe hızı", ""),
    Reg(33, "PD_QMAX", "u16", 0.1, "dB", "RF tepe genlik", "pC eşdeğeri, IEC 60270 izlenebilir DEĞİL"),
    Reg(34, "PD_CLASS", "u16", 1, "-", "PRPD sınıfı", "0 GURULTU · 1 BOSLUK · 2 YUZEY · 3 KORONA · 4 YUZEN"),
    Reg(35, "TEV_LEVEL", "u16", 0.1, "dB", "TEV seviyesi", ""),
    Reg(36, "ARC_STATE", "bits", 1, "-", "Ark koruma durumu", "ARC_BITS"),
    Reg(37, "ARC_DETECTORS_OK", "u16", 1, "adet", "Sağlam dedektör", ""),
    Reg(38, "ARC_DETECTORS_TOTAL", "u16", 1, "adet", "Kurulu dedektör", ""),
    Reg(39, "ARC_AMBIENT_WARN", "u16", 1, "adet", "Işık uyarısı veren dedektör", ""),
    Reg(40, "ARC_DETECTOR_MAP_LO", "bits", 1, "-", "Dedektör haritası düşük", "TVOC-2 reg 210 aynası · X1:1-10, X2:1-5"),
    Reg(41, "ARC_DETECTOR_MAP_HI", "bits", 1, "-", "Dedektör haritası yüksek", "TVOC-2 reg 211 aynası · X2:6-10, X3:1-10"),
    Reg(42, "ARC_LAST_SELFTEST_D", "u16", 1, "gün", "Son otokontrolden beri", ""),
    Reg(43, "DEVICES_ONLINE", "u16", 1, "adet", "Çevrimiçi cihaz", "9 üzerinden"),
    Reg(44, "DEVICE_FAULT_MAP", "bits", 1, "-", "Cihaz arıza haritası", "DEVICE_FAULT_BITS"),
    Reg(45, "DATA_AGE_S", "u16", 1, "s", "Veri yaşı", "Son başarılı güncellemeden beri geçen saniye"),
    Reg(46, "UPDATED_AT", "u32", 1, "s", "Son güncelleme", "Unix epoch, UTC"),
)

#: Above this age the STALE bit is set and SCADA should treat the block as
#: unreliable.  Chosen as three times a 30 s SCADA poll cycle.
STALE_AFTER_S = 90


# --------------------------------------------------------------------------
# Consistency checks - run at import so a broken map cannot be served
# --------------------------------------------------------------------------

def _check(regs: Sequence[Reg], size: int, what: str) -> None:
    used: dict[int, str] = {}
    for r in regs:
        for w in range(r.words):
            off = r.offset + w
            if off in used:
                raise ValueError(f"{what}: offset {off} used by {used[off]} and {r.name}")
            if off >= size:
                raise ValueError(f"{what}: {r.name} at {off} exceeds block size {size}")
            used[off] = r.name
    names = [r.name for r in regs]
    if len(names) != len(set(names)):
        raise ValueError(f"{what}: duplicate register name")


_check(GLOBAL_REGS, GLOBAL_SIZE, "global block")
_check(PANEL_REGS, REGS_PER_PANEL, "panel block")

GLOBAL_BY_NAME: dict[str, Reg] = {r.name: r for r in GLOBAL_REGS}
PANEL_BY_NAME: dict[str, Reg] = {r.name: r for r in PANEL_REGS}


def panel_base(index: int) -> int:
    """PDU address of panel ``index`` (1-based)."""
    if not 1 <= index <= MAX_PANELS:
        raise ValueError(f"panel index {index} outside 1..{MAX_PANELS}")
    return PANEL_BASE + REGS_PER_PANEL * (index - 1)


TOP_ADDRESS = PANEL_BASE + REGS_PER_PANEL * MAX_PANELS - 1


# --------------------------------------------------------------------------
# Encoding helpers
# --------------------------------------------------------------------------

def encode(reg: Reg, value: float | int | None) -> list[int]:
    """Engineering value -> Modbus words, saturating rather than wrapping.

    Saturation matters: a wrapped register looks like a plausible small number
    and would silently mislead SCADA, while a saturated one pins at full scale
    and is obviously out of range.
    """
    if value is None:
        return [0] * reg.words
    lo, hi = reg.raw_range
    raw = int(round(float(value) / reg.scale))
    raw = max(lo, min(hi, raw))
    if reg.rtype == "u32":
        raw &= 0xFFFFFFFF
        return [(raw >> 16) & 0xFFFF, raw & 0xFFFF]  # big-endian, high word first
    if reg.rtype == "i16":
        return [raw & 0xFFFF]
    return [raw & 0xFFFF]


def decode(reg: Reg, words: Sequence[int]) -> float:
    if reg.rtype == "u32":
        raw = ((words[0] & 0xFFFF) << 16) | (words[1] & 0xFFFF)
    else:
        raw = words[0] & 0xFFFF
        if reg.rtype == "i16" and raw >= 0x8000:
            raw -= 0x10000
    return raw * reg.scale


def pack_bits(bits: Sequence[Bit], flags: dict[str, bool] | set[str]) -> int:
    """Build a bitfield from a set or dict of set flag names."""
    on = flags if isinstance(flags, (set, frozenset)) else {k for k, v in flags.items() if v}
    word = 0
    for b in bits:
        if b.name in on:
            word |= 1 << b.bit
    return word


def unpack_bits(bits: Sequence[Bit], word: int) -> list[str]:
    return [b.name for b in bits if word & (1 << b.bit)]


# --------------------------------------------------------------------------
# Document generation
# --------------------------------------------------------------------------

def _rows(regs: Sequence[Reg], base: int) -> list[dict]:
    out = []
    for r in regs:
        pdu = base + r.offset
        elo, ehi = r.eng_range
        out.append(
            {
                "pdu_dec": pdu,
                "pdu_hex": f"0x{pdu:04X}",
                "modicon_4x": 40001 + pdu,
                "offset": r.offset,
                "name": r.name,
                "type": r.rtype,
                "words": r.words,
                "scale": r.scale,
                "unit": r.unit,
                "eng_min": round(elo, 4),
                "eng_max": round(ehi, 4),
                "label_tr": r.label_tr,
                "note": r.note,
            }
        )
    return out


def point_list() -> list[dict]:
    """Flat point list for the generated CSV / SCADA import."""
    rows = [dict(block="GLOBAL", **r) for r in _rows(GLOBAL_REGS, GLOBAL_BASE)]
    rows += [dict(block="PANEL[n]", **r) for r in _rows(PANEL_REGS, PANEL_BASE)]
    return rows


def to_csv() -> str:
    import csv
    import io

    rows = point_list()
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def _bit_table(title: str, bits: Sequence[Bit]) -> str:
    out = [f"### {title}", "", "| Bit | Ad | Anlam | Not |", "|---:|---|---|---|"]
    for b in bits:
        out.append(f"| {b.bit} | `{b.name}` | {b.label_tr} | {b.note} |")
    out.append("")
    return "\n".join(out)


def _reg_table(regs: Sequence[Reg], base: int) -> str:
    out = [
        "| PDU (dec) | PDU (hex) | 4x | Ofset | Ad | Tip | Ölçek | Birim | Aralık | Anlam | Not |",
        "|---:|---|---:|---:|---|---|---:|---|---|---|---|",
    ]
    for r in regs:
        pdu = base + r.offset
        elo, ehi = r.eng_range
        rng = f"{elo:g} … {ehi:g}"
        out.append(
            f"| {pdu} | 0x{pdu:04X} | {40001 + pdu} | +{r.offset} | `{r.name}` | {r.rtype} | "
            f"{r.scale:g} | {r.unit} | {rng} | {r.label_tr} | {r.note} |"
        )
    out.append("")
    return "\n".join(out)


def to_markdown() -> str:
    ex = panel_base(14)
    parts = [
        f"# PANO GÖZ · SCADA Arayüz Kontrol Dokümanı (ICD) v{ICD_VERSION}",
        "",
        "**Protokol:** Modbus TCP · **Rol:** slave (server) · **Port:** 502 (yapılandırılabilir)",
        "",
        "**Desteklenen fonksiyon kodları:** 03 (Read Holding Registers), 04 (Read Input Registers).",
        "Her ikisi de aynı adres uzayını okur.",
        "",
        "**Reddedilen fonksiyon kodları:** 05, 06, 15, 16 → exception `0x01 ILLEGAL_FUNCTION`.",
        "Bu harita **salt okunurdur ve istisnası yoktur.** Modbus'ta kimlik doğrulama yoktur;",
        "ark koruma rölesine otokontrol komutu verebilen bir sisteme kimliksiz yazma yolu açmak",
        "kabul edilebilir değildir. PANO GÖZ'deki iki aktüatör yolu (TVOC-2 reg 213 otokontrol ve",
        "reg 1000 açma sıfırlama) ağ geçidinde, operatör kimlik doğrulaması ve fiziksel anahtar",
        "arkasındadır; bu bus üzerinden erişilemez.",
        "",
        "**Adresleme:** tüm adresler 0 tabanlı PDU'dur. `modpoll` ile `-0` bayrağını kullanın.",
        "Modicon 4x sütunu yalnızca kolaylık içindir.",
        "",
        "**32 bit değerler:** big-endian, yüksek word önce (ABCD).",
        "",
        "**Doygunluk:** aralık dışı değerler sarmaz, tam ölçekte doyar. Sarmış bir register",
        "makul küçük bir sayı gibi görünür ve SCADA'yı sessizce yanıltır; doymuş bir register",
        "ise açıkça aralık dışıdır.",
        "",
        f"**Bayatlık:** `DATA_AGE_S` > {STALE_AFTER_S} s olduğunda `STATUS_WORD.STALE` kurulur.",
        "Bu değer tipik 30 s'lik SCADA tarama çevriminin üç katıdır.",
        "",
        "---",
        "",
        "## 1. Adres planı",
        "",
        "| Blok | Unit ID | PDU aralığı | Boyut |",
        "|---|---:|---|---:|",
        f"| Global | 1 | {GLOBAL_BASE} … {GLOBAL_BASE + GLOBAL_SIZE - 1} | {GLOBAL_SIZE} register |",
        f"| Pano n (1…{MAX_PANELS}) | 1 | {PANEL_BASE} + {REGS_PER_PANEL}·(n−1) | {REGS_PER_PANEL} register |",
        "",
        f"Sabit adım, delik yok, sürüm dalı yok. SCADA mühendisi tek blok tanımlar ve {MAX_PANELS}",
        "kez kopyalar. Tanımsız pano bloğu sıfır okur ve `DATA_VALID` biti temizdir; tarama hatası",
        "ile boş pano birbirinden ayırt edilebilir olmalıdır.",
        "",
        f"Örnek: 14 numaralı pano → PDU {ex} … {ex + REGS_PER_PANEL - 1} (4x: {40001 + ex} …).",
        "",
        "Doğrulama komutu:",
        "",
        "```",
        "modpoll -m tcp -0 -r 0    -c 20  <sunucu>     # global blok",
        f"modpoll -m tcp -0 -r {ex} -c {REGS_PER_PANEL}  <sunucu>     # 14 numaralı pano",
        "```",
        "",
        "---",
        "",
        "## 2. Global blok",
        "",
        _reg_table(GLOBAL_REGS, GLOBAL_BASE),
        "---",
        "",
        "## 3. Pano bloğu",
        "",
        _reg_table(PANEL_REGS, PANEL_BASE),
        "---",
        "",
        "## 4. Bit alanları",
        "",
        _bit_table("STATUS_WORD (pano +4)", STATUS_BITS),
        _bit_table("ARC_STATE (pano +36)", ARC_BITS),
        _bit_table("DEVICE_FAULT_MAP (pano +44)", DEVICE_FAULT_BITS),
        _bit_table("ENGINE_STATE (global +10)", ENGINE_BITS),
        "---",
        "",
        "## 5. Diğer protokoller",
        "",
        "IEC 60870-5-104 tercih edilen güney yönlü arayüzdür; alarmlarımız olay biçimlidir ve",
        "104'ün spontane COT=3 gönderimi bunu Modbus taramasından daha iyi taşır. Nokta adresi",
        "`IOA = pano_no * 1000 + nokta_no`, ölçümler `M_ME_NC_1` kısa kayan nokta, zaman damgası",
        "`CP56Time2a`. OPC UA ise varlık yönetimi tarafına `PanelType` bilgi modeli + Part 9",
        "Alarms & Conditions ile hizmet eder. Her üç arayüz de aynı 1 Hz canlı görüntüyü okur.",
        "",
        "Bu hackathon kapsamında **yalnız Modbus TCP slave çalışır durumda teslim edilmiştir.**",
        "104 ve OPC UA nokta listeleri tablo olarak yazılmıştır, sunucuları kurulmamıştır.",
        "",
    ]
    return "\n".join(parts)


if __name__ == "__main__":  # pragma: no cover
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "csv":
        sys.stdout.write(to_csv())
    else:
        sys.stdout.write(to_markdown())
