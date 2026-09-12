"""Çekirdek zaman serilerini (sim/detector/rules) Modbus register anlık görüntüsüne çevirir."""
from __future__ import annotations

from panogoz.contracts.channels import Phase
from panogoz.scada.register_map import ConnectionSnapshot
from panogoz.sim.demo_fleet import ConnectionTimeline


def snapshot_at(timeline: ConnectionTimeline, index: int = -1) -> ConnectionSnapshot:
    last = {phase: timeline.three_phase[phase][index] for phase in Phase}
    return ConnectionSnapshot(
        severity_code=int(timeline.severity[index].severity),
        theta=timeline.theta[index].theta,
        current_l1_a=last[Phase.L1].current_a,
        current_l2_a=last[Phase.L2].current_a,
        current_l3_a=last[Phase.L3].current_a,
        surface_temp_l1_c=last[Phase.L1].surface_temp_c,
        surface_temp_l2_c=last[Phase.L2].surface_temp_c,
        surface_temp_l3_c=last[Phase.L3].surface_temp_c,
    )
