"""K2 2.2: dağıtım sertleştirme -- DOĞRULANABİLENLER.

Docker/Mosquitto/nginx bu ortamda çalıştırılamadı. Burada doğrulananlar:
  * docker-compose.yml / Dockerfile / mosquitto.conf / nginx.conf DEĞİŞMEZLERİ (yapılandırma metni),
  * Mosquitto ACL anlamı (tools/mosquitto_acl.py: kuralların Python yeniden uygulaması),
  * PKI: tools/gen_certs.py'nin ürettiği sertifikalarla GERÇEK karşılıklı TLS el sıkışması (Python ssl),
  * MqttBus'ın TLS/mTLS yolu (sahte bir MQTT-over-TLS sunucusuna karşı),
  * /healthz ve /readyz.
Gerçek broker/proxy/konteyner davranışı docs/13'te AÇIK madde.
"""
import re
import socket
import ssl
import threading
from pathlib import Path

import pytest
import yaml

from panogoz.bus import topics
from panogoz.bus.mqtt_bus import MqttBus
from tools import gen_certs
from tools.mosquitto_acl import Acl, topic_matches_sub

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
SERVICES = COMPOSE["services"]


# ============================================================ compose değişmezleri
@pytest.mark.parametrize("name", list(SERVICES))
def test_every_container_is_locked_down(name):
    svc = SERVICES[name]
    assert svc.get("cap_drop") == ["ALL"], f"{name}: tüm Linux yetenekleri düşürülmeli"
    assert "no-new-privileges:true" in svc.get("security_opt", []), f"{name}: ayrıcalık yükseltme kapalı olmalı"
    assert svc.get("read_only") is True, f"{name}: kök dosya sistemi salt okunur olmalı"
    assert "healthcheck" in svc, f"{name}: sağlık kontrolü zorunlu"
    assert not svc.get("privileged") and "cap_add" not in svc and svc.get("network_mode") != "host"
    assert svc.get("restart") == "unless-stopped"


def test_images_are_pinned_and_app_does_not_run_as_root():
    for name in ("mosquitto", "proxy"):
        image = SERVICES[name]["image"]
        tag = image.split(":")[-1]
        assert tag != "latest" and re.match(r"^\d+\.\d+", tag), f"{name}: sürüm sabitlenmeli ({image})"
    for name in ("mosquitto", "panogoz"):
        uid = str(SERVICES[name]["user"]).split(":")[0]
        assert uid.isdigit() and int(uid) > 0, f"{name}: root olmayan sayısal kullanıcı"


def test_only_intended_ports_are_published_and_scada_binds_to_a_chosen_interface():
    published = {}
    for name, svc in SERVICES.items():
        for p in svc.get("ports", []):
            published.setdefault(name, []).append(str(p))
    assert published["proxy"] == ["443:8443"]
    assert published["mosquitto"] == ["8883:8883"]  # mTLS; 1883 düz metin YOK
    for p in published["panogoz"]:
        assert p.startswith("${SCADA_BIND_ADDR:-127.0.0.1}:"), "SCADA protokolleri varsayılan olarak yalnız yerel arayüze bağlanır"
    assert not any("8080" in p for ports in published.values() for p in ports), "uygulama HTTP'si doğrudan yayınlanmaz"
    assert not any("1883" in p for ports in published.values() for p in ports)


def test_networks_isolate_broker_and_app_from_the_outside():
    nets = COMPOSE["networks"]
    assert nets["backend"].get("internal") is True
    assert "edge" not in SERVICES["panogoz"]["networks"] and "edge" not in SERVICES["mosquitto"]["networks"]
    assert "ingest" not in SERVICES["panogoz"]["networks"] and "ingest" not in SERVICES["proxy"]["networks"]
    assert set(SERVICES["proxy"]["networks"]) == {"backend", "edge"}


def test_certificates_are_mounted_read_only_and_the_ca_private_key_is_never_mounted():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "ca.key" not in text, "kök CA anahtarı hiçbir konteynere verilmez"
    for name, svc in SERVICES.items():
        for vol in svc.get("volumes", []):
            if "certs" in vol:
                assert vol.endswith(":ro"), f"{name}: {vol} salt okunur olmalı"
    mosq_keys = [v for v in SERVICES["mosquitto"]["volumes"] if v.endswith(".key:/mosquitto/certs/mosquitto.key:ro") or "panogoz-health.key" in v]
    assert len(mosq_keys) == 2
    assert not any("panogoz-server.key" in v for v in SERVICES["mosquitto"]["volumes"])  # uygulama anahtarı broker'a verilmez


