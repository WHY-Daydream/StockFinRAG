# StockFinRAG 金融合规问答系统

> 面向个人投资者与金融从业者的智能投教问答系统。基于 **RAG + 多 Agent** 架构，实现数据采集、知识库构建、混合检索、LLM 推理到合规风控的全链路闭环。

---

## 功能特性

| 功能 | 说明 |
|------|------|
| 💬 **智能问答** | 基于 LangGraph 多 Agent 编排，自动检索→分析→合规审核 |
| 📚 **知识库管理** | 文档搜索、过滤、状态查看，一键导入种子数据 |
| 📈 **指数行情** | 实时展示上证/深证/创业板/科创50 指数 |
| 🤖 **多 Agent 流程** | 检索 Agent → 分析 Agent → 合规 Agent，层层把关 |
| 📡 **定时数据更新** | APScheduler 自动爬取新闻（每30分钟）和更新行情（每日） |
| 🔍 **混合检索** | 向量检索 + BM25 + BGE Rerank 三级召回 |
| ✅ **合规审核** | LLM 自动检查投资建议、绝对化表述、内幕信息等风险 |

---

## 快速启动

```bash
# 1. 启动基础设施（Docker）
docker compose up -d

# 2. 安装依赖
cd app && pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env：填入 DEEPSEEK_API_KEY 和数据库 IP

# 4. 导入种子数据
curl -X POST http://127.0.0.1:5000/api/seed

# 5. 打开浏览器
# 访问 http://127.0.0.1:5000
```

---

## 系统架构

```
                   宿主机
┌──────────────────────────────────────────────────────────────┐
│  Flask API (:5000)  ←  Web UI（问答/知识库/行情）            │
│       │                                                       │
│       ▼                                                       │
│  LangGraph Agent 编排                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐               │
│  │ ① 检索   │→│ ② 分析   │→│ ③ 合规审核   │               │
│  │ Agent    │  │ Agent    │  │ Agent        │               │
│  └──────────┘  └──────────┘  └──────────────┘               │
│       │              │              │                         │
│       ▼              ▼              ▼                         │
│  Redis 缓存    DeepSeek V4    审计日志 (MySQL)                │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  APScheduler 定时调度                                    │  │
│  │  ├── 每30分钟 → 财经新闻爬虫                              │  │
│  │  ├── 每日 9:00/15:00 → AKShare 指数行情更新              │  │
│  │  └── 每周一 8:00 → 政策法规检查                           │  │
│  └─────────────────────────────────────────────────────────┘  │
└──────────┬───────────────────────────────────────────────────┘
           │ 网络（桥接）
           ▼
┌──────────────────────────────────────────────────────────────┐
│              虚拟机（Ubuntu 22.04 / Docker）                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │ Milvus   │  │  MySQL   │  │  Redis   │                   │
│  │ 2.4.17   │  │   8.0    │  │   7.x    │                   │
│  │ :19530   │  │   :3306  │  │   :6379  │                   │
│  └──────────┘  └──────────┘  └──────────┘                   │
└──────────────────────────────────────────────────────────────┘
```

### 核心流程

```
用户提问
   │
   ▼
┌─────────────────────┐
│ ① 检索 Agent        │
│  · Redis 缓存命中?   │──命中──▶ 直接返回
│  · Hybrid Search:   │
│    - 向量检索 Child  │
│    - 映射 Parent    │
│    - BGE Rerank    │
└─────────┬───────────┘
          │ 上下文
          ▼
┌─────────────────────┐
│ ② 分析 Agent        │
│  · DeepSeek V4      │
│  · 上下文为空?      │──空──▶ 友好提示
│  · 基于事实回答     │
└─────────┬───────────┘
          │ 回答草案
          ▼
┌─────────────────────┐
│ ③ 合规 Agent        │
│  · 检查投资建议     │
│  · 检查绝对化表述   │
│  · 检查内幕信息     │
│                      │
│  通过? ──否──▶ 拦截 + 提示
│   │
│  是
│   ▼
│  ④ 审计日志写入     │
│  ⑤ 返回最终回答     │
└─────────────────────┘
```

---

## 页面截图

| 页面 | 路由 | 功能 |
|------|------|------|
| 💬 智能问答 | `/` | 聊天主界面、历史会话、Markdown 渲染、合规标签 |
| 📚 知识库管理 | `/knowledge` | 文档搜索/过滤、导入种子数据、触发爬取/向量化 |

首页顶部显示四大指数实时行情（上证/深证/创业板/科创50）。

---

## 数据源

