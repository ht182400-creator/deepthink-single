# 测试文档（Testing）

> 项目：deepthinkSingle 个股主力追踪系统
> 更新：2026-08-14 | 测试基线：**126 tests / 126 PASS**

## 1. 测试策略

| 层级 | 范围 | 方式 | 网络依赖 |
|---|---|---|---|
| **单元测试** | core / sources / services | `unittest` + mock，确定性 | ❌ 无 |
| **集成测试** | Flask API（test_client） | mock 服务层 + 真实冒烟（可选） | ⚠️ 冒烟测试有 |
| **手动冒烟** | 真实浏览器全流程 | curl + 浏览器 | ✅ |

设计原则：
- **零外部依赖**：核心逻辑全部 mock 网络（`unittest.mock.patch`），可离线跑、可进 CI；
- **路径隔离**：`tests/helpers.py::temp_config()` 把 `config` 的数据/日志/缓存路径指向临时目录，杜绝污染真实 `data/`；
- **确定性优先**：mock 固定返回 → 断言精确值；
- **回归优先**：对历史上踩过的坑（熔断器死锁、npx 表头差异、东财多节点）写专用回归测试。

## 2. 如何运行

```bash
cd E:\AI_Studio\deepthinkSingle

# 全部测试（离线，推荐）
python -m unittest discover tests -v

# 只跑单个模块
python -m unittest tests.test_circuit_breaker -v

# 只跑单个用例
python -m unittest tests.test_cache.TestTtlCache.test_expired_returns_none

# 跳过真实联网冒烟
python -m unittest discover tests -v -k TestApi   # 只跑 API 集成
```

## 3. 测试用例库清单（14 个模块 / 126 用例）

### 3.1 稳定性组件 core/（34 例）

| 模块 | 用例数 | 覆盖点 |
|---|---|---|
| `test_circuit_breaker.py` | 9 | CLOSED→OPEN→HALF_OPEN 状态机；阈值触发；超时自动半开；半开放行限量；半开成功关闭/失败再熔断；**死锁回归**（锁内不取锁）；容量上限 |
| `test_rate_limiter.py` | 6 | 初始满桶；按 rate 补充；容量封顶突发；block 超时返回；**capacity=0 语义**（`or` 吞 0 回归）；block 成功 |
| `test_cache.py` | 11 | TTL 命中/过期；**降级缓存 stale**（数据源全挂兜底）；invalidate；get_or_set 命中/未命中；FileCache 过期（mtime）、损坏 JSON 容错 |
| `test_fallback.py` | 8 | 链顺序优先；失败切下一源；全失败抛错；未知源跳过；**熔断跳过**（OPEN 不再调用）；**熔断恢复**（reset 后半开试探）；带参数源；注册表查询 |

### 3.2 数据源 sources/（38 例）

| 模块 | 用例数 | 覆盖点 |
|---|---|---|
| `test_base.py` | 12 | `to_secid` 全市场映射（sh/sz/bj、6/9/5/0/3 开头、纯代码、带点、大小写）；`pure_code` 前缀剥离（**回归：曾不剥 sh 前缀**） |
| `test_tencent.py` | 7 | 报价字段解析（60 字段快照：现价/开高/低/换手/外盘/内盘/PE/市值/市净率/量比/均价）；分时均价=累计额/(累计量×100)；**收盘后截断回归**；空 body/字段不足抛错；未实现方法抛错 |
| `test_eastmoney.py` | 7 | 资金流解析 + **主力=大单+超大单自洽**；资金空抛错；报价解析；分时 trends2 解析；**多节点轮换**（push2 失败切 delay）；全节点失败抛错 |
| `test_tdx.py` | 7 | `.day` 32 字节二进制解析（日期/OHLC/量）；文件缺失返回空；**周/月聚合**（5日/22日 OHLCV 正确性）；limit；周期不支持抛错；只读 K 接口；**`tdx_last_date` 读尾部日期**（K线缓存同步） |
| `test_npx.py` | 5 | **markdown 动态表头**（日线 close/vol vs 分钟线 last/volume）；空文本；坏行跳过；短行跳过 |

