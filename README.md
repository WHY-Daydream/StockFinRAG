# StockFinRAG 金融合规问答系统 — 部署文档

> 面向个人投资者与金融从业者的智能投教问答系统，基于 RAG + 多 Agent 架构，实现数据采集、知识库构建、混合检索、LLM 推理到合规风控的全链路闭环。

---

## 目录

- [1. 系统架构](#1-系统架构)
- [2. 环境要求](#2-环境要求)
- [3. 快速启动](#3-快速启动)
- [4. 虚拟机环境搭建](#4-虚拟机环境搭建)
- [5. 基础设施部署（Docker）](#5-基础设施部署docker)
- [6. Python 环境与配置](#6-python-环境与配置)
- [7. 数据采集](#7-数据采集)
- [8. 知识库构建](#8-知识库构建)
- [9. 启动 API 服务](#9-启动-api-服务)
- [10. 验证与测试](#10-验证与测试)
- [11. 项目文件结构](#11-项目文件结构)
- [12. 常见问题](#12-常见问题)

---

## 1. 系统架构

```
┌────────────────────────────────────────────────────────────┐
│                        宿主机                               │
│  ┌──────────┐  ┌──────────┐  ┌─────────────────────────┐  │
│  │ Flask    │  │ LangGraph│  │ DeepSeek V4 Flash       │  │
│  │ API      │─▶│ Agent    │─▶│ (外部 API)              │  │
│  │ :5000    │  │ 编排     │  │                         │  │
│  └──────────┘  └──────────┘  └─────────────────────────┘  │
│       │                                                   │
└───────┼───────────────────────────────────────────────────┘
        │ 网络 (桥接)
┌───────┼───────────────────────────────────────────────────┐
│  ┌────┴──────────────────────────────────────────────┐   │
│  │              虚拟机 (Ubuntu 22.04)                 │   │
│  │                                                    │   │
│  │  ┌──────────┐  ┌──────────┐  ┌─────────────────┐  │   │
│  │  │  Milvus  │  │  MySQL   │  │     Redis       │  │   │
│  │  │  2.4.17  │  │   8.0    │  │     7.x         │  │   │
│  │  │  :19530  │  │   :3306  │  │     :6379       │  │   │
│  │  └──────────┘  └──────────┘  └─────────────────┘  │   │
│  │                                                    │   │
│  │  ┌──────────────────────────────────────────────┐  │   │
│  │  │  数据采集流水线 (BeautifulSoup)               │  │   │
│  │  │  → 清洗 → 去重 → 存入 MySQL                   │  │   │
│  │  └──────────────────────────────────────────────┘  │   │
│  │                                                    │   │
│  │  ┌──────────────────────────────────────────────┐  │   │
│  │  │  知识库构建 (父子 Chunk + BGE Embedding)      │  │   │
│  │  │  → Parent 1024 / Child 256 → Milvus 向量库   │  │   │
│  │  └──────────────────────────────────────────────┘  │   │
│  └────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

### 核心流程

```
用户提问
   │
   ▼
┌─────────────────────┐
│ ① 检索 Agent        │
│  · Redis 缓存命中?   │──命中──▶ 直接返回缓存结果
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
│  · 基于上下文回答   │
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

## 2. 环境要求

| 组件 | 要求 |
|------|------|
| 宿主机 OS | macOS / Linux / Windows (需网络连通 VM) |
| 虚拟机 | Ubuntu Server 22.04 LTS |
| VM CPU | ≥ 4 核 |
| VM 内存 | ≥ 8 GB（推荐 16 GB） |
| VM 磁盘 | ≥ 80 GB |
| VM 网络 | 桥接模式（固定 IP） |
| Docker | 24.x + Docker Compose v2 |
| Python | 3.11 |
| DeepSeek API | 有效的 API Key |

---

## 3. 快速启动

如果你已经有一台 Ubuntu 虚拟机，5 条命令启动：

```bash
# 1. 进入项目目录
cd StockFinRAG

# 2. 启动数据库
docker compose up -d

# 3. 安装 Python 依赖
cd app && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 和 VM 实际 IP

# 5. 启动服务
python api_server.py
```

---

## 4. 虚拟机环境搭建

### 4.1 创建虚拟机

下载 Ubuntu Server 22.04 LTS ISO，用 VMware / VirtualBox / UTM 创建虚拟机：

| 配置项 | 值 |
|--------|-----|
| 操作系统 | Ubuntu Server 22.04 LTS |
| CPU | 4 核 |
| 内存 | 8 GB（推荐 16 GB） |
| 磁盘 | 80 GB |
| 网络 | 桥接模式 |

### 4.2 安装基础软件

```bash
# 系统更新
sudo apt update && sudo apt upgrade -y

# 安装 Docker
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable docker && sudo systemctl start docker
sudo usermod -aG docker $USER

# 安装 Python 和 Git
sudo apt install -y git curl python3-pip
```

退出当前 SSH 会话重新登录，使 docker 组生效。

### 4.3 确认 IP 地址

```bash
ip addr show
# 记录桥接网卡的 IP，例如 192.168.1.100
```

### 4.4 将项目文件传输到 VM

```bash
# 从宿主机 scp 到 VM
scp -r /path/to/StockFinRAG/ user@192.168.1.100:~/StockFinRAG/
```

---

## 5. 基础设施部署（Docker）

### 5.1 目录结构

```
StockFinRAG/
├── docker-compose.yml       # 容器编排
├── milvus/                  # Milvus 数据持久化
│   ├── etcd/
│   ├── minio/
│   └── data/
├── mysql/
│   ├── init/
│   │   └── 01_schema.sql   # 建表 DDL
│   └── data/                # MySQL 数据持久化
└── redis/
    └── data/                # Redis 数据持久化
```

### 5.2 docker-compose.yml

```yaml
version: "3.8"

services:
  etcd:
    image: quay.io/coreos/etcd:v3.5.16
    container_name: milvus-etcd
    environment:
      - ETCD_AUTO_COMPACTION_MODE=revision
      - ETCD_AUTO_COMPACTION_RETENTION=1000
      - ETCD_QUOTA_BACKEND_BYTES=4294967296
    volumes:
      - ./milvus/etcd:/etcd
    command: etcd --data-dir=/etcd
    networks:
      - finrag-net

  minio:
    image: minio/minio:latest
    container_name: milvus-minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - ./milvus/minio:/data
    command: minio server /data --console-address ":9001"
    networks:
      - finrag-net

  milvus:
    image: milvusdb/milvus:v2.4.17
    container_name: milvus-standalone
    ports:
      - "19530:19530"
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
    volumes:
      - ./milvus/data:/var/lib/milvus
    depends_on:
      - etcd
      - minio
    networks:
      - finrag-net

  mysql:
    image: mysql:8.0
    container_name: finrag-mysql
    ports:
      - "3306:3306"
    environment:
      MYSQL_ROOT_PASSWORD: StockFinRAG@2025
      MYSQL_DATABASE: stock_finrag
      MYSQL_CHARACTER_SET_SERVER: utf8mb4
    volumes:
      - ./mysql/data:/var/lib/mysql
      - ./mysql/init:/docker-entrypoint-initdb.d
    command: >
      --character-set-server=utf8mb4
      --collation-server=utf8mb4_unicode_ci
      --max_connections=500
    networks:
      - finrag-net

  redis:
    image: redis:7-alpine
    container_name: finrag-redis
    ports:
      - "6379:6379"
    volumes:
      - ./redis/data:/data
    command: redis-server --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru
    networks:
      - finrag-net

networks:
  finrag-net:
    driver: bridge
```

### 5.3 MySQL 表结构

三张表：

| 表名 | 用途 | 核心字段 |
|------|------|---------|
| `documents` | 文档元数据 | doc_type, title, source, file_hash, chunk_count |
| `chunks` | Chunk 元数据 | doc_id, chunk_type(parent/child), milvus_id, content |
| `qa_logs` | 问答审计日志 | session_id, question, answer, compliance_check |

详见 `mysql/init/01_schema.sql`。

### 5.4 启动

```bash
cd ~/StockFinRAG
docker compose up -d

# 验证
docker compose ps
mysql -h 127.0.0.1 -P 3306 -u root -pStockFinRAG@2025 stock_finrag -e "SHOW TABLES;"
redis-cli -h 127.0.0.1 -p 6379 PING
```

---

## 6. Python 环境与配置

### 6.1 安装依赖

```bash
cd ~/StockFinRAG/app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 6.2 配置环境变量

```bash
cp .env.example .env
vim .env
```

修改以下关键项：

```ini
MILVUS_HOST=192.168.1.100       # VM 实际 IP
MYSQL_HOST=192.168.1.100
REDIS_HOST=192.168.1.100
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx  # 你的 DeepSeek API Key
```

### 6.3 验证连接

```bash
cd ~/StockFinRAG/app && source venv/bin/activate
python -c "
from config import Config
from db import get_mysql, get_redis
from milvus_client import connect_milvus

conn = get_mysql()
with conn.cursor() as cur:
    cur.execute('SELECT 1')
    print('MySQL OK:', cur.fetchone())
conn.close()

r = get_redis()
print('Redis OK:', r.ping())

connect_milvus()
print('Milvus OK')
"
```

---

## 7. 数据采集

### 7.1 配置采集来源

编辑 `app/crawler/crawl_sources.json`：

```json
[
    {
        "url": "https://www.gov.cn/zhengce/content/202501/content_6999999.htm",
        "type": "政策",
        "title": "关于加强监管防范风险推动资本市场高质量发展的若干意见"
    },
    {
        "url": "http://www.cninfo.com.cn/new/disclosure/stock?stockCode=000001",
        "type": "财报",
        "title": "平安银行2024年年报"
    }
]
```

### 7.2 运行采集

```bash
cd ~/StockFinRAG/app && source venv/bin/activate
python -c "
from crawler.financial_crawler import batch_crawl
batch_crawl('crawler/crawl_sources.json')
"
```

采集器特性：
- HTML 清洗（去除 script/style/nav/footer）
- MD5 去重（重复 URL 不会重复入库）
- 1 秒请求间隔（礼貌爬取）

---

## 8. 知识库构建

### 8.1 父子分块策略

```
原始文档 (财报/研报全文)
        │
        ▼
Parent Chunks (1024 token, overlap 128)
   ├── Child Chunk 1 (256 token)
   ├── Child Chunk 2 (256 token)
   └── Child Chunk 3 (256 token)
        │
        ▼
BGE-large-zh-v1.5 (1024维) 向量化
        │
        ▼
Milvus 双集合存储
  ├── finrag_chunk_parent (Parent)
  └── finrag_chunk_child  (Child)
```

### 8.2 运行构建

```bash
cd ~/StockFinRAG/app && source venv/bin/activate
python -c "
from ingestion.pipeline import FinKnowledgeBuilder
builder = FinKnowledgeBuilder()
builder.process_unprocessed_docs(limit=100)
"
```

### 8.3 验证

```bash
python -c "
from pymilvus import Collection, utility
from config import Config
from milvus_client import connect_milvus
connect_milvus()
for name in ['finrag_chunk_parent', 'finrag_chunk_child']:
    if utility.has_collection(name):
        col = Collection(name)
        col.load()
        print(f'{name}: {col.num_entities} entities')
"
```

---

## 9. 启动 API 服务

### 9.1 启动

```bash
cd ~/StockFinRAG/app && source venv/bin/activate
python api_server.py
# 监听 0.0.0.0:5000
```

生产环境推荐用 gunicorn：

```bash
gunicorn -w 4 -b 0.0.0.0:5000 api_server:app
```

### 9.2 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/ask` | 问答 |
| POST | `/api/ingest` | 触发知识库增量构建 |

#### POST /api/ask

```json
// Request
{
    "question": "2024年银行板块表现如何？",
    "session_id": "可选，不传自动生成"
}

// Response
{
    "session_id": "uuid",
    "question": "2024年银行板块表现如何？",
    "answer": "根据检索到的研报资料，2024年银行板块...",
    "compliance": "pass"
}
```

#### POST /api/ingest

```json
// Request
{
    "limit": 50
}

// Response
{
    "status": "ok",
    "processed": 50
}
```

---

## 10. 验证与测试

### 10.1 端到端测试

```bash
# 健康检查
curl -s http://127.0.0.1:5000/api/health | python -m json.tool
# → {"status": "ok", "service": "StockFinRAG"}

# 问答测试
curl -s -X POST http://127.0.0.1:5000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "金融监管政策有哪些新变化？"}' | python -m json.tool

# 知识库构建
curl -s -X POST http://127.0.0.1:5000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"limit": 50}' | python -m json.tool
```

### 10.2 审计日志查询

```bash
mysql -h 127.0.0.1 -u root -pStockFinRAG@2025 stock_finrag -e \
  "SELECT id, session_id, left(question, 50) as q, compliance_check, created_at FROM qa_logs ORDER BY id DESC LIMIT 5;"
```

### 10.3 缓存验证

```bash
redis-cli -h 127.0.0.1 keys 'finrag:q:*'
# 第一次提问后应有缓存 key
```

---

## 11. 项目文件结构

```
StockFinRAG/
├── docker-compose.yml                   # Docker Compose 编排文件
├── mysql/
│   └── init/
│       └── 01_schema.sql                # MySQL 建表 DDL
├── milvus/                              # Milvus 数据目录（自动创建）
├── redis/                               # Redis 数据目录（自动创建）
├── app/
│   ├── .env                             # 环境变量（从 .env.example 复制）
│   ├── .env.example                     # 环境变量模板
│   ├── requirements.txt                 # Python 依赖列表
│   ├── config.py                        # 统一配置（所有连接参数）
│   ├── db.py                            # MySQL + Redis 连接池
│   ├── milvus_client.py                 # Milvus 连接 + 集合管理
│   ├── __init__.py
│   ├── crawler/
│   │   ├── __init__.py
│   │   ├── financial_crawler.py         # 多源金融数据采集器
│   │   └── crawl_sources.json           # 采集来源配置
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── pipeline.py                  # 知识库构建流水线
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── hybrid_searcher.py           # 混合检索 + Rerank
│   │   └── cache.py                     # Redis 缓存
│   ├── agent/
│   │   ├── __init__.py
│   │   └── graph.py                     # LangGraph 多 Agent 编排
│   └── api_server.py                    # Flask API 服务入口
└── 实施方案.md                          # 前期方案文档
```

### 模块职责

| 文件 | 职责 |
|------|------|
| `config.py` | 统一配置入口，所有连接参数 |
| `db.py` | MySQL 连接池 + Redis 连接 |
| `milvus_client.py` | Milvus 连接、集合创建/管理 |
| `crawler/financial_crawler.py` | 多源网页数据采集、清洗、去重 |
| `ingestion/pipeline.py` | 父子分块、向量化、Milvus 入库 |
| `retrieval/hybrid_searcher.py` | Child 向量检索 → Parent 补全 → Rerank |
| `retrieval/cache.py` | Redis 缓存高频问题 |
| `agent/graph.py` | 检索→分析→合规 三 Agent LangGraph 编排 |
| `api_server.py` | Flask API（ask/ingest/health） |

---

## 12. 常见问题

### Q: Milvus 启动报错？

确保 etcd 和 minio 先启动（docker-compose 已处理 depends_on）。首次启动需拉取镜像，耗时约 2-5 分钟。

### Q: 向量化很慢？

`BAAI/bge-large-zh-v1.5` 首次运行会下载模型（~2GB）。建议在构建知识库前先预热：

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('BAAI/bge-large-zh-v1.5')
model.encode(['预热'])
```

### Q: 如何添加更多数据源？

编辑 `crawler/crawl_sources.json` 添加新的 URL，然后调用 `/api/ingest` 或运行 `pipeline.py`。

### Q: DeepSeek API 连不上？

确认 `.env` 中的 `DEEPSEEK_API_KEY` 正确，网络能访问 `api.deepseek.com`。可用 curl 测试：

```bash
curl https://api.deepseek.com/v1/models \
  -H "Authorization: Bearer sk-xxxx"
```

### Q: 如何切换 Embedding 模型？

修改 `config.py` 中的 `EMBEDDING_MODEL` 和 `EMBEDDING_DIM`，然后重建所有集合和索引（`milvus_client.py` 中 drop + recreate）。

### Q: 容器数据持久化在哪里？

所有数据在 `milvus/`、`mysql/data/`、`redis/data/` 目录下。删除容器不会丢数据。如需重置，直接删除这些目录重新 `docker compose up -d`。

---

> 文档版本: v1.0 · 最后更新: 2026-06-23
