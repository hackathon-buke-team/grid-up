# PANO GÖZ - production image.
#
# READ THIS FIRST: the demo path is NOT this file.  On the demo machine Docker
# is not running and there is no network, so the hackathon demo runs with
#
#     python -m panogoz.run_local           (or ./baslat.sh / .\baslat.ps1)
#
# which needs SQLite, the in-process bus and nothing else.  This Dockerfile and
# the compose file next to it describe the topology a DSO would actually deploy:
# mosquitto for the panel gateways, TimescaleDB for the time series, and this
# image for the detector, the rules engine, the REST API and the SCADA slave.
# Both paths run the same code; only PANOGOZ_BUS and PANOGOZ_DB change.

FROM python:3.11-slim-bookworm AS base

# tini so SIGTERM reaches uvicorn and the runtime threads shut down cleanly
# instead of the container being killed 10 s later. curl is for HEALTHCHECK.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tini curl \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first so a source change does not re-resolve the wheel set.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY panogoz/ ./panogoz/
COPY frontend/ ./frontend/
COPY docs/ ./docs/
COPY tests/ ./tests/

# Never run the API as root: this process is inside the OT zone and a container
# escape from a web handler must not land on a root shell.
RUN useradd --system --create-home --uid 10001 panogoz \
 && mkdir -p /data && chown -R panogoz:panogoz /data /app
USER panogoz

ENV PANOGOZ_DB=/data/panogoz.db \
    PANOGOZ_BUS=inproc \
    PANOGOZ_PANELS=112 \
    PANOGOZ_PORT=8080 \
    PANOGOZ_SCADA_PORT=5020 \
    PANOGOZ_BACKFILL_DAYS=75

EXPOSE 8080 5020
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8080/api/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-c", "python -m panogoz.run_local \
  --host 0.0.0.0 \
  --port ${PANOGOZ_PORT} \
  --scada-port ${PANOGOZ_SCADA_PORT} \
  --panels ${PANOGOZ_PANELS} \
  --backfill-days ${PANOGOZ_BACKFILL_DAYS} \
  --db ${PANOGOZ_DB}"]