### 3.3 服务层 services/（39 例）

| 模块 | 用例数 | 覆盖点 |
|---|---|---|
| `test_quote_service.py` | 11 | `get_all` 全成功；**部分失败隔离**（errors 收集不中断）；全失败；缓存命中不触源；缓存未命中拉取+注入 source；K 线周期映射（day→tdx 链）；批量 `get_many` 部分失败；**K线缓存污染自动重拉**；缓存充足不重拉；**limit<=0 返回全量（日线不限制根数）**；**K线缓存同步三场景**（本地=缓存不刷 / 本地>缓存刷 / 无本地不刷） |
| `test_search.py` | 10 | 空关键词热门；名称/代码/纯代码/行业匹配；大小写不敏感；limit；无匹配；**返回结构完整性**；**纯数字前缀试探**（_guess_prefix + search_stocks_with_guess mock 探测） |
| `test_company.py` | 12 | **东财公告解析**；**财务摘要解析**；**股东户数解析**；`_secucode` 前缀判断；失败返回空 dict；**融资融券解析**；**龙虎榜解析**；**公司信息解析**；**盈利预测解析**；**多空情绪**；**公告正文解析**（去 HTML 标签 + PDF 链接）；**公告正文空 data 容错** |
| `test_stock_list.py` | 6 | **拼音首字母**（中微公司→zwgs）；**市场前缀**（sh/sz/bj 判断）；**clist 拉取解析**（mock 网络）；**本地 JSON 持久化**；**TTL 过期返回 None**；**search 拼音/代码/名称匹配** |

### 3.4 API 集成 tests/test_api.py（15 例）

| 用例 | 断言 |
|---|---|
| `test_index_200` | 主页 200 + HTML |
| `test_quote_returns_structure` | quote 结构 + errors=[] |
| `test_quote_error_still_200` | **服务失败仍 200 + error 字段**（前端不崩） |
| `test_search` / `test_kline_success` / `test_kline_failure_500` | 200 结构 / 500 错误 |
| `test_many` / `test_many_empty_codes_400` | 批量 / 参数校验 |
| `test_watchlist_default` / `test_watchlist_add_remove` | 自选增删；default 断言 len>10（115+ 预置池）+ 第一项 in_watchlist=True |
| `test_sysinfo` / `test_no_cache_headers` | 环境信息 / 反缓存头 |
| `test_announcement_route` | **公告正文路由**（mock content 返回结构；缺 code 400） |
| `test_real_quote` / `test_real_kline_day`（**冒烟**） | 真实链路数据完整性；失败自动 skip |

## 4. 测试发现的 Bug 与修复（本批次）

