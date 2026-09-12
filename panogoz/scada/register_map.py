"""SCADA entegrasyonu için Modbus haritalama (ICD): bağlantı başına sabit register bloğu.

Yarışma brifi gerçek bir RTU/SCADA'ya bağlanmayı istemiyor — yalnızca haritalamanın
gösterilmesi yeterli. Register'lar salt okunur "Input Register" (function code 04)
olarak sunulur; master hiçbir değeri yazamaz.

Ondalıklı değerler (θ, sıcaklık, akım) x10 ölçekle tek bir 16 bit register'a
sığdırılır (örn. 23.4°C -> 234). Negatif olabilecek değerler (θ, sıcaklık) 16 bit
işaretli tam sayı (two's complement) olarak kodlanır — bu, Modbus'ta yaygın bir
uygulamadır ve tek bir register'ın taşıyabileceği aralığı ikiye katlamaya gerek
bırakmaz.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

REGISTERS_PER_CONNECTION = 8


class Register(IntEnum):
    """Bir bağlantı bloğu içindeki göreli register ofseti."""

    SEVERITY_CODE = 0
    THETA_X10 = 1
    CURRENT_L1_X10 = 2
    CURRENT_L2_X10 = 3
    CURRENT_L3_X10 = 4
    SURFACE_TEMP_L1_X10 = 5
    SURFACE_TEMP_L2_X10 = 6
    SURFACE_TEMP_L3_X10 = 7


def connection_base_address(connection_index: int) -> int:
    return connection_index * REGISTERS_PER_CONNECTION


def encode_unsigned_x10(value: float) -> int:
    """Negatif olmayan bir değeri (akım gibi) x10 ölçekle 16 bit register'a kodlar."""
    scaled = round(value * 10)
    return max(0, min(scaled, 0xFFFF))


def encode_signed_x10(value: float) -> int:
    """Negatif olabilecek bir değeri (θ, sıcaklık) x10 ölçekle 16 bit two's complement kodlar."""
    scaled = round(value * 10)
    scaled = max(-32768, min(scaled, 32767))
    return scaled & 0xFFFF


def decode_signed_x10(raw: int) -> float:
    if raw >= 0x8000:
        raw -= 0x10000
    return raw / 10.0


def decode_unsigned_x10(raw: int) -> float:
    return raw / 10.0


@dataclass(frozen=True)
class ConnectionSnapshot:
    """Bir bağlantının Modbus'a yansıtılacak anlık durumu."""

    severity_code: int
    theta: float | None
    current_l1_a: float
    current_l2_a: float
    current_l3_a: float
    surface_temp_l1_c: float
    surface_temp_l2_c: float
    surface_temp_l3_c: float

    def to_registers(self) -> list[int]:
        theta_value = self.theta if self.theta is not None else 0.0
        return [
            self.severity_code,
            encode_signed_x10(theta_value),
            encode_unsigned_x10(self.current_l1_a),
            encode_unsigned_x10(self.current_l2_a),
            encode_unsigned_x10(self.current_l3_a),
            encode_signed_x10(self.surface_temp_l1_c),
            encode_signed_x10(self.surface_temp_l2_c),
            encode_signed_x10(self.surface_temp_l3_c),
        ]
