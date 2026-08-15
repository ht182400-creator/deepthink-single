# 测试文档（Testing）

> 项目：deepthinkSingle 个股主力追踪系统
> 更新：2026-08-15 | 测试基线：**后端 143 tests / 前端 17 tests（dom-smoke 12 + indicators 5）/ 全 PASS**

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

> **前端测试（新增，2026-08-14）**：技术指标算法（`static/js/indicators.js`）已抽离为无 DOM 依赖的纯函数模块，配套 Node 内置 test runner 单测。
>
> ```bash
> # 前端指标算法单测（需 Node ≥ 18，无需浏览器）
> node --test tests/js/*.test.js
> # 或单文件
> node --test tests/js/indicators.test.js
> ```
>
> 覆盖：`ema` 长度/常数序列、`macd`（**D1 回归守护：DEA 与 MACD 柱不得全 null**）、`kdj`（J=3K-2D）、`boll`（上下轨对称）、`rsi`（单调上涨=100）。5 用例全绿。
> **新增回归：K线 60分加载**——`loadKline` 曾因要求分钟数据 ≥10 根而拒绝 npx 返回的当天 4 根 m60 数据，导致一直 fallback/loading；现已被 `dom-smoke` 用例锁定为「m60 返回 4 根仍应渲染并显示 60分K 标题」。
>
> **前端语法校验**（重构/改动后快速把关，无需浏览器）：
> ```bash
> node --check static/js/app.js
> node --check static/js/indicators.js
> ```
>
> **前端页面功能测试（真·冒烟，需 `jsdom`）**：`tests/js/dom-smoke.test.js` 用 `jsdom` 加载**真实 `index.html`**，mock `echarts`/`fetch`/`ResizeObserver` 后触发 `init()`，对真实 DOM 与交互做断言（启动、复盘 modal、搜索下拉 + 键盘导航 + Enter 切换、自选删除、空数据占位、**K线 60分 4 根仍渲染**），不再只是静态文本检查。`jsdom` 已是 `devDependencies`（`npm install` 安装），CI / 本地 `node --test` 恒跑。
>
> ```bash
> npm install        # 安装 jsdom 等 devDependencies（首次）
> node --test tests/js/*.test.js
> ```


## 3. 测试用例库清单（后端 14 模块 / 134 用例 + 前端 2 模块 / 17 用例）

### 3.1 稳定性组件 core/（34 例）

| 模块 | 用例数 | 覆盖点 |
|---|---|---|
| `test_circuit_breaker.py` | 9 | CLOSED→OPEN→HALF_OPEN 状态机；阈值触发；超时自动半开；半开放行限量；半开成功关闭/失败再熔断；**死锁回归**（锁内不取锁）；容量上限 |
| `test_rate_limiter.py` | 6 | 初始满桶；按 rate 补充；容量封顶突发；block 超时返回；**capacity=0 语义**（`or` 吞 0 回归）；block 成功 |
| `test_cache.py` | 11 | TTL 命中/过期；**降级缓存 stale**（数据源全挂兜底）；invalidate；get_or_set 命中/未命中；FileCache 过期（mtime）、损坏 JSON 容错 |
| `test_fallback.py` | 8 | 链顺序优先；失败切下一源；全失败抛错；未知源跳过；**熔断跳过**（OPEN 不再调用）；**熔断恢复**（reset 后半开试探）；带参数源；注册表查询 |

### 3.2 数据源 sources/（40 例）

| 模块 | 用例数 | 覆盖点 |
|---|---|---|
| `test_base.py` | 12 | `to_secid` 全市场映射（sh/sz/bj、6/9/5/0/3 开头、纯代码、带点、大小写）；`pure_code` 前缀剥离（**回归：曾不剥 sh 前缀**） |
| `test_tencent.py` | 7 | 报价字段解析（60 字段快照：现价/开高/低/换手/外盘/内盘/PE/市值/市净率/量比/均价）；**分时解析回归：腾讯 ifzq 返回累计股数/累计金额 → 后端差分为每分钟成交量/成交额，均价 = 累计额 / 累计股数**；**收盘后截断回归**；空 body/字段不足抛错；未实现方法抛错 |
| `test_eastmoney.py` | 9 | 资金流解析 + **主力=大单+超大单自洽**；资金空抛错；报价解析；分时 trends2 解析；**多节点轮换**（push2 失败切 delay）；全节点失败抛错；**5日主力 f178 解析**（Sprint4）；**5日主力空/失败返回空**（前端隐藏） |
| `test_tdx.py` | 7 | `.day` 32 字节二进制解析（日期/OHLC/量）；文件缺失返回空；**周/月聚合**（5日/22日 OHLCV 正确性）；limit；周期不支持抛错；只读 K 接口；**`tdx_last_date` 读尾部日期**（K线缓存同步） |
| `test_tdx_minute.py` | 8 | `.lc1` 32 字节二进制解析（**uint16 日期/时间，2026+ 编码值 >32767 必须用无符号 H 否则溢出变负**）；**按交易日聚合 m5/m15/m30/m60 条数与 OHLC 正确性**；`TdxSource.get_kline` 分钟全量/limit 截断；**历史分时按日期过滤**（当日抛 NotImplementedError 回退腾讯）；文件缺失返回空；**新增 `QuoteServiceFullHistoryTest`：构造 2640 根（>2000）`.lc1`，经 `quote_service.get_kline` 验证返回全量（不被 2000 上限截断），守住「分钟 K 全量历史」回归** |
| `test_npx.py` | 5 | **markdown 动态表头**（日线 close/vol vs 分钟线 last/volume）；空文本；坏行跳过；短行跳过 |

