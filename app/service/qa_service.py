"""服务层：封装问答和知识库操作，隔离 api_server 与下层"""
import json
import time
from loguru import logger
from config import Config
from retrieval.cache import ResultCache


def _truncate_history(history: list, max_rounds: int = 3) -> list:
    """截断历史到最近 N 轮"""
    max_messages = max_rounds * 2
    return history[-max_messages:] if len(history) > max_messages else history


class QAAnswerService:
    """问答服务：缓存检查 -> LLM 调用 -> 审计日志 -> 缓存结果"""

    def __init__(self):
        self.cache = ResultCache()

    def ask(self, question: str, session_id: str) -> dict:
        """处理一个问题，返回结构化结果"""
        cache_key = f"answer:{question}"
        cached = self.cache.redis.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                logger.info(f"Answer cache hit: {question[:50]}...")
                return data
            except Exception:
                pass

        from agent.graph import get_qa_graph
        graph = get_qa_graph()
        initial_state = {
            "question": question,
            "session_id": session_id,
            "retrieved_context": [],
            "analysis_result": "",
            "final_answer": "",
            "compliance_check": "pending",
            "compliance_reason": "",
            "start_time": time.time(),
        }
        result = graph.invoke(initial_state,
                              config={"configurable": {"thread_id": session_id}})

        response = {
            "session_id": session_id,
            "question": question,
            "answer": result["final_answer"],
            "compliance": result.get("compliance_check", "pending"),
            "compliance_reason": result.get("compliance_reason", ""),
        }

        self.cache.redis.setex(cache_key, 1800,
                               json.dumps(response, ensure_ascii=False))

        self._write_audit_log(session_id, question, result)
        return response

    def _write_audit_log(self, session_id: str, question: str, result: dict):
        """写入审计日志到 MySQL（由服务层负责，LLM 层不再直接写库）"""
        from db import get_mysql
        try:
            latency_ms = 0
            if result.get("start_time"):
                latency_ms = int((time.time() - result["start_time"]) * 1000)
            context = result.get("retrieved_context", [])
            conn = get_mysql()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO qa_logs
                           (session_id, question, answer, retrieved_chunks, agent_trace, compliance_check, latency_ms)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (session_id, question, result.get("final_answer", ""),
                         json.dumps([{"doc_id": c.get("doc_id"), "score": c.get("rerank_score", c.get("score"))}
                                     for c in context], ensure_ascii=False),
                         json.dumps({"retrieval_count": len(context)}),
                         result.get("compliance_check", "pending"), latency_ms),
                    )
                    conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Audit log error: {e}")

    def ingest(self, limit: int = 10) -> int:
        """向量化未处理文档"""
        from ingestion.pipeline import FinKnowledgeBuilder
        builder = FinKnowledgeBuilder()
        return builder.process_unprocessed_docs(limit=limit)

    def seed(self, limit: int = 50) -> dict:
        """导入种子数据并向量化"""
        from ingestion.seed_data import load_seed_docs, import_to_mysql
        docs = load_seed_docs()
        imported = import_to_mysql(docs)
        processed = self.ingest(limit=limit)
        return {"imported": imported, "vectorized": processed}