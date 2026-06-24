"""测试多轮对话记忆功能

Task 1: Redis 会话历史方法与历史截断函数
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock


# ======================================================================
# Tests for cache.py session history methods
# ======================================================================

class TestSessionHistoryMethods:
    """ResultCache 需要 get_session_history / set_session_history / append_to_session_history"""

    def test_cache_has_session_methods(self):
        """get/set/append 方法存在于 ResultCache 上"""
        from retrieval.cache import ResultCache
        assert hasattr(ResultCache, "get_session_history")
        assert hasattr(ResultCache, "set_session_history")
        assert hasattr(ResultCache, "append_to_session_history")
        assert callable(getattr(ResultCache, "get_session_history"))
        assert callable(getattr(ResultCache, "set_session_history"))
        assert callable(getattr(ResultCache, "append_to_session_history"))

    def test_session_history_set_get(self):
        """set_session_history 后能正确 get 回"""
        fake_redis = MagicMock()
        session_data = [{"role": "user", "content": "hello"}]
        fake_redis.get.return_value = json.dumps(session_data, ensure_ascii=False)

        with patch("retrieval.cache.get_redis", return_value=fake_redis):
            from retrieval.cache import ResultCache
            cache = ResultCache()

            # 先 set
            cache.set_session_history("sid-001", session_data)
            key = "session:sid-001:history"
            fake_redis.setex.assert_called_once()
            args = fake_redis.setex.call_args
            assert args[0][0] == key
            assert json.loads(args[0][2]) == session_data

            # 再 get
            result = cache.get_session_history("sid-001")
            assert result == session_data
            fake_redis.get.assert_called_with(key)

    def test_session_history_append(self):
        """append 正确追加 Q&A 对"""
        fake_redis = MagicMock()
        # 第一次 get 返回 None（空历史），第二次 get 返回追加后的数据
        existing = [
            {"role": "user", "content": "之前的提问"},
            {"role": "assistant", "content": "之前的回答"},
        ]
        fake_redis.get.return_value = json.dumps(existing, ensure_ascii=False)

        with patch("retrieval.cache.get_redis", return_value=fake_redis):
            from retrieval.cache import ResultCache
            cache = ResultCache()

            cache.append_to_session_history("sid-002", "新问题", "新回答")

            # setex 调用时的完整数据 = existing + 新 Q&A
            expected = existing + [
                {"role": "user", "content": "新问题"},
                {"role": "assistant", "content": "新回答"},
            ]
            fake_redis.setex.assert_called_once()
            args = fake_redis.setex.call_args
            assert json.loads(args[0][2]) == expected

    def test_session_history_nonexistent(self):
        """不存在的 session 返回 None"""
        fake_redis = MagicMock()
        fake_redis.get.return_value = None

        with patch("retrieval.cache.get_redis", return_value=fake_redis):
            from retrieval.cache import ResultCache
            cache = ResultCache()
            result = cache.get_session_history("nonexistent-sid")
            assert result is None


# ======================================================================
# Tests for _truncate_history utility
# ======================================================================

class TestHistoryTruncation:
    """_truncate_history 正确截断历史"""

    def test_history_truncation(self):
        """10 条消息截断到最多 6 条（max_rounds=3）"""
        from service.qa_service import _truncate_history

        # 模拟 5 轮对话 = 10 条消息
        history = []
        for i in range(1, 6):
            history.append({"role": "user", "content": f"Q{i}"})
            history.append({"role": "assistant", "content": f"A{i}"})

        assert len(history) == 10

        truncated = _truncate_history(history, max_rounds=3)

        # 只保留最近 3 轮 = 6 条
        assert len(truncated) == 6
        assert truncated[0]["content"] == "Q3"
        assert truncated[-1]["content"] == "A5"


# ======================================================================
# Tests for Task 2: AgentState + 历史注入 Prompt
# ======================================================================

def test_agent_state_has_conversation_history():
    from agent.graph import AgentState
    assert "conversation_history" in AgentState.__annotations__


def test_analysis_node_prompt_mentions_history():
    """验证 analysis_node 的 prompt 包含对话历史"""
    with open("agent/graph.py", "r", encoding="utf-8") as f:
        source = f.read()
    # 应包含"对话历史"章节
    assert "对话历史" in source
