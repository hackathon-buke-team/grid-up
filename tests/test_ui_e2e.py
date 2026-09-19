"""K3 3.1/3.3/3.5 uçtan uca arayüz testi: GERÇEK Edge/Chromium'da gerçek HTTP sunucusuna karşı.

Playwright + Edge (veya Chromium) + OpenCV yoksa atlanır (`pip install playwright opencv-python-headless`;
Edge için `channel="msedge"`, ek indirme gerekmez).
"""
import re
import threading
import time

import pytest
import requests

pw = pytest.importorskip("playwright.sync_api")
cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from werkzeug.serving import make_server  # noqa: E402

from panogoz.api.app import create_app  # noqa: E402
from panogoz.api.fleet_service import FleetService  # noqa: E402
from tests.test_fleet_service import SPECS  # noqa: E402


@pytest.fixture(scope="module")
def server():
    svc = FleetService(SPECS)
    app = create_app(fleet_service=svc)
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge", headless=True)
        except Exception:
            try:
                b = p.chromium.launch(headless=True)
            except Exception as exc:  # tarayıcı yok
                pytest.skip(f"tarayıcı başlatılamadı: {exc}")
        yield b
        b.close()


@pytest.fixture()
def fresh(server):
    requests.post(f"{server}/api/sim/reset")
    requests.post(f"{server}/api/sim/clock", json={"jump_to_day": 34.4, "running": False})
    return server


def first_token(base, alarm_id):
    for m in requests.get(f"{base}/api/fleet/notifications?limit=500").json():
        if m["alarm_id"] == alarm_id and m["kind"] == "first" and m["status"] == "sent":
            return re.search(r"ONAY \S+ (\d{4})", m["text"]).group(1)
    raise AssertionError("belirteçli mesaj yok")


def test_console_alarm_list_detail_work_order_and_ack_flow(browser, fresh):
    errors = []
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(fresh + "/")
    page.wait_for_selector(".alarm-row", timeout=20000)
    assert page.locator(".alarm-row").count() >= 1
    page.locator(".alarm-row").first.click()
    page.wait_for_selector("#detail-body:not([hidden])")
    assert "Gevşek cıvatalı" in page.inner_text("#d-title")
    assert "PLANLI KESİNTİ" in page.inner_text("#d-wo").upper()  # iş emri kartı: kesinti uyarısı
    assert page.locator("#d-chart").evaluate("c => c.width") > 100
    # yanlış belirteç reddedilir, alarm açık kalır
    page.fill("#ack-token", "abcd")
    page.fill("#ack-by", "Ayşe Yılmaz")
    page.click("#ack-btn")
    page.wait_for_function("document.getElementById('ack-err').textContent.length > 0")
    assert "belirteci hatalı" in page.inner_text("#ack-err")
    # telefon sekmesinden "onay için doldur" -> onayla
    page.click('[data-tab="phones"]')
    page.wait_for_selector('button:has-text("Onay için doldur")')
    page.locator('button:has-text("Onay için doldur")').first.click()
    page.wait_for_function("document.getElementById('ack-token').value.length === 4")
    page.click("#ack-btn")
    page.wait_for_function("document.getElementById('d-ack-info').textContent.includes('üstlendi')", timeout=10000)
    assert errors == []
    page.close()


def test_console_tabs_render_panels_suppression_and_scada(browser, fresh):
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(fresh + "/")
    page.wait_for_selector("#kpis .kpi", timeout=20000)
    page.click('[data-tab="panels"]')
    page.wait_for_selector(".pcard")
    assert page.locator(".pcard").count() == 6
    page.wait_for_selector("#pd-charts canvas")
    assert page.locator("#pd-tracks tr").count() > 10
    page.click('[data-tab="suppression"]')
    page.wait_for_selector("#sup-table tr:nth-child(2)")
    page.click('[data-tab="scada"]')
    page.wait_for_selector("#scada-table tr:nth-child(32)")
    assert page.locator("#scada-table tr").count() == 33  # başlık + 32 register
    assert "SEVERITY_CODE" in page.inner_text("#scada-table")
    assert errors == []
    page.close()


def test_demo_controls_are_mouse_only_and_change_the_fleet(browser, fresh):
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.goto(fresh + "/")
    page.wait_for_selector("#kpis .kpi", timeout=20000)
    page.select_option("#inject-panel", "P04")
    page.select_option("#inject-scenario", "loose_bolt_abrupt")
    page.click("#inject-btn")
    page.wait_for_function("document.getElementById('demo-msg').textContent.includes('enjekte')")
    page.click("#play-btn")  # saati başlat (fareyle)
    page.wait_for_function("document.getElementById('play-btn').textContent.includes('Duraklat')")
    page.click("#play-btn")
    page.click('[data-tab="panels"]')
    page.wait_for_selector(".pcard")
    assert "enjekte" in page.locator(".pcard", has_text="P04").inner_text()
    page.click("#reset-btn")
    page.wait_for_function("document.getElementById('demo-msg').textContent.includes('Sıfırlandı')")
    page.close()


def test_mobile_field_view_has_no_horizontal_scroll_at_400px_and_qr_opens_the_panel(browser, fresh):
    ctx = browser.new_context(viewport={"width": 400, "height": 860}, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    page.goto(fresh + "/saha.html?panel=P01")
    page.wait_for_selector(".s-alarm", timeout=20000)
    time.sleep(0.5)
    assert page.evaluate("document.documentElement.scrollWidth") <= 400
    page.click("text=İş emrini göster")
    assert page.evaluate("document.documentElement.scrollWidth") <= 400
    # QR'ı ekran görüntüsünden çöz: panonun saha bağlantısını vermeli
    png = page.locator("#s-qr").screenshot()
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    assert decoded.endswith("/saha.html?panel=P01")
    # mobilden onay
    alarm = requests.get(f"{fresh}/api/fleet/alarms?panel=P01&state=active").json()[0]
    page.fill(".s-alarm input[aria-label='Onay belirteci']", first_token(fresh, alarm["id"]))
    page.fill(".s-alarm input[aria-label='Adınız']", "Ayşe Yılmaz")
    page.click("text=Onayla")
    page.wait_for_function("document.querySelector('.s-alarm').textContent.includes('üstlendi')", timeout=10000)
    ctx.close()
