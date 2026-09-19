"""PANO GÖZ ICD v2.0: pano başına 32 register'lık Modbus bloğunun TEK gerçek kaynağı.

Nokta listesi burada VERİ olarak tanımlanır; Modbus veri deposu, CSV nokta listesi ve
docs/PANOGOZ-ICD-v2.0.md bu listeden ÜRETİLİR (tools/gen_icd.py). tests/test_icd.py
üretilmiş dokümanın diskteki dosyayla birebir aynı olduğunu doğrular: ICD ile kod
ayrışırsa test kırılır (CLAUDE.md K2 2.5).

Protokol: yalnız Input Register (FC04), salt okunur. Tüm değerler 16 bit: işaretsiz (u16),
işaretli (s16, two's complement) veya bit alanı (bits). Ölçek: değer = ham / scale.
Pano p'nin bloğu: taban = p * BLOCK_SIZE (0 tabanlı pano indeksi), en çok MAX_PANELS pano.

Eski v1 haritası (8 register/bağlantı, panogoz/scada/register_map.py) `tools/run_modbus_server.py`
için korunur; v2 ondan bağımsızdır.
"""
from __future__ import annotations

from dataclasses import dataclass

ICD_VERSION = (2, 0, 0)
ICD_VERSION_CODE = 200  # 2.0.0 -> 200 (bloğun son register'ında)
BLOCK_SIZE = 32
MAX_PANELS = 200
AGE_SATURATION_S = 0xFFFF

# ---- IEC 60870-5-104 nokta adresleme (aynı 32'lik blok; K2 2.3) ----
IEC104_COMMON_ADDRESS = 1
IEC104_FLAG_IOA_BASE = 10000  # bayrak bit'i tekil nokta: 10001 + pano*8 + bit
FLAG_BIT_COUNT = 7


@dataclass(frozen=True)
class Point:
    offset: int
    name: str
    dtype: str  # "u16" | "s16" | "bits"
    scale: float
    unit: str
    description: str
    source: str  # verinin sistemdeki kaynağı (docs/09 §2 ile aynı adlar)


def _p(offset: int, name: str, dtype: str, scale: float, unit: str, description: str, source: str) -> Point:
    return Point(offset, name, dtype, scale, unit, description, source)


