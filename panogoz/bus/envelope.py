"""Wire envelope carried over the bus (in-proc or MQTT), see CLAUDE.md Sec.2:
"sira numarasi ileri-yalniz su damgasi" -- every reading gets a monotonic
per-device sequence number so a subscriber can detect duplicate delivery
(QoS1 redelivery after a reconnect) and store-and-forward replay can be
applied in order.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from panogoz.contracts.channels import ChannelKind, Phase, Reading


@dataclass(frozen=True)
class Envelope:
    seq: int
    device_id: str
    reading: Reading

    def to_json(self) -> bytes:
        body = {
            "seq": self.seq,
            "device_id": self.device_id,
            "reading": {
                "t_s": self.reading.t_s,
                "connection_id": self.reading.connection_id,
                "kind": self.reading.kind.value,
                "value": self.reading.value,
                "phase": self.reading.phase.value if self.reading.phase is not None else None,
            },
        }
        return json.dumps(body).encode("utf-8")

    @staticmethod
    def from_json(data: bytes) -> "Envelope":
        body = json.loads(data.decode("utf-8"))
        r = body["reading"]
        reading = Reading(
            t_s=r["t_s"],
            connection_id=r["connection_id"],
            kind=ChannelKind(r["kind"]),
            value=r["value"],
            phase=Phase(r["phase"]) if r["phase"] is not None else None,
        )
        return Envelope(seq=body["seq"], device_id=body["device_id"], reading=reading)