def test_startup_order_waits_for_healthy_dependencies():
    assert SERVICES["panogoz"]["depends_on"]["mosquitto"]["condition"] == "service_healthy"
    assert SERVICES["proxy"]["depends_on"]["panogoz"]["condition"] == "service_healthy"


def test_broker_healthcheck_uses_a_dedicated_low_privilege_identity_over_mtls():
    test = " ".join(SERVICES["mosquitto"]["healthcheck"]["test"])
    assert "panogoz-health.crt" in test and "--cafile" in test and "8883" in test and "1883" not in test.replace("8883", "")


# ============================================================ Dockerfile
def test_dockerfile_runs_unprivileged_with_a_healthcheck_and_without_test_tooling():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^FROM python:3\.\d+-slim", text, re.M)
    assert re.search(r"^USER 10001", text, re.M) and "HEALTHCHECK" in text
    assert "--no-create-home" in text and "nologin" in text
    assert "COPY . " not in text and "COPY .\n" not in text  # tüm depoyu değil, gereken dizinleri kopyala
    instructions = [ln for ln in text.splitlines() if re.match(r"^(RUN|COPY|CMD)", ln)]
    assert any("requirements-runtime.txt" in ln for ln in instructions)
    for tool in ("pytest", "amqtt", "c104", "playwright"):  # kelime sınırlı: "--iec104-port" bir test aracı değil
        assert not any(re.search(rf"(?<![A-Za-z0-9]){tool}(?![A-Za-z0-9])", ln) for ln in instructions), tool
    runtime = (ROOT / "requirements-runtime.txt").read_text(encoding="utf-8")
    for test_only in ("pytest", "amqtt", "c104", "playwright", "opencv"):
        assert test_only not in runtime
    assert "--no-demo-controls" in text  # üretimde demo kontrol uçları kapalı


def test_dockerignore_keeps_secrets_and_sources_of_bloat_out():
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()
    for item in ("deploy/certs", ".env", ".git", "tests"):
        assert item in ignore
    assert "**/*.pdf" in ignore  # organizatör PDF'leri imaja girmez; çalışma zamanı verisi (xlsx) girer
    assert "*.xlsx" not in ignore


def test_private_keys_are_git_ignored():
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "deploy/certs/" in gi and "*.key" in gi


# ============================================================ Mosquitto yapılandırması
def mosquitto_directives():
    out = []
    for line in (ROOT / "deploy" / "mosquitto" / "mosquitto.conf").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(tuple(line.split(None, 1)) if " " in line else (line, ""))
    return out


def test_mosquitto_accepts_only_mutual_tls_and_no_anonymous_access():
    d = mosquitto_directives()
    values = dict(d)
    assert [v for k, v in d if k == "listener"] == ["8883"]  # tek dinleyici, 1883 yok
    assert values["require_certificate"] == "true" and values["use_identity_as_username"] == "true"
    assert values["allow_anonymous"] == "false" and values["per_listener_settings"] == "true"
    assert values["acl_file"] == "/mosquitto/config/acl"
    assert "password_file" not in values  # parola yok: kimlik sertifikadan
    for limit in ("max_connections", "max_packet_size", "message_size_limit", "max_queued_messages"):
        assert limit in values


# ============================================================ nginx yapılandırması
def test_nginx_terminates_tls_requires_client_certs_and_blocks_demo_controls():
    conf = (ROOT / "deploy" / "nginx" / "nginx.conf").read_text(encoding="utf-8")
    assert "listen 8443 ssl" in conf and "listen 80" not in conf and "listen 8080" not in conf
    assert "ssl_verify_client on" in conf and "TLSv1.2 TLSv1.3" in conf and "TLSv1.1" not in conf and "TLSv1 " not in conf
    assert "server_tokens off" in conf and "Strict-Transport-Security" in conf and "Content-Security-Policy" in conf
    assert re.search(r"location /api/sim/ \{ return 403; \}", conf)
    assert "limit_req_zone" in conf and "client_max_body_size 64k" in conf
    assert "$request_method !~ ^(GET|POST|HEAD)$" in conf


# ============================================================ ACL anlamı
ACL = Acl.load(ROOT / "deploy" / "mosquitto" / "acl")


