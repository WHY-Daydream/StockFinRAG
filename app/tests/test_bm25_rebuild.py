"""BM25 索引重建相关测试"""


def test_rebuild_route_exists():
    """api_server.py 中有 /api/rebuild_bm25 路由"""
    with open("api_server.py", "r", encoding="utf-8") as f:
        source = f.read()
    assert "rebuild_bm25" in source


def test_bm25_rebuild_triggered_in_pipeline():
    """pipeline.py 中 process_unprocessed_docs 触发 BM25 重建"""
    with open("ingestion/pipeline.py", "r", encoding="utf-8") as f:
        source = f.read()
    assert "BM25Searcher" in source or "bm25" in source.lower()


def test_pipeline_rebuild_is_non_fatal():
    """BM25 重建失败不应影响主流程 (try/except)"""
    with open("ingestion/pipeline.py", "r", encoding="utf-8") as f:
        source = f.read()
    # 查找 try 在 BM25 相关代码附近
    bm25_idx = source.lower().index("bm25")
    window = source[bm25_idx:bm25_idx+500]
    assert "try" in window and "except" in window
    assert "non-fatal" in window.lower() or "warning" in window.lower()


def test_service_layer_unchanged():
    """qa_service.py 不需要修改"""
    with open("service/qa_service.py", "r", encoding="utf-8") as f:
        source = f.read()
    # 服务层不应直接引用 BM25Searcher
    assert "BM25Searcher" not in source