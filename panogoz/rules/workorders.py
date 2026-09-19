"""Alarm türüne göre iş emri kartı: kim, ne kadar sürede, hangi adımlar, hangi güvenlik kuralı.

Şartname: "Kontrol ünitesindeki ufak bir çalışma hem hayati risk taşımakta hem de şebekeye
etkisi sebebiyle planlı kesinti yapılmalıdır." Bu yüzden her kart `needs_outage` ve
güvenlik maddelerini açıkça taşır. İçerik genel saha uygulaması bilgisidir; kurumun
kendi işletme talimatı (ör. TEDAŞ/ADM-GDZ iş güvenliği prosedürleri) önceliklidir ve
sahaya çıkmadan önce onlarla doğrulanmalıdır (docs/12 §5).
"""
from __future__ import annotations

from dataclasses import dataclass

from panogoz.rules.engine import Severity


@dataclass(frozen=True)
class WorkOrderTemplate:
    title: str
    crew: str
    needs_outage: bool
    steps: tuple[str, ...]
    safety: tuple[str, ...]
    est_duration: str


_ARC_GENERIC = (
    "Enerjili panoda kapak açılmaz, cıvata sıkılmaz; ark flaş KKD'si olmadan yaklaşılmaz.",
    "Çalışma öncesi kesme-ayırma, gerilimsizlik doğrulaması ve topraklama (5 emniyet kuralı).",
)