def test_device_can_publish_only_its_own_telemetry_and_read_only_its_own_commands():
    dev = "TC-0001"
    assert ACL.allowed(dev, "c1", topics.telemetry(dev), "write")
    assert ACL.allowed(dev, "c1", topics.command(dev), "read")
    assert ACL.allowed(dev, "c1", topics.command(dev), "subscribe")
    other = "TC-0002"
    assert not ACL.allowed(dev, "c1", topics.telemetry(other), "write")  # başkası adına yayın YOK
    assert not ACL.allowed(dev, "c1", topics.command(other), "subscribe")
    assert not ACL.allowed(dev, "c1", topics.command(dev), "write")  # kendi komutuna yazamaz (sahte komut)
    assert not ACL.allowed(dev, "c1", topics.telemetry(dev), "subscribe")


def test_device_cannot_eavesdrop_with_wildcards_or_touch_server_and_system_topics():
    dev = "TC-0001"
    for f in ("#", "+/#", "panogoz/#", "panogoz/v1/dev/+/telemetry", "panogoz/v1/dev/#", "panogoz/v1/dev/+/cmd", "$SYS/#", "$SYS/broker/uptime"):
        assert not ACL.allowed(dev, "c1", f, "subscribe"), f"{f} aboneliği reddedilmeli"
    assert not ACL.allowed(dev, "c1", "panogoz/v1/srv/x", "write")
    assert not ACL.allowed(dev, "c1", "panogoz/v1/dev/+/telemetry", "write")  # yayın konusunda joker olamaz


def test_server_reads_all_telemetry_writes_commands_but_cannot_forge_telemetry():
    srv = "panogoz-server"
    assert ACL.allowed(srv, "s", topics.TELEMETRY_ALL, "subscribe")
    assert ACL.allowed(srv, "s", topics.telemetry("GW-0001"), "read")
    assert ACL.allowed(srv, "s", topics.command("GW-0001"), "write")
    assert not ACL.allowed(srv, "s", topics.telemetry("GW-0001"), "write")  # cihaz adına telemetri UYDURAMAZ
    assert not ACL.allowed(srv, "s", "#", "subscribe")


def test_health_identity_is_tiny_and_anonymous_gets_nothing():
    assert ACL.allowed("panogoz-health", "hp", "$SYS/broker/uptime", "subscribe")
    assert ACL.allowed("panogoz-health", "health-probe", topics.health("health-probe"), "write")
    assert not ACL.allowed("panogoz-health", "hp", topics.telemetry("TC-0001"), "read")
    assert not ACL.allowed("panogoz-health", "hp", topics.health("other"), "write")  # yalnız kendi sabit konusu
    # gerçek Mosquitto'da `topic` satırlarında %c/%u değişmez metindir: ACL dosyasında topic satırında yer tutucu OLMAMALI
    text = (ROOT / "deploy" / "mosquitto" / "acl").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip().startswith("topic "):
            assert "%u" not in line and "%c" not in line, line
    for t, a in ((topics.telemetry("TC-0001"), "write"), ("#", "subscribe"), (topics.command("TC-0001"), "read")):
        assert not ACL.allowed(None, "anon", t, a)


def test_acl_evaluator_semantics_deny_first_and_wildcards():
    acl = Acl.parse("user u\ntopic read a/#\ntopic deny a/secret\n")
    assert acl.allowed("u", "c", "a/b/c", "read") and acl.allowed("u", "c", "a/#", "subscribe")
    assert not acl.allowed("u", "c", "a/secret", "read") and not acl.allowed("u", "c", "#", "subscribe")
    assert not acl.allowed("u", "c", "a/b", "write") and not acl.allowed("v", "c", "a/b", "read")
    assert topic_matches_sub("a/+/c", "a/b/c") and not topic_matches_sub("a/+/c", "a/b/d/c")
    assert not topic_matches_sub("#", "$SYS/x") and topic_matches_sub("$SYS/#", "$SYS/x")
    with pytest.raises(ValueError):
        Acl.parse("topic bogus a/b\n")


def test_device_identity_validation_blocks_wildcards_slashes_and_reserved_names():
    for ok in ("TC-0001", "IRPD-0001", "gw_01"):
        assert topics.valid_device_id(ok)
    for bad in ("", "a", "+", "#", "TC/0001", "TC 1", "$SYS", "panogoz-server", "panogoz-health", "x" * 40, "-lead"):
        assert not topics.valid_device_id(bad), bad
        with pytest.raises(ValueError):
            topics.telemetry(bad)


# ============================================================ PKI + GERÇEK karşılıklı TLS
@pytest.fixture(scope="module")
def pki(tmp_path_factory):
    out = tmp_path_factory.mktemp("pki")
    paths = gen_certs.generate(out, ["TC-0001", "TC-0002"], days=30)
    return out, paths


