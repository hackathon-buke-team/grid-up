"""K4 4.5: docs/08 fare yolunu GERÇEK arayüz düğmeleriyle yürütüp webm ekran kaydı üretir.

`record_demo.py` API saat ucuyla ara günlere atlar; bu betik ise yalnız arayüzün kendi kontrollerini kullanır
(Sıfırla, Güne atla menüsü, Başlat/Duraklat, hız, sekmeler, filtre, Onay için doldur, Onayla, Fırtına başlat),
yani docs/08 §1'deki "yalnız fareyle" iddiasını uçtan uca sınar. Ekrana adım başlıkları ve imleç noktası
bindirilir (yalnız kayıtta; uygulama kodu değişmez).

Önkoşul: sunucu çalışıyor (`python -m panogoz.run_local --port 8090 --modbus-port 5030 --iec104-port 2414`),
`pip install playwright opencv-python`, Edge kurulu.

    python -m tools.record_video --base http://127.0.0.1:8090

Çıktı: docs/ekran-goruntuleri/panogoz-demo-video.webm
"""
from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "ekran-goruntuleri" / "panogoz-demo-video.webm"

CURSOR_JS = """
window.addEventListener('DOMContentLoaded', () => {
  const c = document.createElement('div');
  c.id = 'demo-cursor';
  c.style.cssText = 'position:fixed;width:20px;height:20px;border-radius:50%;background:rgba(251,191,36,.85);border:2px solid #fff;z-index:99999;pointer-events:none;transform:translate(-50%,-50%);left:-60px;top:-60px';
  document.body.appendChild(c);
  document.addEventListener('mousemove', (e) => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
});
"""

