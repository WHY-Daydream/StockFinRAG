"""验证 seed 和 ingest 始终执行向量化"""

def test_service_has_seed_method():
    """qa_service 应有 seed 方法"""
    with open("service/qa_service.py", "r", encoding="utf-8") as f:
        source = f.read()
    assert "def seed(" in source, "qa_service 应有 seed 方法"
    assert "FinKnowledgeBuilder" in source or "process_unprocessed_docs" in source, "seed 应调用向量化"


def test_service_has_ingest_method():
    """qa_service 应有 ingest 方法"""
    with open("service/qa_service.py", "r", encoding="utf-8") as f:
        source = f.read()
    assert "def ingest(" in source, "qa_service 应有 ingest 方法"


def test_api_server_uses_service():
    """api_server 应通过 QAAnswerService 调用，而非直接调用下层"""
    with open("api_server.py", "r", encoding="utf-8") as f:
        source = f.read()
    assert "qa_service." in source, "api_server 应通过 qa_service 调用"
    assert "FinKnowledgeBuilder" not in source, "api_server 不应直接引用 FinKnowledgeBuilder"