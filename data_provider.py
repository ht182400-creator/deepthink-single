# -*- coding: utf-8 -*-
"""
兼容转发层（deprecated）：
历史版本的统一入口。新代码请直接使用 services.quote_service / services.search_service。
保留本文件仅为兼容旧引用，功能全部委托服务层。
"""
import services.quote_service as svc
import services.search_service as search_svc

# ---- 旧函数签名转发 ----
def get_quote(code):
    return svc.get_quote(code)

def get_minute(code):
    return svc.get_minute(code)

def get_fund_flow(code):
    return svc.get_fund_flow(code)

def get_kline(code, period="day", limit=260):
    return svc.get_kline(code, period, limit)

def get_all(code):
    return svc.get_all(code)

def search_stocks(keyword, limit=20):
    return search_svc.search_stocks(keyword, limit)

def get_many(codes):
    return svc.get_many(codes)

# ---- 数据源模块转发（若旧代码 import data_provider.tencent_minute 等） ----
def tencent_quote(code):
    from sources.tencent import TencentSource
    return TencentSource().get_quote(code)

def tencent_minute(code):
    from sources.tencent import TencentSource
    return TencentSource().get_minute(code)

def em_fund_flow(code):
    from sources.eastmoney import EastmoneySource
    return EastmoneySource().get_fund_flow(code)

def em_quote(code):
    from sources.eastmoney import EastmoneySource
    return EastmoneySource().get_quote(code)

def em_minute(code):
    from sources.eastmoney import EastmoneySource
    return EastmoneySource().get_minute(code)

def read_tdx_day(code):
    from sources.tdx import read_tdx_day as _f
    return _f(code)

def parse_kline(text):
    from sources.npx import parse_kline as _f
    return _f(text)


if __name__ == "__main__":
    import json
    d = get_all("sh600519")
    d["quote"] = {k: v for k, v in d.get("quote", {}).items()}
    print("报价:", json.dumps(d.get("quote", {}), ensure_ascii=False))
    print("分时点数:", len(d.get("minute", [])))
    print("资金点数:", len(d.get("fund", [])))
    print("errors:", d.get("errors"))
    print("K线 day 前3:", get_kline("sh600519", "day")[:3])
    print("搜索 茅台:", search_stocks("茅台"))
