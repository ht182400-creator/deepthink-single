# -*- coding: utf-8 -*-
"""
降级编排器：按优先级链依次尝试数据源，失败自动切下一源。
结合熔断器：某源熔断时跳过它；所有源失败抛 RuntimeError。
"""
import logging
import threading
import time

from core.circuit_breaker import CircuitBreaker

LOG = logging.getLogger("deepthink")


class FallbackOrchestrator:
    """数据源降级编排：sources 注册表 + 熔断器 + 指数退避。"""

    def __init__(self):
        self._sources = {}       # name -> source 对象
        self._breakers = {}      # name -> CircuitBreaker
        self._lock = threading.Lock()

    def register(self, name: str, source, fail_threshold=5, reset_seconds=60):
        """注册数据源适配器（实现 get_quote/get_minute/get_kline/get_fund_flow 接口）"""
        with self._lock:
            self._sources[name] = source
            self._breakers[name] = CircuitBreaker(fail_threshold, reset_seconds)

    def names(self):
        return list(self._sources.keys())

    def get_source(self, name: str):
        return self._sources.get(name)

    def _call_one(self, name: str, method: str, *args, **kwargs):
        """调用单个源（带熔断）。成功返回 (True, result)；失败返回 (False, err)"""
        brk = self._breakers[name]
        if not brk.allow():
            return False, RuntimeError(f"熔断: {name}")
        try:
            src = self._sources[name]
            result = getattr(src, method)(*args, **kwargs)
            brk.record_success()
            return True, result
        except Exception as e:
            brk.record_failure()
            LOG.warning("source[%s].%s 失败: %s", name, method, e)
            return False, e

    def fallback(self, chain: list, method: str, *args, **kwargs):
        """按优先级链尝试，返回 (result, used_source_name)。全失败抛 RuntimeError。
        chain 如 ['tencent', 'eastmoney']；支持带参数 ('eastmoney', {'host': 'x'})。"""
        last_err = None
        for item in chain:
            if isinstance(item, tuple):
                name, opts = item[0], item[1]
            else:
                name, opts = item, None
            if name not in self._sources:
                continue
            ok, res = self._call_one(name, method, *args, **kwargs)
            if ok:
                return res, name
            last_err = res
        raise RuntimeError(f"数据源全失败({chain}): {last_err}")


# 全局编排器（单实例）
_orch = FallbackOrchestrator()


def register(name, source, **kw):
    _orch.register(name, source, **kw)


def fallback(chain, method, *args, **kwargs):
    return _orch.fallback(chain, method, *args, **kwargs)


def orchestrator() -> FallbackOrchestrator:
    return _orch
