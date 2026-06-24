"""验证 /api/ask 缓存实现没有变量作用域 bug"""
import os


def get_source(file_name):
    test_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.dirname(test_dir)
    with open(os.path.join(app_dir, file_name), "r", encoding="utf-8") as f:
        return f.read()


class TestAskFunction:
    """ask 函数和 qa_service 的代码结构检查"""

    def test_json_imported_in_service(self):
        """json 导入在 qa_service.py 中（不在 api_server.py）"""
        source = get_source("service/qa_service.py")
        assert "import json" in source, "json 导入应在 qa_service.py 中"

    def test_no_inline_import_in_ask(self):
        """ask 函数内部不应有 import"""
        source = get_source("api_server.py")
        if "def ask" in source:
            ask_start = source.index("def ask")
            remainder = source[ask_start:]
            next_def = remainder.find("\ndef ", 1)
            ask_body = remainder[:next_def] if next_def > 0 else remainder
            lines = [l.strip() for l in ask_body.split("\n")]
            inline_imports = [l for l in lines if l.startswith("import ") or l.startswith("from ")]
            assert not inline_imports, f"ask 函数内不应有 import: {inline_imports}"

    def test_service_imported_at_top(self):
        """QAAnswerService 在 api_server.py 顶部导入"""
        source = get_source("api_server.py")
        import_section = source.split("def ask")[0]
        assert "from service.qa_service import QAAnswerService" in import_section, \
            "QAAnswerService 应在 api_server.py 顶部导入"