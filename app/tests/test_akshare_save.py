"""验证 save_news 有正确的异常处理"""
import os


def get_source(filename):
    test_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.dirname(test_dir)
    with open(os.path.join(app_dir, filename), "r", encoding="utf-8") as f:
        return f.read()


class TestSaveNewsStructure:
    """save_news 和 save_indices 的异常处理结构"""

    def test_save_news_has_except_clause(self):
        """save_news 应有 except 处理 commit 失败"""
        source = get_source("data_providers/akshare_provider.py")
        assert "except Exception as e:" in source, "save_news 缺少 except"
        assert "conn.rollback()" in source, "应有 rollback"
        assert "return 0" in source, "失败应返回 0"

    def test_save_indices_has_except_clause(self):
        """save_indices 也应有 except 处理"""
        source = get_source("data_providers/akshare_provider.py")
        assert "except Exception as e:" in source, "save_indices 缺少 except"
        assert "conn.rollback()" in source, "应有 rollback"