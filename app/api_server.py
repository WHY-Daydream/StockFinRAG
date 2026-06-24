import os

# Set HF cache paths before any model imports
_base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "huggingface")
os.environ["HF_HOME"] = _base
os.environ["HF_HUB_CACHE"] = os.path.join(_base, "hub")
os.environ["TRANSFORMERS_CACHE"] = os.path.join(_base, "hub")
os.environ["SENTENCE_TRANSFORMERS_HOME"] = os.path.join(_base, "hub")

# 仅当 embedding 模型已缓存到本地时才启用离线模式
# 从 config.py 中读取 EMBEDDING_MODEL 避免在环境变量设置前导入
_hf_cache_dir = os.path.join(_base, "hub")
_embedding_model = None
_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
if os.path.isfile(_config_path):
    with open(_config_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            if "EMBEDDING_MODEL" in _line and "=" in _line:
                _parts = _line.split("=", 1)
                if len(_parts) == 2:
                    _val = _parts[1].strip().strip("\"'")
                    if _val:
                        _embedding_model = _val
                    break

if _embedding_model:
    _model_slug = "models--" + _embedding_model.replace("/", "--")
    _model_cached = os.path.isdir(_hf_cache_dir) and os.path.isdir(
        os.path.join(_hf_cache_dir, _model_slug, "snapshots")
    )
    if _model_cached:
        os.environ["HF_HUB_OFFLINE"] = "1"

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from loguru import logger
import uuid
import traceback, sys

from config import Config
from db import get_mysql
from service.qa_service import QAAnswerService

app = Flask(__name__)
CORS(app)

app.config["SCHEDULER_ENABLED"] = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"

# 服务层实例
qa_service = QAAnswerService()


@app.errorhandler(Exception)
def handle_all_errors(e):
    traceback.print_exc()
    logger.exception(f"Unhandled error: {e}")
    return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/", methods=["GET"])
def index():
    return render_template("base.html")


@app.route("/knowledge", methods=["GET"])
def knowledge_page():
    return render_template("base.html")


@app.route("/favicon.ico", methods=["GET"])
def favicon():
    return "", 204


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "StockFinRAG"})


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400

    session_id = data.get("session_id", str(uuid.uuid4()))

    try:
        result = qa_service.ask(question, session_id)
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        logger.exception(f"Ask failed for question: {question}")
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/ingest", methods=["POST"])
def ingest():
    try:
        data = request.get_json(force=True) or {}
        limit = data.get("limit", 10)
        count = qa_service.ingest(limit=limit)
        return jsonify({"status": "ok", "processed": count})
    except Exception as e:
        logger.exception("Ingest failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/seed", methods=["POST"])
def seed():
    try:
        data = request.get_json(force=True) or {}
        limit = data.get("limit", 50)
        result = qa_service.seed(limit=limit)
        return jsonify({
            "status": "ok",
            "imported": result["imported"],
            "vectorized": result["vectorized"],
            "message": f"导入 {result['imported']} 篇文档，向量化 {result['vectorized']} 篇",
        })
    except Exception as e:
        logger.exception("Seed import failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/documents", methods=["GET"])
def list_documents():
    """列出库中文档状态"""
    try:
        conn = get_mysql()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, doc_type, title, source, chunk_count, DATE(publish_date) as pub_date, "
                    "LEFT(summary, 100) as summary_short, created_at "
                    "FROM documents ORDER BY created_at DESC LIMIT 100"
                )
                docs = cur.fetchall()
            return jsonify({"status": "ok", "total": len(docs), "documents": docs})
        finally:
            conn.close()
    except Exception as e:
        logger.exception("List documents failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/crawl", methods=["POST"])
def crawl():
    """从配置的 URL 源抓取最新金融文档"""
    try:
        from crawler.financial_crawler import batch_crawl

        data = request.get_json(force=True) or {}
        config_path = data.get("config")  # 可选：自定义爬取配置

        doc_ids = batch_crawl(config_path)
        return jsonify({
            "status": "ok",
            "crawled": len(doc_ids),
            "doc_ids": doc_ids,
            "message": f"成功抓取 {len(doc_ids)} 篇新文档",
        })
    except Exception as e:
        logger.exception("Crawl failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/indices", methods=["GET"])
def get_indices():
    """获取最新指数行情"""
    INDICES = [
        ("000001", "上证指数"),
        ("399001", "深证成指"),
        ("399006", "创业板指"),
        ("000688", "科创50"),
    ]
    results = []
    try:
        conn = get_mysql()
        try:
            with conn.cursor() as cur:
                for code, name in INDICES:
                    cur.execute(
                        "SELECT date, close, open, high, low, volume "
                        "FROM stock_indices WHERE index_code=%s ORDER BY date DESC LIMIT 1",
                        (code,),
                    )
                    row = cur.fetchone()
                    if row:
                        results.append({
                            "code": code,
                            "name": name,
                            "close": float(row["close"]),
                            "open": float(row["open"]),
                            "high": float(row["high"]),
                            "low": float(row["low"]),
                            "volume": int(row["volume"]),
                            "date": str(row["date"]),
                        })
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to fetch indices: {e}")
    return jsonify({"indices": results})


if __name__ == "__main__":
    from scheduler import init_scheduler
    init_scheduler(app)
    app.run(host="0.0.0.0", port=5000, debug=False)
