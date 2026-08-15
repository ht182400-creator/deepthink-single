# -*- coding: utf-8 -*-
"""
个股主力追踪系统 - Flask 后端
- GET /             主页
- GET /api/quote    单只个股分时+主力+报价（30s 轮询）
- GET /api/watchlist 自选列表
- POST /api/watchlist 维护自选（add/remove/set）
- GET /api/sysinfo  环境信息
数据源：services.quote_service（腾讯首选 + 东财兜底/多节点）
"""
import os
import sys
import json
import logging
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
WATCHLIST_FILE = os.path.join(DATA_DIR, "watchlist.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


# ---- 日志（带 PID，避免多实例写冲突） ----
def setup_logging():
    logfile = os.path.join(LOG_DIR, "deepthink_%s_%d.log" % (
        datetime.date.today().isoformat(), os.getpid()))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(logfile, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
    for name in ("urllib3", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)
    return logging.getLogger("deepthink")


LOG = setup_logging()

# ---- 业务模块（服务层） ----
import config  # noqa: E402
import services.quote_service as svc  # noqa: E402
import services.search_service as search_svc  # noqa: E402
import services.db as db  # noqa: E402
db.init_db()  # SQLite 建表

from flask import Flask, request, jsonify, render_template  # noqa: E402

app = Flask(__name__)


@app.after_request
def add_no_cache(response):
    """禁止缓存，保证前端每次拉到最新行情"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# =====================================================================
# 自选列表
# =====================================================================
_DEFAULT_WATCHLIST = ["sh600519", "sz000858", "sz300750", "sh601318"]


def _load_watchlist() -> list:
    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else _DEFAULT_WATCHLIST
    except Exception:
        return list(_DEFAULT_WATCHLIST)


def _save_watchlist(items: list):
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


@app.route("/")
def index():
    return render_template("index.html", watchlist=_load_watchlist())


@app.route("/api/watchlist")
def api_watchlist():
    """返回自选 + 全部预置池（datalist 用），每项 {code, name, in_watchlist}"""
    wl = list(_load_watchlist())
    wl_set = set(wl)
    pool = search_svc.all_pool_items()
    out = [{"code": c, "name": search_svc.get_code_name(c), "in_watchlist": True} for c in wl]
    for code, name in pool:
        if code in wl_set:
            continue
        out.append({"code": code, "name": name, "in_watchlist": False})
    return jsonify(out)


@app.route("/api/watchlist", methods=["POST"])
def api_watchlist_set():
    data = request.get_json(force=True) or {}
    action = data.get("action", "set")
    items = list(_load_watchlist())
    if action == "add":
        code = (data.get("code") or "").strip().lower()
        if code and code not in items:
            items.append(code)
    elif action == "remove":
        code = (data.get("code") or "").strip().lower()
        if code in items:
            items.remove(code)
    else:
        items = [c for c in (data.get("items") or []) if isinstance(c, str)]
    _save_watchlist(items)
    LOG.info("watchlist %s → %s", action, items)
    return jsonify({"ok": True, "items": items})


# =====================================================================
# 行情 API
# =====================================================================
@app.route("/api/quote")
def api_quote():
    code = request.args.get("code", "sh600519").strip().lower()
    try:
        data = svc.get_all(code)
        data["errors"] = data.get("errors", [])
        return jsonify(data)
    except Exception as e:
        LOG.error("api/quote %s 失败: %s", code, e)
        return jsonify({"code": code, "error": str(e),
                        "quote": None, "minute": [], "fund": []}), 200


@app.route("/api/search")
def api_search():
    """股票搜索（关键词：代码/名称/拼音/行业）"""
    q = request.args.get("q", "").strip()
    return jsonify(search_svc.search_stocks_with_guess(q))


@app.route("/api/kline")
def api_kline():
    """K线（通达信本地优先；分钟走 npx + 缓存）"""
    code = request.args.get("code", "sh600519").strip().lower()
    period = request.args.get("period", "day")
    try:
        limit = int(request.args.get("limit", "260"))
    except ValueError:
        limit = 260
    try:
        return jsonify(svc.get_kline(code, period, limit))
    except Exception as e:
        LOG.error("api/kline %s/%s 失败: %s", code, period, e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/many")
def api_many():
    """批量聚合并发拉取（自选批量，Sprint 3）"""
    codes = [c.strip().lower() for c in request.args.get("codes", "").split(",") if c.strip()]
    if not codes:
        return jsonify({"error": "codes 必填，逗号分隔"}), 400
    if len(codes) > config.MAX_CODES:
        return jsonify({"error": f"codes 单次上限 {config.MAX_CODES}（收到 {len(codes)}）"}), 400
    return jsonify(svc.get_many(codes))


@app.route("/api/minute")
def api_minute():
    """分时数据：date 缺省当日；YYYYMMDD（注意是 8 位无分隔符）拉历史某日分时。

    历史某日（date 有值）返回 {data, meta} 信封，meta 含来源与本地数据截止日期，
    供前端标注「本地数据滞后、该日来自腾讯/东财」。当日分时返回纯数组（兼容日内图）。
    """
    code = request.args.get("code", "").strip().lower()
    date = request.args.get("date", "").strip().replace("-", "")
    if not code:
        return jsonify({"error": "code 必填"}), 400
    try:
        if date:
            return jsonify(svc.get_minute_with_meta(code, date))
        return jsonify(svc.get_minute(code, date))
    except Exception as e:
        LOG.error("api/minute %s/%s 失败: %s", code, date, e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/announcement")
def api_announcement():
    """公告正文：?code=ANxxx（art_code）→ title/date/content/pdf_url"""
    art_code = request.args.get("code", "").strip()
    if not art_code:
        return jsonify({"error": "code 必填"}), 400
    try:
        from sources.company import get_announcement_content
        return jsonify(get_announcement_content(art_code))
    except Exception as e:
        LOG.error("api/announcement %s 失败: %s", art_code, e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/analysis", methods=["GET", "POST"])
def api_analysis():
    """复盘/分析记录（US-017）：GET 列表（?code= 过滤某标的），POST 新增笔记。"""
    if request.method == "GET":
        code = request.args.get("code", "").strip().lower() or None
        rows = db.get_analysis_log(code)
        out = []
        for r in rows:
            try:
                data = json.loads(r["data"])
            except Exception:
                data = {}
            out.append({"id": r["id"], "ts": r["ts"], "code": r["code"], "data": data})
        return jsonify(out)
    payload = request.get_json(force=True) or {}
    code = (payload.get("code") or "").strip().lower()
    note = (payload.get("note") or "").strip()
    if not code:
        return jsonify({"error": "code 必填"}), 400
    db.log_analysis(code, {"note": note,
                            "created": datetime.datetime.now().isoformat(timespec="seconds")})
    LOG.info("analysis %s 记录 %d 字", code, len(note))
    return jsonify({"ok": True})


@app.route("/api/sysinfo")
def api_sysinfo():
    import platform
    return jsonify({
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "watchlist": _load_watchlist(),
    })


if __name__ == "__main__":
    LOG.info("=== deepthinkSingle 启动 watchlist=%s ===", _load_watchlist())
    # 后台预热全 A 股清单（不阻塞首屏）
    try:
        from services.stock_list import warmup_async
        warmup_async()
    except Exception as e:
        LOG.warning("stock_list 预热失败: %s", e)
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
