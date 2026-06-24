"""验证 /api/seed 始终执行向量化"""

def test_seed_always_vectorizes():
    """seed 无论是否导入新文档，都应调用向量化"""
    with open("api_server.py", "r", encoding="utf-8") as f:
        source = f.read()

    seed_start = source.index("def seed():")
    remainder = source[seed_start:]
    next_def = remainder.find("\ndef ", 1)
    seed_body = remainder[:next_def] if next_def > 0 else remainder

    # seed 函数中应包含 FinKnowledgeBuilder（向量化）
    assert "FinKnowledgeBuilder" in seed_body, "seed 函数应始终调用向量化"
    assert "process_unprocessed_docs" in seed_body, "seed 函数应处理未向量化的文档"
    # 不应有过早 return（count==0 时直接返回）
    assert "count == 0" not in seed_body, "count==0 的提前 return 已被移除"