# PANO GÖZ Kurulum ve Çalıştırma Kılavuzu

Windows üzerinde yerel uygulama ve demo kullanımı

12 Eylül 2026 · Uygulama sürümü 1.0.0 · Kaynak kod esas alınmıştır

Bu kılavuz, PANO GÖZ projesini mevcut bilgisayarda açmak veya yeni bir bilgisayara kurmak için hazırlanmıştır. Çalışan yerel yol, Python içinden bütün demo bileşenlerini başlatır: simülatör, veri aktarımı, dedektör, alarm kuralları, bildirim simülasyonu, SQLite, web arayüzü ve Modbus TCP sunucusu. İlk hedef, tarayıcıda filo ekranını görmek ve `/api/health` çıktısını doğrulamaktır.

Ana örnekler Windows PowerShell içindir. Terminal 1 uygulamayı açık tutar; Terminal 2 kontrol ve API komutlarını çalıştırır. Komut kutularındaki satırları sırasıyla kopyalayın. `PS C:\...>` gibi bir terminal istemi yazmanız gerekmez.

## 1 Bu bilgisayarda hemen başlatma

Bu bilgisayardaki Python 3.11.2 ve mevcut paketlerle uygulama 12 Eylül 2026 tarihinde çalıştırılarak kontrol edildi. Yeni kurulum yapmadan önce aşağıdaki yolu kullanabilirsiniz.

PowerShell açın ve Terminal 1 içinde çalıştırın:

```powershell
Set-Location 'C:\Users\darkb\Desktop\grid-up-v2'
$env:PYTHONIOENCODING = 'utf-8'
$env:PANOGOZ_BUS = 'inproc'
python -m panogoz.run_local --db .\panogoz.db --scada-host 127.0.0.1 --open
```

Bu komut varsayılan 112 pano hedefi ve 75 günlük demo geçmişiyle açılır. `--db` veritabanını açıkça seçer; `--scada-host 127.0.0.1` Modbus erişimini bu bilgisayarla sınırlar. Tarayıcı otomatik açılmazsa `http://127.0.0.1:8080/` adresini elle açın.

Terminalde varlıklar, senaryolar, geçmiş, günlük özet, filo ısınması ve temizlik adımları görünür. Geçmiş oluşturulurken bekleyin. `HAZIR` satırı açılışın ilerlediğini gösterir; kesin kontrol için API yanıtını da alın. Terminal 1 açık kalmalıdır.

Terminal 2 içinde:

```powershell
$pgBase = 'http://127.0.0.1:8080'
$health = Invoke-RestMethod "$pgBase/api/health"
$health | Select-Object ok, sim_running, panels, degraded
```

Beklenen: `ok` ve `sim_running` değerleri `True`; `degraded` listesi boş olmalıdır. Pano sayısını bu çıktıdan okuyun. Küçük filo isteklerinde sabit demo panoları ayrıca korunabildiği için sayı `--panels` değerinden fazla olabilir.

**Daha hızlı açılış:** Önce çalışan uygulamayı Ctrl+C ile kapatın, sonra ayrı bir demo veritabanıyla aşağıdakini çalıştırın. Kısa geçmiş, 75 günlük gösterimle aynı tarihsel bulguları garanti etmez.

```powershell
python -m panogoz.run_local --panels 8 --backfill-days 20 --db .\demo-kucuk.db --open
```

## 2 Yeni bilgisayara ilk kurulum

### Gerekli dosyalar ve araçlar

Proje klasörünü eksiksiz taşıyın. En az `panogoz`, `frontend`, `requirements.txt`, `docs` ve başlatma betikleri bulunmalıdır. Testler için `tests`, veri analizi için `analysis` ve açılmış yarışma veri klasörü, C firmware denemesi için `firmware` gerekir.

Python 3.11 64 bit, mevcut uygulama kontrolünün yapıldığı sürüm ailesidir. Başlatıcı 3.11 veya üstünü kabul eder; farklı Python sürümlerinde sabitlenmiş paketlerin uyumluluğunu ayrıca kontrol edin. İlk paket kurulumu internet ister. Hazır paketlerle yerel demo internet gerektirmez.

Web arayüzü düz HTML, CSS ve JavaScript dosyalarından oluşur. Bu yol için Node.js, npm kurulumu veya ayrı bir frontend sunucusu gerekmez. SQLite Python içindedir. Docker, PostgreSQL ve MQTT brokerı varsayılan yerel yolun ön koşulu değildir.

### Python seçimi ve sanal ortam

Proje dizininde sürümü kontrol edin:

```powershell
python --version
python -c "import sys; print(sys.executable)"
```

