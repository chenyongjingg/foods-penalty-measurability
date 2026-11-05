#!/usr/bin/env bash
# Bootstrap the Foods pipeline environment on the pod.
# Idempotent. Installs: pip, runtime deps (CPU), optional playwright, vLLM stack.
set -euo pipefail

ROOT="${FOODS_ROOT:-/opt/foods}"
VENV="$ROOT/venv"
PIP_MIRROR="${PIP_MIRROR:-https://mirrors.aliyun.com/pypi/simple/}"
LOG="$ROOT/logs/bootstrap.log"
mkdir -p "$ROOT"/{logs,state,data,reports/daily}
exec > >(tee -a "$LOG") 2>&1

echo "=== [$(date -u +%FT%TZ)] bootstrap start ==="
python3 -V

if ! python3 -m pip --version >/dev/null 2>&1; then
  echo "--- installing pip via get-pip.py (aliyun mirror) ---"
  curl -fsSL -m 60 https://mirrors.aliyun.com/pypi/get-pip.py -o /tmp/get-pip.py
  python3 /tmp/get-pip.py -i "$PIP_MIRROR" --no-warn-script-location
fi

if [ ! -x "$VENV/bin/python" ]; then
  echo "--- creating venv ---"
  python3 -m venv "$VENV" || {
    echo "venv module missing -> virtualenv fallback"
    python3 -m pip install -q -i "$PIP_MIRROR" virtualenv
    python3 -m virtualenv -p python3 "$VENV"
  }
fi
"$VENV/bin/python" -m pip install -q --upgrade pip -i "$PIP_MIRROR"

echo "--- installing core deps ---"
"$VENV/bin/pip" install -q -i "$PIP_MIRROR" \
  requests==2.32.3 lxml==5.3.0 beautifulsoup4==4.12.3 \
  PyYAML==6.0.2 python-dateutil==2.9.0.post0 \
  pandas==2.2.3 numpy==1.26.4 scipy==1.14.1 networkx==3.4.2 \
  scikit-learn==1.5.2 lifelines==0.30.0 \
  pymupdf==1.24.14 jsonschema==4.23.0 tqdm==4.67.1 \
  filelock==3.16.1 orjson==3.10.12 tenacity==9.0.0

echo "--- installing GPU stack (torch + vllm) ---"
"$VENV/bin/pip" install -q -i "$PIP_MIRROR" torch==2.5.1 --index-url https://mirrors.aliyun.com/pypi/simple/ || \
  "$VENV/bin/pip" install -q -i "$PIP_MIRROR" torch==2.5.1
"$VENV/bin/pip" install -q -i "$PIP_MIRROR" vllm==0.6.6.post1 || {
  echo "WARN: vllm install failed; will use transformers fallback if present"
}

echo "--- optional: playwright chromium (municipal JS fallback) ---"
"$VENV/bin/pip" install -q -i "$PIP_MIRROR" playwright==1.49.1 || true
"$VENV/bin/python" -m playwright install chromium || echo "WARN: playwright browser install skipped"

echo "--- verify ---"
"$VENV/bin/python" - <<'PY'
import importlib
mods = ["requests","lxml","bs4","yaml","dateutil","pandas","numpy","scipy","networkx","sklearn","lifelines","fitz","jsonschema","filelock"]
for m in mods:
    try:
        importlib.import_module(m)
        print("OK ", m)
    except Exception as e:
        print("MISS", m, type(e).__name__, e)
try:
    import torch
    print("torch", torch.__version__, "cuda", torch.cuda.is_available())
except Exception as e:
    print("torch MISS", e)
try:
    import vllm
    print("vllm", vllm.__version__)
except Exception as e:
    print("vllm MISS", type(e).__name__)
PY
echo "=== [$(date -u +%FT%TZ)] bootstrap done ==="
