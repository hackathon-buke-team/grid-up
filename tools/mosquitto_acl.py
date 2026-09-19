"""Mosquitto ACL dosyası ayrıştırıcı + değerlendirici (broker ÇALIŞTIRMADAN ACL mantığını sınamak için).

Mosquitto'nun `acl_file` anlamını Python'da yeniden uygular:
- `user X` satırından sonraki `topic ...` kuralları X'e aittir; ilk `user`'dan ÖNCEKİ `topic` kuralları
  yalnız anonim istemciye uygulanır; `pattern ...` kuralları HERKESE uygulanır (`%u` = kullanıcı adı,
  `%c` = istemci kimliği).
- Erişim: `read` (abone olma + mesaj alma), `write` (yayın), `readwrite`, `deny`.
- Varsayılan REDDET. `deny` her zaman `allow`'dan önce gelir.
- ABONELİK kontrolünde istenen süzgeç, ACL süzgecinin *eşleştirdiği bir dize* olarak ele alınır:
  ACL `dev/#` iken `dev/+/telemetry` aboneliği izinli, `#` aboneliği REDDEDİLİR.

DÜRÜSTLÜK: bu bir yeniden uygulamadır, gerçek Mosquitto değildir; broker bu ortamda çalıştırılamadı
(Docker/yönetici yok). Gerçek broker'a karşı doğrulama docs/13'te açık madde.

    python -m tools.mosquitto_acl deploy/mosquitto/acl --user TC-0001 --topic panogoz/v1/dev/TC-0001/telemetry --access write
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path


def topic_matches_sub(sub: str, topic: str) -> bool:
    """MQTT süzgeç eşleşmesi (`+` bir seviye, `#` kalan). `$` ile başlayan konular joker ile başlayan
    süzgeçlerle eşleşmez."""
    if topic.startswith("$") and (sub.startswith("+") or sub.startswith("#")):
        return False
    s_parts, t_parts = sub.split("/"), topic.split("/")
    for i, s in enumerate(s_parts):
        if s == "#":
            return i == len(s_parts) - 1
        if i >= len(t_parts):
            return False
        if s != "+" and s != t_parts[i]:
            return False
    return len(s_parts) == len(t_parts)


@dataclass(frozen=True)
class Rule:
    access: str  # read | write | readwrite | deny
    topic: str


@dataclass
class Acl:
    anonymous: list[Rule] = field(default_factory=list)
    users: dict[str, list[Rule]] = field(default_factory=dict)
    patterns: list[Rule] = field(default_factory=list)

    @classmethod
    def parse(cls, text: str) -> "Acl":
        acl = cls()
        current: list[Rule] | None = None
        for lineno, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 2)
            keyword = parts[0].lower()
            if keyword == "user":
                if len(parts) != 2:
                    raise ValueError(f"{lineno}: 'user' tek argüman ister")
                current = acl.users.setdefault(parts[1], [])
            elif keyword in ("topic", "pattern"):
                if len(parts) < 2:
                    raise ValueError(f"{lineno}: '{keyword}' konu ister")
                if len(parts) == 2:
                    access, topic = "readwrite", parts[1]
                else:
                    access, topic = parts[1].lower(), parts[2]
                    if access not in ("read", "write", "readwrite", "deny"):
                        raise ValueError(f"{lineno}: geçersiz erişim türü {access!r}")
                rule = Rule(access, topic.strip())
                if keyword == "pattern":
                    acl.patterns.append(rule)
                else:
                    (current if current is not None else acl.anonymous).append(rule)
            else:
                raise ValueError(f"{lineno}: bilinmeyen anahtar {keyword!r}")
        return acl

    @classmethod
    def load(cls, path: str | Path) -> "Acl":
        return cls.parse(Path(path).read_text(encoding="utf-8"))

    def _rules_for(self, username: str | None, clientid: str) -> list[Rule]:
        rules = list(self.users.get(username, [])) if username else list(self.anonymous)
        for p in self.patterns:
            if "%u" in p.topic and not username:
                continue
            topic = p.topic.replace("%c", clientid)
            if username:
                topic = topic.replace("%u", username)
            rules.append(Rule(p.access, topic))
        return rules

    def allowed(self, username: str | None, clientid: str, topic: str, access: str) -> bool:
        """`access`: 'read' (mesaj alma), 'write' (yayın) veya 'subscribe' (abonelik isteği)."""
        if access not in ("read", "write", "subscribe"):
            raise ValueError("access read/write/subscribe olmalı")
        if access == "write" and any(ch in topic for ch in "+#"):
            return False  # yayın konusunda joker olamaz
        rules = self._rules_for(username, clientid)
        wanted = "write" if access == "write" else "read"

        def hit(rule: Rule) -> bool:
            return topic_matches_sub(rule.topic, topic)

        if any(r.access == "deny" and hit(r) for r in rules):
            return False
        return any(r.access in (wanted, "readwrite") and hit(r) for r in rules)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("acl")
    parser.add_argument("--user")
    parser.add_argument("--client", default="client")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--access", choices=("read", "write", "subscribe"), required=True)
    args = parser.parse_args()
    ok = Acl.load(args.acl).allowed(args.user, args.client, args.topic, args.access)
    print("İZİN VERİLDİ" if ok else "REDDEDİLDİ")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
