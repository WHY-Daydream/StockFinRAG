"""ContextEnricher — 检索上下文增强

对候选 chunk 列表，从 MySQL chunks 表中查找同一 doc_id 下
相邻的 chunk 记录，扩展上下文窗口。
"""

from typing import Dict, List, Set
import sys

sys.path.insert(0, "..")
from db import get_mysql


class ContextEnricher:
    """检索上下文增强器"""

    def enrich(
        self, candidates: List[Dict], window_size: int = 2
    ) -> List[Dict]:
        """对每个候选 chunk，从 MySQL 查找相邻 chunk 并去重合并。

        Args:
            candidates: 候选 chunk 列表，每个 dict 至少包含 doc_id 和 chunk_id。
            window_size: 前后各取多少条邻居（默认 2）。

        Returns:
            原 candidates + 不重复的邻居 chunk（标记 type=context,
            score=0.0, rerank_score=0.0）。
        """
        if not candidates:
            return []

        # 按 doc_id 分组收集 chunk_id
        doc_chunks: Dict[int, Set[int]] = {}
        for c in candidates:
            doc_id = c.get("doc_id")
            chunk_id = c.get("chunk_id")
            if doc_id is None or chunk_id is None:
                continue
            doc_chunks.setdefault(doc_id, set()).add(chunk_id)

        # 查询邻居
        neighbors = self._fetch_neighbors(doc_chunks, window_size)

        # 去重：已存在于 candidates 中的 chunk 不重复添加
        existing = {(c["doc_id"], c["chunk_id"]) for c in candidates}
        new_neighbors = [
            n
            for n in neighbors
            if (n["doc_id"], n["chunk_id"]) not in existing
        ]

        return candidates + new_neighbors

    def _fetch_neighbors(
        self, doc_chunks: Dict[int, Set[int]], window_size: int
    ) -> List[Dict]:
        """从 MySQL 查询邻居 chunk。

        Args:
            doc_chunks: doc_id -> chunk_id 集合的映射。
            window_size: 前后窗口大小。

        Returns:
            邻居 chunk 列表，每个 dict 已标记 type=context,
            score=0.0, rerank_score=0.0。
        """
        conn = get_mysql()
        try:
            with conn.cursor() as cursor:
                neighbors: List[Dict] = []
                for doc_id, chunk_ids in doc_chunks.items():
                    min_id = min(chunk_ids) - window_size
                    max_id = max(chunk_ids) + window_size

                    sql = (
                        "SELECT doc_id, id AS chunk_id, chunk_type, content "
                        "FROM chunks "
                        "WHERE doc_id=%s AND id>=%s AND id<=%s "
                        "ORDER BY chunk_index"
                    )
                    cursor.execute(sql, (doc_id, min_id, max_id))
                    rows = cursor.fetchall()

                    for row in rows:
                        row["type"] = "context"
                        row["score"] = 0.0
                        row["rerank_score"] = 0.0
                        neighbors.append(row)

                return neighbors
        finally:
            conn.close()
