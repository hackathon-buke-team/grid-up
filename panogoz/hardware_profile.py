"""B1 design limits shared by the simulator and the presentation layer.

The channel/asset registry describes possible measurements, not validated optical
coverage. No per-lug IR ROI has been calibrated for the supplied B1 mounting.
"""
from math import hypot, radians, tan
from panogoz.contracts.assets import DEVICES, monitored_joints

REVISION = "B1"
TC_LIFE_DAYS = 721.0  # modeled duty mix; not a measured service-life guarantee
TC_JOINTS = frozenset(k for d in DEVICES if d.kind == "TC" for k in d.covers)
IR_DISTANCE_MM = hypot(350.0, 235.0)
IR_WIDTH_MM = 2 * IR_DISTANCE_MM * tan(radians(110 / 2))
IR_PIXEL_MM = IR_WIDTH_MM / 32
IR_VALIDATED_JOINTS: frozenset[str] = frozenset()


def coverage() -> dict:
    return {
        "revision": REVISION,
        "candidate_joint_count": len(monitored_joints()),
        "resolved_joint_count": len(TC_JOINTS | IR_VALIDATED_JOINTS),
        "tc_joint_keys": sorted(TC_JOINTS),
        "ir_validated_joint_keys": sorted(IR_VALIDATED_JOINTS),
        "ir_pixel_mm": round(IR_PIXEL_MM, 2),
        "lug_pitch_mm": 20,
        "note_tr": "B1: 6 TC ölçüm noktası. IR pabuç ayrımı doğrulanmadı; "
                   "diğer 34 bağlantı için bağımsız sıcaklık üretilmez.",
    }
