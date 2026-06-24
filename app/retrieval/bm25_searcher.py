"""
BM25Searcher — BM25 关键词检索引擎

从 MySQL chunks 表读取文本 → jieba 分词 → BM25Okapi 建索引 → 检索。
与 Milvus 向量检索并列，供上层 hybrid_searcher 调用。

Usage:
    searcher = BM25Searcher()
    searcher.build_from_chunks()   # 从 MySQL 构建索引
    results = searcher.search("营业收入增长", top_k=10)
    searcher.save()                # 持久化到 models/bm25_index.pkl
    searcher.load()                # 从磁盘恢复
"""

import os
import pickle
from typing import List, Dict, Optional

import jieba
from rank_bm25 import BM25Okapi
from loguru import logger

# 路径计算：不使用 Config.PROJECT_ROOT（尚未定义）
# bm25_searcher.py 位于 app/retrieval/，往上一级到 app/，再往上一级到 project root
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_INDEX_PATH = os.path.join(_BASE_DIR, "models", "bm25_index.pkl")


class BM25Searcher:
    """BM25 关键词检索器"""

    def __init__(self, index_path: Optional[str] = None):
        """
        Args:
            index_path: 索引文件路径，默认为 models/bm25_index.pkl
        """
        self.index_path = index_path or _DEFAULT_INDEX_PATH
        self.bm25: Optional[BM25Okapi] = None
        self.metadata: List[Dict] = []   # 每条对应一个 chunk
        self.corpus: List[List[str]] = []  # 每个 chunk 的分词结果

    # ------------------------------------------------------------------
    # 索引构建
    # ------------------------------------------------------------------

    def build_from_chunks(self) -> None:
        """从 MySQL chunks 表读取所有 chunk -> jieba 分词 -> 构建 BM25Okapi"""
        from db import get_mysql

        conn = get_mysql()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT c.doc_id, c.id AS chunk_id, c.chunk_type,
                              c.content, d.doc_type
                       FROM chunks c
                       JOIN documents d ON c.doc_id = d.id
                       ORDER BY c.doc_id, c.chunk_index"""
                )
                rows = cur.fetchall()

            if not rows:
                logger.warning("No chunks found in MySQL, BM25 index is empty")
                self.bm25 = BM25Okapi([])
                self.metadata = []
                self.corpus = []
                return

            self.metadata = []
            self.corpus = []

            for row in rows:
                content = row["content"] or ""
                tokens = list(jieba.cut(content))
                self.corpus.append(tokens)
                self.metadata.append({
                    "doc_id": row["doc_id"],
                    "chunk_id": row["chunk_id"],
                    "type": row["chunk_type"],
                    "content": content,
                })

            self.bm25 = BM25Okapi(self.corpus)
            logger.info(
                "Built BM25 index with {} chunks from MySQL",
                len(self.metadata),
            )
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """对 query 分词 -> BM25 检索 -> 返回 top_k 结果

        结果 dict 字段: doc_id, chunk_id, type, content, score, rerank_score
        """
        if self.bm25 is None:
            logger.warning("BM25 index not built yet, returning empty results")
            return []

        if not query or not query.strip():
            return []

        query_tokens = list(jieba.cut(query))
        scores = self.bm25.get_scores(query_tokens)

        # 按 BM25 得分降序取 top_k
        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:top_k]

        results = []
        for idx in top_indices:
            result = dict(self.metadata[idx])
            result["score"] = float(scores[idx])
            result["rerank_score"] = 0.0
            results.append(result)

        return results

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def save(self) -> None:
        """pickle 序列化到 index_path"""
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        data = {
            "bm25": self.bm25,
            "metadata": self.metadata,
            "corpus": self.corpus,
        }
        with open(self.index_path, "wb") as f:
            pickle.dump(data, f)
        logger.info("BM25 index saved to {}", self.index_path)

    def load(self) -> bool:
        """从磁盘加载索引，成功返回 True"""
        if not os.path.exists(self.index_path):
            logger.warning("BM25 index file not found: {}", self.index_path)
            return False
        try:
            with open(self.index_path, "rb") as f:
                data = pickle.load(f)
            self.bm25 = data["bm25"]
            self.metadata = data["metadata"]
            self.corpus = data["corpus"]
            logger.info(
                "BM25 index loaded from {} ({} chunks)",
                self.index_path,
                len(self.metadata),
            )
            return True
        except Exception as e:
            logger.error("Failed to load BM25 index: {}", e)
            return False