def server_ctx(pki_dir, *, cert="mosquitto", require_client=True, ca="ca"):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(pki_dir / f"{cert}.crt", pki_dir / f"{cert}.key")
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    if require_client:
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_verify_locations(pki_dir / f"{ca}.crt")
    return ctx


def client_ctx(pki_dir, *, device=None, ca="ca"):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(pki_dir / f"{ca}.crt")
    ctx.check_hostname = True
    if device:
        ctx.load_cert_chain(pki_dir / "devices" / f"{device}.crt", pki_dir / "devices" / f"{device}.key")
    return ctx


class TlsEcho:
    """Tek bağlantılık TLS sunucusu: el sıkışma sonucunu ve istemci CN'ini kaydeder."""

    def __init__(self, ctx, handler=None):
        self.ctx, self.handler = ctx, handler
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        self.results = []
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while True:
            try:
                raw, _ = self.sock.accept()
            except OSError:
                return
            try:
                raw.settimeout(3)
                tls = self.ctx.wrap_socket(raw, server_side=True)
                cert = tls.getpeercert()
                cn = None
                if cert:
                    cn = dict(x[0] for x in cert["subject"]).get("commonName")
                self.results.append(("ok", cn))
                if self.handler:
                    self.handler(tls)
                tls.close()
            except (ssl.SSLError, OSError) as exc:
                self.results.append(("fail", type(exc).__name__))
                raw.close()

    def close(self):
        self.sock.close()


def wait_result(srv, timeout=3.0):
    """Sunucu iş parçacığı sonucu, istemci istisnası döndükten SONRA kaydedebilir (yarış)."""
    import time

    end = time.time() + timeout
    while not srv.results and time.time() < end:
        time.sleep(0.02)
    return srv.results[-1] if srv.results else None


def handshake(port, ctx, hostname="localhost"):
    with socket.create_connection(("127.0.0.1", port), timeout=3) as raw:
        with ctx.wrap_socket(raw, server_hostname=hostname) as tls:
            tls.recv(1)  # TLS 1.3'te istemci hatası (ör. sertifika yok) ilk okumada görünür
            return tls.version()


def test_generated_pki_has_expected_shape(pki):
    out, paths = pki
    from cryptography import x509
    from cryptography.x509.oid import ExtendedKeyUsageOID

    ca = x509.load_pem_x509_certificate((out / "ca.crt").read_bytes())
    assert ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is True
    dev = x509.load_pem_x509_certificate((out / "devices" / "TC-0001.crt").read_bytes())
    assert dev.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[0].value == "TC-0001"
    eku = dev.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    assert list(eku) == [ExtendedKeyUsageOID.CLIENT_AUTH]
    assert dev.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is False
    srv = x509.load_pem_x509_certificate((out / "mosquitto.crt").read_bytes())
    assert list(srv.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value) == [ExtendedKeyUsageOID.SERVER_AUTH]
    sans = srv.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert "localhost" in sans.get_values_for_type(x509.DNSName) and "mosquitto" in sans.get_values_for_type(x509.DNSName)
    assert set(paths) >= {"ca", "mosquitto", "proxy", "panogoz-server", "panogoz-health", "TC-0001", "TC-0002"}


def test_reserved_and_malformed_identities_cannot_be_issued_as_devices(pki):
    out, _ = pki
    ca_key, ca_cert = gen_certs.make_ca()
    for bad in ("panogoz-server", "panogoz-health", "TC/0001", "+", ""):
        with pytest.raises(ValueError):
            gen_certs.issue(ca_key, ca_cert, bad)
    gen_certs.issue(ca_key, ca_cert, "panogoz-server", allow_reserved=True)  # yalnız açık izinle


def test_device_with_valid_certificate_completes_mutual_tls_and_server_learns_its_cn(pki):
    out, _ = pki
    srv = TlsEcho(server_ctx(out), handler=lambda tls: tls.send(b"x"))
    try:
        version = handshake(srv.port, client_ctx(out, device="TC-0001"))
        assert version in ("TLSv1.2", "TLSv1.3")
        assert srv.results[-1] == ("ok", "TC-0001")  # kimlik = sertifikadan
    finally:
        srv.close()


def test_client_without_certificate_is_rejected_by_the_server(pki):
    out, _ = pki
    srv = TlsEcho(server_ctx(out))
    try:
        with pytest.raises((ssl.SSLError, ConnectionError, OSError)):
            handshake(srv.port, client_ctx(out, device=None))
        assert wait_result(srv)[0] == "fail"
    finally:
        srv.close()


