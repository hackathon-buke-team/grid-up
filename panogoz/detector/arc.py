"""Ark koruma dedektörleri: ABB TVOC-2 Modbus kayıtlarından.

- Trip: bir tahmin değil bir olgudur; tek örnek yeter (debounce yok), CRITICAL.
- Bütünlük: tanılama bitleri koruma zincirinin sağlığını söyler. "Sensör hatası" =
  ark koruma DEVRE DIŞI; kabin korumasız demektir, bakım ekibi sevk edilir.
"""
from __future__ import annotations

from panogoz.detector.common import Scored, gap_reasons


def arc_trip_scores(arc_trip: list[int], valid: list[bool]) -> Scored:
    values: list[float | None] = [(2.0 if trip else 0.0) if ok else None for trip, ok in zip(arc_trip, valid)]
    return Scored(values, gap_reasons(valid))


def arc_integrity_scores(arc_sensor_ok: list[int], valid: list[bool]) -> Scored:
    values: list[float | None] = [(0.0 if healthy else 1.0) if ok else None for healthy, ok in zip(arc_sensor_ok, valid)]
    return Scored(values, gap_reasons(valid))