POINTS: tuple[Point, ...] = (
    _p(0, "SEVERITY_CODE", "u16", 1, "", "Pano şiddeti: 0 NORMAL, 1 UYARI, 2 ALARM, 3 KRİTİK (süreç izlerinin en yükseği)", "rules/pipeline: fused"),
    _p(1, "ALARMS_OPEN", "u16", 1, "adet", "Onay bekleyen (OPEN) alarm sayısı", "rules/alarms"),
    _p(2, "ALARMS_ACTIVE", "u16", 1, "adet", "Aktif (OPEN + ACKED) alarm sayısı", "rules/alarms"),
    _p(3, "FLAGS", "bits", 1, "", "Bit alanı, aşağıdaki FLAG_BITS tablosuna bakın", "detector/flags + rules"),
    _p(4, "THETA_MAX_X10", "s16", 10, "K", "En yüksek |θ| (üç faz, kardeş medyanına göre, süzülmüş I²'ye normalize)", "detector/theta"),
    _p(5, "CURRENT_L1_X10", "u16", 10, "A", "L1 akımı", "CT / MPR-53CS"),
    _p(6, "CURRENT_L2_X10", "u16", 10, "A", "L2 akımı", "CT / MPR-53CS"),
    _p(7, "CURRENT_L3_X10", "u16", 10, "A", "L3 akımı", "CT / MPR-53CS"),
    _p(8, "NEUTRAL_CURRENT_X10", "u16", 10, "A", "Nötr akımı", "CT / MPR-53CS"),
    _p(9, "JOINT_TEMP_L1_X10", "s16", 10, "°C", "L1 bağlantı sıcaklığı", "MAX31855 (TC düğümü)"),
    _p(10, "JOINT_TEMP_L2_X10", "s16", 10, "°C", "L2 bağlantı sıcaklığı", "MAX31855 (TC düğümü)"),
    _p(11, "JOINT_TEMP_L3_X10", "s16", 10, "°C", "L3 bağlantı sıcaklığı", "MAX31855 (TC düğümü)"),
    _p(12, "NEUTRAL_TEMP_X10", "s16", 10, "°C", "Nötr bağlantı sıcaklığı", "MAX31855 (TC düğümü)"),
    _p(13, "AMBIENT_TEMP_X10", "s16", 10, "°C", "Kabin içi hava sıcaklığı", "T/RH sensörü (donanımda EKSİK, docs/09 §5)"),
    _p(14, "WALL_TEMP_X10", "s16", 10, "°C", "Kabin duvarı (soğuk nokta) sıcaklığı", "NTC (donanımda EKSİK, docs/09 §5)"),
    _p(15, "HUMIDITY_X10", "u16", 10, "%RH", "Bağıl nem", "T/RH sensörü (donanımda EKSİK, docs/09 §5)"),
    _p(16, "DEW_MARGIN_X10", "s16", 10, "K", "Çiy noktası marjı (duvar − çiy noktası); ≤0 yoğuşma", "detector/condensation"),
    _p(17, "PD_INDEX_X10", "u16", 10, "idx", "Kısmi deşarj indeksi (1,5 sa medyan)", "HFCT30/50 (IR/PD düğümü)"),
    _p(18, "OVERLOAD_RATIO_X100", "u16", 100, "×Ir", "1 saatlik RMS akım / anma akımı", "detector/overload"),
    _p(19, "NEUTRAL_LOADING_X100", "u16", 100, "×In", "1 saatlik RMS nötr akımı / nötr anma", "detector/neutral"),
    _p(20, "SEV_LOOSE_BOLT", "u16", 1, "", "Gevşek cıvata izi şiddeti (0..3)", "rules/pipeline"),
    _p(21, "SEV_OVERLOAD", "u16", 1, "", "Aşırı yük izi şiddeti (0..3)", "rules/pipeline"),
    _p(22, "SEV_NEUTRAL", "u16", 1, "", "Nötr izleri (yüklenme/bağlantı) şiddeti (0..3)", "rules/pipeline"),
    _p(23, "SEV_CONDENSATION", "u16", 1, "", "Yoğuşma/nem izleri şiddeti (0..3)", "rules/pipeline"),
    _p(24, "SEV_PD", "u16", 1, "", "PD izi şiddeti, füzyon sonrası (0..3)", "rules/pipeline"),
    _p(25, "SEV_ARC", "u16", 1, "", "Ark koruma izleri (trip/bütünlük) şiddeti (0..3)", "rules/pipeline"),
    _p(26, "DATA_AGE_S", "u16", 1, "s", "Son geçerli örnekten bu yana geçen süre (65535'te doyar)", "detector/flags (STALE)"),
    _p(27, "RESERVED_27", "u16", 1, "", "Ayrılmış (0)", "-"),
    _p(28, "RESERVED_28", "u16", 1, "", "Ayrılmış (0)", "-"),
    _p(29, "RESERVED_29", "u16", 1, "", "Ayrılmış (0)", "-"),
    _p(30, "RESERVED_30", "u16", 1, "", "Ayrılmış (0)", "-"),
    _p(31, "ICD_VERSION", "u16", 1, "", "ICD sürümü: 2.0.0 -> 200", "sabit"),
)

# FLAGS bit alanı
FLAG_BITS: dict[int, tuple[str, str]] = {
    0: ("STALE", "Cihaz beklenen periyotta örnek göndermiyor (3 x periyot)"),
    1: ("DE_ENERGISED", "Akım anma akımının %2'sinin altında: enerjisiz / kesici açık"),
    2: ("ARC_TRIP_LATCHED", "Ark koruma TRIP alarmı onay bekliyor (olay tipi, sinyal dönse de açık)"),
    3: ("ARC_INTEGRITY_FAULT", "Ark koruma tanılama hatası: koruma devre dışı"),
    4: ("MUTED", "Bu panoda en az bir iz sessize alınmış"),
    5: ("PD_ADVISORY", "PD yükselmiş ama ikinci kanal ailesi olmadığı için UYARI'da tutuluyor"),
    6: ("ALARM_PAGED", "En az bir ALARM+ alarm nöbetçiye sevk edildi ve onay bekliyor"),
}

SEVERITY_TEXT = {0: "NORMAL", 1: "UYARI", 2: "ALARM", 3: "KRİTİK"}

_BY_NAME = {p.name: p for p in POINTS}


def point(name: str) -> Point:
    return _BY_NAME[name]


def block_base(panel_index: int) -> int:
    if not 0 <= panel_index < MAX_PANELS:
        raise ValueError(f"pano indeksi 0..{MAX_PANELS - 1} olmalı")
    return panel_index * BLOCK_SIZE


def ioa_measurand(panel_index: int, offset: int) -> int:
    """M_ME_NB_1 (ölçülen değer, ölçekli) IOA'sı: 1 + pano*32 + ofset (1..6400)."""
    if not 0 <= offset < BLOCK_SIZE:
        raise ValueError("ofset 0..31 olmalı")
    return 1 + block_base(panel_index) + offset


