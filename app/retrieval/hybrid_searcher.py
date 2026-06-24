from typing import List, Dict, Any
from pymilvus import Collection
from sentence_transformers import SentenceTransformer, CrossEncoder
from loguru import logger
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from milvus_client import connect_milvus, create_collection_if_not_exists


class HybridSearcher:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        connect_milvus()
        self.col_child = create_collection_if_not_exists(
            Config.MILVUS_COLLECTION_CHILD, Config.EMBEDDING_DIM
        )
        self.col_parent = create_collection_if_not_exists(
            Config.MILVUS_COLLECTION_PARENT, Config.EMBEDDING_DIM
        )
        self.embedder = SentenceTransformer(Config.EMBEDDING_MODEL)
        self.reranker = CrossEncoder(Config.RERANK_MODEL)
        self._initialized = True

    def _search_collection(self, collection: Collection, query_vec: list,
                           top_k: int) -> List[Dict[str, Any]]:
        """对单个集合执行向量检索"""
        search_params = {"metric_type": "IP", "params": {}}
        results = collection.search(
            data=[query_vec],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["doc_id", "chunk_id", "content"],
        )
        hits = []
        for hits_group in results:
            for hit in hits_group:
                hits.append({
                    "doc_id": hit.entity.get("doc_id"),
                    "chunk_id": hit.entity.get("chunk_id"),
                    "content": hit.entity.get("content"),
                    "score": hit.score,
                })
        return hits

    def _rerank(self, query: str, candidates: List[Dict]) -> List[Dict]:
        """BGE Rerank 重排序"""
        if not candidates:
            return candidates
        pairs = [(query, c["content"]) for c in candidates]
        scores = self.reranker.predict(pairs)
        for i, score in enumerate(scores):
            candidates[i]["rerank_score"] = float(score)
        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        return candidates

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        双通道加权混合检索

        Channel A - Parent（权重 0.6）: 向量搜索 parent 集合 → Rerank
        Channel B - Child（权重 0.4）: 向量搜索 child 集合 → Rerank → doc 去重

        合并：按加权分排序，同 doc 保留高分，取最终 top_k
        """
        query_vec = self.embedder.encode(query, normalize_embeddings=True).tolist()

        # Channel A: 搜索 Parent（完整段落，高权重）
        parent_hits = self._search_collection(self.col_parent, query_vec, top_k * 2)
        parent_hits = self._rerank(query, parent_hits)
        for h in parent_hits:
            h["type"] = "parent"
            h["weighted_score"] = h["rerank_score"] * 0.6

        # Channel B: 搜索 Child（精确匹配，低权重）
        child_hits = self._search_collection(self.col_child, query_vec, top_k * 2)
        child_hits = self._rerank(query, child_hits)
        for h in child_hits:
            h["type"] = "child"
            h["weighted_score"] = h["rerank_score"] * 0.4

        # 合并：按加权分排序，同 doc 保留高分
        combined = parent_hits + child_hits
        combined.sort(key=lambda x: x["weighted_score"], reverse=True)

        # doc 级别去重（相同 doc 只保留最高分的）
        seen_docs = set()
        deduped = []
        for h in combined:
            if h["doc_id"] not in seen_docs:
                seen_docs.add(h["doc_id"])
                deduped.append(h)
            if len(deduped) >= top_k:
                    break

        logger.info(f"Search '{query[:30]}': {len(parent_hits)} parent + {len(child_hits)} child -> {len(deduped)} final")
        return deduped