TEMPLATES: dict[str, WorkOrderTemplate] = {
    "loose_bolt": WorkOrderTemplate(
        "Gevşek cıvatalı bağlantı — sıkma ve kontak direnci kontrolü",
        "Bakım-onarım ekibi (yetkili, 2 kişi)",
        True,
        (
            "Yük altında termal kamerayla ilgili fazın eklem noktasını ölç, kanıt görüntüsü al.",
            "Planlı kesinti talebi aç; kesinti onayı gelmeden panoya müdahale etme.",
            "Fideri gerilimsiz bırak, gerilimsizliği doğrula, topraklama uygula.",
            "Bağlantı yüzeyini temizle (oksit/kararma), cıvatayı üretici tork değerine göre sık.",
            "Kontak direncini ölç (mikro-ohmmetre); komşu fazla kıyasla.",
            "Yük al, 1 saat sonra termal kamerayla tekrar ölç; θ'nın düştüğünü konsoldan doğrula.",
        ),
        _ARC_GENERIC,
        "2–4 saat (kesinti dahil)",
    ),
    "loose_bolt_trend": WorkOrderTemplate(
        "Kalıcı θ kayması — planlı bakım listesine ekle",
        "Planlı bakım ekibi",
        False,
        (
            "Sonraki planlı bakımda ilgili fazın eklemini termal kamerayla ölç.",
            "Kayma sürerse iş emrini 'gevşek cıvatalı bağlantı' kartına yükselt.",
        ),
        ("Bu bir erken uyarıdır; acil müdahale gerektirmez.",),
        "Planlı bakım penceresinde",
    ),
    "overload": WorkOrderTemplate(
        "Sürekli aşırı yük — yük dağılımı kontrolü",
        "Operasyon / şebeke planlama + saha ekibi",
        False,
        (
            "Fider yükünü SCADA/pano ölçüsüyle doğrula (CT oranı ve ölçü zinciri).",
            "Yükü komşu fiderlere dağıtmayı veya geçici yük azaltmayı değerlendir.",
            "Kablo/bara kesitini ve koruma ayarını anma akımıyla karşılaştır.",
            "Aşırı yük sürüyorsa kapasite artırımı için planlama talebi aç.",
        ),
        ("Yük atma/aktarma manevraları işletme talimatına göre yapılır.",),
        "1–2 saat (değerlendirme)",
    ),
    "neutral_overload": WorkOrderTemplate(
        "Nötr harmonik yüklenmesi — harmonik analizi ve nötr kesit kontrolü",
        "Kalite/ölçüm ekibi + bakım ekibi",
        False,
        (
            "Güç analizörüyle THD ve 3. harmonik oranını ölç (MPR-53CS register'ları).",
            "Nötr bara kesitini ve nötr akımını karşılaştır; nötr kızarması var mı bak.",
            "Yük dengeleme veya harmonik filtre/K-faktörlü trafo seçeneğini değerlendir.",
        ),
        _ARC_GENERIC[:1],
        "2–3 saat",
    ),
    "neutral_joint": WorkOrderTemplate(
        "Nötr bağlantı gevşemesi — sıkma ve kontrol",
        "Bakım-onarım ekibi (yetkili, 2 kişi)",
        True,
        (
            "Nötr bara bağlantısını yük altında termal kamerayla ölç.",
            "Planlı kesinti talebi aç, gerilimsizliği doğrula, topraklama uygula.",
            "Nötr bağlantı cıvatasını tork değerine göre sık, temas yüzeyini temizle.",
            "Yük al, tekrar ölç.",
        ),
        _ARC_GENERIC,
        "2–3 saat (kesinti dahil)",
    ),
    "condensation": WorkOrderTemplate(
        "Yoğuşma riski — nem kaynağını bul ve gider",
        "Saha bakım ekibi",
        False,
        (
            "Kapı contası, kablo girişleri ve havalandırma açıklıklarını kontrol et.",
            "Kabin ısıtıcısı / nem alıcıyı devreye al veya çalışıp çalışmadığını doğrula.",
            "Yoğuşma görüldüyse yalıtım direncini ölç; gerekirse planlı kesinti talep et.",
            "Nem kaynağı giderilince RH ve çiy marjının normale döndüğünü konsoldan doğrula.",
        ),
        ("Islak yüzey görüldüyse panoya müdahale için kesinti şarttır.",),
        "1–3 saat",
    ),
    "humidity_high": WorkOrderTemplate(
        "Yüksek nem — izleme",
        "Saha bakım ekibi (rutin)",
        False,
        ("Rutin turda kabin mahali ve havalandırmayı kontrol et.",),
        (),
        "Rutin tur",
    ),
    "pd_tracking": WorkOrderTemplate(
        "Kısmi deşarj + destekleyici belirti — yalıtım muayenesi",
        "Ölçüm/test ekibi",
        True,
        (
            "Ultrasonik/TEV ölçümüyle PD'yi doğrula (konsol PD indeksi yalnız yönlendirmedir).",
            "Yalıtım yüzeylerini kirlilik/izlenme (tracking) açısından incele; nem kaynağını gider.",
            "Gerekirse planlı kesintide yalıtım direnci ve temizlik yap.",
        ),
        _ARC_GENERIC,
        "3–5 saat",
    ),
    "arc_trip": WorkOrderTemplate(
        "ARK KORUMA TETİKLEDİ — acil müdahale",
        "Acil müdahale ekibi + operasyon merkezi",
        True,
        (
            "Panonun enerjisinin gerçekten kesildiğini operasyon merkezinden doğrula.",
            "Panoya girme: TVOC-2 kayıtlarını (Trip 1-7: dedektör/röle/tarih-saat) uzaktan/yerinde oku.",
            "Hasar ve yangın belirtisini uzaktan/güvenli mesafeden değerlendir.",
            "Nedeni bulmadan yeniden enerjilendirme yapma; kök neden raporu aç.",
        ),
        (
            "Ark flaş sonrası pano içi gaz/is ve gerilim altında kalan parça riski vardır.",
            *_ARC_GENERIC,
        ),
        "Olay yerine göre",
    ),
    "arc_integrity": WorkOrderTemplate(
        "Ark koruma bütünlüğü kaybı — koruma devre dışı",
        "Bakım-onarım + koruma ekibi",
        False,
        (
            "TVOC-2 tanılama register'larını (200–225) ve son hata kodlarını (6 haneli DTC) oku.",
            "Sensör kablosu/konnektörü ve ışık sensörü bağlantısını kontrol et.",
            "Onarılana kadar bu panoda ark korumasız çalışmanın risk değerlendirmesini yap (yük azaltma/erişim kısıtı).",
        ),
        ("Bu panoda ark koruma çalışmıyor: kapak açma ve manevra kısıtlanmalıdır.",),
        "1–2 saat",
    ),
    "comms_lost": WorkOrderTemplate(
        "Cihaz susuyor — haberleşme kontrolü",
        "Haberleşme / saha ekibi",
        False,
        (
            "Ağ geçidi ve düğüm güç/anten/ağ durumunu uzaktan kontrol et.",
            "Uzaktan çözülemezse sahaya kontrol turu planla (süreç alarmı değildir).",
        ),
        (),
        "1 saat",
    ),
}

DEFAULT_TEMPLATE = WorkOrderTemplate(
    "İnceleme", "Saha ekibi", False, ("Konsoldaki kanıt ekranına göre incele.",), (), "—"
)

PRIORITY = {
    Severity.WARNING: ("Düşük", "Bir sonraki planlı turda"),
    Severity.ALARM: ("Yüksek", "24 saat içinde"),
    Severity.CRITICAL: ("ACİL", "Derhal"),
}


def work_order(kind: str, severity: Severity, *, connection_id: str, location: str = "", phase: str | None = None) -> dict:
    tpl = TEMPLATES.get(kind, DEFAULT_TEMPLATE)
    priority, due = PRIORITY.get(severity, PRIORITY[Severity.WARNING])
    return {
        "title": tpl.title,
        "connection_id": connection_id,
        "location": location,
        "phase": phase,
        "priority": priority,
        "due": due,
        "crew": tpl.crew,
        "needs_outage": tpl.needs_outage,
        "steps": list(tpl.steps),
        "safety": list(tpl.safety),
        "est_duration": tpl.est_duration,
    }
