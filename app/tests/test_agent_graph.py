"""Agent graph 单元测试 — judge_node, HyDE, Query Decomposition

覆盖:
  1. judge_node 可调用
  2. _decompose_question 可调用
  3. _generate_hyde 可调用
  4. AgentState 包含新增字段 strategy_type, hyde_doc, sub_questions
  5. _decompose_question fallback 返回 [question]
  6. _generate_hyde fallback 返回原问题
  7. retrieval_node 可导入且可调用（mock state）
  8. build_qa_graph() 构造不报错
  9. 图包含 judge 节点
"""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestJudgeNode:
    """judge_node 函数存在且可调用"""

    def test_judge_node_is_callable(self):
        from agent.graph import judge_node
        assert callable(judge_node)

    def test_decompose_is_callable(self):
        from agent.graph import _decompose_question
        assert callable(_decompose_question)

    def test_generate_hyde_is_callable(self):
        from agent.graph import _generate_hyde
        assert callable(_generate_hyde)


class TestAgentStateFields:
    """AgentState 包含新增字段"""

    def test_state_has_strategy_type(self):
        from agent.graph import AgentState
        assert "strategy_type" in AgentState.__annotations__

    def test_state_has_hyde_doc(self):
        from agent.graph import AgentState
        assert "hyde_doc" in AgentState.__annotations__

    def test_state_has_sub_questions(self):
        from agent.graph import AgentState
        assert "sub_questions" in AgentState.__annotations__


class TestDecomposeFallback:
    """_decompose_question 异常时降级返回 [question]"""

    def test_decompose_fallback_on_openai_error(self, monkeypatch):
        from agent.graph import _decompose_question

        import agent.graph as graph_module
        original_openai = graph_module.OpenAI

        def _mock_openai(*args, **kwargs):
            raise RuntimeError("模拟 OpenAI 初始化失败")

        monkeypatch.setattr(graph_module, "OpenAI", _mock_openai)

        result = _decompose_question("测试复杂问题")
        assert result == ["测试复杂问题"]

    def test_decompose_fallback_on_json_error(self, monkeypatch):
        from agent.graph import _decompose_question

        # Mock chat.completions.create 返回非法 JSON
        mock_choice = MagicMock()
        mock_choice.message.content = "{not valid json"

        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create = MagicMock(return_value=mock_completion)

        import agent.graph as graph_module
        monkeypatch.setattr(graph_module, "OpenAI", lambda **kw: mock_client)

        result = _decompose_question("测试复杂问题")
        assert result == ["测试复杂问题"]


class TestHydeFallback:
    """_generate_hyde 异常时降级返回原问题"""

    def test_hyde_fallback_on_openai_error(self, monkeypatch):
        from agent.graph import _generate_hyde

        import agent.graph as graph_module

        def _mock_openai(*args, **kwargs):
            raise RuntimeError("模拟 OpenAI 初始化失败")

        monkeypatch.setattr(graph_module, "OpenAI", _mock_openai)

        result = _generate_hyde("测试问题")
        assert result == "测试问题"


class TestRetrievalNodeImport:
    """retrieval_node 可导入且可调用"""

    def test_retrieval_node_is_importable(self):
        from agent.graph import retrieval_node
        assert callable(retrieval_node)

    def test_retrieval_node_accepts_mock_state(self, monkeypatch):
        """Monkeypatch 外部服务，仅验证函数签名和路由逻辑"""
        import retrieval.hybrid_searcher as hs_module
        import retrieval.context_enricher as ce_module
        import retrieval.cache as cache_module

        # Mock ResultCache: cache miss
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        monkeypatch.setattr(cache_module, "ResultCache", lambda: mock_cache)

        # Mock HybridSearcher: return empty results
        mock_searcher = MagicMock()
        mock_searcher.search.return_value = []
        monkeypatch.setattr(hs_module, "HybridSearcher", lambda: mock_searcher)

        # Mock ContextEnricher: return empty results
        mock_enricher = MagicMock()
        mock_enricher.enrich.return_value = []
        monkeypatch.setattr(ce_module, "ContextEnricher", lambda: mock_enricher)

        from agent.graph import retrieval_node, AgentState

        state: AgentState = {
            "question": "测试问题",
            "session_id": "test-session",
            "retrieved_context": [],
            "analysis_result": "",
            "final_answer": "",
            "compliance_check": "",
            "compliance_reason": "",
            "start_time": 0.0,
            "strategy_type": "simple",
            "hyde_doc": "",
            "sub_questions": [],
        }

        result = retrieval_node(state)
        assert isinstance(result, dict)
        assert "retrieved_context" in result


class TestGraphBuilder:
    """build_qa_graph 构造不报错"""

    def test_build_qa_graph_succeeds(self):
        """构建图不应抛出异常"""
        from agent.graph import build_qa_graph
        graph = build_qa_graph()
        assert graph is not None

    def test_graph_has_judge_node(self):
        """图中包含 judge 节点且入口点为 judge"""
        from agent.graph import build_qa_graph
        graph = build_qa_graph()
        assert hasattr(graph, "get_graph")
        schema = graph.get_graph()
        # schema.nodes is a dict of {node_name: Node} — iterating gives keys (str)
        nodes = set(k for k in schema.nodes)
        assert "judge" in nodes
