"""BM25Searcher 单元测试

覆盖:
  1. 模块导入
  2. jieba 中文分词
  3. 检索结果格式 (手动构造 corpus + BM25Okapi)
  4. 空索引检索
  5. save / load (tmp_path)
  6. build_from_chunks 与 mock MySQL
"""

import os
import sys
from unittest.mock import MagicMock

import jieba
import pytest
from rank_bm25 import BM25Okapi

# 确保 app 目录在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── 1. 模块导入 ─────────────────────────────────────────────

class TestBM25SearcherImport:
    """测试 BM25Searcher 模块可导入"""

    def test_bm25_searcher_module_importable(self):
        from retrieval.bm25_searcher import BM25Searcher
        assert BM25Searcher is not None


# ── 2. jieba 分词 ───────────────────────────────────────────

class TestChineseTokenizer:
    """测试 jieba 中文分词器"""

    def test_chinese_tokenizer_splits(self):
        text = "营业收入增长百分之十"
        tokens = list(jieba.cut(text))
        assert isinstance(tokens, list)
        assert len(tokens) > 0
        assert all(isinstance(t, str) for t in tokens)


# ── 3. 检索结果格式 ─────────────────────────────────────────

class TestBM25SearchShape:
    """手动构造 BM25Okapi 并检验结果 dict 字段"""

    def test_bm25_search_returns_correct_shape(self):
        from retrieval.bm25_searcher import BM25Searcher

        # 手工 corpus + metadata
        corpus = [
            list("营业收入增长"),
            list("净利润下降"),
            list("现金流量充足"),
        ]
        searcher = BM25Searcher()
        searcher.bm25 = BM25Okapi(corpus)
        searcher.metadata = [
            {"doc_id": 1, "chunk_id": 10, "type": "parent", "content": "营业收入增长"},
            {"doc_id": 2, "chunk_id": 20, "type": "child",  "content": "净利润下降"},
            {"doc_id": 3, "chunk_id": 30, "type": "parent", "content": "现金流量充足"},
        ]
        searcher.corpus = corpus

        results = searcher.search("增长", top_k=2)

        assert isinstance(results, list)
        assert len(results) <= 2
        if len(results) > 0:
            r = results[0]
            for key in ("doc_id", "chunk_id", "type", "content", "score", "rerank_score"):
                assert key in r, f"结果缺少字段: {key}"
            assert isinstance(r["score"], float)
            assert isinstance(r["rerank_score"], float)
            assert r["rerank_score"] == 0.0


# ── 4. 空索引检索 ───────────────────────────────────────────

class TestBM25EmptyIndex:
    """索引未构建时 search 应返回空列表"""

    def test_bm25_empty_index(self):
        from retrieval.bm25_searcher import BM25Searcher

        searcher = BM25Searcher()
        # 未调用 build_from_chunks，bm25 为 None
        results = searcher.search("测试查询")
        assert results == []


# ── 5. save / load ──────────────────────────────────────────

class TestBM25SaveLoad:
    """save → load 后检索结果一致"""

    def test_bm25_save_load(self, tmp_path):
        from retrieval.bm25_searcher import BM25Searcher

        index_file = tmp_path / "bm25_index.pkl"

        # 构建索引并保存
        searcher1 = BM25Searcher(index_path=str(index_file))
        searcher1.bm25 = BM25Okapi([list("营收增长"), list("利润下降")])
        searcher1.metadata = [
            {"doc_id": 1, "chunk_id": 10, "type": "parent", "content": "营收增长"},
            {"doc_id": 2, "chunk_id": 20, "type": "child",  "content": "利润下降"},
        ]
        searcher1.corpus = [list("营收增长"), list("利润下降")]
        searcher1.save()

        assert os.path.exists(index_file)

        # 新建实例并加载
        searcher2 = BM25Searcher(index_path=str(index_file))
        ok = searcher2.load()
        assert ok is True

        results = searcher2.search("增长", top_k=5)
        assert len(results) >= 1
        assert results[0]["doc_id"] == 1
        assert results[0]["rerank_score"] == 0.0


# ── 6. build_from_chunks mock ───────────────────────────────

class TestBuildFromChunksMock:
    """mock get_mysql 来测试 build_from_chunks"""

    def test_build_from_chunks_with_mock(self, monkeypatch):
        from retrieval.bm25_searcher import BM25Searcher

        # 构造 mock 行数据
        fake_rows = [
            {"doc_id": 10, "chunk_id": 100, "chunk_type": "parent",
             "content": "公司营业收入大幅增长", "doc_type": "财报"},
            {"doc_id": 10, "chunk_id": 101, "chunk_type": "child",
             "content": "净利润同比增长百分之二十", "doc_type": "财报"},
            {"doc_id": 11, "chunk_id": 200, "chunk_type": "parent",
             "content": "现金流量表显示经营状况良好", "doc_type": "年报"},
        ]

        # mock cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = fake_rows

        # mock connection
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # mock get_mysql 函数
        def mock_get_mysql():
            return mock_conn

        monkeypatch.setattr("db.get_mysql", mock_get_mysql)

        searcher = BM25Searcher()
        searcher.build_from_chunks()

        # 验证索引构建
        assert searcher.bm25 is not None
        assert len(searcher.metadata) == 3
        assert len(searcher.corpus) == 3

        # 验证元数据字段
        assert searcher.metadata[0]["doc_id"] == 10
        assert searcher.metadata[0]["chunk_id"] == 100
        assert searcher.metadata[0]["type"] == "parent"
        assert "营业收入" in searcher.metadata[0]["content"]

        # 验证检索
        results = searcher.search("净利润", top_k=5)
        assert len(results) >= 1
        for key in ("doc_id", "chunk_id", "type", "content", "score", "rerank_score"):
            assert key in results[0]
        assert results[0]["rerank_score"] == 0.0

        # 验证 mock 被正确调用了
        mock_cursor.execute.assert_called_once()
        mock_conn.close.assert_called_once()
