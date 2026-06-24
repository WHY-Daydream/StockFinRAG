"""
Tests for hybrid_searcher.py — RRF fusion, BM25 integration, _tokenize_cn
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from typing import List, Dict
from unittest.mock import patch, MagicMock


# ======================================================================
# Module-level imports (what we test)
# ======================================================================

from retrieval.hybrid_searcher import _rrf_merge, _tokenize_cn, HybridSearcher


# ======================================================================
# Tests for _rrf_merge
# ======================================================================

class TestRrfMerge:
    def test_rrf_merge_function_exists(self):
        """_rrf_merge is importable and callable"""
        assert callable(_rrf_merge)

    def test_rrf_merge_empty(self):
        """empty lists return []"""
        result = _rrf_merge([], top_k=10)
        assert result == []

    def test_rrf_merge_empty_lists(self):
        """list of empty lists returns []"""
        result = _rrf_merge([[], [], []], top_k=10)
        assert result == []

    def test_rrf_merge_single_list(self):
        """single list: items maintain input order in RRF"""
        docs = [
            {"doc_id": "d1", "chunk_id": "c1", "content": "first", "score": 0.9},
            {"doc_id": "d2", "chunk_id": "c2", "content": "second", "score": 0.8},
            {"doc_id": "d3", "chunk_id": "c3", "content": "third", "score": 0.7},
        ]
        result = _rrf_merge([docs], top_k=3)
        assert len(result) == 3
        # d1 should rank highest (pos 0 -> 1/61)
        assert result[0]["doc_id"] == "d1"
        assert result[1]["doc_id"] == "d2"
        assert result[2]["doc_id"] == "d3"
        # score should be rounded 1/(60+0+1)=0.016393...
        assert abs(result[0]["score"] - 1.0 / 61.0) < 1e-6

    def test_rrf_merge_dedup(self):
        """same (doc_id, chunk_id) in multiple lists gets cumulative score"""
        list_a = [
            {"doc_id": "d1", "chunk_id": "c1", "content": "A", "score": 0.9},
        ]
        list_b = [
            {"doc_id": "d1", "chunk_id": "c1", "content": "A", "score": 0.8},
        ]
        result = _rrf_merge([list_a, list_b], top_k=1)
        assert len(result) == 1
        assert result[0]["doc_id"] == "d1"
        # RRF scores: 1/61 + 1/61 = 2/61
        expected = 2.0 / 61.0
        assert abs(result[0]["score"] - expected) < 1e-6

    def test_rrf_merge_multi_channel(self):
        """three channels produce expected top_k"""
        ch_a = [
            {"doc_id": "d1", "chunk_id": "c1", "content": "A", "score": 0.9},
            {"doc_id": "d2", "chunk_id": "c2", "content": "B", "score": 0.8},
        ]
        ch_b = [
            {"doc_id": "d2", "chunk_id": "c2", "content": "B", "score": 0.7},
            {"doc_id": "d3", "chunk_id": "c3", "content": "C", "score": 0.6},
        ]
        ch_c = [
            {"doc_id": "d4", "chunk_id": "c4", "content": "D", "score": 0.5},
        ]
        result = _rrf_merge([ch_a, ch_b, ch_c], top_k=3)
        assert len(result) == 3
        doc_ids = {r["doc_id"] for r in result}
        assert "d1" in doc_ids
        assert "d2" in doc_ids   # appears in ch_a (pos 1) + ch_b (pos 0) = higher RRF
        assert "d4" in doc_ids   # appears in ch_c (pos 0)


# ======================================================================
# Tests for _tokenize_cn
# ======================================================================

class TestTokenizeCn:
    def test_tokenize_cn_exists(self):
        """_tokenize_cn is importable and callable"""
        assert callable(_tokenize_cn)

    def test_tokenize_cn_returns_list_of_strings(self):
        """splits Chinese text into tokens"""
        text = "营业收入增长"
        tokens = _tokenize_cn(text)
        assert isinstance(tokens, list)
        assert all(isinstance(t, str) for t in tokens)
        assert len(tokens) > 0

    def test_tokenize_cn_empty_string(self):
        """empty string returns empty list"""
        assert _tokenize_cn("") == []

    def test_tokenize_cn_mixed_text(self):
        """handles mixed Chinese and ASCII"""
        tokens = _tokenize_cn("hello世界")
        assert isinstance(tokens, list)
        assert len(tokens) >= 2


# ======================================================================
# Tests for HybridSearcher initialization (mocked)
# ======================================================================

class TestHybridSearcherInit:
    """Test HybridSearcher can initialize with mocked dependencies"""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset HybridSearcher singleton before each test"""
        HybridSearcher._instance = None
        yield
        HybridSearcher._instance = None

    @patch("retrieval.hybrid_searcher.connect_milvus", return_value=None)
    @patch("retrieval.hybrid_searcher.create_collection_if_not_exists")
    @patch("retrieval.hybrid_searcher.SentenceTransformer")
    @patch("retrieval.hybrid_searcher.CrossEncoder")
    @patch("retrieval.bm25_searcher.BM25Searcher.load", return_value=True)
    def test_searcher_init_loads_bm25(self, mock_bm25_load,
                                       mock_cross_encoder,
                                       mock_sentence_transformer,
                                       mock_create_collection,
                                       mock_connect_milvus):
        """HybridSearcher initializes successfully with BM25 load"""
        mock_create_collection.side_effect = lambda name, dim: MagicMock()

        searcher = HybridSearcher()

        # Verify BM25Searcher.load() was called
        mock_bm25_load.assert_called_once()

        # Verify connect_milvus was called
        mock_connect_milvus.assert_called_once()

        # Verify collections were created
        assert mock_create_collection.call_count == 2

        # Verify embedder and reranker were created
        mock_sentence_transformer.assert_called_once()
        mock_cross_encoder.assert_called_once()

        # Verify the BM25 searcher attribute exists
        assert hasattr(searcher, "_bm25_searcher")
        assert searcher._initialized

    @patch("retrieval.hybrid_searcher.connect_milvus", return_value=None)
    @patch("retrieval.hybrid_searcher.create_collection_if_not_exists")
    @patch("retrieval.hybrid_searcher.SentenceTransformer")
    @patch("retrieval.hybrid_searcher.CrossEncoder")
    @patch("retrieval.bm25_searcher.BM25Searcher.load", return_value=False)
    @patch("retrieval.bm25_searcher.BM25Searcher.build_from_chunks", return_value=None)
    @patch("retrieval.bm25_searcher.BM25Searcher.save", return_value=None)
    def test_searcher_init_builds_bm25_when_no_index(self, mock_save,
                                                      mock_build_from_chunks,
                                                      mock_bm25_load,
                                                      mock_cross_encoder,
                                                      mock_sentence_transformer,
                                                      mock_create_collection,
                                                      mock_connect_milvus):
        """HybridSearcher builds BM25 index when no pre-existing index found"""
        mock_create_collection.side_effect = lambda name, dim: MagicMock()

        searcher = HybridSearcher()

        # Verify BM25Searcher.load() returned False and triggered build
        mock_bm25_load.assert_called_once()
        mock_build_from_chunks.assert_called_once()
        mock_save.assert_called_once()

        assert searcher._initialized