| 类型 | 来源 | 更新方式 |
|------|------|---------|
| 📰 **财经新闻** | BeautifulSoup 爬虫（东方财富、央行官网等） | APScheduler 每 30 分钟 |
| 📋 **政策法规** | 爬虫（证监会、上交所、深交所） | 每周一 8:00 |
| 📈 **指数行情** | AKShare 开源金融数据库 | 工作日 9:00 / 15:00 |
| 📑 **种子知识** | 内置 JSON（证券法、财务指标、风险管理等） | 手动调用 `/api/seed` |

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 智能问答页面 |
| GET | `/knowledge` | 知识库管理页面 |
| GET | `/api/health` | 健康检查 |
| POST | `/api/ask` | 提交问题 |
| POST | `/api/ingest` | 向量化未处理文档 |
| POST | `/api/seed` | 导入种子数据 |
| POST | `/api/crawl` | 触发爬虫 |
| GET | `/api/documents` | 列出知识库文档 |
| GET | `/api/indices` | 获取最新指数行情 |

### POST /api/ask

```json
// Request
{"question": "2024年银行板块表现如何？"}

// Response
{
    "session_id": "uuid",
    "question": "2024年银行板块表现如何？",
    "answer": "根据检索到的资料，2024年银行板块...",
    "compliance": "pass"
}
```

---

## 项目结构

```
StockFinRAG/
├── docker-compose.yml              # Docker 编排
├── mysql/
│   └── init/
│       ├── 01_schema.sql           # 文档/Chunk/审计表
│       └── 02_akshare.sql          # 指数行情表
├── app/
│   ├── api_server.py               # Flask 入口（页面 + API）
│   ├── config.py                   # 统一配置
│   ├── db.py                       # MySQL + Redis 连接池
│   ├── milvus_client.py            # Milvus 向量库客户端
│   ├── scheduler.py                # APScheduler 定时任务
│   ├── data_providers/
│   │   └── akshare_provider.py     # AKShare 数据采集封装
│   ├── templates/
│   │   ├── base.html               # 基础布局
│   │   ├── index.html              # 问答页面
│   │   └── knowledge.html          # 知识库页面
│   ├── static/
│   │   ├── css/style.css           # 全局样式
│   │   └── js/
│   │       ├── chat.js             # 问答交互
│   │       └── knowledge.js        # 知识库交互
│   ├── agent/
│   │   └── graph.py                # LangGraph 多 Agent 编排
│   ├── crawler/
│   │   ├── financial_crawler.py    # 多源金融数据采集器
│   │   └── crawl_sources.json      # 爬取源配置
│   ├── ingestion/
│   │   ├── pipeline.py             # 父子分块 + 向量化入库
│   │   └── seed_data.py            # 种子数据导入
│   ├── retrieval/
│   │   ├── hybrid_searcher.py      # 混合检索 + Rerank
│   │   └── cache.py                # Redis 缓存
│   ├── tests/                      # 单元测试
│   ├── data/seed_financial_docs.json  # 种子知识数据
│   └── requirements.txt            # Python 依赖
└── 实施方案.md                     # 详细部署文档
```

---

## 环境要求

| 组件 | 要求 |
|------|------|
| 宿主机 OS | macOS / Linux / Windows |
| 虚拟机 | Ubuntu Server 22.04 LTS |
| Docker | 24.x + Docker Compose v2 |
| Python | 3.11 |
| DeepSeek API | 有效的 API Key |

---

## 完整部署

详细部署文档请参考 [`实施方案.md`](实施方案.md)，包含：
- 虚拟机搭建步骤
- Docker 服务启动
- Python 环境配置
- 数据采集与知识库构建
- 生产环境部署（gunicorn）

---

## 运行测试

```bash
cd app
pip install pytest
python -m pytest tests/ -v
```

测试覆盖：导入验证、异常处理、路径解析、Milvus 查询语法、空上下文处理、审计日志字段。

---

## 技术栈

| 层 | 技术 |
|------|------|
| 后端框架 | Flask + Flask-CORS |
| Agent 编排 | LangGraph |
| 向量数据库 | Milvus 2.4.17 |
| 结构化存储 | MySQL 8.0 |
| 缓存 | Redis 7.x |
| LLM | DeepSeek V4 Flash |
| 文本嵌入 | shibing624/text2vec-base-chinese (768维) |
| 重排序 | BAAI/bge-reranker-v2-m3 |
| 前端 | Jinja2 + HTMX + marked.js |
| 数据采集 | AKShare + BeautifulSoup |
| 定时调度 | APScheduler |
| 测试 | pytest |

---

> **文档版本**: v2.0 · 最后更新: 2026-06-23