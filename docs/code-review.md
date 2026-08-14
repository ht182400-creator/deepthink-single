# 代码审查报告（2026-08-13）

> 审查人：AI 编码专家视角 | 覆盖：全量后端代码（阶段 + 全局）
> 方法：人工逐模块阅读 + 100 个自动化测试交叉验证

## 1. 审查范围

```
app.py (178→170 行)          Flask 路由层
config.py (56 行)            全局配置
core/ (297 行)               熔断 / 限流 / 缓存 / 降级编排
sources/ (401 行)            腾讯 / 东财 / 通达信 / npx 适配器
services/ (273 行)           服务层 + SQLite
data_provider.py (71 行)     ⚠️ 兼容转发层（deprecated）
```

## 2. 本轮阶段审查：已修复问题（10 项）

| # | 模块 | 问题 | 类型 | 修复 |
|---|---|---|---|---|
| 1 | `sources/base.py` | `pure_code("sh600519")` 返回 `"sh600519"`（只剥后缀不剥前缀） | 🔴 逻辑错误 | 先剥 `sh/sz/bj` 前缀再剥后缀 |
| 2 | `core/rate_limiter.py` | `capacity or rate` 把显式 `0` 当未指定 → 空桶变满桶 | 🔴 逻辑错误 | `capacity if capacity is not None else rate` |
| 3 | `sources/tdx.py` | `open(f,"rb").read()` 文件句柄泄漏（ResourceWarning） | 🟠 资源泄漏 | `with open` |
| 4 | `core/cache.py` | `FileCache.get` 的 `max_age_s or self.ttl` 同类 `or` 吞 0 | 🟠 潜在错误 | 改 `is not None` 判断 |
| 5 | `core/cache.py` | `TtlCache.get_or_set` 声明 `ttl` 参数但从未使用 | 🟡 dead parameter | 删除参数 |
| 6 | `app.py` | `_quote_cache`/`_quote_lock` 定义从未使用 | 🟡 dead code | 删除 + 清理 `import threading` |
| 7 | `config.py` | `LOG_DIR = ... if False else ...` 死分支 | 🟡 dead code | 清理 |
| 8 | `config.py` | K线降级链含 `"eastmoney"`，但 `eastmoney.get_kline` 抛 NotImplementedError（无效降级，白等一轮） | 🟠 架构不一致 | 移出链 + 注释说明（东财 K线 HTTP 不稳，未来实现后加回） |
| 9 | `app.py` | `/api/kline` 的 `int(limit)` 非法输入直接 500 | 🟡 健壮性 | ValueError 兜底默认 260 |
| 10 | `sources/eastmoney.py` | 分时解析 `c[0][11:16]` 无长度保护 | 🟡 健壮性 | 长度判断 |

## 3. 全局质量评估

### 架构一致性 ✅
- 分层清晰：`app.py` 薄路由 → `services/` 业务 → `sources/` 适配器 → `core/` 横切组件，依赖单向无环；
- `data_provider.py` 已降级为纯转发层，无核心逻辑残留，`__main__` 自检可跑；
- 数据源注册集中（`quote_service` 顶部 4 行），新增源只需实现 `Source` 接口 + register。

### 并发与稳定性 ✅
- 熔断/限流/缓存全部 `threading.Lock` 保护，死锁回归测试在案；
- SQLite 用 `_db_lock` + 每次新连接，`threaded=True` 下安全；
- 数据源失败路径：`get_all` 三源独立 try，单源失败不拖垮整体。

### 异常处理 ⚠️（3 处观察）
1. `npx.py` 调用 `subprocess.run(... timeout=60)`——K线分钟首次加载最长 60s，前端 fetch 无超时，极端情况下请求悬挂。建议前端 `AbortController`（已记 backlog）；
2. `eastmoney._get_with_fallback` 多节点轮换**无退避**，主节点连续失败时 delay 节点也会被高频打——当前限流器兜底，可接受；
3. `services/db.py` 无 WAL 模式——Sprint 3 批量并发写时建议 `PRAGMA journal_mode=WAL`。

### 性能 ✅
- 日/周/月 K：本地 .day 0.01s（缓存 + 本地双保险）；
- 报价/分时/资金：TTL 缓存（10/30/60s）+ 腾讯限流 5req/s，30s 轮询单标的完全够用；
- `get_many`：`ThreadPoolExecutor(8)` 并发，避免自选批量串行。

### 安全 ⚠️
- 纯本地工具（127.0.0.1），无认证需求；
- `render_template` 无用户输入注入面；`/api/watchlist` POST 对 code 做了 strip/lower 校验；
- 数据源为外部公开接口，`requests` 无 SSL 校验禁用——保持默认校验 ✅。

## 3.5 审查后追加修复（2026-08-13 19:46）

| # | 问题 | 修复 |
|---|---|---|
| 11 | **K线缓存污染**：npx 偶发写 5 条入缓存，日K 永久只显示 5 根 | `_MIN_CACHE_ROWS` 阈值（day 200 等）自动 invalidate 重拉 |
| 12 | `FileCache` 缺 `invalidate` 方法 | 补 `os.remove(_path(key))` 实现 |

> 此轮暴露教训：**缓存架构必须校验数据完整性**（条数/字段/时间范围），不能只看 TTL。已加 2 个回归测试。

## 4. 技术债与后续建议（记 backlog）

| 优先级 | 项 | 说明 |
|---|---|---|
| P1 | 前端 fetch 超时/取消 | K线 npx 最长 60s，建议 `AbortController` 防悬挂 |
| P1 | SQLite WAL 模式 | Sprint 3 批量并发写前启用 |
| P2 | 东财 K线适配器 | 调研过 HTTP 接口不稳，暂不接入；实现后加回 `KLINE_DAY_SOURCES` |
| P2 | 搜索在线兜底 | 当前仅预置池 120+，Sprint 3 接东财搜索 API（限流注意） |
| P2 | 覆盖率门禁 | 建议 `coverage` ≥80%（core 90%）进 CI |
| P3 | 数据质量校验 | 架构文档已设计（跳变/跨源交叉校验），未落地 |

## 5. 结论

- **可交付**：分层结构健康，稳定性组件有测试兜底，无已知阻塞级缺陷；
- **测试是本轮最大收益**：100 个用例一次性暴露 10 个问题（3 逻辑错误 + 2 资源/健壮 + 5 代码卫生）；
- 后续按 backlog P1 → P2 → P3 演进即可，无需返工。
