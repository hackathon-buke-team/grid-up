# PANO GÖZ uygulaması (on-prem). Yalnız çalışma zamanı bağımlılıkları; test araçları (pytest, amqtt,
# c104, playwright, opencv) imaja GİRMEZ. Sertleştirme notları: docs/13-DAGITIM-SERTLESTIRME.md
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements-runtime.txt .
RUN pip install -r requirements-runtime.txt

COPY panogoz ./panogoz
COPY frontend ./frontend
COPY tools ./tools
COPY ["Hackathon Verileri", "./Hackathon Verileri"]

# root olmayan, ev dizini ve kabuğu olmayan hizmet kullanıcısı
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin panogoz \
    && chown -R 10001:10001 /app
USER 10001:10001

# HTTP (proxy arkasında), Modbus TCP, IEC 60870-5-104
EXPOSE 8080 5020 2404

HEALTHCHECK --interval=15s --timeout=4s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/readyz', timeout=3).status == 200 else 1)"

# Üretimde demo kontrol uçları kapalı. NOT: bugünkü çalıştırıcı SİMÜLE filoyu sunar; MQTT'den canlı
# besleme henüz boru hattına bağlı değil (docs/01-MIMARI.md §6, docs/13 §5).
CMD ["python", "-m", "panogoz.run_local", "--port", "8080", "--modbus-port", "5020", "--iec104-port", "2404", "--no-demo-controls", "--panels", "2"]