| # | 模块 | 现象 | 根因 | 修复 |
|---|---|---|---|---|
| 1 | `sources/base.py` | `pure_code("sh600519")` 返回 `"sh600519"` | 只处理 `.sh` 后缀，不剥 `sh` 前缀 | 先剥 `sh/sz/bj` 前缀再剥后缀 |
| 2 | `core/rate_limiter.py` | `capacity=0` 变成满桶 | `capacity or rate` 把合法 0 当未指定 | `capacity if capacity is not None else rate` |
| 3 | `sources/tdx.py` | 文件句柄未关闭（ResourceWarning） | `open(f,"rb").read()` 无 with | 改 `with open` |
| 4 | `services/quote_service.py` | **K线缓存污染**：npx 偶发写 5 条入缓存，日K 永久只显示 5 根 | 缓存无数据完整性校验 | `_MIN_CACHE_ROWS` 阈值（day 200 等）自动 invalidate 重拉 + `FileCache.invalidate` 补全 |
| 5 | `sources/tencent.py` | 腾讯 quote 换手率/高低字段映射错误（f[33]=最高 f[34]=最低 f[38]=换手率） | 腾讯文档字段与实测不符 | 按实测重映射；振幅按 (high-low)/pre_close 自算 |
| 6 | `sources/tencent.py` | **分时均价放大 100 倍**（如茅台显示 134803 而非 1348，Y 轴被拉高到 150000） | 腾讯 ifzq 分时 `vol` 单位是"手"（1手=100股），代码直接 `cum_amt/cum_vol`=元/手=真实均价×100 | 改为 `cum_amt / (cum_vol * 100)`；同步更新 `test_tencent.test_minute_parse` 断言 |
| 7 | `sources/tencent.py` | **收盘后分时图仍画出 15:00 后的 25 根伪数据**：价格定格在收盘价、vol/amt 微量累加，VOLFS/主力追踪/资金博弈指标全部被拉高 | 腾讯 ifzq 在收盘后仍持续返回"最后一帧"（接口特性），代码无截断逻辑 | `get_minute` 末尾加"价格最后变动位置截断"逻辑，丢掉收盘后伪数据；`test_tencent.test_minute_truncate_after_close` 回归 |
| 8 | `static/js/app.js` | **VOLFS 显示累计成交量**（柱子单调递增到 30 万手）而非行业标准的"每分钟成交量" | 腾讯 ifzq 分时 `vol` 是累计值（手），VOLFS 标准是差分值 | `renderVolfs` 改为 `vol[i] - vol[i-1]` 差分；tooltip 加"手"；series 名改"每分钟成交量" |
| 9 | `static/js/app.js` | **VOLFS 染色与"价格涨跌方向"不一致**（原按主力资金流染色） | 行业惯例 VOLFS 柱色按"该分钟价格变化方向"染色（A 股：红涨绿跌），参考通达信/同花顺 | `renderVolfs` 改为 `m[i].price vs m[i-1].price` 比较染色 |
| 10 | `static/js/app.js` | **分时图右侧无选中分钟详情**：用户按方向键时无法查看"某分钟"的成交明细 | 缺少键盘切换分钟 + 右侧详情面板机制 | 加 `_selectedMinuteIdx` 全局状态 + `p1.keydown` 监听 ↑/↓ + `renderOrderBook(q, minuteList, selIdx)` 扩展签名 + 详情面板显示价格/均价/每分成交/成交额 |
| 11 | `tests/test_tencent.py` | **测试 mock 字段不足**：`_quote_text()` 只 40 字段且结尾 `"0";` 分号串到 f[39]，新代码 `float(f[39])` 报 `'0";'` | mock 数据与真实腾讯快照字段数不符 | mock 补足到 60 个真实字段（外盘/内盘/PE/市值/市净率/量比/均价），修正 f[37] 保持 amount 断言 |
| 12 | `app.py` | **watchlist 只返回自选 4 项**，下拉列表太短 | API 只返回自选，不含预置池 | `api_watchlist` 改为返回 watchlist + 全部预置池（115+ 项），每项 `{code, name, in_watchlist}`；`test_watchlist_default` 增加 len>10 与 in_watchlist 断言 |
| 13 | `sources/tencent.py` | **五档盘口缺外盘/内盘/PE/市值/市净率/量比/均价**，用户要求的指标显示不了 | quote 只解了 30 个字段 | 按实测扩展 f[7]/f[8]/f[39]/f[44]/f[45]/f[46]/f[49]/f[51] 8 字段；前端补 16 项指标 2 组/行 |


> 这就是「先写测试再验证」的价值：7 个 bug 都是断言跑红后反向定位的，人工 review 未必能第一时间发现。

## 5. 覆盖率现状与提升方向

当前无覆盖率统计。目标基线：

| 模块 | 目标 | 说明 |
|---|---|---|
| core/ | ≥90% | 纯逻辑，最值得保 |
| sources/ | ≥80% | 解析函数全覆盖，HTTP 层 mock |
| services/ | ≥85% | 错误路径全覆盖 |
| app.py | ≥60% | 路由分发，薄层 |

可执行 `python -m coverage run -m unittest discover tests && python -m coverage report` 生成报告（需先 `pip install coverage`）。

## 6. 测试纪律（DoD 挂钩）

- 每次新需求（US-x）实现 → 必带 ≥2 个测试用例（正常路径 + 异常路径）；
- 修 bug → 先写回归测试再修代码（TDD 风格）；
- CI/发布前 → `python -m unittest discover tests` 必须全绿；
- 冒烟测试默认在线可用才跑（skip 不阻塞）。
