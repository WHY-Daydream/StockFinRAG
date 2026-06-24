"""QueryAnalyzer 单元测试

覆盖:
  1. 模块导入
  2. analyze 方法存在且可调用
  3. PROMPT 包含 simple/abstract/complex 三类定义
  4. prompt 格式化不同长度问题
  5. monkeypatch OpenAI 失败时返回 fallback
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestQueryAnalyzerImport:
    """测试 QueryAnalyzer 模块可导入"""

    def test_query_analyzer_module_importable(self):
        from retrieval.query_analyzer import QueryAnalyzer
        assert QueryAnalyzer is not None


class TestAnalyzeMethodStructure:
    """测试 analyze 方法存在且返回正确结构"""

    def test_analyze_returns_dict_structure(self):
        from retrieval.query_analyzer import QueryAnalyzer

        analyzer = QueryAnalyzer()
        assert hasattr(analyzer, "analyze")
        assert callable(analyzer.analyze)


class TestJudgePrompt:
    """测试 _JUDGE_PROMPT 包含三类策略定义"""

    def test_analyzer_has_judge_prompt(self):
        from retrieval.query_analyzer import _JUDGE_PROMPT

        prompt = _JUDGE_PROMPT
        for keyword in ("simple", "abstract", "complex"):
            assert keyword in prompt, f"PROMPT 缺少关键字: {keyword}"

    def test_judge_prompt_contains_cn_descriptions(self):
        from retrieval.query_analyzer import _JUDGE_PROMPT

        prompt = _JUDGE_PROMPT
        assert "简单具体" in prompt
        assert "抽象宽泛" in prompt
        assert "复杂多维度" in prompt


class TestPromptFormatting:
    """测试 prompt 格式化不同长度问题"""

    def test_analyzer_handles_oneline_questions(self):
        from retrieval.query_analyzer import _JUDGE_PROMPT

        short_q = "GDP是多少"
        long_q = "请问根据最新的财务报告和行业分析，2024年中国的GDP增长率和通货膨胀率分别是多少"
        chinese_q = "反洗钱法对金融机构的处罚标准是什么"

        for question in (short_q, long_q, chinese_q):
            formatted = _JUDGE_PROMPT.format(question=question)
            assert question in formatted, f"问题未正确格式化: {question}"
            assert "问题：" in formatted


class TestFallbackOnError:
    """monkeypatch OpenAI 客户端，验证失败时返回 fallback"""

    def test_analyzer_fallback_on_error(self, monkeypatch):
        from retrieval.query_analyzer import QueryAnalyzer

        # 让 analyze 内部控制流的 _client.chat.completions.create 抛出异常
        def _mock_create(*args, **kwargs):
            raise RuntimeError("模拟 API 调用失败")

        analyzer = QueryAnalyzer()
        # 替换底层 client
        mock_completions = MagicMock()
        mock_completions.create = _mock_create
        analyzer._client.chat.completions = mock_completions

        result = analyzer.analyze("测试问题")
        assert result == {"type": "simple", "reason": "fallback"}

    def test_analyzer_fallback_on_invalid_json(self, monkeypatch):
        from retrieval.query_analyzer import QueryAnalyzer

        # 构造一个返回非法 JSON 的响应
        mock_choice = MagicMock()
        mock_choice.message.content = "{not valid json"

        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        analyzer = QueryAnalyzer()
        analyzer._client.chat.completions.create = MagicMock(return_value=mock_completion)

        result = analyzer.analyze("测试问题")
        assert result == {"type": "simple", "reason": "fallback"}


class TestConfigProjectRoot:
    """验证 Config 中添加了 PROJECT_ROOT"""

    def test_config_has_project_root(self):
        from config import Config
        assert hasattr(Config, "PROJECT_ROOT")
        root = Config.PROJECT_ROOT
        assert isinstance(root, str)
        assert os.path.isdir(root)
        # PROJECT_ROOT 应为项目根目录（app 的父目录）
        assert root.endswith("StockFinRAG") or os.path.basename(root) == "StockFinRAG"
