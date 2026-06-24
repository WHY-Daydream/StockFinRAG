from typing import List, Dict, Any
from pymilvus import Collection
from sentence_transformers import SentenceTransformer, CrossEncoder
from loguru import logger
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from milvus_client import connect_milvus, create_collection_if_not_exists


def _rrf_merge(results_list: List[List[Dict]], top_k: int = 10, k: int = 60) -> List[Dict]:
    """
    Reciprocal Rank Fusion: 融合多路检索结果
    results_list: 每路检索结果列表（已按得分降序排列）
    k: RRF 常数（默认 60）
    """
    from collections import defaultdict
    doc_scores = defaultdict(float)
    doc_info = {}

    for rank_idx, results in enumerate(results_list):
        for pos, doc in enumerate(results):
            key = (doc["doc_id"], doc.get("chunk_id"))
            doc_scores[key] += 1.0 / (k + pos + 1)
            if key not in doc_info:
                doc_info[key] = doc

    ranked = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
    final = []
    for key, score in ranked[:top_k]:
        item = dict(doc_info[key])
        item["score"] = round(score, 6)
        final.append(item)
    return final


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
        from retrieval.bm25_searcher import BM25Searcher
        self._bm25_searcher = BM25Searcher()
        if not self._bm25_searcher.load():
            logger.info("No BM25 index found, building...")
            try:
                self._bm25_searcher.build_from_chunks()
                self._bm25_searcher.save()
            except Exception as e:
                logger.warning(f"BM25 index build failed (non-fatal): {e}")
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
        混合检索: BM25 + 向量搜索(双通道) -> RRF 融合 -> Rerank
        """
        query_vec = self.embedder.encode(query, normalize_embeddings=True).tolist()

        # Channel A: Parent 向量检索
        parent_hits = self._search_collection(self.col_parent, query_vec, top_k * 2)
        parent_hits = self._rerank(query, parent_hits)
        for h in parent_hits:
            h["type"] = "parent"

        # Channel B: Child 向量检索
        child_hits = self._search_collection(self.col_child, query_vec, top_k * 2)
        child_hits = self._rerank(query, child_hits)
        for h in child_hits:
            h["type"] = "child"

        # Channel C: BM25 关键词检索
        bm25_hits = self._bm25_searcher.search(query, top_k * 2)

        # RRF 融合三路结果
        combined = _rrf_merge([parent_hits, child_hits, bm25_hits], top_k=top_k * 2)

        if not combined:
            logger.info(f"Search '{query[:30]}': 0 results")
            return []

        # 最终 Rerank（对融合后的全部结果）
        reranked = self._rerank(query, combined)

        # doc 级别去重（同 doc 保留最高 rerank 分）
        seen_docs = set()
        deduped = []
        for h in reranked:
            if h["doc_id"] not in seen_docs:
                seen_docs.add(h["doc_id"])
                deduped.append(h)
            if len(deduped) >= top_k:
                break

        logger.info(
            f"Search '{query[:30]}': "
            f"{len(parent_hits)}p + {len(child_hits)}c + {len(bm25_hits)}bm25 "
            f"-> {len(deduped)} final"
        )
        return deduped