`python` bulunmuyorsa ve Windows Python başlatıcısı kuruluysa `py -3.11 --version` deneyin. Python kurulu değilse Python resmi dağıtımından 3.11 64 bit kurulumu tamamlayıp yeni PowerShell açın.

Yeni bir kurulumda projeye ait sanal ortam oluşturun:

```powershell
Set-Location 'C:\Users\darkb\Desktop\grid-up-v2'
python -m venv .venv
$pgPython = '.\.venv\Scripts\python.exe'
& $pgPython -m pip install -r requirements.txt
& $pgPython -m pip install pytest==8.4.0
& $pgPython -m pip check
```

Klasör başka yerdeyse ilk satırı değiştirin. `pytest` mevcut `requirements.txt` içinde bulunmadığı için testleri çalıştırmak üzere ayrı kurulur. Sanal ortamı etkinleştirmek zorunlu değildir; bu kılavuzdaki `& $pgPython` çağrıları doğrudan doğru Python dosyasını kullanır. Her yeni terminalde `$pgPython` değişkenini yeniden tanımlayın.

Çalışan mevcut ortamınız varsa boş bir `.venv` oluşturmak gerekli değildir. Sistem Python kullanacaksanız aşağıdaki bölümlerde `$pgPython = 'python'` seçebilirsiniz. Sanal ortam yaklaşımı ve etkinleştirmeden kullanım için resmi kaynak: [Python venv belgesi](https://docs.python.org/3.11/library/venv.html).

### Kurulumun doğrulanması

```powershell
$env:PYTHONIOENCODING = 'utf-8'
& $pgPython -c "import fastapi, uvicorn, numpy, scipy, pandas, sklearn"
& $pgPython -c "import pymodbus, paho.mqtt, openpyxl, websockets; print('Paketler hazir')"
& $pgPython -m panogoz.run_local --help
```

Hata oluşursa ilk eksik paket veya sürüm çakışmasını çözün. Paketleri uygulamayı çalıştıran aynı Python ile kurun. `baslat.ps1` paket indirmez; eksik bağımlılıkları bildirir ve bazı durumlarda boş sanal ortam oluşturur.

## 3 Çalıştırma seçenekleri

### Günlük kullanım ve tam demo

Sanal ortam kurduysanız Terminal 1 içinde:

```powershell
$pgPython = '.\.venv\Scripts\python.exe'
$env:PYTHONIOENCODING = 'utf-8'
$env:PANOGOZ_BUS = 'inproc'
$pgArgs = @(
  '-m', 'panogoz.run_local',
  '--panels', '112', '--backfill-days', '75',
  '--port', '8080', '--scada-port', '5020',
  '--scada-host', '127.0.0.1',
  '--db', '.\panogoz.db', '--open'
)
& $pgPython @pgArgs
```

`--backfill-days`, başlangıçta simülasyondan tarihsel veri üretir. Bu, gerçek sahadan alınmış geçmiş değildir. Tarihsel örnekleme pano gruplarına göre dağıtılır; tüm panoların aynı uzunlukta geçmişi bulunması beklenmez. Yeniden açılışta da önyükleme ve simülasyon hazırlığı yürütülür.

### PowerShell başlatıcısı

Hazır Python ortamı için kısa yol:

```powershell
.\baslat.ps1
.\baslat.ps1 -Panels 24 -BackfillDays 75 -NoBrowser
```

Bu iki satır alternatif komutlardır; aynı anda çalıştırmayın. Başlatıcının varsayılan HTTP portu 8080, Modbus portu 5020, geçmişi 75 gündür. `-NoBrowser`, yalnız otomatik tarayıcı açılmasını kapatır.

Başlatıcı Modbus için `0.0.0.0` kullanır; bu, bütün ağ arayüzlerinde dinlemek anlamına gelir. Yalnız yerel erişim istiyorsanız yukarıdaki doğrudan Python komutundaki `--scada-host 127.0.0.1` seçeneğini kullanın. Başlatıcıda `-ScadaHost` parametresi yoktur.

### Port çakışınca ikinci profil

```powershell
& $pgPython -m panogoz.run_local --port 8099 --scada-port 5021 --db .\demo-8099.db
```

Arayüz bu durumda `http://127.0.0.1:8099/` adresindedir. İki örneği aynı anda çalıştıracaksanız hem iki portu hem veritabanını ayırın. Port değiştirmek tek başına veritabanını ayırmaz.

### Parametre başvuru tablosu

| Python seçeneği | PowerShell betiği | İşlev ve varsayılan |
| --- | --- | --- |
| `--panels 112` | `-Panels 112` | Filo büyüklüğü hedefi; demo panoları korunur |
| `--backfill-days 75` | `-BackfillDays 75` | Tarihsel simülasyon süresi |
| `--port 8080` | `-Port 8080` | Web ve API portu |
| `--scada-port 5020` | `-ScadaPort 5020` | Modbus TCP portu |
| `--db yol` | `-Db yol` | SQLite dosyası |
| `--seed 42` | `-Seed 42` | Simülasyon tohumu |
| `--no-backfill` | `-NoBackfill` | Geçmiş üretimini atlar |
| `--reset` | `-Reset` | Seçilen veritabanını silerek başlar |
| `--open` | Varsayılan açık | Tarayıcıyı otomatik açar |
| Seçeneği vermeyin | `-NoBrowser` | Otomatik tarayıcı açmaz |
| `--host 127.0.0.1` | Karşılığı yok | HTTP dinleme adresi |
| `--scada-host 0.0.0.0` | Karşılığı yok | Modbus dinleme adresi |
| `--speed 1` | Karşılığı yok | Simülasyon saati çarpanı |
| `--log-level info` | Karşılığı yok | Web sunucusu günlük seviyesi |

`--no-backfill` yalnız hızlı bağlantı kontrolünde uygundur; değişim noktası ve günler boyunca teyit isteyen alarm yolları geçmiş olmadan aynı sonucu vermez. `--speed` simülasyon saatini hızlandırır; bütün bildirim ve gerçek zaman davranışlarının aynı oranda hızlandığını varsaymayın.

## 4 Web arayüzünü kullanma

Arayüzü API ile aynı adresten açın. `frontend/index.html` dosyasına çift tıklayarak `file://` üzerinden açmayın; ekranların ihtiyaç duyduğu API ve WebSocket bu şekilde sağlanmaz.

### Filo ve pano seçimi

Filo ekranı panoların sağlık, seviye ve bağlantı durumlarını topluca gösterir. Üstteki pano seçicisinden `SOKE-14` seçin. Sol menüde Pano ekranına geçerek dijital ikizi ve ölçülen bağlantıları inceleyin. Referans bağlantı `C07-L2-PABUC` olarak adlandırılır.

Ekrandaki değerler canlı simülasyonla değişir. Önceki bir ekran görüntüsündeki sıcaklığın veya alarm seviyesinin her açılışta birebir görünmesi beklenmez. Filo seviyesinin, tek bağlantı seviyesinden düşük olması iki bağımsız ölçüm ailesiyle teyit koşulundan kaynaklanabilir; olayın kanıtını ve bastırma gerekçesini birlikte okuyun.

### Ekranların amacı

| Ekran | Ne incelenir |
| --- | --- |
| Filo | Panoların toplu durumu ve önceliklendirme |
| Pano | Dijital ikiz, bağlantılar, ölçümler ve cihaz durumu |
| Kanıt | Seçilen bağlantının theta geçmişi, eğim ve değişim göstergeleri |
| PRPD | Simüle RF örüntüsü ve sınıflandırma bilgisi |
| Alarmlar | Aktif olaylar, bastırılan kayıtlar ve bildirim simülasyonu |
| SCADA | Pano register bloğu ve kodlanmış değerler |
| Demo | Seçili panoya senaryo ekleme ve demoyu sıfırlama |

Doğrudan açılabilecek örnekler:

```text
http://127.0.0.1:8080/#/filo
http://127.0.0.1:8080/#/pano/SOKE-14
http://127.0.0.1:8080/#/kanit/SOKE-14/C07-L2-PABUC
http://127.0.0.1:8080/#/prpd/SOKE-14
http://127.0.0.1:8080/#/alarm/bastirilan
http://127.0.0.1:8080/#/scada/SOKE-14
```

### Canlı bağlantıyı anlama

Üst bağlantı göstergesi WebSocket veya 3 saniyelik yoklama durumunu gösterir. WebSocket kurulamazsa arayüz API yoklamasına geçebilir; bu durumda ekranın çalışması mümkündür. Simülatör yaklaşık 2 saniyede, dedektör 5 saniyede bir ilerler; WebSocket yayın periyodu 2 saniyedir. Her sayının her saniye değişmesi beklenmez.

## 5 Demo senaryoları ve alarm onayı

### Hazır tarihsel gösterim

İlk gösterimde 75 günlük geçmişli profili kullanın. Filo ekranından `SOKE-14` panosuna, ardından `C07-L2-PABUC` kanıt ekranına geçin. Gevşek bağlantı senaryosu başlangıçta hazırlanır. Daha sonra Alarmlar ekranındaki Aktif ve Bastırılan sekmelerini karşılaştırın. Kayıt bulunmayan bir listeyi tek başına arıza olarak yorumlamayın.

### Ekrandan senaryo ekleme

Önce hedef panoyu seçin. Sol menüde Demo düğmesine basın ve ilgili senaryoda Enjekte et seçeneğini kullanın. Her tıklama yeni bir arıza örneği ekleyebilir; aynı deneyi tekrarlamadan önce temiz bir demo durumuna dönün.

Ekrandaki düğme senaryonun varsayılan parametrelerini kullanır. Örneğin `ark_olayi` varsayılanında olay başlangıçtan 3600 saniye sonraya ayarlıdır. Bu düğmeye basınca hemen ark olayı görmek beklenmez. Isıl senaryoların fiziksel ısınması ve tarihsel alarm teyidi de zaman alır.

### Hemen gözlenebilen ark denemesi

Bu örnek yerel simülatörde çalışır. Gerçek cihaza komut veya gerçek SMS göndermez. Varsayılan filo içindeki `SOKE-14` üzerinde kısa bir gözlem yapmak için Terminal 2 içinde:

```powershell
$pgBase = 'http://127.0.0.1:8080'
$body = @{
  panel_key = 'SOKE-14'
  at_s = 0
  detector = 'X2:3'
  relay = 'K5'
} | ConvertTo-Json
$request = @{
  Uri = "$pgBase/api/scenario/ark_olayi"
  Method = 'Post'
  ContentType = 'application/json'
  Body = $body
}
Invoke-RestMethod @request
```

Birkaç veri ve dedektör çevrimi sonra Pano, Alarmlar ve Bildirimler ekranlarını kontrol edin. Beklenen işaretler aktif ark açması, `arc_integrity` olayı ve ACİL seviyesidir. Fiziksel ark koruması bu uygulamanın görevi değildir; burada koruma rölesinin olay çıktısı simüle edilir.

```powershell
Invoke-RestMethod "$pgBase/api/panel/SOKE-14" | Select-Object severity, arc, alarms
Invoke-RestMethod "$pgBase/api/notifications?limit=10"
```

### Alarmı onaylama

Aktif olayda Onayla düğmesini açın. Onaylayan alanı, mevcut sunucu uygulamasında nöbet listesindeki telefon numarası olarak doğrulanır; yalnız bir kişi adı yazmak yeterli değildir. Varsayılan demo listesindeki birincil örnek numara `+905321112233` değeridir. Bu, gerçek gönderim hedefi olarak kullanılacak bir talimat değildir.

Jeton, Bildirimler sekmesindeki ilgili olayın simüle mesaj gövdesinde bulunan dört haneli koddur. Doğru olayın kodunu kullanın. Hatalı kod veya nöbet listesinde olmayan numara reddedilir. Bildirim yoksa olayın henüz yönlendirilmemiş olabileceğini kontrol edin; her olay SMS üretmek zorunda değildir. Kritik ve Acil bildirimler panoya en yakın nöbetçi ekibe gider: hedef sütununda ekibin adı ve numarası, ardından aynı ekibe giden `KONUM · <pano> · ~N km · maps.google.com/?q=…` mesajı görünür. Söke panoları için örnek numara yine `+905321112233` değeridir.

Onay, olayın alındığını belirtir ve tekrar bildirimlerini durdurur. Arızayı fiziksel olarak gidermez ve olayı zorunlu olarak kapanmış hâle getirmez; kapanma kuralları ayrıdır.

## 6 Durdurma yedekleme ve sıfırlama

### Normal durdurma

Terminal 1 içinde Ctrl+C kullanın. Kapanış tamamlanana kadar bekleyin. Tarayıcı sekmesini kapatmak Python sunucusunu kapatmaz. Yeniden başlatmak için aynı komutu kullanabilirsiniz; mevcut SQLite kayıtları aynı dosyada kalır ve açılış hazırlığı yeniden çalışır.

### Veritabanı yedeği

Uygulamayı durdurduktan sonra, kullandığınız gerçek veritabanı yolunu seçerek yedek alın. Aşağıdaki örnek yalnız `panogoz.db` içindir:

```powershell
$backupDir = Join-Path (Get-Location) 'yedekler'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Copy-Item -LiteralPath '.\panogoz.db' -Destination "$backupDir\panogoz-$stamp.db"
```

Çalışan SQLite veritabanını yalnız `.db` dosyasını kopyalayarak yedeklemeyin; henüz ana dosyaya alınmamış WAL verisi olabilir. Normal kapanış sonrası `-wal` veya `-shm` yan dosyaları hâlâ varsa tek dosya yedeği yerine SQLite yedekleme API’sini kullanın. Projeyi başka bilgisayara taşımak ile veri yedeğini taşımak ayrı işlemlerdir.

### Temiz demo açma

Mevcut kayıtları korumak istiyorsanız en kolay yol daha önce kullanılmamış farklı bir dosya seçmektir:

```powershell
& $pgPython -m panogoz.run_local --db .\demo-yeni-oturum.db --open
```

Seçilen veritabanını gerçekten silerek yeniden üretmek için uygulama kapalıyken:

```powershell
& $pgPython -m panogoz.run_local --db .\demo-kucuk.db --reset --panels 8 --backfill-days 20
```

**Bu komuttaki `--reset`, belirtilen dosyanın mevcut verisini siler.** Dosya adını kontrol edin. Web arayüzündeki Demoyu sıfırla düğmesi de mevcut demo kayıtlarını temizleyip başlangıç durumunu yeniden kurar; yalnız ekran filtrelerini sıfırlamaz.

`/api/demo/clear-faults` yalnız simülatördeki arızaları kaldırır. Geçmiş ölçümleri, açık olayları ve alarmın kapanma koşullarını otomatik olarak temizlediği varsayılmamalıdır.

## 7 API ve SCADA kontrolü

### Kullanılan adresler

| Adres veya port | Amaç |
| --- | --- |
| `http://127.0.0.1:8080/` | Web arayüzü |
| `/api/health` | Uygulama ve alt bileşen durumu |
| `/api/fleet` | Filo verisi |
| `/api/panel/SOKE-14` | Tek panonun canlı verisi |
| `/docs` | Etkileşimli API başvuru ekranı |
| `/api/scenarios` | Senaryolar ve varsayılan parametreleri |
| `/api/notifications` | Simüle bildirimler |
| `/api/audit/verify` | Denetim zinciri bütünlüğü |
| `/api/icd` ve `/api/icd.csv` | Modbus arayüz belgesi ve nokta listesi |
| `/api/analysis/supplied-data` | Sağlanan yarışma verisinin analizi |
| `ws://127.0.0.1:8080/ws` | WebSocket veri akışı |
| TCP `5020` | Modbus SCADA sunucusu |

Tablodaki `/` ile başlayan yolları web sunucusunun adresine ekleyin. Modbus portu bir web sayfası değildir; tarayıcıda `http://127.0.0.1:5020` açılmaz.

### Bileşen durumunu kontrol etme

```powershell
$health = Invoke-RestMethod "$pgBase/api/health"
$health.stats | Select-Object sim_ticks, detect_passes, buffered, dropped
$health.stats.scada | Select-Object listening, request_count, rejected_writes
$health.stats.detector
$health.degraded
Invoke-RestMethod "$pgBase/api/audit/verify"
```

Bir süre sonra sorguyu yeniden çalıştırdığınızda `sim_ticks` ve `detect_passes` ilerlemelidir. `scada.listening` true olmalı; `degraded` listesi sorun bildiriyorsa arayüz açılsa bile ilgili bileşen tamamlanmış sayılmaz. `backlog` anlık kuyruk miktarıdır; bir ölçümde sıfırdan büyük olması tek başına hata kanıtı değildir. Sürekli büyüyen kuyruk ve artan `dropped` araştırılmalıdır.

### Python ile Modbus okuma

Terminal 2 içinde proje dizininde ve doğru Python ile çalıştırın:

```powershell
@'
from pymodbus.client import ModbusTcpClient
c = ModbusTcpClient('127.0.0.1', port=5020)
try:
    assert c.connect(), 'Modbus baglantisi kurulamadi'
    r = c.read_holding_registers(1624, count=48, device_id=1)
    assert not r.isError(), str(r)
    print('Okunan register sayisi:', len(r.registers))
    print(r.registers)
finally:
    c.close()
'@ | & $pgPython -
```

Beklenen 48 kelimelik yanıttır. `SOKE-14` için başlangıç PDU adresi `1000 + 48 × (14 − 1) = 1624` olur. Ölçek ve alan anlamları için `/api/icd` kullanılır. Harita salt okunurdur; FC05, FC06, FC15 ve FC16 yazma istekleri reddedilir.

`modpoll` ayrıca kuruluysa aynı okuma:

```powershell
modpoll -m tcp -a 1 -0 -r 1624 -c 48 -p 5020 127.0.0.1
```

## 8 Testler analiz ve firmware

### Python kontrolleri

Testleri uygulamadan ayrı terminalde çalıştırın. Tam takım simülasyon geçmişi ürettiğinden birkaç dakika sürebilir. İlk çıktı gecikebilir; bazı kabul kontrolleri test dosyaları yüklenirken çalışır.

```powershell
$env:PYTHONIOENCODING = 'utf-8'
& $pgPython -m pytest -q
& $pgPython -m tests.test_integration
& $pgPython -m tests.test_rules
```

Üç komutu ayrı ayrı değerlendirin. Mevcut kodda `test_rules.py` içindeki bazı kontroller pytest’e başarısızlık iletmiyor; bağımsız modülün sonuç satırı ve çıkış kodu da kontrol edilmelidir. `test_integration.py` ayrı kabul raporu verir. Yalnız `pytest` sonucunu bütün davranışların doğrulandığı şeklinde yorumlamayın.

Ek bileşen kontrolleri:

```powershell
& $pgPython -m tests.test_scada
& $pgPython -m tests.test_modbus
& $pgPython -m tests.test_detector
& $pgPython -m tests.test_prpd
& $pgPython -m tests.test_sim_acceptance
```

Bir komuttan hemen sonra `$LASTEXITCODE` değerini okuyabilirsiniz; sıfır dışı değer başarısızlıktır. Bu testler simülasyon ve yerel protokoller içindir; saha başarımını ölçmez.

### Sağlanan veri analizi

```powershell
& $pgPython -m analysis.supplied_data
```

Bu komut daha uzun bir analiz ve raporlama akışı yürütür. `analysis/README.md` açıklamalarını okuyun. Açılmış yarışma veri klasöründeki çalışma kitabını koruyun; ZIP dosyasının tek başına durması yeterli değildir. Uygulama içinden temel sonuçlar `/api/analysis/supplied-data` üzerinden okunabilir. Veri kümesinde eksik sıcaklık ve arıza etiketleri bulunduğundan bu analiz dedektörün saha doğruluğunu kanıtlamaz.

### Firmware host denemesi

C firmware denemesi, web uygulamasının açılması için gerekli değildir. Aynı C çekirdeğinin bilgisayar üzerinde çalışan ayrı simülasyonudur; web sunucusuna canlı donanım olarak otomatik bağlanmaz. MinGW GCC ve `mingw32-make` kuruluysa:

```powershell
Push-Location .\firmware\node
mingw32-make host
.\panogoz_node.exe --selftest
.\panogoz_node.exe --scenario energy
Pop-Location
```

Öz testte `ozet: 0 hata` beklenir. Enerji senaryosundaki pil ömrü hesaplanmış tasarım modelidir. ARM hedef derlemesi için gerekli `port/stm32wle5` donanım portu bu depoda yoktur; yalnız araç zinciri kurmak kart üzerinde çalıştırmaya yetmez. Ayrıntı: `firmware/README.md` ve `firmware/node/Makefile`.

## 9 Sık karşılaşılan sorunlar

### Python veya panogoz bulunamıyor

`python --version` çalışmıyorsa Python kurulumu veya PATH seçimini kontrol edin. `No module named panogoz` durumunda projenin kök klasöründe olduğunuzu `Get-Location` ile doğrulayın. `panogoz` klasörünün içine girip komutu oradan çalıştırmayın.

### Paket kuruldu ama uygulama bulamıyor

Kurulum ve çalıştırma farklı Python dosyalarına gitmiş olabilir. Aşağıdaki iki komut aynı `$pgPython` ile çalışmalıdır:

```powershell
& $pgPython -c "import sys; print(sys.executable)"
& $pgPython -m pip show fastapi pymodbus
```

Eksik `.venv` varken `baslat.ps1` sistem Python’una geçtiğini yazsa bile seçili yorumlayıcı sanal ortamda kalabilir. Bu durumda paketleri o ortama tamamlayın veya çalıştığını bildiğiniz Python dosyasını doğrudan kullanın.

### PowerShell betiği çalıştırılamıyor

Betik çalıştırma ilkesi `.\baslat.ps1` çağrısını engelliyorsa, bu kılavuzdaki doğrudan `python -m panogoz.run_local` yolunu kullanın. Sanal ortamı `Activate.ps1` ile etkinleştirmek yerine `.venv\Scripts\python.exe` dosyasını doğrudan çağırabilirsiniz.

### Port kullanımda veya arayüz açılmıyor

```powershell
Get-NetTCPConnection -LocalPort 8080,5020 -State Listen -ErrorAction SilentlyContinue
```

Başka bir süreç dinliyorsa kendi önceki uygulama terminalinizi kontrol edin veya 8099 ve 5021 gibi boş portlarla ayrı veritabanı seçin. Web adresindeki portu da değiştirin. `HAZIR` satırından sonra HTTP portu bağlanırken hata oluşabilir; terminalin son satırlarını ve `/api/health` yanıtını birlikte inceleyin.

Arayüzde bağlantı yoksa önce `/api/health` deneyin. API çalışıyor ama ekran eski görünüyorsa tarayıcıyı Ctrl+F5 ile yenileyin. Önceki incelemede HTML ve JavaScript sunumu doğrulandı; görsel tarayıcı testi yapılamadı.

### Veritabanı kilitli veya adresi desteklenmiyor

`database is locked` görülürse aynı dosyayla birden fazla uygulama açılıp açılmadığını kontrol edin. Ayrı denemelerde ayrı `--db` dosyaları kullanın. Çalışan veritabanını ve WAL yan dosyalarını elle silmeyin.

`postgresql://...` biçiminde adres reddedilir; mevcut sürücünün desteklediği yol SQLite dosyasıdır. Ortam değişkeninden gelen eski ayarı aşmak için `--db .\panogoz.db` verin. Dosya adının üst klasörü mevcut olmalıdır.

### Senaryo eklendi ama alarm hemen çıkmadı

Senaryonun `default_kw` alanını `/api/scenarios` üzerinden okuyun. Zaman gecikmesi, ısıl atalet, günlük teyit, bastırma veya bağımsız ikinci ölçüm koşulu devrede olabilir. Ekrandan eklenen ark olayının varsayılan gecikmesi bir saattir; hemen denemek için Bölüm 5 içindeki `at_s = 0` örneğini kullanın.

### Alarm onayı reddediliyor

Onaylayan alanına mevcut nöbet listesindeki numarayı, Jeton alanına aynı olayın dört haneli kodunu girin. Başka olayın kodu, kişi adı veya boş kod kabul edilmez. Bildirim simülasyonunda gerçek telefonunuza SMS gelmesini beklemeyin.

### Türkçe karakterler veya terminal çıktısı bozuk

```powershell
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

Yeni terminalde değişkenleri yeniden ayarlayın. Kaynak dosyalarını okurken PowerShell için `Get-Content -Encoding UTF8` kullanın.

## 10 Çevrimdışı kurulum ve diğer çalışma yolları

### İnternetsiz demo bilgisayarı

Paketler zaten kuruluysa yerel demo çevrimdışı çalışabilir. İlk kurulum için aynı işletim sistemi, mimari ve Python sürümündeki internetli bilgisayarda paketleri önceden indirin:

```powershell
& $pgPython -m pip download -r requirements.txt pytest==8.4.0 -d .\wheelhouse
```

Proje, `wheelhouse` klasörü ve uygun Python kurulum dosyasını hedef bilgisayara taşıyın. Hedefte Python ve sanal ortamı kurduktan sonra:

```powershell
$pgPython = '.\.venv\Scripts\python.exe'
$offlineArgs = @(
  '-m', 'pip', 'install', '--no-index', '--find-links', '.\wheelhouse',
  '-r', 'requirements.txt', 'pytest==8.4.0'
)
& $pgPython @offlineArgs
& $pgPython -m pip check
```

Kaynak paket yerine uygun hazır wheel bulunduğunu ve bütün bağımlılıkların indirildiğini hedef makinede prova ederek doğrulayın. `.venv` klasörünü başka bilgisayara kopyalamak yerine hedefte yeniden oluşturun. İndirme ve yerel klasörden kurulum seçenekleri: [pip download belgesi](https://pip.pypa.io/en/stable/cli/pip_download/).

### Linux veya macOS

Bu yol kod yapısından türetilmiştir; bu incelemede Windows dışında çalıştırılmadı. Proje kökünde Bash ile:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt pytest==8.4.0
export PYTHONIOENCODING=utf-8
export PANOGOZ_BUS=inproc
.venv/bin/python -m panogoz.run_local --scada-host 127.0.0.1 --db ./panogoz.db
```

Hazır ortam için `bash ./baslat.sh --help` ile betik seçeneklerine bakabilirsiniz. Windows PowerShell parametrelerini Bash betiğine aynı yazımla aktarmayın.

### MQTT ve Docker durumu

Yerel çalışmada `PANOGOZ_BUS=inproc` yeterlidir. Ayrı bir MQTT brokerıyla deney yapmak isterseniz brokerı ayrıca kurup başlatmanız gerekir. Aynı makinede 1883 portunda hazır bir broker varsa:

```powershell
$env:PANOGOZ_BUS = 'mqtt://127.0.0.1:1883'
& $pgPython -m panogoz.run_local --db .\demo-mqtt.db --scada-host 127.0.0.1
```

Bu ayar taşıma katmanını değiştirir; sensör verisi yine simülatörden gelir. Gerçek Mosquitto ile bağlantı, yeniden bağlanma ve yeniden başlatma kabulü bu çalışmada doğrulanmadı. Eski oturum mesajlarının güncel ölçümü ezmesiyle ilgili açık hata da vardır. Normal demoya dönmeden önce uygulamayı durdurup `$env:PANOGOZ_BUS = 'inproc'` ayarlayın.

`docker-compose.yml` mevcut hâliyle tamamlanmış alternatif dağıtım değildir. TimescaleDB servisi tanımlı olsa da uygulamanın PostgreSQL sürücüsü yoktur. Bu yüzden tüm sistemi çalıştırma talimatı olarak `docker compose up` kullanmayın. `Dockerfile` ve Compose dosyaları, mevcut eksikleriyle birlikte ayrı bir geliştirme konusu olarak değerlendirilmelidir.

## 11 Doğrulanan durum ve açık konular

12 Eylül 2026 tarihindeki incelemede Windows Python 3.11.2 üzerinde aşağıdaki sonuçlar alındı. Bunlar o kod sürümü ve o test koşumunun sonuçlarıdır; daha sonraki değişikliklerde kontrolleri yeniden çalıştırın.

| Kontrol | Sonuç |
| --- | --- |
| `python -m pytest -q` | 138 geçti, yaklaşık 4 dakika 26 saniye |
| `python -m tests.test_integration` | 17 geçti, 0 kaldı, 0 atlandı |
| `python -m tests.test_rules` | 40 kontrolün tamamı geçti |
| C host derlemesi ve öz testi | Proje derleme ayarlarıyla 0 hata |
| Web ve API adresleri | Kontrol edilen 20 adreste HTTP 200 |
| WebSocket | Filo ve pano mesajları alındı |
| Küçük canlı demo | 8 pano isteği, 20 gün geçmiş; gerçekte 10 pano oluştu |
| Görsel arayüz kontrolü | Tarayıcı bağlantısı bulunmadığından yapılmadı |

**Açık hata 1:** Yeniden başlatma öncesinden kalan bir mesaj yeni oturum kabul edilerek ölçümü geriye çevirebiliyor. İncelemede 250 A değeri eski mesajla 100 A oldu. Kaynak: `panogoz/contracts/envelope.py`, `SeqTracker.check`.

**Açık hata 2:** Donan ve kayan sensör senaryolarında beklenen cihaz arızası işaretleri üretilmiyor. `device_residual` geçmişi çalışma akışında doldurulmuyor. İncelemede her iki pano yalnız `DATA_VALID` bildirdi. Kaynak: `panogoz/api/runtime.py` ve `panogoz/rules/suppression.py`.

**Açık hata 3:** Bazı kural kontrolleri başarısızlığı yalnız iç listeye kaydediyor; pytest başarılı çıkabiliyor. Bu nedenle Bölüm 8 içindeki bağımsız kabul ve kural komutları önemlidir. Kaynak: `tests/test_rules.py` ve `tests/test_integration.py`.

Senaryo sözleşmesinde başka bayrak uyuşmazlıkları da vardır. Örneğin sessiz düğümde `STALE` yerine `DEVICE_FAULT`, enerjisiz pano senaryosunda `DE_ENERGISED` yerine `ANALYSER_COMMS_LOST` görülebilir. Analizörün susması tek başına enerjisizliğin kanıtı sayılmamalıdır.

Bu kılavuzun hazırlanması uygulama kodundaki hataları düzeltmez. Gerçek sensör kartı, ARM hedef portu, saha ölçümü, gerçek SMS veya sesli arama servisi, TimescaleDB, IEC 104 ve OPC UA sunucuları tamamlanmış yerel demo bileşenleri değildir.

## 12 Kaynak dosyalar ve gösterim öncesi son kontrol

Başlatma ve seçenekler için `baslat.ps1`, `baslat.sh`, `panogoz/run_local.py`; zamanlama ve simülasyon için `panogoz/api/runtime.py`; uçlar için `panogoz/api/app.py`; senaryolar için `panogoz/sim/faults.py`; ekranlar için `frontend/js` kaynak alınmıştır. Ayrıntılı proje anlatımı `README.md`, gösterim akışı `docs/08-DEMO-SENARYOSU.md`, protokol haritası `docs/PANOGOZ-ICD-v2.0.md` içindedir.

Gösterime başlamadan önce:

1. Doğru proje klasörü, Python ve veritabanı seçildiğini kontrol edin.
2. Tam tarihsel gösterim için 75 günlük profili açın ve önyüklemeyi bekleyin.
3. `/api/health` içinde `ok`, `sim_running`, `degraded` ve SCADA durumunu okuyun.
4. `SOKE-14` pano ve kanıt ekranlarına geçin; geçmişin geldiğini kontrol edin.
5. Aktif, Bastırılan ve Bildirimler sekmelerinin farkını gösterime hazırlayın.
6. Anlık ark deneyi için `at_s = 0` örneğini kullanın; varsayılan düğme gecikmesini unutmayın.
7. Sıfırlamanın kayıtları sildiğini, bildirimlerin ve sensörlerin simüle olduğunu açıklayın.
8. Gösterim sonunda Terminal 1 içinde Ctrl+C ile uygulamayı kapatın.