### 3.3 服务层 services/（39 例）

| 模块 | 用例数 | 覆盖点 |
|---|---|---|
| `test_quote_service.py` | 11 | `get_all` 全成功；**部分失败隔离**（errors 收集不中断）；全失败；缓存命中不触源；缓存未命中拉取+注入 source；K 线周期映射（day→tdx 链）；批量 `get_many` 部分失败；**K线缓存污染自动重拉**；缓存充足不重拉；**limit<=0 返回全量（日线不限制根数）**；**K线缓存同步三场景**（本地=缓存不刷 / 本地>缓存刷 / 无本地不刷） |
| `test_search.py` | 10 | 空关键词热门；名称/代码/纯代码/行业匹配；大小写不敏感；limit；无匹配；**返回结构完整性**；**纯数字前缀试探**（_guess_prefix + search_stocks_with_guess mock 探测） |
| `test_company.py` | 12 | **东财公告解析**；**财务摘要解析**；**股东户数解析**；`_secucode` 前缀判断；失败返回空 dict；**融资融券解析**；**龙虎榜解析**；**公司信息解析**；**盈利预测解析**；**多空情绪**；**公告正文解析**（去 HTML 标签 + PDF 链接）；**公告正文空 data 容错** |
| `test_stock_list.py` | 6 | **拼音首字母**（中微公司→zwgs）；**市场前缀**（sh/sz/bj 判断）；**clist 拉取解析**（mock 网络）；**本地 JSON 持久化**；**TTL 过期返回 None**；**search 拼音/代码/名称匹配** |

### 3.3.1 前端算法 tests/js/（5 例，Node）

| 模块 | 用例数 | 覆盖点 |
|---|---|---|
| `indicators.test.js` | 5 | `ema` 长度/常数序列；`macd`（**D1 回归守护：DEA 与 MACD 柱不得全 null、对齐不早于 DIF**）；`kdj`（J=3K-2D）；`boll`（上下轨对称于中轨）；`rsi`（单调上涨序列=100） |
| `dom-smoke.test.js` | 12 | 源码级 D2/D3/M1 回归守护（3，恒跑，守护 resize 崩溃 / zoom 监听泄漏 / 副图去重不被回退）+ jsdom 真·页面功能测试（9，**已安装依赖恒跑**）：启动不崩且 DTIndicators 挂载 / p1 init；复盘 modal 开-关；搜索输入触发 `/api/search` 并渲染 2 项；ArrowDown 高亮首项 + Enter 触发 `/api/quote` 切换；「−」触发 `/api/watchlist` remove；空分钟数据显示「暂无分时数据」占位；**K线 60分 只返回 4 根仍应渲染并显示 60分K 标题（锁定分钟 K 接受阈值 bug）**；**历史分时弹窗（缺陷#14 回归）：双击 K 线打开 modal 取数，`renderHistChart` 正确 `setOption` 渲染（非白图）**；**历史分时空数据边界：提示「暂无历史分时」不崩溃** |

### 3.3.2 前端工程配置
- `package.json`：`npm test` → `node --test tests/js/*.test.js`；`devDependencies: jsdom`（`npm install` 拉取，不提交 `node_modules`）。
- 运行前需 `npm install`；若 `jsdom` 缺失，功能用例会自动 skip 并提示，不影响指标算法单测。

### 3.4 API 集成 tests/test_api.py（15 例）

