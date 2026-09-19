"""MQTT konu şeması (v1) ve cihaz kimliği doğrulaması.

Konu ağacı, broker ACL'inin (deploy/mosquitto/acl) TEK gerçek kaynağıdır:

    panogoz/v1/dev/<cihaz_id>/telemetry   cihaz -> sunucu (yalnız o cihaz yazar)
    panogoz/v1/dev/<cihaz_id>/cmd         sunucu -> cihaz (yalnız o cihaz okur)
    panogoz/v1/srv/#                      sunucu içi
    panogoz/v1/health/<istemci_id>        sağlık denetimi

Cihaz kimliği aynı zamanda istemci sertifikasının CN'idir (Mosquitto `use_identity_as_username`):
kimlik ELDE tutulan özel anahtardan gelir, konu adından değil. Kimlik MQTT joker karakteri, `/`
veya `$` içeremez (aksi halde bir cihaz başkasının konusunu "kendi kimliği" diye adlandırabilirdi).
"""
from __future__ import annotations

import re

ROOT = "panogoz/v1"
TELEMETRY_ALL = f"{ROOT}/dev/+/telemetry"
RESERVED_IDENTITIES = frozenset({"panogoz-server", "panogoz-health"})

_DEVICE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,31}$")


def valid_device_id(device_id: str) -> bool:
    return bool(_DEVICE_ID.match(device_id)) and device_id not in RESERVED_IDENTITIES


def _checked(device_id: str) -> str:
    if not valid_device_id(device_id):
        raise ValueError(f"geçersiz veya ayrılmış cihaz kimliği: {device_id!r}")
    return device_id


def telemetry(device_id: str) -> str:
    return f"{ROOT}/dev/{_checked(device_id)}/telemetry"


def command(device_id: str) -> str:
    return f"{ROOT}/dev/{_checked(device_id)}/cmd"


def health(client_id: str) -> str:
    return f"{ROOT}/health/{client_id}"
