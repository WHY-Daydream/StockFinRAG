"""验证 /api/ask 缓存实现没有变量作用域 bug"""
import os


def get_source():
    test_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.dirname(test_dir)
    with open(os.path.join(app_dir, "api_server.py"), "r", encoding="utf-8") as f:
        return f.read()


class TestAskFunction:
    """ask 函数的代码结构检查"""

    def test_json_imported_at_module_level(self):
        """json 应该在文件顶部导入，不在函数内部"""
        source = get_source()
        # 检查 import json 在文件顶部（不在 ask 函数内部）
        import_section = source.split("def ask")[0]
        assert "import json" in import_section, "json 应在文件顶部导入，不应在 ask 函数内部"

    def test_no_inline_import_in_ask(self):
        """ask 函数内部不应有 import json"""
        source = get_source()
        if "def ask" in source:
            # 提取 ask 函数体到下一个 def
            ask_start = source.index("def ask")
            remainder = source[ask_start:]
            next_def = remainder.find("\ndef ", 1)
            ask_body = remainder[:next_def] if next_def > 0 else remainder
            # 检查函数体内的 import
            lines = [l.strip() for l in ask_body.split("\n")]
            inline_imports = [l for l in lines if l.startswith("import ") or l.startswith("from ")]
            problematic = [l for l in inline_imports if "json" in l]
            assert not problematic, f"ask 函数内不应有 json 导入: {problematic}"

    def test_redis_cache_imported_at_top(self):
        """ResultCache 导入在文件顶部，不在 ask 内部"""
        source = get_source()
        import_section = source.split("def ask")[0]
        assert "from retrieval.cache import ResultCache" in import_section, \
            "ResultCache 应在文件顶部导入"