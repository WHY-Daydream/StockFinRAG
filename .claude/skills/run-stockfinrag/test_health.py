"""Minimal Flask server mimicking StockFinRAG's /api/health for smoke tests.

Used by the smoke-test driver when Docker infrastructure is unavailable.
"""
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "StockFinRAG"})

@app.route("/api/ask", methods=["POST"])
def ask():
    return jsonify({
        "session_id": "test-session",
        "question": "模拟问题",
        "answer": "模拟回答（需要 Docker + DeepSeek API）",
        "compliance": "pass",
    })

@app.route("/api/ingest", methods=["POST"])
def ingest():
    return jsonify({"status": "ok", "processed": 0})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
