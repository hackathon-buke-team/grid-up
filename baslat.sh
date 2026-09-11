#!/usr/bin/env bash
# PANO GOZ - tek komutla yerel demo (Linux / macOS / Git Bash)
#
#   ./baslat.sh                       varsayilan: 112 pano, 75 gun gecmis, port 8080
#   ./baslat.sh --panels 24 --port 8099
#   ./baslat.sh --reset               veritabanini silerek bastan basla
#
# Bu betik AGA CIKMAZ. Paket kurmaz, indirmez, guncellemez. Demo makinesinde
# Docker calismiyor ve internet yok; bu yol tam olarak bunun icin var.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Turkce cikti; Windows konsolu varsayilan cp1254, Linux'ta zararsiz.
export PYTHONIOENCODING=utf-8

PANELS=112
PORT=8080
SCADA_PORT=5020
SEED=42
BACKFILL_DAYS=75
DB=""
EXTRA=()
OPEN_BROWSER=1

while [ $# -gt 0 ]; do
  case "$1" in
    --panels)        PANELS="$2"; shift 2 ;;
    --port)          PORT="$2"; shift 2 ;;
    --scada-port)    SCADA_PORT="$2"; shift 2 ;;
    --seed)          SEED="$2"; shift 2 ;;
    --backfill-days) BACKFILL_DAYS="$2"; shift 2 ;;
    --db)            DB="$2"; shift 2 ;;
    --reset)         EXTRA+=("--reset"); shift ;;
    --no-backfill)   EXTRA+=("--no-backfill"); shift ;;
    --no-browser)    OPEN_BROWSER=0; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "bilinmeyen secenek: $1" >&2; exit 1 ;;
  esac
done

echo
echo "PANO GOZ - yerel demo baslatiliyor"
echo "----------------------------------"

# ---------------------------------------------------------------- python ---

pick_python() {
  for cand in "$ROOT/.venv/bin/python" "$ROOT/.venv/Scripts/python.exe" python3 python; do
    if command -v "$cand" >/dev/null 2>&1 || [ -x "$cand" ]; then
      if "$cand" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,11) else 1)' 2>/dev/null; then
        echo "$cand"; return 0
      fi
    fi
  done
  return 1
}

PY="$(pick_python || true)"
if [ -z "${PY:-}" ]; then
  echo "Python 3.11+ bulunamadi." >&2
  exit 1
fi
echo "  python       . $PY ($("$PY" -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])'))"

# ------------------------------------------------------------------ venv ---
# Var olan bir .venv, bagimliliklari tamsa tercih edilir.
#
# YOKSA: bos bir .venv olusturmak bu makinede ise YARAMAZ. Ag yok, yani icine
# paket kurulamaz; kurulamayan bir sanal ortam olusturmak, calisan sistem
# Python'unu golgeleyen kullanilamaz bir dizin birakmaktan baska bir sey
# yapmaz. Bu yuzden .venv yalnizca sistem Python'u bagimliliklari SAGLAMIYORSA
# olusturulur - o zaman zaten elle kurulum gerekir ve izole edilecek bir yer
# lazimdir.

VENV_PY=""
for cand in "$ROOT/.venv/bin/python" "$ROOT/.venv/Scripts/python.exe"; do
  if [ -x "$cand" ] && "$cand" -c 'import fastapi, uvicorn, numpy, pymodbus' 2>/dev/null; then
    VENV_PY="$cand"; break
  fi
done
if [ -n "$VENV_PY" ]; then
  PY="$VENV_PY"
  echo "  sanal ortam  . .venv (bagimliliklar hazir)"
fi

# --------------------------------------------------------- bagimliliklar ---

DEPS='import fastapi, uvicorn, numpy, scipy, pandas, sklearn, pymodbus, paho.mqtt, openpyxl'
if ! "$PY" -c "$DEPS" 2>/dev/null; then
  echo
  echo "Eksik bagimlilik var. Bu betik kurulum YAPMAZ (ag yok)." >&2
  "$PY" -c "$DEPS" || true
  if [ ! -d "$ROOT/.venv" ] && "$PY" -c 'import venv' 2>/dev/null; then
    echo "  .venv olusturuluyor (bos; paketleri siz kuracaksiniz)" >&2
    "$PY" -m venv "$ROOT/.venv" >/dev/null 2>&1 || true
  fi
  echo >&2
  echo "Elle kurmak icin:" >&2
  echo "  $ROOT/.venv/bin/python -m pip install -r requirements.txt" >&2
  echo "  (Windows: $ROOT/.venv/Scripts/python.exe -m pip install -r requirements.txt)" >&2
  exit 1
fi
echo "  bagimliliklar. tamam (fastapi, uvicorn, numpy, scipy, pandas, sklearn, pymodbus, paho-mqtt)"

# --------------------------------------------------------------- calistir ---

ARGS=(-m panogoz.run_local --panels "$PANELS" --port "$PORT"
      --scada-port "$SCADA_PORT" --seed "$SEED" --backfill-days "$BACKFILL_DAYS")
[ -n "$DB" ] && ARGS+=(--db "$DB")
[ "${#EXTRA[@]}" -gt 0 ] && ARGS+=("${EXTRA[@]}")
[ "$OPEN_BROWSER" -eq 1 ] && ARGS+=(--open)

echo "  arayuz       . http://127.0.0.1:$PORT"
echo "  scada        . Modbus TCP 0.0.0.0:$SCADA_PORT (salt okunur)"
echo

exec "$PY" "${ARGS[@]}"
