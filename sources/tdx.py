# -*- coding: utf-8 -*-
"""
通达信本地数据源：历史日/周/月 K 权威源（0.01s，含全历史）。
.day 每条 32 字节: <iiiiifii> 日期(YYYYMMDD) 开 高 低 收(×100) 额(float) 量(手) 保留
周/月 K 从日线本地聚合（无网络依赖）。
"""
import struct
import os

import config
from sources.base import Source


def read_tdx_day(code: str) -> list:
    """读本地通达信 .day 全部记录 → [{date,open,close,high,low,vol},...]"""
    mkt, pure = code[:2], code[2:]
    f = os.path.join(config.TDX_ROOT, mkt, "lday", f"{mkt}{pure}.day")
    if not os.path.exists(f):
        return []
    try:
        with open(f, "rb") as fh:
            data = fh.read()
    except Exception:
        return []
    n = len(data) // 32
    out = []
    for i in range(n):
        d, o, h, l, c, _amt, vol, _r = struct.unpack("<iiiiifii", data[i * 32:(i + 1) * 32])
        if d <= 0 or c <= 0:
            continue
        out.append({
            "date": f"{d // 10000:04d}-{d % 10000 // 100:02d}-{d % 100:02d}",
            "open": o / 100.0,
            "close": c / 100.0,
            "high": h / 100.0,
            "low": l / 100.0,
            "vol": vol,
        })
    return out


def tdx_last_date(code: str) -> str:
    """轻量读通达信 .day 最后一条日期（YYYY-MM-DD），不解析全部记录。
    用于判断本地数据源是否更新（缓存同步）。"""
    mkt, pure = code[:2], code[2:]
    f = os.path.join(config.TDX_ROOT, mkt, "lday", f"{mkt}{pure}.day")
    if not os.path.exists(f):
        return ""
    try:
        size = os.path.getsize(f)
        if size < 32:
            return ""
        with open(f, "rb") as fh:
            fh.seek(size - 32)
            data = fh.read(32)
        d, _o, _h, _l, _c, _amt, _vol, _r = struct.unpack("<iiiiifii", data)
        if d <= 0:
            return ""
        return f"{d // 10000:04d}-{d % 10000 // 100:02d}-{d % 100:02d}"
    except Exception:
        return ""


def aggregate(days: list, n_per: int) -> list:
    """日线 → 周期线（每 n_per 根聚合 OHLCV）"""
    out = []
    for i in range(0, len(days), n_per):
        chunk = days[i:i + n_per]
        out.append({
            "date": chunk[-1]["date"],
            "open": chunk[0]["open"],
            "close": chunk[-1]["close"],
            "high": max(x["high"] for x in chunk),
            "low": min(x["low"] for x in chunk),
            "vol": sum(x["vol"] for x in chunk),
        })
    return out


class TdxSource(Source):
    name = "tdx"

    def get_kline(self, code: str, period: str, limit: int) -> list:
        days = read_tdx_day(code)
        if not days:
            raise RuntimeError(f"通达信本地无 {code} 数据")
        if period == "day":
            rows = days
        elif period == "week":
            rows = aggregate(days, 5)
        elif period == "month":
            rows = aggregate(days, 22)
        else:
            raise RuntimeError(f"通达信仅支持 day/week/month: {period}")
        return rows[-limit:]

    def get_quote(self, code: str) -> dict:
        raise NotImplementedError("通达信只提供历史 K")

    def get_minute(self, code: str) -> list:
        raise NotImplementedError("通达信只提供历史 K")

    def get_fund_flow(self, code: str) -> list:
        raise NotImplementedError("通达信只提供历史 K")
