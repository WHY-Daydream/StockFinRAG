from flask import Flask, request, jsonify
from flask_cors import CORS
from loguru import logger
import uuid

from config import Config
from agent.graph import get_qa_graph
from ingestion.pipeline import FinKnowledgeBuilder

app = Flask(__name__)
CORS(app)


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
    graph = get_qa_graph()

    initial_state = {
        "question": question,
        "session_id": session_id,
        "retrieved_context": [],
        "analysis_result": "",
        "final_answer": "",
        "compliance_check": "pending",
        "compliance_reason": "",
    }

    result = graph.invoke(initial_state, config={"configurable": {"thread_id": session_id}})
    return jsonify({
        "session_id": session_id,
        "question": question,
        "answer": result["final_answer"],
        "compliance": result.get("compliance_check", "pending"),
    })


@app.route("/api/ingest", methods=["POST"])
def ingest():
    try:
        data = request.get_json(force=True) or {}
        limit = data.get("limit", 10)
        builder = FinKnowledgeBuilder()
        builder.process_unprocessed_docs(limit=limit)
        return jsonify({"status": "ok", "processed": limit})
    except Exception as e:
        logger.exception("Ingest failed")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
