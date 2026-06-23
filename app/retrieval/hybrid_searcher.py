from typing import List, Dict, Any
from pymilvus import Collection
from sentence_transformers import SentenceTransformer, CrossEncoder
from loguru import logger
import sys; sys.path.insert(0, "..")
from config import Config
from milvus_client import connect_milvus


class HybridSearcher:

    def __init__(self):
        connect_milvus()
        self.col_child = Collection(Config.MILVUS_COLLECTION_CHILD)
        self.col_child.load()
        self.col_parent = Collection(Config.MILVUS_COLLECTION_PARENT)
        self.col_parent.load()
        self.embedder = SentenceTransformer(Config.EMBEDDING_MODEL)
        self.reranker = CrossEncoder(Config.RERANK_MODEL)

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        # 1. 向量检索 child
        query_vec = self.embedder.encode(query, normalize_embeddings=True).tolist()
        search_params = {"metric_type": "IP", "params": {"nprobe": 128}}
        results = self.col_child.search(
            data=[query_vec],
            anns_field="embedding",
            param=search_params,
            limit=top_k * 2,
            output_fields=["doc_id", "chunk_id", "content"],
        )
        child_hits = []
        for hits in results:
            for hit in hits:
                child_hits.append({
                    "doc_id": hit.entity.get("doc_id"),
                    "chunk_id": hit.entity.get("chunk_id"),
                    "content": hit.entity.get("content"),
                    "score": hit.score,
                    "type": "child",
                })

        # 2. 从 child 找对应的 parent 补全上下文
        parent_hits = self._fetch_parents(child_hits)

        # 3. 合并 + Rerank
        candidates = child_hits + parent_hits
        if candidates:
            pairs = [(query, c["content"]) for c in candidates]
            rerank_scores = self.reranker.predict(pairs)
            for i, score in enumerate(rerank_scores):
                candidates[i]["rerank_score"] = float(score)
            candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
            candidates = candidates[:top_k]
        return candidates

    def _fetch_parents(self, child_hits: List[Dict]) -> List[Dict]:
        seen_doc_ids = set()
        for hit in child_hits:
            did = hit.get("doc_id")
            if did is not None:
                seen_doc_ids.add(did)
        if not seen_doc_ids:
            return []
        expr = " || ".join(f"doc_id == {did}" for did in seen_doc_ids)
        # 去重，每个 doc 取第一条 parent
        results = self.col_parent.query(
            expr=f'{expr} && chunk_type == "parent"',
            output_fields=["doc_id", "chunk_id", "content"],
            limit=len(seen_doc_ids),
        )
        seen = set()
        deduped = []
        for r in results:
            if r["doc_id"] not in seen:
                seen.add(r["doc_id"])
                deduped.append({
                    "doc_id": r["doc_id"],
                    "content": r["content"],
                    "score": 0,
                    "type": "parent",
                })
        return deduped
