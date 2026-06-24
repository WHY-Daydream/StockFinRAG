"""验证关键导入问题修复

Bug #1: api_server.py 应导入 get_mysql
Bug #2: requirements.txt 应包含 DBUtils
"""
import sys
import os
import importlib.util

# 确保可以在 app/ 目录下导入
test_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.dirname(test_dir)
sys.path.insert(0, app_dir)


def test_get_mysql_can_be_imported():
    """from db import get_mysql 应该成功"""
    from db import get_mysql
    assert callable(get_mysql), "get_mysql should be a callable function"


def test_api_server_has_get_mysql_import():
    """api_server.py 应包含 get_mysql 导入语句"""
    with open(os.path.join(app_dir, "api_server.py"), "r", encoding="utf-8") as f:
        source = f.read()
    assert "from db import get_mysql" in source, (
        "api_server.py 缺少 'from db import get_mysql'，list_documents 端点将 NameError"
    )


def test_dbutils_is_in_requirements():
    """requirements.txt 应包含 DBUtils"""
    req_path = os.path.join(app_dir, "requirements.txt")
    with open(req_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "DBUtils" in content, "requirements.txt 缺少 DBUtils 依赖"


def test_hf_offline_is_not_always_on():
    """HF_HUB_OFFLINE 应为条件性设置，不应在模块顶层硬编码为 '1'"""
    with open(os.path.join(app_dir, "api_server.py"), "r", encoding="utf-8") as f:
        source = f.read()
    lines = source.split('\n')
    # 检查顶层（无缩进）的 HF_HUB_OFFLINE = "1"
    top_level_assignments = [
        l.strip() for l in lines
        if l.strip().startswith('os.environ[') and 'HF_HUB_OFFLINE' in l and '= "1"' in l
        and not l.startswith((' ', '\t'))  # 没有缩进的才是顶层
    ]
    assert not top_level_assignments, (
        f"HF_HUB_OFFLINE 不应在模块顶层硬编码为 '1'，应在条件块内设置: {top_level_assignments}"
    )