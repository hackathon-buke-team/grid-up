"""On-prem PKI üreticisi: kök CA + sunucu/istemci sertifikaları (karşılıklı TLS için).

    python -m tools.gen_certs --out deploy/certs --devices TC-0001 TC-0002 IRPD-0001 GW-0001

Üretilenler (`--out` altında):
    ca.crt / ca.key                    kök CA (ca.key ÇEVRİMDIŞI saklanmalı, sunucuya konmaz)
    mosquitto.crt / mosquitto.key      broker sunucu sertifikası (SAN: mosquitto, localhost, 127.0.0.1)
    proxy.crt / proxy.key              ters vekil sunucu sertifikası
    panogoz-server.crt / .key          uygulamanın broker istemci kimliği (CN=panogoz-server)
    panogoz-health.crt / .key          sağlık denetimi kimliği (CN=panogoz-health)
    devices/<id>.crt / <id>.key        cihaz başına istemci sertifikası (CN = cihaz kimliği)

Cihaz kimliği = CN = Mosquitto kullanıcı adı (`use_identity_as_username`), böylece ACL
(deploy/mosquitto/acl) cihazı yalnız KENDİ konularına bağlar. Anahtarlar ECDSA P-256'dır
(gömülü cihazlar için küçük ve hızlı). `.gitignore` deploy/certs'i dışarıda tutar: anahtarlar
ASLA depoya girmemeli.
"""
from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from panogoz.bus import topics

ORG = "PANO GOZ"


def _name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, ORG), x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def new_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def make_ca(cn: str = "PANO GOZ Kok CA", days: int = 3650):
    key = new_key()
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name(cn))
        .issuer_name(_name(cn))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(True, False, False, False, False, True, True, False, False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def issue(ca_key, ca_cert, cn: str, *, server: bool = False, sans: tuple[str, ...] = (), days: int = 365, allow_reserved: bool = False):
    """`server=True`: sunucu sertifikası (serverAuth + SAN); aksi halde istemci (clientAuth)."""
    if not server and not allow_reserved and not topics.valid_device_id(cn):
        raise ValueError(f"geçersiz veya ayrılmış cihaz kimliği (CN): {cn!r}")
    key = new_key()
    now = dt.datetime.now(dt.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(_name(cn))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH if server else ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
    )
    if server:
        names: list[x509.GeneralName] = []
        for s in sans:
            try:
                names.append(x509.IPAddress(ipaddress.ip_address(s)))
            except ValueError:
                names.append(x509.DNSName(s))
        builder = builder.add_extension(x509.SubjectAlternativeName(names or [x509.DNSName(cn)]), critical=False)
    return key, builder.sign(ca_key, hashes.SHA256())


def write_pair(directory: Path, name: str, key, cert) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    key_path = directory / f"{name}.key"
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    (directory / f"{name}.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def generate(out: Path, devices: list[str], *, days: int = 365) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    ca_key, ca_cert = make_ca()
    write_pair(out, "ca", ca_key, ca_cert)
    paths = {"ca": out / "ca.crt"}
    for name, sans in (("mosquitto", ("mosquitto", "localhost", "127.0.0.1")), ("proxy", ("localhost", "127.0.0.1", "panogoz.local"))):
        key, cert = issue(ca_key, ca_cert, name, server=True, sans=sans, days=days)
        write_pair(out, name, key, cert)
        paths[name] = out / f"{name}.crt"
    for name in sorted(topics.RESERVED_IDENTITIES):
        key, cert = issue(ca_key, ca_cert, name, days=days, allow_reserved=True)
        write_pair(out, name, key, cert)
        paths[name] = out / f"{name}.crt"
    for device_id in devices:
        key, cert = issue(ca_key, ca_cert, device_id, days=days)
        write_pair(out / "devices", device_id, key, cert)
        paths[device_id] = out / "devices" / f"{device_id}.crt"
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path("deploy/certs"))
    parser.add_argument("--devices", nargs="*", default=["TC-0001", "IRPD-0001", "GW-0001"])
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()
    paths = generate(args.out, args.devices, days=args.days)
    print(f"{len(paths)} sertifika üretildi -> {args.out} (ca.key'i çevrimdışı saklayın, depoya koymayın)")


if __name__ == "__main__":
    main()
