"""Enhanced retrieval pipeline integration tests

Covers:
  1. Full pipeline module imports (BM25Searcher, QueryAnalyzer, ContextEnricher, _rrf_merge, _tokenize_cn)
  2. AgentState has new fields (strategy_type, hyde_doc, sub_questions)
  3. RRF merge stability (duplicate input dedup, top_k clamp)
  4. Config.PROJECT_ROOT exists
  5. All new retrieval modules importable via importlib
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_full_pipeline_imports():
    """Verify all new modules can be imported"""
    from retrieval.bm25_searcher import BM25Searcher
    from retrieval.query_analyzer import QueryAnalyzer
    from retrieval.context_enricher import ContextEnricher
    from retrieval.hybrid_searcher import _rrf_merge, _tokenize_cn
    assert BM25Searcher is not None
    assert QueryAnalyzer is not None
    assert ContextEnricher is not None
    assert callable(_rrf_merge)
    assert callable(_tokenize_cn)


def test_agent_state_has_new_fields():
    """Verify AgentState has retrieval strategy-related fields"""
    from agent.graph import AgentState
    hints = AgentState.__annotations__
    required = {"strategy_type", "hyde_doc", "sub_questions"}
    assert required.issubset(hints.keys()), f"Missing: {required - set(hints.keys())}"


def test_rrf_merge_stability():
    """Verify RRF merge stability (dedup, top_k clamp)"""
    from retrieval.hybrid_searcher import _rrf_merge

    # Two identical result lists — should dedup by (doc_id, chunk_id)
    docs = [
        {"doc_id": 1, "chunk_id": 0, "content": "A"},
        {"doc_id": 2, "chunk_id": 0, "content": "B"},
    ]
    merged = _rrf_merge([docs, docs], top_k=5)
    assert len(merged) == 2  # dedup on doc/chunk level

    # top_k clamp
    merged2 = _rrf_merge([docs, docs], top_k=1)
    assert len(merged2) == 1


def test_config_has_project_root():
    """Verify Config.PROJECT_ROOT exists"""
    from config import Config
    assert hasattr(Config, "PROJECT_ROOT")
    assert Config.PROJECT_ROOT.endswith("StockFinRAG")


def test_all_new_modules_importable():
    """Batch-verify all new modules import via importlib"""
    modules = [
        "retrieval.bm25_searcher",
        "retrieval.query_analyzer",
        "retrieval.context_enricher",
    ]
    for mod_name in modules:
        import importlib
        mod = importlib.import_module(mod_name)
        assert mod is not None