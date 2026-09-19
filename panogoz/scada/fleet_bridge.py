"""Filo servisi -> ICD v2 register blokları (Modbus, CSV ve konsolun SCADA sekmesi ortak kaynağı).

Konsolda görünen değer ile SCADA'nın okuduğu register AYNI fonksiyondan çıkar
(`panel_values`); bu yüzden "register <-> ekran eşlemesi" bir iddia değil, yapısal bir
garantidir. `screen_label` her noktanın konsolda nerede görüldüğünü söyler.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from panogoz.contracts.channels import Phase
from panogoz.rules.alarms import AlarmState
from panogoz.rules.engine import Severity
from panogoz.rules.pipeline import Family
from panogoz.scada import icd

if TYPE_CHECKING:  # döngüsel içe aktarmayı önler
    from panogoz.api.fleet_service import FleetService, Panel

SCREEN_LABELS = {
    "SEVERITY_CODE": "Pano kartı → durum rozeti",
    "ALARMS_OPEN": "Alarm konsolu → 'Onay bekleyen'",
    "ALARMS_ACTIVE": "Pano kartı → aktif alarm sayısı",
    "FLAGS": "Pano kartı → bayraklar (STALE / ENERJİSİZ / ARK)",
    "THETA_MAX_X10": "Pano detayı → θ grafiği (en yüksek |θ|)",
    "CURRENT_L1_X10": "Pano detayı → Akım (L1)",
    "CURRENT_L2_X10": "Pano detayı → Akım (L2)",
    "CURRENT_L3_X10": "Pano detayı → Akım (L3)",
    "NEUTRAL_CURRENT_X10": "Pano detayı → Nötr akımı",
    "JOINT_TEMP_L1_X10": "Pano detayı → Bağlantı sıcaklığı (L1)",
    "JOINT_TEMP_L2_X10": "Pano detayı → Bağlantı sıcaklığı (L2)",
    "JOINT_TEMP_L3_X10": "Pano detayı → Bağlantı sıcaklığı (L3)",
    "NEUTRAL_TEMP_X10": "Pano detayı → Nötr sıcaklığı",
    "AMBIENT_TEMP_X10": "Pano detayı → Ortam sıcaklığı",
    "WALL_TEMP_X10": "Pano detayı → Duvar sıcaklığı",
    "HUMIDITY_X10": "Pano detayı → Bağıl nem",
    "DEW_MARGIN_X10": "Pano detayı → Çiy marjı",
    "PD_INDEX_X10": "Pano detayı → PD indeksi",
    "OVERLOAD_RATIO_X100": "Pano detayı → Aşırı yük oranı",
    "NEUTRAL_LOADING_X100": "Pano detayı → Nötr yüklenme",
    "SEV_LOOSE_BOLT": "Kanıt ekranı → gevşek cıvata izi",
    "SEV_OVERLOAD": "Kanıt ekranı → aşırı yük izi",
    "SEV_NEUTRAL": "Kanıt ekranı → nötr izleri",
    "SEV_CONDENSATION": "Kanıt ekranı → yoğuşma/nem izleri",
    "SEV_PD": "Kanıt ekranı → PD izi",
    "SEV_ARC": "Kanıt ekranı → ark izleri",
    "DATA_AGE_S": "Pano kartı → 'veri yaşı'",
    "ICD_VERSION": "SCADA sekmesi → sürüm",
}


def _sev(panel: "Panel", i: int, kinds: set[str]) -> int:
    return max((int(t.fused[i]) for t in panel.analysis.tracks if t.spec.kind in kinds), default=0)


def panel_values(service: "FleetService", panel: "Panel") -> dict[str, float | int | None]:
    """Panonun şu anki (simülasyon saatindeki) ICD noktaları -> mühendislik değerleri."""
    i = service.now_index
    d, an, eng = panel.data, panel.analysis, panel.engine

    def track_score(kind: str) -> float | None:
        vals = [t.scores[i] for t in an.tracks if t.spec.kind == kind and t.scores[i] is not None]
        return max(vals) if vals else None

    comms = next(t for t in an.tracks if t.spec.kind == "comms_lost")
    active = [a for a in eng.alarms.values() if a.state in (AlarmState.OPEN, AlarmState.ACKED)]
    # olay tipi (latching) alarm sinyal dönse de onaylanana kadar şiddette görünür (konsolla aynı kural)
    latched = {a.kind: int(a.severity) for a in active if a.latching}
    process_max = max(
        [int(t.fused[i]) for t in an.tracks if t.spec.family is not Family.SYSTEM] + list(latched.values()), default=0
    )
    flags: list[str] = []
    if comms.fused[i] >= Severity.WARNING:
        flags.append("STALE")
    if any(t.reasons[i] == "DE_ENERGISED" for t in an.tracks if t.spec.kind == "loose_bolt"):
        flags.append("DE_ENERGISED")
    if any(a.kind == "arc_trip" for a in active):
        flags.append("ARC_TRIP_LATCHED")
    if _sev(panel, i, {"arc_integrity"}) >= int(Severity.ALARM):
        flags.append("ARC_INTEGRITY_FAULT")
    if any(m.until_t_s > service.now_t_s for m in eng.mutes):
        flags.append("MUTED")
    if any(t.capped[i] for t in an.tracks if t.spec.advisory):
        flags.append("PD_ADVISORY")
    if any(a.state is AlarmState.OPEN and a.needs_notification for a in active):
        flags.append("ALARM_PAGED")

    from panogoz.detector.condensation import dew_margin_c

    age_s = (comms.scores[i] or 0.0) * d.period_s
    return {
        "SEVERITY_CODE": process_max,
        "ALARMS_OPEN": sum(1 for a in active if a.state is AlarmState.OPEN),
        "ALARMS_ACTIVE": len(active),
        "FLAGS": icd.set_flags(*flags),
        "THETA_MAX_X10": track_score("loose_bolt") or 0.0,
        "CURRENT_L1_X10": d.current_a[Phase.L1][i],
        "CURRENT_L2_X10": d.current_a[Phase.L2][i],
        "CURRENT_L3_X10": d.current_a[Phase.L3][i],
        "NEUTRAL_CURRENT_X10": d.neutral_current_a[i],
        "JOINT_TEMP_L1_X10": d.joint_temp_c[Phase.L1][i],
        "JOINT_TEMP_L2_X10": d.joint_temp_c[Phase.L2][i],
        "JOINT_TEMP_L3_X10": d.joint_temp_c[Phase.L3][i],
        "NEUTRAL_TEMP_X10": d.neutral_temp_c[i],
        "AMBIENT_TEMP_X10": d.ambient_c[i],
        "WALL_TEMP_X10": d.wall_temp_c[i],
        "HUMIDITY_X10": d.humidity_rh[i],
        "DEW_MARGIN_X10": dew_margin_c(d.ambient_c[i], d.humidity_rh[i], d.wall_temp_c[i]),
        "PD_INDEX_X10": d.pd_index[i],
        "OVERLOAD_RATIO_X100": track_score("overload") or 0.0,
        "NEUTRAL_LOADING_X100": track_score("neutral_overload") or 0.0,
        "SEV_LOOSE_BOLT": _sev(panel, i, {"loose_bolt", "loose_bolt_trend"}),
        "SEV_OVERLOAD": _sev(panel, i, {"overload"}),
        "SEV_NEUTRAL": _sev(panel, i, {"neutral_overload", "neutral_joint"}),
        "SEV_CONDENSATION": _sev(panel, i, {"condensation", "humidity_high"}),
        "SEV_PD": _sev(panel, i, {"pd_tracking"}),
        "SEV_ARC": max(_sev(panel, i, {"arc_trip", "arc_integrity"}), latched.get("arc_trip", 0)),
        "DATA_AGE_S": age_s,
    }


def panel_registers(service: "FleetService", panel: "Panel") -> list[int]:
    return icd.build_block(panel_values(service, panel))


def all_registers(service: "FleetService") -> list[int]:
    """Tüm panoların blokları arka arkaya (pano indeksi sırasıyla)."""
    service.sync()
    regs: list[int] = []
    for panel in sorted(service.panels.values(), key=lambda p: p.index):
        regs.extend(panel_registers(service, panel))
    return regs


def scada_view(service: "FleetService", panel_id: str) -> dict:
    """Konsolun SCADA sekmesi: bir panonun register bloğu ham + çözülmüş + ekran eşlemesiyle."""
    with service._lock:  # noqa: SLF001 -- aynı paket ailesi, tutarlı anlık görüntü için
        service.sync()
        panel = service.panels[panel_id]
        values = panel_values(service, panel)
        regs = icd.build_block(values)
        base = icd.block_base(panel.index)
        rows = []
        for pt in icd.POINTS:
            raw = regs[pt.offset]
            decoded = icd.decode(pt, raw)
            rows.append(
                {
                    "address": base + pt.offset,
                    "offset": pt.offset,
                    "name": pt.name,
                    "type": pt.dtype,
                    "raw": raw,
                    "hex": f"0x{raw:04X}",
                    "value": decoded,
                    "unit": pt.unit,
                    "description": pt.description,
                    "screen": SCREEN_LABELS.get(pt.name, "—"),
                }
            )
        flags = regs[icd.point("FLAGS").offset]
        return {
            "panel_id": panel_id,
            "panel_name": panel.spec.name,
            "panel_index": panel.index,
            "base_address": base,
            "block_size": icd.BLOCK_SIZE,
            "icd_version": ".".join(str(x) for x in icd.ICD_VERSION),
            "function_code": 4,
            "flags": icd.flag_names(flags),
            "severity_text": icd.SEVERITY_TEXT[regs[icd.point("SEVERITY_CODE").offset]],
            "registers": rows,
        }