def ioa_flag(panel_index: int, bit: int) -> int:
    """M_SP_NA_1 / M_SP_TB_1 (tekil bilgi) IOA'sı: 10001 + pano*8 + bit."""
    if not 0 <= bit < 8:
        raise ValueError("bit 0..7 olmalı")
    block_base(panel_index)
    return IEC104_FLAG_IOA_BASE + 1 + panel_index * 8 + bit


def total_registers(n_panels: int = MAX_PANELS) -> int:
    return n_panels * BLOCK_SIZE


def encode(pt: Point, value: float | int | None) -> int:
    """Değeri 16 bit register ham değerine çevirir (doyurarak; None -> 0)."""
    if value is None:
        return 0
    if pt.dtype == "bits":
        return int(value) & 0xFFFF
    scaled = round(float(value) * pt.scale)
    if pt.dtype == "s16":
        return max(-32768, min(32767, scaled)) & 0xFFFF
    return max(0, min(0xFFFF, scaled))


def decode(pt: Point, raw: int) -> float | int:
    if pt.dtype == "bits":
        return raw
    if pt.dtype == "s16" and raw >= 0x8000:
        raw -= 0x10000
    return raw / pt.scale if pt.scale != 1 else raw


def build_block(values: dict[str, float | int | None]) -> list[int]:
    """`values` (nokta adı -> mühendislik değeri) -> BLOCK_SIZE uzunlukta ham register listesi.
    Verilmeyen noktalar 0; ICD_VERSION otomatik doldurulur; bilinmeyen ad reddedilir."""
    unknown = set(values) - set(_BY_NAME)
    if unknown:
        raise KeyError(f"ICD'de olmayan nokta(lar): {sorted(unknown)}")
    regs = [0] * BLOCK_SIZE
    for pt in POINTS:
        if pt.name == "ICD_VERSION":
            regs[pt.offset] = ICD_VERSION_CODE
        elif pt.name in values:
            regs[pt.offset] = encode(pt, values[pt.name])
    return regs


def decode_block(regs: list[int]) -> dict[str, float | int]:
    if len(regs) != BLOCK_SIZE:
        raise ValueError(f"blok {BLOCK_SIZE} register olmalı, {len(regs)} verildi")
    return {pt.name: decode(pt, regs[pt.offset]) for pt in POINTS}


def flag_names(value: int) -> list[str]:
    return [name for bit, (name, _) in sorted(FLAG_BITS.items()) if value & (1 << bit)]


def set_flags(*names: str) -> int:
    by_name = {name: bit for bit, (name, _) in FLAG_BITS.items()}
    out = 0
    for n in names:
        out |= 1 << by_name[n]
    return out


# ------------------------------------------------------------------ üretilen çıktılar
def csv_point_list() -> str:
    """Üçüncü taraf (SCADA/ADMS entegratörü) için nokta listesi. Adres = 0 tabanlı pano
    indeksi * 32 + ofset; FC04."""
    lines = ["offset,name,type,scale,unit,description,source"]
    for p in POINTS:
        desc = p.description.replace('"', "'")
        lines.append(f'{p.offset},{p.name},{p.dtype},{p.scale:g},{p.unit},"{desc}","{p.source}"')
    return "\n".join(lines) + "\n"


