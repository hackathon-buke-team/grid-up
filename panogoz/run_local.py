"""``python -m panogoz.run_local`` - the whole system, one process, no Docker.

This is the path that must never fail.  Docker is not running on the demo
machine, there is no broker, there is no PostgreSQL, and there is no network.
So: SQLite on disk, the in-process bus, uvicorn on localhost, and a Modbus TCP
slave a judge can poll with modpoll from a second terminal.

    python -m panogoz.run_local [--panels 112] [--port 8080] [--scada-port 5020]
                                [--seed 42] [--backfill-days 75] [--db path]
                                [--no-backfill] [--reset] [--open]

Everything it prints is meant to be read out loud during a demo: what is
running, where it is, what a judge should type, and what the system is honest
about not being.
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # allow `python panogoz/run_local.py` too
    sys.path.insert(0, str(ROOT))

BANNER = r"""
  ____   _    _   _  ___     ____  ____ _____
 |  _ \ / \  | \ | |/ _ \   / ___|/ __ \_   _|   PANO GOZ
 | |_) / _ \ |  \| | | | | | |  _| |  | || |     Pano ici anomali erken uyari
 |  __/ ___ \| |\  | |_| | | |_| | |__| || |     TEDAS 1600 kVA AG dagitim panosu
 |_| /_/   \_\_| \_|\___/   \____|\____/ |_|     Grid Up · ADM & GDZ Elektrik
"""

HONESTY = [
    "PANO GOZ koruma DEGILDIR. Ark acmasi TVOC-2 donaniminda ~1 ms'de, SIL-2",
    "kapsaminda gerceklesir ve bizi beklemez. Biz gozler, konumlandirir, zaman",
    "damgalar, iliskilendirir ve haber veririz. Bildirim gecikmesi tek bir sayi",
    "degil, 4-13 saniyelik bir ARALIKTIR.",
    "",
    "Kor oldugumuz haller ayri durumlardir ve gizlenmez: DE_ENERGISED,",
    "SENSITIVITY_LOW, MOUNT_LOST, AIM_SHIFTED, CELL_LOW, STALE.",
    "Bastirilan alarmlar kendi ekraninda, kendi gerekcesiyle durur.",
]


def _lan_ip() -> str | None:
    """This machine's LAN address.  A UDP ``connect`` sends no packet, so this
    works on an air-gapped network too."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return None


def _print_notify(rt, args) -> None:
    """Which notification channels are real, and where the crew app lives."""
    n = rt.notifier
    print("  BILDIRIM KANALLARI")
    if n is None:
        print("    bildirim katmani calismiyor (bkz. /api/health degraded)")
        print()
        return
    st = n.status()
    sms = st["channels"]["sms"]
    tg = st["channels"]["telegram"]
    if sms.get("simulated", True):
        print("    SMS          SIMULE  (hicbir yere mesaj gitmez; gercek modem: docs/12)")
    else:
        ok = "hazir" if sms.get("registered") else f"HAZIR DEGIL ({sms.get('error') or 'agda degil'})"
        print(f"    SMS          GERCEK  {sms.get('port')}  {ok}")
    if tg.get("configured"):
        if tg.get("ok"):
            print(f"    Telegram     AKTIF   {tg.get('bot')}  gizlilik: {tg.get('privacy')}")
        else:
            print(f"    Telegram     ANAHTAR VAR AMA CALISMIYOR: {tg.get('error')}")
    else:
        print("    Telegram     KAPALI  (notify.local.json ile acilir; docs/12)")
    host = args.host
    lan = _lan_ip()
    shown = n.public_url or (f"http://{lan}:{args.port}" if host in ("0.0.0.0", "::") and lan
                             else f"http://{host}:{args.port}")
    print(f"    Saha uygulamasi  {shown}/saha/")
    if host in ("127.0.0.1", "localhost"):
        print("                 telefondan acmak icin: --host 0.0.0.0 (ya da baslat.ps1 -Telefon)")
    cfg = getattr(n, "config", None)
    if cfg is not None:
        for w in cfg.warnings:
            print(f"    UYARI        {w}")
        if cfg.generated_pins:
            print("    Saha PIN'leri (rastgele, yalniz bu konsolda; sabitlemek icin notify.local.json):")
            for name, pin in cfg.generated_pins.items():
                print(f"      {name:<22} {pin}")
    print()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m panogoz.run_local",
        description="PANO GOZ - local demo runtime (no Docker, no broker, no network)",
    )
    p.add_argument("--panels", type=int, default=112,
                   help="fleet size (default 112; SOKE-14 and TURGUTLU-02 always exist)")
    p.add_argument("--port", type=int, default=8080, help="HTTP/UI port (default 8080)")
    p.add_argument("--scada-port", type=int, default=5020,
                   help="Modbus TCP slave port (default 5020)")
    p.add_argument("--host", default="127.0.0.1", help="HTTP bind address")
    p.add_argument("--scada-host", default="0.0.0.0", help="Modbus bind address")
    p.add_argument("--seed", type=int, default=42, help="simulation seed (default 42)")
    p.add_argument("--backfill-days", type=int, default=75,
                   help="days of history for the demo panel (default 75)")
    p.add_argument("--db", default=None, help="sqlite path (default ./panogoz.db)")
    p.add_argument("--no-backfill", action="store_true",
                   help="skip history; the demo's dated changepoint will not exist")
    p.add_argument("--reset", action="store_true",
                   help="wipe the database before starting")
    p.add_argument("--speed", type=float, default=1.0,
                   help="sim clock multiplier (1.0 = wall clock; >1 runs ahead)")
    p.add_argument("--open", dest="open_browser", action="store_true",
                   help="open the UI in the default browser once it is up")
    p.add_argument("--log-level", default="warning",
                   choices=["critical", "error", "warning", "info", "debug"])
    return p.parse_args(argv)


