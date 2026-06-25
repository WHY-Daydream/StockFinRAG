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

    def ask(self, question: str, session_id: str, history: list = None) -> dict:
        """处理一个问题，返回结构化结果（三级缓存：Redis → MySQL → RAG）"""
        cache_key = f"answer:{question}"

        # ——— 第一级：Redis 缓存（最快） ———
        cached = self.cache.redis.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                logger.info(f"Answer cache hit (Redis): {question[:40]}...")
                return data
            except Exception:
                pass

        # ——— 第二级：MySQL qa_logs 历史回答（中等速度） ———
        try:
            mysql_answer = self._lookup_mysql_answer(question)
            if mysql_answer:
                logger.info(f"Answer cache hit (MySQL): {question[:40]}...")
                # 写入 Redis 加速下次访问
                self.cache.redis.setex(cache_key, 1800,
                    json.dumps(mysql_answer, ensure_ascii=False))
                return mysql_answer
        except Exception as e:
            logger.warning(f"MySQL answer lookup failed: {e}")

        # ——— 第三级：完整 RAG 管道（最慢） ———
        conversation_history = self._get_history(session_id, frontend_history=history)

        from agent.graph import get_qa_graph
        graph = get_qa_graph()
        initial_state = {
            "question": question,
            "session_id": session_id,
            "conversation_history": conversation_history,
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

        # 将本轮问答追加到 Redis 历史
        try:
            self.cache.append_to_session_history(session_id, question, result.get("final_answer", ""))
        except Exception:
            pass

        self._write_audit_log(session_id, question, result)
        return response

    def ask_stream(self, question: str, session_id: str, history: list = None):
        """SSE 流式回答生成器（Redis → MySQL → RAG）"""

        # ——— 第一级：Redis 缓存 ———
        cache_key = f"answer:{question}"
        cached = self.cache.redis.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                logger.info(f"Stream cache hit (Redis): {question[:40]}...")
                # 以 SSE 事件形式直接输出缓存的回答
                yield f"event: token\ndata: {data.get('answer','')}\n\n"
                yield "event: step\ndata: checking\n\n"
                done = json.dumps({
                    "answer": data.get("answer", ""),
                    "compliance": data.get("compliance", "pass"),
                    "compliance_reason": data.get("compliance_reason", ""),
                    "total_duration": 0,
                    "timing": {"retrieving": 0, "analyzing": 0, "checking": 0},
                    "from_cache": True,
                }, ensure_ascii=False)
                yield f"event: done\ndata: {done}\n\n"
                return
            except Exception:
                pass

        # ——— 第二级：MySQL qa_logs ———
        try:
            mysql_answer = self._lookup_mysql_answer(question)
            if mysql_answer:
                logger.info(f"Stream cache hit (MySQL): {question[:40]}...")
                self.cache.redis.setex(cache_key, 1800,
                    json.dumps(mysql_answer, ensure_ascii=False))
                yield f"event: token\ndata: {mysql_answer.get('answer','')}\n\n"
                yield "event: step\ndata: checking\n\n"
                done = json.dumps({
                    "answer": mysql_answer.get("answer", ""),
                    "compliance": mysql_answer.get("compliance", "pass"),
                    "compliance_reason": mysql_answer.get("compliance_reason", ""),
                    "total_duration": 0,
                    "timing": {"retrieving": 0, "analyzing": 0, "checking": 0},
                    "from_cache": True,
                }, ensure_ascii=False)
                yield f"event: done\ndata: {done}\n\n"
                return
        except Exception as e:
            logger.warning(f"Stream MySQL lookup failed: {e}")

        # ——— 第三级：完整 RAG 管道 ———
        yield ":connected\n\n"  # 初始事件：冲刷缓存，确保 SSE 连接已打开
        from openai import OpenAI
        from retrieval.hybrid_searcher import HybridSearcher
        from retrieval.context_enricher import ContextEnricher
        from agent.graph import compliance_node

        yield "event: step\ndata: retrieving\n\n"
        conversation_history = self._get_history(session_id, frontend_history=history)
        t_retrieving = time.time()

        # 逐步展示检索过程
        yield "event: progress\ndata: 初始化检索引擎...\n\n"
        try:
            searcher = HybridSearcher()
            yield "event: progress\ndata: 向量检索 + BM25 关键词检索...\n\n"
            results = searcher.search(question, top_k=10)
            yield f"event: progress\ndata: 已找到 {len(results)} 篇候选文档\n\n"
            enricher = ContextEnricher()
            enriched = enricher.enrich(results, window_size=2)
            yield f"event: progress\ndata: 上下文扩展完成, 共 {len(enriched)} 篇\n\n"
        except Exception as e:
            logger.warning(f"Stream retrieval failed: {e}")
            enriched = []

        t_retrieving = time.time() - t_retrieving
        yield f"event: timing\ndata: {json.dumps({'s':'retrieving','d':round(t_retrieving,1)})}\n\n"

        yield "event: step\ndata: analyzing\n\n"

        # 构建 prompt（与 graph.py analysis_node 一致）
        history_text = ""
        if conversation_history:
            lines = []
            for msg in conversation_history:
                role_label = "用户" if msg.get("role") == "user" else "助手"
                lines.append(f"{role_label}：{msg.get('content', '')}")
            history_text = "\n".join(lines)

        context_text = "\n---\n".join(
            [f"[{c['type']} | score={c.get('rerank_score', c['score']):.4f}]\n{c['content']}"
             for c in enriched]
        ) if enriched else "（未检索到相关资料）"

        prompt = f"""你是一位专业的金融分析师助手。请基于以下检索到的金融资料和对话历史，回答用户的问题。

## 对话历史
{history_text or '（无历史记录）'}

## 检索到的上下文
{context_text}

## 当前问题
{question}

## 要求
1. 优先使用上下文中的信息回答，如信息不足请明确说明
2. 回答必须基于事实，不得编造数据
3. 对于财务数据，需要注明来源和时间
4. 使用简洁清晰的语言
5. 如果当前问题可以结合历史对话理解，请综合利用上下文
"""

        full_answer = ""
        client = OpenAI(api_key=Config.DEEPSEEK_API_KEY, base_url=Config.DEEPSEEK_BASE_URL)
        t_analyzing = time.time()
        try:
            stream = client.chat.completions.create(
                model=Config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    full_answer += delta
                    safe = delta.replace("\n", "\\n").replace("\r", "\\r")
                    yield f"event: token\ndata: {safe}\n\n"
        except Exception as e:
            logger.error(f"Stream API call failed: {e}")
            err_msg = f"⚠️ 分析服务暂时不可用。错误: {str(e)}"
            yield f"event: token\ndata: {err_msg}\n\n"
            full_answer = err_msg

        t_analyzing = time.time() - t_analyzing
        yield f"event: timing\ndata: {json.dumps({'s':'analyzing','d':round(t_analyzing,1)})}\n\n"

        yield "event: step\ndata: checking\n\n"
        t_checking = time.time()
        compliance_result = {"compliance": "pass", "compliance_reason": ""}
        try:
            result = compliance_node({
                "question": question,
                "analysis_result": full_answer,
            })
            compliance_result["compliance"] = result.get("compliance_check", "reject")
            compliance_result["compliance_reason"] = result.get("compliance_reason", "")
        except Exception as e:
            logger.error(f"Compliance check failed: {e}")
        t_checking = time.time() - t_checking
        yield f"event: timing\ndata: {json.dumps({'s':'checking','d':round(t_checking,1)})}\n\n"

        total_duration = round(t_retrieving + t_analyzing + t_checking, 1)
        done_data = json.dumps({
            "answer": full_answer,
            "compliance": compliance_result["compliance"],
            "compliance_reason": compliance_result["compliance_reason"],
            "total_duration": total_duration,
            "timing": {"retrieving": round(t_retrieving,1), "analyzing": round(t_analyzing,1), "checking": round(t_checking,1)},
        }, ensure_ascii=False)
        yield f"event: done\ndata: {done_data}\n\n"

        # 写入答案缓存（让第二次问同一个问题秒回）
        try:
            cache_payload = json.dumps({
                "session_id": session_id,
                "question": question,
                "answer": full_answer,
                "compliance": compliance_result["compliance"],
                "compliance_reason": compliance_result["compliance_reason"],
            }, ensure_ascii=False)
            self.cache.redis.setex(f"answer:{question}", 1800, cache_payload)
        except Exception as e:
            logger.error(f"Stream cache write error: {e}")

        # 审计日志 + Redis 历史
        try:
            self._write_audit_log(session_id, question, {
                "final_answer": full_answer,
                "compliance_check": compliance_result["compliance"],
                "compliance_reason": compliance_result["compliance_reason"],
                "retrieved_context": enriched,
                "start_time": 0,
            })
            self.cache.append_to_session_history(session_id, question, full_answer)
        except Exception as e:
            logger.error(f"Stream audit error: {e}")

    def _get_history(self, session_id: str, frontend_history: list = None) -> list:
        """三级兜底获取对话历史"""
        # 优先级 1: 前端传的 history
        if frontend_history is not None:
            try:
                self.cache.set_session_history(session_id, frontend_history)
            except Exception:
                pass
            return _truncate_history(frontend_history)

        # 优先级 2: Redis 缓存
        try:
            redis_history = self.cache.get_session_history(session_id)
            if redis_history is not None:
                return _truncate_history(redis_history)
        except Exception:
            pass

        # 优先级 3: MySQL qa_logs 表
        try:
            mysql_history = self._load_mysql_history(session_id)
            if mysql_history:
                try:
                    self.cache.set_session_history(session_id, mysql_history)
                except Exception:
                    pass
                return _truncate_history(mysql_history)
        except Exception:
            pass

        return []

    def _load_mysql_history(self, session_id: str) -> list:
        """从 MySQL qa_logs 表加载历史"""
        from db import get_mysql
        conn = get_mysql()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT question, answer FROM qa_logs "
                    "WHERE session_id=%s ORDER BY id ASC LIMIT 6",
                    (session_id,),
                )
                rows = cur.fetchall()
                if not rows:
                    return None
                history = []
                for row in rows:
                    history.append({"role": "user", "content": row["question"]})
                    history.append({"role": "assistant", "content": row["answer"]})
                return history
        finally:
            conn.close()

    def _lookup_mysql_answer(self, question: str) -> dict:
        """从 MySQL qa_logs 查询历史回答（精确匹配）"""
        from db import get_mysql
        conn = get_mysql()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT question, answer, compliance_check, compliance_reason "
                    "FROM qa_logs WHERE question=%s ORDER BY id DESC LIMIT 1",
                    (question,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "session_id": "",
                    "question": row["question"],
                    "answer": row["answer"],
                    "compliance": row.get("compliance_check", "pass"),
                    "compliance_reason": row.get("compliance_reason") or "",
                }
        finally:
            conn.close()

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
                    try:
                        cur.execute(
                            """INSERT INTO qa_logs
                               (session_id, question, answer, retrieved_chunks, agent_trace, compliance_check, compliance_reason, latency_ms)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                            (session_id, question, result.get("final_answer", ""),
                             json.dumps([{"doc_id": c.get("doc_id"), "score": c.get("rerank_score", c.get("score"))}
                                         for c in context], ensure_ascii=False),
                             json.dumps({"retrieval_count": len(context)}),
                             result.get("compliance_check", "pending"),
                             result.get("compliance_reason", ""), latency_ms),
                        )
                    except Exception as _e:
                        if "Unknown column" in str(_e):
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
                            logger.warning("compliance_reason missing in qa_logs, run: ALTER TABLE qa_logs ADD COLUMN compliance_reason TEXT")
                        else:
                            raise
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