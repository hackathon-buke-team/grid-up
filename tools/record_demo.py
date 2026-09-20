"""K3 3.6: docs/08-DEMO-SENARYOSU.md adımlarını GERÇEK tarayıcıda yürütüp ekran görüntüsü, GIF ve
SCADA okuma çıktısı üretir (elle çekilmiş/uydurma görüntü yok; her dosya çalışan sistemden gelir).

Önkoşul: sunucu çalışıyor (`python -m panogoz.run_local --port 8090 --modbus-port 5030 --iec104-port 2414`),
`pip install playwright pillow`, Edge kurulu (Chromium için --browser chromium).

    python -m tools.record_demo --base http://127.0.0.1:8090 --modbus-port 5030 --iec104-port 2414

Çıktı: docs/ekran-goruntuleri/NN-*.png, panogoz-demo-walkthrough.gif, scada-okuma.txt
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parents[1] / "docs" / "ekran-goruntuleri"
DEMO_FRAMES = ["03-alarm-acildi.png", "04-alarm-detay.png", "05-telefon.png", "06-onay.png", "07-mobil-saha.png", "08-pd-fuzyon.png", "10-scada.png", "11-firtina.png", "12-firtina-telefon.png"]


def clock(base, **body):
    return requests.post(f"{base}/api/sim/clock", json=body, timeout=60).json()


def reset(base):
    requests.post(f"{base}/api/sim/reset", timeout=60)


def wait_ui(page, selector, timeout=20000):
    page.wait_for_selector(selector, timeout=timeout)
    time.sleep(0.9)


def build_gif(frames: list[Path], target: Path, width: int = 960, seconds: float = 1.8) -> None:
    from PIL import Image

    images = []
    for f in frames:
        im = Image.open(f).convert("RGB")
        h = int(im.height * width / im.width)
        images.append(im.resize((width, min(h, 1400)), Image.LANCZOS).convert("P", palette=Image.ADAPTIVE, colors=128))
    images[0].save(target, save_all=True, append_images=images[1:], duration=int(seconds * 1000), loop=0, optimize=True)


def read_scada(base, modbus_port, iec104_port, panel="P01") -> str:
    from pymodbus.client import ModbusTcpClient

    from panogoz.scada import icd

    view = requests.get(f"{base}/api/fleet/scada?panel={panel}", timeout=30).json()
    idx = view["panel_index"]
    lines = [f"# {panel} ({view['panel_name']}) — {view['icd_version']} — konsolun SCADA sekmesiyle aynı an", ""]
    c = ModbusTcpClient("127.0.0.1", port=modbus_port)
    if c.connect():
        rr = c.read_input_registers(icd.block_base(idx), count=icd.BLOCK_SIZE, device_id=1)
        lines.append(f"[Modbus TCP :{modbus_port}] FC04 adres {icd.block_base(idx)}..{icd.block_base(idx) + icd.BLOCK_SIZE - 1} (pymodbus istemcisi)")
        if not rr.isError():
            dec = icd.decode_block(list(rr.registers))
            for name in ("SEVERITY_CODE", "ALARMS_OPEN", "FLAGS", "THETA_MAX_X10", "CURRENT_L2_X10", "JOINT_TEMP_L2_X10", "HUMIDITY_X10", "ICD_VERSION"):
                pt = icd.point(name)
                extra = f" {icd.flag_names(dec[name])}" if name == "FLAGS" else ""
                lines.append(f"  {name:<22} ham={rr.registers[pt.offset]:>6}  değer={dec[name]}{extra}")
        w = c.write_register(icd.block_base(idx), 0, device_id=1)
        lines.append(f"  yazma denemesi (FC06) -> {'REDDEDİLDİ: ' + str(w) if w.isError() else 'KABUL EDİLDİ (HATA!)'}")
        c.close()
    try:
        import c104

        cl = c104.Client(tick_rate_ms=100, command_timeout_ms=4000)
        conn = cl.add_connection(ip="127.0.0.1", port=iec104_port, init=c104.Init.NONE)
        st = conn.add_station(common_address=1)
        pts = {n: st.add_point(io_address=icd.ioa_measurand(idx, icd.point(n).offset), type=c104.Type.M_ME_NB_1) for n in ("SEVERITY_CODE", "THETA_MAX_X10", "JOINT_TEMP_L2_X10")}
        cl.start()
        conn.connect()
        t0 = time.time()
        while not conn.is_connected and time.time() - t0 < 5:
            time.sleep(0.05)
        ok = conn.interrogation(common_address=1, cause=c104.Cot.ACTIVATION, qualifier=c104.Qoi.STATION, wait_for_response=True)
        time.sleep(0.5)
        lines += ["", f"[IEC 60870-5-104 :{iec104_port}] genel tarama (c104 master) -> {'ACT_CON alındı' if ok else 'BAŞARISIZ'}"]
        for n, p in pts.items():
            lines.append(f"  IOA {p.io_address:<5} {n:<22} değer={int(p.value)}")
        cl.stop()
    except ImportError:
        lines.append("(c104 kurulu değil, IEC 104 okuması atlandı)")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8090")
    ap.add_argument("--modbus-port", type=int, default=5030)
    ap.add_argument("--iec104-port", type=int, default=2414)
    ap.add_argument("--browser", default="msedge", help="msedge | chromium")
    ap.add_argument("--scada-only", action="store_true", help="yalnız SCADA okumasını stdout'a yaz (iç kullanım)")
    args = ap.parse_args()
    base = args.base
    if args.scada_only:
        sys.stdout.reconfigure(encoding="utf-8")
        print(read_scada(base, args.modbus_port, args.iec104_port), end="")
        return
    OUT.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True) if args.browser == "msedge" else p.chromium.launch(headless=True)
        except Exception:
            browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(base + "/")
        page.add_style_tag(content=".topbar{position:static !important}")  # tam sayfa çekimde yapışkan başlık ortaya düşmesin
        wait_ui(page, "#kpis .kpi")

        # 01 — normal filo (Gün 30)
        reset(base)
        clock(base, jump_to_day=30.0, running=False)
        page.click('[data-tab="panels"]')
        wait_ui(page, ".pcard")
        page.screenshot(path=OUT / "01-normal-filo.png")

        # 02 — sıcak yaz: mutlak sıcaklık yüksek, θ düz (sabit eşik yanlış alarm verirdi)
        clock(base, jump_to_day=33.9, running=False)
        page.click(".pcard:has-text('P14')")
        wait_ui(page, "#pd-charts canvas")
        time.sleep(1.5)
        page.screenshot(path=OUT / "02-sicak-yaz-normal.png", full_page=True)

        # 03 — alarm açıldı
        clock(base, jump_to_day=34.4, running=False)
        page.click('[data-tab="alarms"]')
        wait_ui(page, ".alarm-row")
        page.screenshot(path=OUT / "03-alarm-acildi.png")

        # 04 — alarm detayı (kanıt, iş emri kartı, bildirim geçmişi)
        page.locator(".alarm-row").first.click()
        wait_ui(page, "#detail-body:not([hidden])")
        page.screenshot(path=OUT / "04-alarm-detay.png", full_page=True)

        # 05 — nöbetçinin telefonu
        page.click('[data-tab="phones"]')
        wait_ui(page, ".phone")
        page.screenshot(path=OUT / "05-telefon.png", full_page=True)

        # 06 — telefondan "onay için doldur" -> onayla
        page.locator('button:has-text("Onay için doldur")').first.click()
        page.wait_for_function("document.getElementById('ack-token').value.length === 4")
        page.click("#ack-btn")
        page.wait_for_function("document.getElementById('d-ack-info').textContent.includes('üstlendi')", timeout=10000)
        time.sleep(0.8)
        page.screenshot(path=OUT / "06-onay.png", full_page=True)

        # 07 — mobil saha görünümü (400 px)
        ctx = browser.new_context(viewport={"width": 400, "height": 860}, device_scale_factor=2, is_mobile=True, has_touch=True)
        m = ctx.new_page()
        m.goto(f"{base}/saha.html?panel=P01")
        m.add_style_tag(content=".s-top{position:static !important}")
        wait_ui(m, ".s-alarm")  # bu adımda P01'de gerçek bir alarm olmalı; yoksa zaman aşımı = senaryo bozuk
        m.click("text=İş emrini göster")
        time.sleep(0.5)
        overflow = m.evaluate("document.documentElement.scrollWidth")
        assert overflow <= 400, f"mobilde yatay kaydırma var: scrollWidth={overflow}"
        m.screenshot(path=OUT / "07-mobil-saha.png", full_page=True)
        ctx.close()

        # 08 — PD füzyonu: destekli PD ALARM, tek başına PD yalnız UYARI (tavsiye)
        reset(base)
        clock(base, jump_to_day=54.5, running=False)
        page.click('[data-tab="alarms"]')
        page.select_option("#f-family", "pd")
        page.select_option("#f-state", "")
        wait_ui(page, ".alarm-row")
        page.locator(".alarm-row:has-text('P12')").first.click()  # PD tek başına: tavsiye, füzyonda UYARI'da tavanlı
        wait_ui(page, "#detail-body:not([hidden])")
        page.screenshot(path=OUT / "08-pd-fuzyon.png", full_page=True)
        page.select_option("#f-family", "")
        page.select_option("#f-state", "active")

        # 09 — bastırma ekranı
        page.click('[data-tab="suppression"]')
        wait_ui(page, "#sup-table tr:nth-child(3)")
        page.screenshot(path=OUT / "09-bastirma.png", full_page=True)

        # 10 — SCADA register tablosu (+ gerçek Modbus/IEC 104 okuması)
        page.click('[data-tab="scada"]')
        wait_ui(page, "#scada-table tr:nth-child(32)")
        page.screenshot(path=OUT / "10-scada.png", full_page=True)
        # c104 istemcisi Playwright'ın olay döngüsü içinde el sıkışamıyor: okuma ayrı süreçte yapılır (saat duraklatılmış, durum aynı)
        proc = subprocess.run(
            [sys.executable, "-m", "tools.record_demo", "--scada-only", "--base", base, "--modbus-port", str(args.modbus_port), "--iec104-port", str(args.iec104_port)],
            capture_output=True, encoding="utf-8", cwd=OUT.parents[1], timeout=120,
        )
        assert proc.returncode == 0, f"SCADA okuması çöktü: {proc.stderr[-400:]}"
        assert "BAŞARISIZ" not in proc.stdout and "REDDEDİLDİ" in proc.stdout and "ACT_CON alındı" in proc.stdout, f"SCADA okuması eksik/başarısız:\n{proc.stdout}"
        (OUT / "scada-okuma.txt").write_text(proc.stdout, encoding="utf-8")

        # 11/12 — alarm fırtınası
        reset(base)
        clock(base, jump_to_day=31.0, running=False)
        page.click('[data-tab="alarms"]')
        wait_ui(page, "#kpis .kpi")
        page.click("#storm-btn")
        time.sleep(0.8)
        clock(base, jump_to_day=31.05, running=False)
        page.wait_for_selector("#storm-banner:not([hidden])", timeout=15000)
        time.sleep(1.0)
        page.screenshot(path=OUT / "11-firtina.png")
        clock(base, jump_to_day=31.12, running=False)  # saatlik pencere açılır: bastırılanlar tek [ÖZET] mesajına döner
        page.click('[data-tab="phones"]')
        wait_ui(page, ".phone")
        page.wait_for_function("document.body.innerText.includes('[ÖZET]')", timeout=15000)
        time.sleep(0.8)
        page.screenshot(path=OUT / "12-firtina-telefon.png", full_page=True)
        browser.close()

    build_gif([OUT / f for f in DEMO_FRAMES], OUT / "panogoz-demo-walkthrough.gif")
    print(f"tamam: {len(list(OUT.glob('*.png')))} PNG + GIF + scada-okuma.txt -> {OUT} (mobil scrollWidth={overflow})")


if __name__ == "__main__":
    main()
