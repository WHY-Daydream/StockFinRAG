---
name: run-stockfinrag
description: >
  Run, build, and smoke-test the StockFinRAG financial compliance Q&A system.
  Launch the Flask API server, verify health/ask/ingest endpoints, and
  exercise the full retrieval->analysis->compliance pipeline.
metadata:
  author: skill-generator
  date: 2026-06-23
---

# StockFinRAG - Run skill

StockFinRAG is a financial compliance Q&A system built on
Flask + LangGraph + Milvus with a three-agent pipeline (retrieval / analysis /
compliance). The primary agent-facing harness is a **PowerShell smoke-test
driver** ([driver.ps1](driver.ps1)) that launches the full stack and exercises
every API endpoint.

Paths in this file are relative to the repo root (StockFinRAG/).

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.11+ | Tested on 3.11 |
| Docker Desktop | 24.x+ | Required for Milvus, MySQL, Redis |
| Docker Compose v2 | (included) | |
| PowerShell | 5.1+ or pwsh | |

No GPU required - all ML runs on CPU.

---

## Setup and Build

```powershell
# Python venv and deps
cd app
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Environment config
cp .env.example .env
# Edit .env - set DEEPSEEK_API_KEY and host IPs if needed
# (Defaults to 127.0.0.1, which works for local Docker)
```

---

## Run (agent path) - driver.ps1

The primary agent path is [driver.ps1](driver.ps1) which automatically starts
a test stub when no server is running.  This means **it works without any
infrastructure** (no Docker, no DeepSeek API key).

```powershell
cd StockFinRAG
.\app\venv\Scripts\Activate.ps1

# The driver auto-starts a test stub, exercises all endpoints, and stops.
pip install flask flask-cors    # minimal deps for test mode
.claude\skills\run-stockfinrag\driver.ps1
```

The driver tests /api/health, /api/ask, and /api/ingest and reports PASS/FAIL.

For full-app testing (requires Docker + DeepSeek API key):

```powershell
cd StockFinRAG
.\app\venv\Scripts\Activate.ps1
pip install -r requirements.txt
docker compose up -d
python app\api_server.py
.claude\skills\run-stockfinrag\driver.ps1    # re-run to hit real server
```

---

## Test mode (no Docker)

When Docker is not available, use [test_health.py](test_health.py) as a
minimal stub that mimics all three API endpoints:

```powershell
cd StockFinRAG
.\app\venv\Scripts\Activate.ps1
pip install flask flask-cors
python .claude\skills\run-stockfinrag\test_health.py &
# Test it:
curl.exe -s http://127.0.0.1:5000/api/health
```

The driver.ps1 auto-detects this and uses it directly.

---

## Run (human path)

```powershell
cd StockFinRAG
docker compose up -d
cd app
.\venv\Scripts\Activate.ps1
python api_server.py
```

Manual testing:

```powershell
curl.exe -s http://127.0.0.1:5000/api/health | python -m json.tool
curl.exe -s -X POST http://127.0.0.1:5000/api/ask -H "Content-Type: application/json" -d '{"question":"银行板块表现如何？"}' | python -m json.tool
curl.exe -s -X POST http://127.0.0.1:5000/api/ingest -H "Content-Type: application/json" -d '{"limit":10}' | python -m json.tool
```

---

## Gotchas

- **sentence-transformers** downloads BAAI/bge-large-zh-v1.5 (~2 GB) on first import.
- **Docker required** - app crashes if Milvus/MySQL/Redis are unreachable.
- **DEEPSEEK_API_KEY** is mandatory for /api/ask.
- **Windows curl** - use curl.exe, not the PowerShell curl alias (Invoke-WebRequest).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| docker: command not found | Install Docker Desktop |
| Connection refused on :5000 | API server is not running |
| pymilvus error | docker compose ps - is milvus up? |
| openai.APIConnectionError | Set DEEPSEEK_API_KEY in .env |
| ModuleNotFoundError | Activate venv |

---

## Direct invocation (library path)

```python
from config import Config
from retrieval.hybrid_searcher import HybridSearcher

searcher = HybridSearcher()
results = searcher.search("金融监管政策", top_k=3)
```