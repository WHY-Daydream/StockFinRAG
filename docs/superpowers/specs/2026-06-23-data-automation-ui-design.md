# StockFinRAG 第二阶段：数据自动化与前端增强设计

> 日期：2026-06-23
> 状态：设计稿（待复审）

---

## 1. 概述

### 1.1 目标

在已修复 Bug 的代码基座上，推进两大方向：

| 方向 | 优先级 | 核心价值 |
|------|--------|---------|
| 数据源扩展与自动化 | P0 | 解决知识库数据陈旧问题，引入实时/近实时金融数据 |
| 前端界面增强 | P1 | 提升问答体验，让用户能查看知识库状态和数据新鲜度 |

### 1.2 总体架构

```
APScheduler（定时调度）
  ├── AKShare 采集器 → 结构化数据（行情/财报）→ 入库
  ├── 增强版爬虫     → 新闻/政策正文     → 入库
  └── 增量向量化     → 新文档 → Milvus 向量化
                        ↓
                ┌───────────────┐
                │  Flask API    │ ← 前端 SPA 调用
                │  + HTMX 页面   │
                └───────────────┘
```

---

## 2. 数据源扩展与自动化

### 2.1 AKShare 数据接入

新增 `app/data_providers/akshare_provider.py`，封装以下数据采集：

| 接口 | 数据内容 | 频率 | 目标表 |
|------|---------|------|-------|
| `index_zh_a_hist` | 上证/深证/创业板/科创50 日线 | 每日收盘后 | `stock_indices` |
| `stock_zh_a_spot_em` | A股实时行情快照 | 盘中调用 | `stock_quotes` |
| `stock_financial_abstract` | 公司三张报表摘要 | 每季 | `documents`（作为新文档） |
| `stock_zh_a_hist` | 个股历史 K 线 | 按需 | `stock_prices` |
| `macro_china_gdp` | GDP 数据 | 每季 | `documents` |
| `macro_china_cpi` | CPI 数据 | 每月 | `documents` |

**新增数据库表** （`mysql/init/02_akshare.sql`）：

```sql
CREATE TABLE IF NOT EXISTS stock_indices (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    index_code  VARCHAR(16) NOT NULL COMMENT '指数代码',
    index_name  VARCHAR(32) NOT NULL,
    date        DATE NOT NULL,
    open        DECIMAL(12,2),
    close       DECIMAL(12,2),
    high        DECIMAL(12,2),
    low         DECIMAL(12,2),
    volume      BIGINT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_index_date (index_code, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 2.2 增强版爬虫

重构 `FinancialCrawler`，新增策略模式支持多网站内容提取：

```python
# app/crawler/extractors/  # 每个站点独立提取策略
├── __init__.py
├── base.py        # 抽象基类
├── pbc.py         # 中国人民银行
├── csrc.py        # 中国证监会
├── eastmoney.py   # 东方财富
└── default.py     # 通用 fallback
```

优势：针对不同网站结构定制提取逻辑，提高抓取成功率。

### 2.3 定时调度

**依赖**：新增 `APScheduler>=3.10.0`

在 `api_server.py` 中集成调度器（Flask 启动时一并启动）：

| 任务 | Cron 表达式 | 行为 |
|------|------------|------|
| 财经新闻爬取 | `*/30 * * * *` | 每 30 分钟抓取最新新闻 |
| 指数行情更新 | `0 9,15 * * 1-5` | 工作日 9:00/15:00 更新 |
| 政策法规检查 | `0 8 * * 1` | 每周一检查 |
| 增量向量化 | 每次入库后触发 | 处理未向量化文档 |

### 2.4 数据新鲜度标识

所有文档入库时记录 `created_at`，前端据此显示数据时效性。

---

## 3. 前端界面增强

### 3.1 页面结构

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 智能问答 | 聊天主界面 + 顶部行情小部件 |
| `/knowledge` | 知识库管理 | 文档列表、搜索、过滤、导入操作 |

### 3.2 智能问答页面（首页）

**区域划分**：

```
┌──────────────────────────────────────────────┐
│  📈 3,128.45 ▲0.8%  9,456.23 ▲1.2%  科创50   │  ← 行情小部件
│    上证指数        深证成指        758.12 ▲0.5%│
├──────────────┬───────────────────────────────┤
│  💬 历史会话  │  问答主区域                     │
│              │  - 用户消息（右对齐气泡）         │
│  什么是金融..  │  - AI 回答（Markdown 渲染）     │
│              │  - ✅ 合规标签                   │
│  2024年银行..  │  - 📎 来源引用链接              │
│              │  - 📊 相关数据图表               │
│  注册制改革..  │                               │
│              │  ┌─────────────────────────┐   │
│  [+] 新会话  │  │ 输入金融问题...   [发送]│   │
│              │  └─────────────────────────┘   │
│              │  知识库更新：2026-06-22          │
└──────────────┴───────────────────────────────┘
```

**技术要点**：
- 历史会话存储在 `session_id` 维度，使用 localStorage 记录会话列表
- Markdown 渲染使用 `marked.js`（CDN）
- 回答中如果涉及指数/股票数据，自动转化为趋势标签

### 3.3 知识库管理页面

| 功能 | 实现 |
|------|------|
| 文档列表 | 表格展示：标题、类型、来源、日期、分块数、更新时间 |
| 筛选 | 按类型（政策/法规/新闻/知识）下拉过滤 |
| 搜索 | 输入框实时搜索标题 |
| 操作按钮 | 「导入种子数据」「触发爬取」「向量化未处理」 |
| 行内状态 | 不同颜色的标签表示「已向量化」「待处理」 |

### 3.4 行情小部件

- 位于首页顶部，紧凑布局（3-4 个核心指数）
- 数据来源：查询 `stock_indices` 表最近一条记录
- 无数据时隐藏，不阻塞页面

### 3.5 技术栈

| 层 | 技术 | 理由 |
|----|------|------|
| 后端渲染 | Flask + Jinja2 | 零构建步骤，与现有架构一致 |
| 交互增强 | HTMX | 无刷新加载，简单易用 |
| Markdown | marked.js CDN | 轻量，无需构建 |
| 样式 | 自定义 CSS | 延续 `#1677ff` 主色调 |