def _rule(char: str = "-", n: int = 78) -> str:
    return char * n


def main(argv: list[str] | None = None) -> int:
    # Line-buffer stdout.  Python block-buffers when its output is a pipe or a
    # file rather than a terminal, so `python -m panogoz.run_local > log.txt`
    # would show nothing at all until the process exited - including the banner
    # that tells the operator which URL to open.  A start-up message that only
    # appears after shutdown is worse than no message.
    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):  # pragma: no cover - exotic stdio
        pass

    args = parse_args(argv)

    print(BANNER)
    print(_rule("="))

    db_path = args.db or os.environ.get("PANOGOZ_DB") or str(ROOT / "panogoz.db")
    if args.reset and Path(db_path).exists():
        try:
            Path(db_path).unlink()
            for suffix in ("-wal", "-shm"):
                extra = Path(db_path + suffix)
                if extra.exists():
                    extra.unlink()
            print(f"  --reset      · {db_path} silindi")
        except OSError as exc:
            print(f"  --reset      · {db_path} silinemedi: {exc}")

    # Imported here, not at module scope, so that a broken optional dependency
    # produces a readable message instead of an import traceback before the
    # banner has even printed.
    import uvicorn

    from panogoz.api.app import create_app
    from panogoz.api.runtime import CONTROL_PANEL, DEMO_PANEL, Runtime
    from panogoz.bus.bus import make_bus
    from panogoz.contracts import icd

    # Real notification channels (Telegram, a serial GSM modem) are opt-in per
    # process and this launcher is what opts in.  Tests and helper scripts build
    # Runtimes too and must never message a real phone; see notify/factory.py.
    os.environ.setdefault("PANOGOZ_NOTIFY_LIVE", "1")

    bus_spec = os.environ.get("PANOGOZ_BUS", "inproc")
    bus = make_bus(bus_spec)

    print(f"  veritabani   · {db_path}")
    print(f"  veri yolu    · {bus.kind}"
          + ("  (PANOGOZ_BUS ile mqtt://host:port yapilabilir)"
             if bus.kind == "inproc" else f"  ({bus_spec})"))
    print(f"  filo         · {args.panels} pano, tohum {args.seed}")
    print(f"  gecmis       · {0 if args.no_backfill else args.backfill_days} gun")
    print(_rule())
    print("  ONYUKLEME (bir kez calisir, sonra canli)")

    t0 = time.time()
    rt = Runtime(
        n_panels=args.panels, seed=args.seed, db_path=db_path,
        backfill_days=0 if args.no_backfill else args.backfill_days,
        speed=args.speed, scada_port=args.scada_port, bus=bus,
        scada_host=args.scada_host,
    )
    try:
        rt.bootstrap()
        rt.start()
    except Exception as exc:  # noqa: BLE001
        print(f"\n  ONYUKLEME BASARISIZ: {exc!r}")
        import traceback
        traceback.print_exc()
        return 2
    boot_s = time.time() - t0

    live = rt.panel(DEMO_PANEL)
    base = icd.panel_base(live.panel_index)
    url = f"http://{args.host}:{args.port}"

    print(_rule("="))
    print(f"  HAZIR · {boot_s:.1f} s")
    print(_rule("="))
    print()
    print(f"  ARAYUZ         {url}")
    print(f"  API            {url}/api/health")
    print(f"                 {url}/api/panel/{DEMO_PANEL}")
    print(f"                 {url}/api/fleet")
    print(f"                 {url}/api/icd        (ICD, markdown)")
    print(f"                 {url}/api/icd.csv    (SCADA nokta listesi)")
    print(f"                 {url}/docs           (OpenAPI)")
    print(f"  WEBSOCKET      ws://{args.host}:{args.port}/ws")
    print()
    print(f"  SCADA          Modbus TCP  {args.scada_host}:{args.scada_port}"
          f"  · unit id 1 · SALT OKUNUR")
    print(f"                 kuresel blok  PDU {icd.GLOBAL_BASE}..{icd.GLOBAL_SIZE - 1}"
          f"   ({icd.GLOBAL_SIZE} kelime)")
    print(f"                 {DEMO_PANEL} blogu  PDU {base}..{base + icd.REGS_PER_PANEL - 1}"
          f"   = {icd.PANEL_BASE} + {icd.REGS_PER_PANEL} x {live.panel_index - 1}")
    print(f"                 Modicon 4x    {40001 + base}")
    print()
    _print_notify(rt, args)
    print("  JURI ICIN, IKINCI BIR TERMINALDE:")
    if rt.scada is not None:
        for cmd in rt.scada.modpoll_commands(live.panel_index, "127.0.0.1",
                                             args.scada_port):
            print(f"    {cmd}")
    print()
    print(f"    curl -s {url}/api/health | python -m json.tool")
    print(f"    curl -s {url}/api/panel/{DEMO_PANEL} | python -m json.tool")
    print(f"    curl -s \"{url}/api/scada/registers?panel={DEMO_PANEL}\" | python -m json.tool")
    print(f"    curl -s {url}/api/analysis/supplied-data | python -m json.tool")
    print()
    print(_rule())
    print("  DEMO ICERIGI (hepsi simulatore enjekte edildi, hicbiri sahte degil)")
    for rec in rt.injected:
        flag = "ALARM" if rec.get("expect_alarm") else "NEGATIF"
        print(f"    {rec['panel_key']:<16} {rec['scenario']:<20} "
              f"{rec.get('ago_days', 0):>5.1f} gun once  [{flag}]")
    print()
    jv = next((j for j in live.joints if j.key == "C07-L2-PABUC"), None)
    if jv is not None:
        fa = rt.first_alarm_day(DEMO_PANEL, "C07-L2-PABUC")
        sib = jv.sibling_median_c
        print(f"  AMIRAL GEMISI · {DEMO_PANEL} / C07-L2-PABUC (Cikis 7 / L2 pabucu)")
        print(f"    mutlak sicaklik  {jv.temp_c if jv.temp_c is None else round(jv.temp_c,1)} C"
              f"   kardes medyani {sib if sib is None else round(sib,1)} C"
              f"    -> hicbir esik atmaz")
        print(f"    theta            {jv.theta_k if jv.theta_k is None else round(jv.theta_k,2)} K"
              f" @ 400 A referans   (gunluk medyan {fa['theta_last']} K, tepe {fa['theta_max']} K)")
        print(f"    CUSUM            {jv.cusum:.1f}  (h = 8.0)"
              f"   ·  egim {jv.slope_k_per_week:+.2f} K/hafta"
              f"   ·  {fa['days']} gunluk seri")
        print(f"    fazla direnc     {jv.excess_r_lo_uohm:.1f} .. {jv.excess_r_hi_uohm:.1f} uohm"
              f"   (R_th 2-4 K/W araligi ile; tek sayi olarak verilmez)")
        print(f"    NE ZAMAN BASLADI enjekte edilen baslangic 41 gun once;"
              f" degisim noktasi kestirimi {fa['changepoint_days_ago']} gun once")
        print(f"                     (dogrusal rampada BIC adim uydurmasi rampanin"
              f" ORTASINA kayar - gec tarafta yanli, ve bunu soyluyoruz)")
        print(f"    NE ZAMAN BILDIK  CUSUM esigi ilk {fa['cusum_first_days_ago']} gun once asildi"
              f"  <- operatore verilebilecek tarih budur")
        print(f"    durum            {jv.severity}   ·  pano {live.severity}"
              f"  HI {live.health_index:.1f}   ·  acik alarm {len(live.alarms)}")
    print()
    print(_rule())
    for line in HONESTY:
        print(f"  {line}")
    print(_rule("="))
    print("  Durdurmak icin Ctrl+C")
    print()

    app = create_app(rt)

    if args.open_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    config = uvicorn.Config(app, host=args.host, port=args.port,
                            log_level=args.log_level, access_log=False)
    server = uvicorn.Server(config)

    def _shutdown(signum, frame) -> None:  # noqa: ANN001
        server.should_exit = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _shutdown)
        except (ValueError, OSError):  # not on the main thread / not supported
            pass

    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        print()
        print("  kapatiliyor ...")
        rt.stop()
        try:
            rt.store.close()
        except Exception:  # noqa: BLE001
            pass
        print("  kapandi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