def test_client_certificate_from_a_foreign_ca_is_rejected(pki, tmp_path):
    out, _ = pki
    rogue = tmp_path / "rogue"
    gen_certs.generate(rogue, ["TC-0001"], days=30)  # başka bir CA, aynı cihaz kimliği!
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(out / "ca.crt")
    ctx.load_cert_chain(rogue / "devices" / "TC-0001.crt", rogue / "devices" / "TC-0001.key")
    srv = TlsEcho(server_ctx(out))
    try:
        with pytest.raises((ssl.SSLError, ConnectionError, OSError)):
            handshake(srv.port, ctx)
        assert wait_result(srv)[0] == "fail"
    finally:
        srv.close()


def test_client_refuses_a_server_with_the_wrong_hostname_or_wrong_ca(pki, tmp_path):
    out, _ = pki
    srv = TlsEcho(server_ctx(out, require_client=False))
    try:
        with pytest.raises(ssl.SSLCertVerificationError):
            handshake(srv.port, client_ctx(out), hostname="evil.example")  # SAN'da yok
        rogue = tmp_path / "rogue2"
        gen_certs.generate(rogue, [], days=30)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_verify_locations(rogue / "ca.crt")  # güvenilmeyen CA
        with pytest.raises(ssl.SSLCertVerificationError):
            handshake(srv.port, ctx)
    finally:
        srv.close()


def test_a_device_certificate_cannot_impersonate_the_broker(pki):
    """EKU=clientAuth olan cihaz sertifikası sunucu kimliği olarak KABUL EDİLMEZ."""
    out, _ = pki
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(out / "devices" / "TC-0001.crt", out / "devices" / "TC-0001.key")
    srv = TlsEcho(ctx)
    try:
        with pytest.raises(ssl.SSLCertVerificationError):
            handshake(srv.port, client_ctx(out), hostname="TC-0001")
    finally:
        srv.close()


# ============================================================ MqttBus TLS
def fake_mqtt_over_tls(pki_dir):
    def handler(tls):
        data = tls.recv(64)
        if data and data[0] == 0x10:  # CONNECT
            tls.send(bytes([0x20, 0x02, 0x00, 0x00]))  # CONNACK, kabul
            tls.settimeout(1.0)
            try:
                tls.recv(64)
            except (socket.timeout, TimeoutError, ssl.SSLError, OSError):
                pass

    return TlsEcho(server_ctx(pki_dir), handler=handler)


def test_mqtt_bus_connects_over_mutual_tls_and_presents_the_device_identity(pki):
    out, _ = pki
    srv = fake_mqtt_over_tls(out)
    bus = MqttBus(
        "localhost", srv.port, client_id="TC-0001",
        tls_ca=str(out / "ca.crt"), tls_cert=str(out / "devices" / "TC-0001.crt"), tls_key=str(out / "devices" / "TC-0001.key"),
    )
    try:
        bus.connect(timeout=5)
        assert bus.is_connected()
        assert srv.results[0] == ("ok", "TC-0001")
    finally:
        bus.disconnect()
        srv.close()


def test_mqtt_bus_without_a_client_certificate_cannot_connect_to_an_mtls_broker(pki):
    out, _ = pki
    srv = fake_mqtt_over_tls(out)
    bus = MqttBus("localhost", srv.port, client_id="anon", tls_ca=str(out / "ca.crt"))
    try:
        with pytest.raises((ssl.SSLError, TimeoutError, OSError, ConnectionError)):
            bus.connect(timeout=2)
        assert not bus.is_connected()
    finally:
        try:
            bus.disconnect()
        except Exception:  # noqa: BLE001
            pass
        srv.close()


def test_mqtt_bus_rejects_a_client_certificate_without_a_ca():
    with pytest.raises(ValueError, match="tls_ca"):
        MqttBus("localhost", 8883, tls_cert="x.crt", tls_key="x.key")


# ============================================================ sağlık uçları
def test_healthz_is_always_ok_and_readyz_reflects_fleet_readiness():
    from panogoz.api.app import create_app
    from panogoz.api.fleet_service import FleetService
    from tests.test_fleet_service import SPECS

    cold = create_app().test_client()  # filo henüz kurulmadı
    assert cold.get("/healthz").get_json() == {"status": "ok"}
    r = cold.get("/readyz")
    assert r.status_code == 503 and r.get_json()["status"] == "starting"
    warm = create_app(fleet_service=FleetService(SPECS)).test_client()
    assert warm.get("/readyz").status_code == 200 and warm.get("/readyz").get_json()["status"] == "ready"
