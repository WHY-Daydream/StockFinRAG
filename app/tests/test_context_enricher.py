"""ContextEnricher 单元测试

覆盖:
  1. 模块导入
  2. 空输入返回 []
  3. monkeypatch mock get_mysql 验证能取到邻居
  4. window_size=0 且空输入返回 []
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestContextEnricherImport:
    """测试 ContextEnricher 模块可导入"""

    def test_enricher_module_importable(self):
        from retrieval.context_enricher import ContextEnricher

        assert ContextEnricher is not None


class TestEmptyInput:
    """测试空输入返回空列表"""

    def test_enricher_empty_input(self):
        from retrieval.context_enricher import ContextEnricher

        enricher = ContextEnricher()
        result = enricher.enrich([])
        assert result == []

    def test_enricher_window_size_zero_with_empty_input(self):
        from retrieval.context_enricher import ContextEnricher

        enricher = ContextEnricher()
        result = enricher.enrich([], window_size=0)
        assert result == []


class TestEnrichWithMock:
    """monkeypatch mock get_mysql 验证能取到邻居"""

    def _make_mock_cursor(self, rows):
        """创建一个返回指定行的 mock cursor"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = rows
        return mock_cursor

    def _make_mock_conn(self, mock_cursor):
        """创建一个返回 mock cursor 的 mock connection"""
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        return mock_conn

    def test_enricher_enriches_with_mock(self, monkeypatch):
        from retrieval.context_enricher import ContextEnricher

        # 模拟邻居数据
        fake_neighbors = [
            {
                "doc_id": 1,
                "chunk_id": 1,
                "chunk_type": "child",
                "content": "邻居 chunk 1",
                "type": "context",
                "score": 0.0,
                "rerank_score": 0.0,
            },
            {
                "doc_id": 1,
                "chunk_id": 3,
                "chunk_type": "child",
                "content": "邻居 chunk 3",
                "type": "context",
                "score": 0.0,
                "rerank_score": 0.0,
            },
        ]

        mock_cursor = self._make_mock_cursor(fake_neighbors)
        mock_conn = self._make_mock_conn(mock_cursor)

        def mock_get_mysql():
            return mock_conn

        monkeypatch.setattr(
            "retrieval.context_enricher.get_mysql", mock_get_mysql
        )

        enricher = ContextEnricher()
        candidates = [
            {"doc_id": 1, "chunk_id": 2, "content": "候选 chunk 2"},
        ]
        result = enricher.enrich(candidates, window_size=1)

        # 验证结果包含原候选 + 邻居
        assert len(result) == 3

        # 验证原候选还在
        assert result[0]["doc_id"] == 1
        assert result[0]["chunk_id"] == 2

        # 验证邻居 chunk_id=1
        assert result[1]["doc_id"] == 1
        assert result[1]["chunk_id"] == 1
        assert result[1]["type"] == "context"
        assert result[1]["score"] == 0.0
        assert result[1]["rerank_score"] == 0.0

        # 验证邻居 chunk_id=3
        assert result[2]["doc_id"] == 1
        assert result[2]["chunk_id"] == 3
        assert result[2]["type"] == "context"
        assert result[2]["score"] == 0.0
        assert result[2]["rerank_score"] == 0.0

        # 验证 SQL 查询参数（window_size=1, chunk_id=2 → [1, 3]）
        mock_cursor.execute.assert_called_once()
        args = mock_cursor.execute.call_args[0]
        assert args[1] == (1, 1, 3)

    def test_enricher_deduplicates_with_mock(self, monkeypatch):
        """验证候选已存在的 chunk 不会被重复添加"""
        from retrieval.context_enricher import ContextEnricher

        # 模拟邻居数据（包含已在 candidates 中的 chunk）
        fake_neighbors = [
            {
                "doc_id": 1,
                "chunk_id": 1,
                "chunk_type": "child",
                "content": "邻居 chunk 1",
                "type": "context",
                "score": 0.0,
                "rerank_score": 0.0,
            },
            {
                "doc_id": 1,
                "chunk_id": 2,
                "chunk_type": "child",
                "content": "重复 chunk 2",
                "type": "context",
                "score": 0.0,
                "rerank_score": 0.0,
            },
        ]

        mock_cursor = self._make_mock_cursor(fake_neighbors)
        mock_conn = self._make_mock_conn(mock_cursor)

        def mock_get_mysql():
            return mock_conn

        monkeypatch.setattr(
            "retrieval.context_enricher.get_mysql", mock_get_mysql
        )

        enricher = ContextEnricher()
        candidates = [
            {"doc_id": 1, "chunk_id": 2, "content": "候选 chunk 2"},
        ]
        result = enricher.enrich(candidates, window_size=1)

        # 验证结果：只有 chunk_id=1 是新添加的（chunk_id=2 已存在）
        assert len(result) == 2

        # 验证候选仍然在
        assert result[0]["doc_id"] == 1
        assert result[0]["chunk_id"] == 2

        # 验证只有 chunk_id=1 的邻居被添加
        assert result[1]["doc_id"] == 1
        assert result[1]["chunk_id"] == 1

    def test_enricher_window_size_zero_enriches(self, monkeypatch):
        """验证 window_size=0 时只取 chunk_id 自身"""
        from retrieval.context_enricher import ContextEnricher

        fake_neighbors = [
            {
                "doc_id": 1,
                "chunk_id": 2,
                "chunk_type": "child",
                "content": "自身 chunk 2",
                "type": "context",
                "score": 0.0,
                "rerank_score": 0.0,
            },
        ]

        mock_cursor = self._make_mock_cursor(fake_neighbors)
        mock_conn = self._make_mock_conn(mock_cursor)

        def mock_get_mysql():
            return mock_conn

        monkeypatch.setattr(
            "retrieval.context_enricher.get_mysql", mock_get_mysql
        )

        enricher = ContextEnricher()
        candidates = [
            {"doc_id": 1, "chunk_id": 2, "content": "候选 chunk 2"},
        ]
        result = enricher.enrich(candidates, window_size=0)

        # window_size=0，且 chunk_id=2 已在 candidates 中，所以无新增
        assert len(result) == 1
        assert result[0]["chunk_id"] == 2