CAPTION_JS = """(txt) => {
  let d = document.getElementById('demo-caption');
  if (!d) {
    d = document.createElement('div'); d.id = 'demo-caption';
    d.style.cssText = 'position:fixed;left:50%;bottom:16px;transform:translateX(-50%);z-index:99998;max-width:92vw;padding:10px 18px;border-radius:8px;background:rgba(15,22,32,.94);color:#e6edf3;border:1px solid #5b8dee;font:600 15px/1.35 system-ui,-apple-system,Segoe UI,sans-serif;text-align:center;pointer-events:none';
    document.body.appendChild(d);
  }
  d.textContent = txt;
}"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8090")
    ap.add_argument("--browser", default="msedge", help="msedge | chromium")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    tmp = Path(tempfile.mkdtemp(prefix="panogoz-video-"))
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True) if args.browser == "msedge" else p.chromium.launch(headless=True)
        except Exception:
            browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=str(tmp), record_video_size={"width": 1280, "height": 720})
        ctx.add_init_script(CURSOR_JS)
        page = ctx.new_page()

        def cap(text: str) -> None:
            page.evaluate(CAPTION_JS, text)

        def hold(seconds: float) -> None:
            page.wait_for_timeout(int(seconds * 1000))

        def click(selector: str, *, nth: int | None = None) -> None:
            loc = page.locator(selector)
            loc = loc.nth(nth) if nth is not None else loc.first
            loc.scroll_into_view_if_needed()
            box = loc.bounding_box()
            assert box, f"görünmüyor: {selector}"
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=14)
            page.wait_for_timeout(250)
            loc.click()

        def day_is(prefix: str) -> None:
            page.wait_for_function(f"document.getElementById('clock-day').textContent.trim().startsWith('{prefix}')", timeout=20000)

        def run_clock(speed: str, seconds: float) -> None:
            page.select_option("#speed-select", speed)
            click("#play-btn")
            hold(seconds)
            click("#play-btn")
            page.wait_for_function("document.getElementById('clock-state').textContent.includes('Duraklat')", timeout=10000)

        def reset() -> None:
            click("#reset-btn")
            day_is("Gün 30")
            click('[data-tab="alarms"]')  # filtreler yalnız bu sekmede görünür
            page.select_option("#f-family", "")
            page.select_option("#f-state", "active")

        page.goto(args.base + "/")
        page.wait_for_selector("#kpis .kpi", timeout=60000)
        hold(1.0)

        # 1 — normal filo
        reset()
        click('[data-tab="panels"]')
        page.wait_for_selector(".pcard")
        cap("1 · Gün 30: 22 pano, hepsi NORMAL, aktif alarm yok")
        hold(4)

        # 2 — sıcak yaz
        page.select_option("#jump-select", "34")
        day_is("Gün 34")
        click(".pcard:has-text('P14')")
        page.wait_for_selector("#pd-charts canvas")
        page.locator("#pd-charts").scroll_into_view_if_needed()
        cap("2 · Sıcak yaz (P14): sıcaklık 80 °C'ye çıkıyor ama θ düz, alarm yok")
        hold(5)
        page.evaluate("window.scrollTo(0, 0)")

        # 3–4 — alarm ve iş emri
        cap("3 · Başlat: Gün 34, 00:45'te P01 L2 fazında θ sıçrıyor")
        run_clock("3600", 3.5)
        click('[data-tab="alarms"]')
        page.wait_for_selector(".alarm-row")
        cap("3 · ALARM açıldı, onay bekliyor")
        hold(3)
        click(".alarm-row")
        page.wait_for_selector("#detail-body:not([hidden])")
        cap("4 · Kanıt grafiği, iş emri kartı, bildirim geçmişi")
        hold(3)
        page.mouse.wheel(0, 650)
        hold(4)

        # 5–6 — telefon ve onay
        click('[data-tab="phones"]')
        page.wait_for_selector(".phone")
        cap("5 · Nöbetçi telefonları: kademeli eskalasyon; onay belirteci yalnız mesajda")
        hold(5)
        click('button:has-text("Onay için doldur")')
        page.wait_for_function("document.getElementById('ack-token').value.length === 4")
        cap("6 · Telefondaki belirteçle, kimlikli onay")
        hold(2.5)
        click("#ack-btn")
        page.wait_for_function("document.getElementById('d-ack-info').textContent.includes('üstlendi')", timeout=10000)
        hold(3.5)

        # 8 — PD füzyonu
        reset()
        page.select_option("#jump-select", "52")
        day_is("Gün 52")
        run_clock("43200", 5)
        click('[data-tab="alarms"]')
        page.select_option("#f-family", "pd")
        page.select_option("#f-state", "")
        page.wait_for_selector(".alarm-row")
        click(".alarm-row:has-text('P12')")
        page.wait_for_selector("#detail-body:not([hidden])")
        cap("8 · PD füzyonu: P09 nemle destekli ALARM; P12 kuru havada tek başına UYARI'da tavanlı")
        hold(6)
        page.select_option("#f-family", "")
        page.select_option("#f-state", "active")

        # 9–10 — bastırma ve SCADA
        click('[data-tab="suppression"]')
        page.wait_for_selector("#sup-table tr:nth-child(3)")
        cap("9 · Bastırma: veri yok / enerjisiz / düşük yük / PD tavanlama sayaçları")
        hold(5)
        click('[data-tab="scada"]')
        page.wait_for_selector("#scada-table tr:nth-child(32)")
        cap("10 · SCADA: 32 register/pano, ICD v2.0, her register'ın ekrandaki karşılığı")
        hold(6)

        # 11–12 — fırtına
        reset()
        click('[data-tab="alarms"]')
        click("#storm-btn")
        hold(0.6)
        run_clock("3600", 1.2)
        page.wait_for_selector("#storm-banner:not([hidden])", timeout=15000)
        cap("11 · Fırtına: 8 panoda ortak olay, alıcı başına saatlik bildirim sınırı")
        hold(5)
        run_clock("3600", 3)
        click('[data-tab="phones"]')
        page.wait_for_function("document.body.innerText.includes('[ÖZET]')", timeout=15000)
        cap("12 · Sınırlanan mesajlar tek [ÖZET] mesajına döndü")
        hold(5)

        video = page.video
        ctx.close()  # video dosyası bağlam kapanınca tamamlanır; save_as tarayıcı kapanmadan önce çağrılmalı
        OUT.parent.mkdir(parents=True, exist_ok=True)
        video.save_as(str(OUT))
        browser.close()
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"tamam: {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