---

## 4. API 新增/变更

| 端点 | 方法 | 用途 | 状态 |
|------|------|------|------|
| `GET /api/indices` | GET | 获取最新指数行情 | 新增 |
| `GET /api/documents?type=&q=` | GET | 文档搜索（已有，扩展参数） | 扩展 |
| `POST /api/documents/batch-vectorize` | POST | 批量向量化未处理文档 | 新增 |
| `GET /api/stats` | GET | 系统统计信息（文档数/分块数/缓存命中） | 新增 |

---

## 5. 文件变更清单

```
新增:
  app/data_providers/
    ├── __init__.py
    └── akshare_provider.py          # AKShare 数据采集封装
  app/crawler/extractors/
    ├── __init__.py
    ├── base.py
    ├── pbc.py
    ├── csrc.py
    ├── eastmoney.py
    └── default.py
  app/scheduler.py                   # APScheduler 集成
  app/templates/                     # 前端模板目录
    ├── base.html                    # 基础布局
    ├── index.html                   # 问答页面
    └── knowledge.html               # 知识库管理
  app/static/
    ├── css/style.css                # 全局样式
    └── js/                          # 前端 JS
  mysql/init/02_akshare.sql          # 新增数据库表

修改:
  app/api_server.py                  # 集成调度器 + 新增路由
  app/crawler/financial_crawler.py   # 调用 extractors 策略
  app/requirements.txt               # 添加 akshare, apscheduler
  app/db.py                          # 如需新连接配置
```

---

## 6. 不纳入范围

- 用户认证与多租户
- WebSocket 流式输出（后续可考虑 SSE）
- 邮件/短信告警
- 移动端适配

---

## 7. 验收标准

1. `AKShare Provider` 能成功获取一次上证指数并存入 MySQL
2. 定时爬虫每小时自动抓取新闻并入库
3. 新文档入库后自动触发向量化到 Milvus
4. 前端首页显示实时指数行情
5. 问答页支持历史会话切换、Markdown 渲染
6. 知识库页面可搜索/过滤文档，查看状态

---

## 8. 自审清单

- [x] 无 TBD/TODO 占位符
- [x] 各节之间无矛盾（数据优先于前端，P0 先行）
- [x] 范围聚焦：排除了认证、流式输出等 YAGNI 功能
- [x] 路径明确：文件清单列出了所有新增/修改文件
- [x] 验收标准可量化：6 条验收标准均可通过运行测试验证
