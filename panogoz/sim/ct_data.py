"""Organizatörün verdiği tek gerçek seriyi okur: İstenen Veriler.xlsx / Akım Sensörü.

Sekme yapısı (elle doğrulandı): 6. satır başlık, 7. satırdan itibaren 152 satır
gerçek veri — 15 dakika aralıklı L1 fazı sekonder akımı (mA) ve organizatörün
kendi çarpanıyla (6000) hesapladığı primer akım karşılığı (A), ~1,5 günlük seri.

Diğer üç sekme (ARC, PD, Sıcaklık_Nem) veri içermiyor — yalnızca hangi gerçek
cihazdan (ABB TVOC-2 / HFCT30) okunacağına dair referans notu. Bu kanalların
verisi ayrı bir modülde kendi fizik modelimizden sentetik üretilecek.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import openpyxl

REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_default_xlsx_path() -> Path:
    # Dosya adındaki Türkçe "İ" bileşik (NFD) Unicode ile diskte duruyor; sabit
    # dizgeyle (genelde NFC üretir) eşleşmeyebiliyor, bu yüzden glob ile bulunuyor.
    matches = list((REPO_ROOT / "Hackathon Verileri").glob("*stenen*eriler.xlsx"))
    if not matches:
        raise FileNotFoundError("Hackathon Verileri/ altında 'İstenen Veriler.xlsx' bulunamadı")
    return matches[0]


DEFAULT_XLSX_PATH = _resolve_default_xlsx_path()
SHEET_NAME = "Akım Sensörü"
DATA_START_ROW = 7
SAMPLE_PERIOD_S = 15 * 60


@dataclass(frozen=True)
class CtSample:
    t_s: float
    secondary_ma: float
    primary_a: float


def load_real_l1_series(xlsx_path: Path | str = DEFAULT_XLSX_PATH) -> list[CtSample]:
    """Organizatörün gerçek L1 fazı CT verisini (15 dk örnekleme) zaman sırasıyla döner."""
    workbook = openpyxl.load_workbook(xlsx_path, data_only=True)
    sheet = workbook[SHEET_NAME]
    samples: list[CtSample] = []
    for row in sheet.iter_rows(min_row=DATA_START_ROW, values_only=True):
        secondary_ma, primary_a = row[1], row[4]
        if secondary_ma is None or primary_a is None:
            continue
        samples.append(CtSample(t_s=len(samples) * SAMPLE_PERIOD_S, secondary_ma=float(secondary_ma), primary_a=float(primary_a)))
    return samples
