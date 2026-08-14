#!/usr/bin/env bash
# 锁定本机 Python 3.13.3 启动 deepthinkSingle
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

# 优先用脚本中固定的 3.13；找不到则回退到 PATH 中名为 python3.13 的执行文件
PY="${PY313:-$ROOT/.venv/bin/python}"
if [ ! -x "$PY" ]; then
  if command -v "C:/Users/ht182/AppData/Local/Programs/Python/Python313/python" >/dev/null 2>&1; then
    PY="C:/Users/ht182/AppData/Local/Programs/Python/Python313/python"
  elif command -v python3.13 >/dev/null 2>&1; then
    PY="python3.13"
  else
    echo "[ERROR] 未找到 Python 3.13，请安装或设置 PY313 环境变量" >&2
    exit 1
  fi
fi

if ! "$PY" -c "import flask, requests" 2>/dev/null; then
  echo "[WARN] 缺少依赖 flask/requests，正在安装..."
  "$PY" -m pip install -r "$ROOT/requirements.txt"
fi

cd "$ROOT"
URL="http://127.0.0.1:5000"
echo "[INFO] Using $PY"
echo "[INFO] Serving at $URL  (Ctrl+C to quit)"

# Auto-open the browser after a short wait (server needs a moment to bind the port)
( sleep 2 && { xdg-open "$URL" || open "$URL" || start "$URL"; } ) >/dev/null 2>&1 &

exec "$PY" app.py
