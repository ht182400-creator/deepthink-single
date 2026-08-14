# 个股主力追踪系统（deepthinkSingle）

盘中实时盯盘工具——**股票搜索 + 分时走势 + 五档盘口信息卡（16 项指标）+ 方向键分钟详情 + VOLFS 成交量 + 主力资金追踪 + 资金博弈副图 + 历史K线（全量）+ K线双击历史分时小图**网页版。

![主力追踪参考](docs/images/ref-main-force.png)

> 项目状态：敏捷开发 | Sprint 2 完成
> 数据源：腾讯自选股首选，东财兜底，通达信本地历史，npx 离线补全

## 项目愿景

为个人投资者提供一个**开盘期间实时刷新**的个股主力资金追踪工具，一眼看清：

1. **股票搜索/下拉**：115+ 主流标的（4 自选 + 111 预置池），输入式 datalist 模糊搜索
2. **分时价格线**（现价白线 + 均价黄线，右轴涨跌幅%）
3. **VOLFS 成交量**（每分钟柱状，按价格涨跌红/绿/灰着色）
4. **主力追踪**（主力净流入累计曲线，紫色面积图）
5. **方向键分钟详情**（↑/↓ 逐分钟切换，右侧 240 行滚动列表）
6. **历史 K线**（分时双击进入：日/周/月/60/30/15/5分，MA均线 + VOL副图）

参考同花顺 / 东方财富 / 通达信通用显示模式，网页版免安装、浏览器即开即用。

## 核心功能

| 功能 | 说明 |
|---|---|
| 股票搜索/下拉 | 115+ 主流 A 股 + ETF，输入式 datalist（代码/名称模糊），★ 标记自选 |
| 单只个股实时分时 | 逐分钟价格/均价/成交量，30s 自动刷新 |
| 主力资金追踪 | 主力净流入累计曲线（分钟级，东财数据） |
| VOLFS 量能 | 每分钟成交柱 + 按价格涨跌方向红/绿着色 |
| 五档盘口信息卡 | 卖5→卖1/现价/买1→买5 + 16 项指标（外盘/内盘/股本/净资/收益/PE 等） |
| 方向键分钟详情 | 分时视图 ↑/↓ 切换选中分钟，右侧 240 行滚动列表（时间/价格/量/额） |
| 历史 K线 | 分时双击/回车进入；日/周/月/多周期切换；MA5/10/20 + VOL |
| 本地历史数据 | **通达信 .day 直读**（0.01s，含 2001 至今全历史） |
| 分钟数据缓存 | npx 拉取后写本地 JSON（24h 有效） |
| 双数据源容灾 | 腾讯 → 东财多节点 → npx 四级降级 |

## 技术架构

```
浏览器（ECharts 黑底 + 搜索框 + 视图切换）
    │  fetch /api/quote /api/kline /api/search   每 30s
    ▼
Flask 后端（app.py，薄路由）
    │
    ├── services/          服务层（quote/kline/fund/search/cache）
    │
    ├── sources/           数据源适配器（Source 抽象 + 降级编排）
    │     ├── tencent.py      腾讯自选股（分时/报价）
    │     ├── eastmoney.py    东方财富（主力资金/多节点）
    │     ├── tdx.py          通达信本地 .day（历史日/周/月）
    │     └── npx.py          npx westock（分钟K兜底）
    │
    └── data/
          ├── kline_cache/    JSON 缓存（分钟K，24h）
          ├── watchlist.json  自选
          └── market.db       SQLite（预留）
```

## 快速开始

```bash
cd E:\AI_Studio\deepthinkSingle
python app.py
# 浏览器打开 http://localhost:5000
```

或双击 `run.bat`（自动杀旧进程 → 启动 → 开浏览器）。

## 数据源优先级

| 数据 | 优先级链 | 说明 |
|---|---|---|
| 报价/分时 | 腾讯 → 东财 | 盘中实时 |
| 主力资金 | 东财 push2 → push2delay | 腾讯公开接口无 |
| 日/周/月 K | **通达信本地 .day** → npx → 东财 | 0.01s，含全历史 |
| 分钟 K | npx → 东财 | 首次 2s，缓存后 0.01s |

> **注意**：通达信本地数据需定期"盘后数据下载"保持最新；分钟 K 首次调用会下载 westock-data-skillhub 包（5-10s）。

## 目录结构

```
E:\AI_Studio\deepthinkSingle\
├── app.py                 # Flask 入口（薄）
├── config.py              # 配置（规划中）
├── services/              # 服务层（规划中）
├── sources/               # 数据源适配器（规划中）
├── data_provider.py       # 数据层（当前单文件，待分层）
├── templates/index.html   # 单页前端
├── static/css/style.css
├── static/js/app.js       # 前端逻辑（待模块化）
├── data/                  # 运行时数据（缓存/自选）
├── logs/                  # 日志
├── docs/                  # 敏捷文档
│   ├── README.md
│   ├── architecture.md    # 架构规划
│   ├── backlog.md         # 需求池
│   ├── PRD.md             # 需求规格（EARS）
│   ├── sprint-1.md
│   └── sprint-2.md
└── run.bat                # 一键启动（先杀旧进程）
```

## API

| 端点 | 说明 |
|---|---|
| `GET /api/quote?code=` | 报价 + 分时 + 主力资金（quote 含外盘/内盘/PE/市值/市净率/量比/均价等 16+ 指标） |
| `GET /api/kline?code=&period=&limit=` | 历史/分钟 K 线（limit<=0 返回全量） |
| `GET /api/minute?code=&date=` | 历史某日分时（约 30 天，缺省当日） |
| `GET /api/search?q=` | 股票搜索 |
| `GET/POST /api/watchlist` | 自选列表（返回 watchlist + 全部预置池，含 in_watchlist 标记） |
| `GET /api/sysinfo` | 环境信息 |

## 敏捷迭代

| Sprint | 目标 | 状态 |
|---|---|---|
| Sprint 1 | 三面板 MVP + 30s 刷新 + 双源容灾 | ✅ 完成 |
| Sprint 2 | 搜索 + K线面板 + 通达信本地化 + 架构分层 + 测试体系 | ✅ 完成 |
| Sprint 3 | 自选批量表格 + 分钟资金流明细 | 待排 |
| Sprint 4 | 多日主力对比 + 异动告警 | 待排 |

## 测试

**128 个自动化测试，全部通过**（单元 + 集成，离线可跑）。

```bash
python -m unittest discover tests -v     # 全部测试
```

| 层级 | 文件 | 覆盖 |
|---|---|---|
| 单元测试 | `tests/test_circuit_breaker.py` 等 9 个 | core 稳定性组件、sources 数据源解析、services 服务层 |
| 集成测试 | `tests/test_api.py` | Flask API + 真实链路冒烟 |
| 测试文档 | `docs/testing.md` | 策略 / 用例库 / 运行方式 / Bug 记录 |

测试体系建立后已发现并修复 10 类真实问题：`pure_code` 前缀剥离、限流器 `capacity=0` 语义、通达信文件句柄泄漏、**K线缓存污染**、腾讯字段映射、分时均价 100 倍、收盘后伪数据、VOLFS 累计、VOLFS 染色、方向键详情（详见 `docs/testing.md` Bug 记录表）。

详见 `docs/`。