| 用例 | 断言 |
|---|---|
| `test_index_200` | 主页 200 + HTML |
| `test_quote_returns_structure` | quote 结构 + errors=[] |
| `test_quote_error_still_200` | **服务失败仍 200 + error 字段**（前端不崩） |
| `test_search` / `test_kline_success` / `test_kline_failure_500` | 200 结构 / 500 错误 |
| `test_many` / `test_many_empty_codes_400` | 批量 / 参数校验 |
| `test_watchlist_default` / `test_watchlist_add_remove` | 自选增删；default 断言 len>10（5549+ 全 A 股池）+ 第一项 in_watchlist=True |
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
| 12 | `app.py` | **watchlist 只返回自选 4 项**，下拉列表太短 | API 只返回自选，不含预置池 | `api_watchlist` 改为返回 watchlist + 全部预置池（5549+ 项），每项 `{code, name, in_watchlist}`；`test_watchlist_default` 增加 len>10 与 in_watchlist 断言 |
| 13 | `sources/tencent.py` | **五档盘口缺外盘/内盘/PE/市值/净市率/量比/均价**，用户要求的指标显示不了 | quote 只解了 30 个字段 | 按实测扩展 f[7]/f[8]/f[39]/f[44]/f[45]/f[46]/f[49]/f[51] 8 字段；前端补 16 项指标 2 组/行 |
| 14 | `app.py` | **v0.0.4 回归：`/api/many` 必然 500**——C5 改动引入 `config.MAX_CODES` 上限，但 `app.py` 从未 `import config`（NameError），自选批量表格功能完全不可用 | `py_compile` 抓不到未定义名，仅运行时暴露 | 补 `import config`；`test_many` 断言 200 守护，CI 防回退 |
| 15 | `static/js/app.js` `services/quote_service.py` | **60 分钟 K 线加载白图/卡 loading**：前端 `loadKline` 要求分钟 K ≥10 根才接受，但 npx 分钟数据源只返回当天（m60 约 4 根），导致一直 fallback 或显示 loading；同时后端把分钟 K 小数据量当作缓存污染，强制重拉加速 npx 熔断 | 必须结合真实浏览器/接口 + 数据源行为才能发现；单元测试无法覆盖 | 前端：分钟 K 非空即接受；后端：分钟 K 不应用最小条数阈值；新增 jsdom 功能测试锁定「m60 4 根仍渲染 60分K」 |
| 16 | `services/quote_service.py` `static/js/app.js` | **分钟 K 全量历史被后端 2000 上限截断**：`get_kline` 对分钟周期强制 `fetch_limit = max(limit, 2000)`，tdx 返回全量后被 `rows[-2000:]` 截掉，m1/超长历史 m5 丢失大量数据；前端 `loadKline` 也只请求 2000；标题还错标「当日」 | 真实 D 盘 `.lc1` 验证才发现（fixture 自洽测不出）；m60/m30/m15 因数据量 <2000 未暴露 | 后端 `fetch_limit` 改为 0（日线/分钟均拉全量存缓存）；前端 `limit=0` 拉全量；标题「当日」→「本地」；新增 `test_tdx_minute.py::QuoteServiceFullHistoryTest` 用 2640 根 fixture 守住全量不截断 |
| 17 | `static/js/app.js` | **K线加载失败时显示"数据为空"且旧图表残留**：`/api/kline` 抛异常返回 `{error: ...}` 时，前端把它当空数组，最终显示"K线数据为空"；出错也不清 charts.p4，上一只股票图表仍留在画面上 | 需服务端返回 500 的异常路径才能暴露 | `loadKline` 检查 `data.error` 并记入 `lastErr`；失败时 `charts.p4.clear()` + 置空 option；`app.js?v=36` 强制浏览器刷新 |
| 18 | `services/quote_service.py` `core/cache.py` | **分钟 K 显示陈旧数据（茅台停在 07-06 而其他股是 08-03）**：`get_kline` 的"通达信本地有更新则重拉"过期检查只对日 K 生效（`ptype == "day"`），分钟 K 永不检查；`kline_cache` 是 `FileCache` 落盘持久化（TTL 24h），旧代码调试期写入的陈旧分钟缓存即便重启进程也清不掉，于是一直命中旧值 | 真实浏览器 E2E（puppeteer-core）切 4 只股票对比才发现——curl 单测测不出"某只股陈旧而其他新鲜"的差异 | 过期检查扩展到 `(ptype == "day" or ptype == "min")`；手动清空 `data/kline_cache` 陈旧文件；新增 `tests/e2e_kline.js` 真实 Chrome 端到端（打开页面→切4只股→30分K→校验图表数据点）守护回归 |
| 19 | `sources/tencent.py` `static/js.app.js` | **历史分时弹窗成交量呈单调递增"山形"且均价为真实值 100 倍（澜起科技 08-13）**：腾讯 ifzq 接口返回累计成交量（手）/累计成交额（元），但旧代码未差分、且均价多除 100；07-21 因通达信本地有数据所以正常 | 真实截图对比 + curl 抓原始响应才发现数据源格式理解错误 | 后端做差分：输出每分钟成交量（手）/成交额（元），均价 = 累计额 /（累计手数 × 100）；`renderVolfs` 与历史分时弹窗成交量直接使用"手"；历史分时消息去掉硬编码"来源腾讯"；`app.js?v=39`；更新 `test_tencent.py` mock 数据与断言守护 |
| 20 | `static/js/app.js` | **日线 tooltip 把 dataIndex 当开盘价（保利发展 05-21 显示"开盘 4785"）**：旧 tooltip formatter 用 `const [o,c,l,h] = p.data` 解构 ECharts 传入的 candlestick 数组，而该环境下 `p.data[0]` 实为 K 线序列索引（4785）；同时成交额用 `c*today.vol*100/1e8` 估算、且日线 `.day` 本就有真实 `amount` 字段未透传 | 真实浏览器 E2E 悬停 05-21 触发 tooltip，且 `idx=4785` 与用户截图数字吻合，确认根因 | tooltip 不再依赖 `p.data` 顺序，改用 `list[i]`（i 为 dataIndex）直接取 OHLC；成交额优先用真实 `amount`（tdx 已透传 `amount` 字段，聚合周/月累加）；`app.js?v=38` |
| 21 | `services/quote_service.py` `app.py` `static/js/app.js` | **历史分时来源不透明**：本地通达信分钟数据滞后时（如请求日 > `.lc1` 最后日期），静默回退腾讯/东财，用户无从得知、易误判日线出错 | 用户主动要求"本地数据落后时标注来源" | 新增 `get_minute_with_meta` 返回 `{data, meta:{source, local_last_date, requested_date}}`；`/api/minute?date=` 返回信封、当日仍返回纯数组兼容；前端历史分时 `histMsg` 标注「本地数据止于 MM-DD，该日来自 腾讯/东财」或「来源 本地通达信」；`app.js?v=38` |
| 22 | `services/quote_service.py` `static/js/app.js` | **不同历史日期的分时走势图完全一样（茅台 2024-10-08 vs 2024-11-04）**：腾讯/东财免费接口对较远历史日期会忽略 `date` 参数，直接返回最近交易日（2026-08-14）的分时数据；前端据此画出错误走势 | 用户截图对比两个日期发现走势完全重合 | 增加 `_minute_matches_day` 校验：在线源回退数据用请求日日线 OHLC 做交叉验证，首/尾价不匹配则返回空数据 + `meta.mismatch=true, source="none"`；前端提示"本地未下载该日分钟数据，免费在线源返回的不是该日真实走势"；新增 `test_quote_service.py` 守护；`app.js?v=40` |
| 23 | `static/js/app.js` | **自选批量监控表格空白（贵州茅台加入自选后不显示）**：`/api/watchlist` 返回对象数组 `[{code,name,in_watchlist},...]`，但 `loadWatchlistTable` 直接 `codes.join(",")`，把每个对象转成 `"[object Object]"`，`/api/many` 收到 100 个无效 code 返回 400，表格循环拿不到数据 → 空白（加自选动作本身成功，顶部"已加自选"正常） | 浏览器控制台 / Flask 访问日志 `GET /api/many?codes=[object Object],...` 400 暴露 | 先 `items = await r.json()` 再 `codes = items.map(x=>x.code)`，循环改用 `item.code`；`app.js?v=41` |
| 24 | `static/js/app.js` `config.py` | **自选批量监控仍空白（即便 join 已修）**：`/api/watchlist` 返回约 100 只预置池（含不在自选的），整池发给 `/api/many`，超过 `config.MAX_CODES=50` 触发 400，表格仍空白 | 日志显示 `/api/many?codes=sh600519,sz000858,...` 已为真实 code 但仍 400 | `loadWatchlistTable` 先 `items.filter(x=>x.in_watchlist)`，只对真正自选的标的（当前 4 只）拉取；空自选时显示占位提示；`app.js?v=42` |

> **E2E（真实浏览器）**：`tests/e2e_kline.js` 用 `puppeteer-core`（系统 Chrome，不下载 Chromium）加载真实页面、模拟搜索切换与周期切换，断言 `#ch4` 图表真渲染出数据点数。运行：`node tests/e2e_kline.js`（需先 `python app.py` 起服务 + `npm i puppeteer-core`）。本批次靠它在真实环境发现 #18。


> 这就是「先写测试再验证」的价值：本批次 #14 这类**运行时才暴露的回归**，正是靠 `test_many` 跑红反向定位——`py_compile` 静态编译对未定义名无能为力，运行时测试是最后一道关。

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
