# -*- coding: utf-8 -*-
"""降级编排器单元测试：链顺序 / 熔断跳过 / 带参数源 / 全失败。"""
import unittest
from unittest.mock import MagicMock

from core.circuit_breaker import CircuitBreaker
from core.fallback import FallbackOrchestrator


class _Source:
    """可编程假源。"""

    def __init__(self, name, results=None, errors=None):
        self.name = name
        self.results = results or {}
        self.errors = errors or {}
        self.calls = []

    def get_quote(self, code):
        self.calls.append(("get_quote", code))
        if "get_quote" in self.errors:
            raise self.errors["get_quote"]
        return {"code": code, "name": self.name}


class TestFallbackOrchestrator(unittest.TestCase):

    def setUp(self):
        self.orch = FallbackOrchestrator()

    def test_first_success_wins(self):
        a = _Source("a")
        b = _Source("b")
        self.orch.register("a", a)
        self.orch.register("b", b)
        res, src = self.orch.fallback(["a", "b"], "get_quote", "sh600519")
        self.assertEqual(res["name"], "a")
        self.assertEqual(src, "a")
        self.assertEqual(len(b.calls), 0)      # b 未被调用

    def test_fallback_to_next_on_error(self):
        a = _Source("a", errors={"get_quote": RuntimeError("boom")})
        b = _Source("b")
        self.orch.register("a", a)
        self.orch.register("b", b)
        res, src = self.orch.fallback(["a", "b"], "get_quote", "sh600519")
        self.assertEqual(res["name"], "b")
        self.assertEqual(src, "b")

    def test_all_fail_raises(self):
        a = _Source("a", errors={"get_quote": RuntimeError("x")})
        b = _Source("b", errors={"get_quote": RuntimeError("y")})
        self.orch.register("a", a)
        self.orch.register("b", b)
        with self.assertRaises(RuntimeError) as ctx:
            self.orch.fallback(["a", "b"], "get_quote", "sh600519")
        self.assertIn("数据源全失败", str(ctx.exception))

    def test_unknown_source_skipped(self):
        a = _Source("a")
        self.orch.register("a", a)
        res, src = self.orch.fallback(["ghost", "a"], "get_quote", "sh600519")
        self.assertEqual(src, "a")

    def test_breaker_skips_open_source(self):
        a = _Source("a", errors={"get_quote": RuntimeError("bad")})
        b = _Source("b")
        self.orch.register("a", a, fail_threshold=2, reset_seconds=3600)
        self.orch.register("b", b)
        # 前 2 次：a 失败 → 熔断
        for _ in range(2):
            res, src = self.orch.fallback(["a", "b"], "get_quote", "sh600519")
            self.assertEqual(src, "b")
        # 第 3 次：a 已 OPEN，直接跳过 a
        a.calls.clear()
        res, src = self.orch.fallback(["a", "b"], "get_quote", "sh600519")
        self.assertEqual(src, "b")
        self.assertEqual(a.calls, [])          # a 完全没被调

    def test_breaker_recovers_after_reset(self):
        a = _Source("a", errors={"get_quote": RuntimeError("bad")})
        b = _Source("b")
        self.orch.register("a", a, fail_threshold=1, reset_seconds=0.1)
        self.orch.register("b", b)
        res, src = self.orch.fallback(["a", "b"], "get_quote", "sh600519")
        self.assertEqual(src, "b")             # a 熔断
        import time
        time.sleep(0.15)
        # 恢复 HALF_OPEN，放行一次；仍失败 → 再熔断
        a.errors["get_quote"] = RuntimeError("still bad")
        res, src = self.orch.fallback(["a", "b"], "get_quote", "sh600519")
        self.assertEqual(src, "b")

    def test_tuple_source_with_opts(self):
        """带参数源（('eastmoney', {'host': 'x'})）——opts 被忽略但不应报错。"""
        a = _Source("a")
        self.orch.register("a", a)
        res, src = self.orch.fallback([("a", {"host": "x"})], "get_quote", "sh600519")
        self.assertEqual(src, "a")

    def test_get_source_returns_registered(self):
        a = _Source("a")
        self.orch.register("a", a)
        self.assertIs(self.orch.get_source("a"), a)
        self.assertIsNone(self.orch.get_source("nope"))


if __name__ == "__main__":
    unittest.main()