def markdown_doc() -> str:
    v = ".".join(str(x) for x in ICD_VERSION)
    out = [
        f"# PANO GÖZ ICD v{v} — Modbus TCP Register Haritası",
        "",
        "> **Bu dosya `python -m tools.gen_icd` ile ÜRETİLİR; elle düzenlemeyin.** Tek gerçek kaynak",
        "> `panogoz/scada/icd.py`. `tests/test_icd.py` bu dosyanın koddan üretilenle birebir aynı",
        "> olduğunu doğrular (ICD ↔ kod tutarlılık testi, K2 2.5).",
        "",
        "## Genel",
        "",
        "- Protokol: **Modbus TCP**, yalnız **FC04 (Read Input Registers)** — salt okunur; Holding Register bloğu boş.",
        f"- Pano başına **{BLOCK_SIZE} register**; pano `p` (0 tabanlı) için taban adres = `p × {BLOCK_SIZE}`; en çok **{MAX_PANELS} pano** ({total_registers()} register).",
        "- Değer = ham / ölçek. `s16`: 16 bit işaretli (two's complement). `bits`: bit alanı.",
        f"- Sürüm kaydı: bloğun son register'ı (ofset 31) `{ICD_VERSION_CODE}` (= {v}).",
        "- Modbus FC04 tek istekte **en çok 125 register** okutur (≈ 3 pano); master birden çok okuma yapar.",
        "- Olay tipi (latching) alarmlar (ark TRIP) sinyal dönse de onaylanana kadar `SEVERITY_CODE`/`SEV_ARC`/`FLAGS`'ta görünür.",
        "- Eski v1 haritası (8 register/bağlantı) `docs/modbus-haritalama.md`'de, yalnızca `tools/run_modbus_server.py` için korunmuştur.",
        "",
        "## Noktalar (pano başına)",
        "",
        "| Ofset | Ad | Tip | Ölçek | Birim | Açıklama | Kaynak |",
        "| ---: | --- | --- | ---: | --- | --- | --- |",
    ]
    for p in POINTS:
        out.append(f"| {p.offset} | `{p.name}` | {p.dtype} | {p.scale:g} | {p.unit or '—'} | {p.description} | {p.source} |")
    out += ["", "## FLAGS bit alanı (ofset 3)", "", "| Bit | Ad | Anlam |", "| ---: | --- | --- |"]
    for bit, (name, meaning) in sorted(FLAG_BITS.items()):
        out.append(f"| {bit} | `{name}` | {meaning} |")
    out += [
        "",
        "## Şiddet kodları",
        "",
        "| Kod | Anlam |",
        "| ---: | --- |",
        *[f"| {k} | {v} |" for k, v in SEVERITY_TEXT.items()],
        "",
        "## Örnek: pano 2'nin sıcaklığını okumak",
        "",
        "```",
        f"taban = 2 x {BLOCK_SIZE} = {2 * BLOCK_SIZE}",
        f"JOINT_TEMP_L2_X10  -> adres {2 * BLOCK_SIZE + point('JOINT_TEMP_L2_X10').offset} (FC04)",
        "modpoll -m tcp -a 1 -r <adres+1> -c 1 -t 3 127.0.0.1 -p 5020   # modpoll 1 tabanlı adres kullanır",
        "```",
        "",
        "## IEC 60870-5-104 (ikinci SCADA protokolü)",
        "",
        f"Aynı 32'lik blok IEC 104 üzerinden de yayınlanır (`panogoz/scada/iec104.py`, TCP **2404**, ortak adres **{IEC104_COMMON_ADDRESS}**).",
        "",
        "| Bilgi | Tip | IOA | Not |",
        "| --- | --- | --- | --- |",
        f"| 32 ölçüm/kod (bloğun tüm ofsetleri) | `M_ME_NB_1` (11), ölçekli | `1 + pano × {BLOCK_SIZE} + ofset` (1…{MAX_PANELS * BLOCK_SIZE}) | Değer = Modbus register'ı ile aynı tam sayı (s16 işaretli; u16 32767'de doyar → OV bitli). STALE iken NT biti. |",
        f"| FLAGS bit'leri ({FLAG_BIT_COUNT} adet) | `M_SP_NA_1` (1) genel taramada, `M_SP_TB_1` (30, CP56Time2a) anlık olayda | `{IEC104_FLAG_IOA_BASE + 1} + pano × 8 + bit` | Bit adları yukarıdaki FLAGS tablosunda |",
        "| Genel tarama | `C_IC_NA_1` (100), QOI 20 | — | ACT_CON → veri (COT 20) → ACT_TERM |",
        "| Kendiliğinden bildirim | COT 3 | — | Şiddet/alarm sayacı/SEV_* değişimi (`M_ME_NB_1`), bayrak değişimi (`M_SP_TB_1`) |",
        "| Saat senkronu | `C_CS_NA_1` (103) | — | Sunucunun olay zaman damgası ofseti ayarlanır |",
        "| Okuma / test | `C_RD_NA_1` (102) / `C_TS_NA_1` (104) | — | Okuma COT 5 ile yanıtlanır |",
        "| Kontrol komutları (45…69) | — | — | **Reddedilir** (yalnız izleme; ACT_CON negatif, COT 44) |",
        "",
        "Varsayılan APCI parametreleri: k=12, w=8, t1=15 s, t2=10 s, t3=20 s.",
        "",
        "## Alarm ↔ register eşlemesi",
        "",
        "SCADA'nın alarm listesi `SEVERITY_CODE` ve `SEV_*` register'larından türetilir; `FLAGS` bit'leri",
        "alarm kaynağını (ark, PD tavsiyesi, haberleşme) açıklar. Konsoldaki SCADA sekmesi aynı",
        "register'ları ham + çözülmüş haliyle yan yana gösterir (görsel kanıt).",
        "",
    ]
    return "\n".join(out)
